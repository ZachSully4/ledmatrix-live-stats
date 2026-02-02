"""
Data fetching and extraction for LivePlayerStats plugin.

Handles ESPN API integration and extraction of stat leaders for
basketball (NBA/NCAAM) and football (NFL/NCAAF) games.
"""

from typing import Dict, List, Optional
from datetime import datetime


# ESPN API league mapping
LEAGUE_MAP = {
    'nba': ('basketball', 'nba'),
    'nfl': ('football', 'nfl'),
    'ncaam': ('basketball', 'mens-college-basketball'),
    'ncaaf': ('football', 'college-football')
}

# NCAA API base URL
NCAA_API_BASE = "https://ncaa-api.henrygd.me"

# Basketball stat array indices (from NCAA boxscore API)
BASKETBALL_STAT_INDICES = {
    'PTS': 15,  # Points
    'REB': 10,  # Rebounds
    'AST': 11,  # Assists
    'STL': 13,  # Steals
    'BLK': 14   # Blocks
}


class DataFetcher:
    """Fetches and extracts player statistics from ESPN API."""

    def __init__(self, api_helper, cache_manager, logger):
        """
        Initialize data fetcher.

        Args:
            api_helper: APIHelper instance for ESPN requests
            cache_manager: CacheManager for data caching
            logger: Logger instance
        """
        self.api_helper = api_helper
        self.cache_manager = cache_manager
        self.logger = logger

    def fetch_live_games(self, league_key: str, max_games: int = 50, power_conferences_only: bool = False,
                        favorite_teams: List[str] = None, favorite_team_expanded_stats: bool = True) -> List[Dict]:
        """
        Fetch live games for a specific league.

        Args:
            league_key: League identifier ('nba', 'nfl', 'ncaam', 'ncaaf')
            max_games: Maximum number of games to return
            power_conferences_only: Filter to only power conference games (NCAA only)
            favorite_teams: List of favorite team abbreviations (if set, only show these teams)
            favorite_team_expanded_stats: Show expanded stats for favorite team games

        Returns:
            List of game dictionaries with extracted stats
        """
        if league_key not in LEAGUE_MAP:
            self.logger.warning(f"Unknown league: {league_key}")
            return []

        # Use NCAA API for college basketball (better player stats)
        if league_key == 'ncaam':
            return self._fetch_ncaa_basketball_games(max_games, power_conferences_only, favorite_teams, favorite_team_expanded_stats)

        sport, league = LEAGUE_MAP[league_key]

        # Create cache key with current date
        date_str = datetime.now().strftime('%Y%m%d')
        cache_key = f"live_stats_{league_key}_{date_str}"

        try:
            # Fetch scoreboard with 60-second cache for live updates
            scoreboard = self.api_helper.fetch_espn_scoreboard(
                sport=sport,
                league=league,
                cache_key=cache_key,
                cache_ttl=60
            )

            if not scoreboard or 'events' not in scoreboard:
                self.logger.debug(f"No scoreboard data for {league_key}")
                return []

            # Extract live games
            live_games = []
            total_events = len(scoreboard.get('events', []))
            self.logger.debug(f"Processing {total_events} total events for {league_key}")

            for event in scoreboard.get('events', []):
                # Stop if we've reached max games
                if len(live_games) >= max_games:
                    self.logger.info(f"Reached max_games limit ({max_games}) for {league_key}")
                    break

                # Only process games that are live (in progress)
                status_state = event.get('status', {}).get('type', {}).get('state')
                status_detail = event.get('status', {}).get('type', {}).get('detail', '')

                # Log game status for debugging
                comp = event.get('competitions', [{}])[0]
                comps = comp.get('competitors', [])
                if len(comps) >= 2:
                    away = comps[0].get('team', {}).get('abbreviation', '?')
                    home = comps[1].get('team', {}).get('abbreviation', '?')
                    self.logger.info(f"Game: {away} @ {home}, Status: {status_state} ({status_detail})")

                if status_state != 'in':
                    continue

                # Parse game event
                game_info = self._parse_game_event(event, league_key, favorite_teams, favorite_team_expanded_stats)
                if game_info:
                    live_games.append(game_info)
                    self.logger.info(f"Parsed live game: {game_info.get('away_abbr')} @ {game_info.get('home_abbr')}, "
                                   f"home_leaders: {bool(game_info.get('home_leaders'))}, "
                                   f"away_leaders: {bool(game_info.get('away_leaders'))}")

            self.logger.info(f"Found {len(live_games)} live games in {league_key} (out of {total_events} total, max={max_games})")
            return live_games

        except Exception as e:
            self.logger.error(f"Error fetching live games for {league_key}: {e}", exc_info=True)
            return []

    def _parse_game_event(self, event: Dict, league_key: str, favorite_teams: List[str] = None,
                         favorite_team_expanded_stats: bool = True) -> Optional[Dict]:
        """
        Parse a game event and extract relevant information.

        Args:
            event: ESPN API event dictionary
            league_key: League identifier for sport-specific parsing
            favorite_teams: List of favorite team abbreviations
            favorite_team_expanded_stats: Show expanded stats for favorite team games

        Returns:
            Dictionary with game info and stat leaders, or None if parsing fails
        """
        try:
            competition = event.get('competitions', [{}])[0]
            status = event.get('status', {})
            competitors = competition.get('competitors', [])
            game_id = event.get('id')

            if len(competitors) < 2:
                return None

            # Identify home and away teams
            home_team = next((c for c in competitors if c.get('homeAway') == 'home'), None)
            away_team = next((c for c in competitors if c.get('homeAway') == 'away'), None)

            if not home_team or not away_team:
                return None

            # Extract basic game info
            home_abbr = home_team.get('team', {}).get('abbreviation', 'HOME')
            away_abbr = away_team.get('team', {}).get('abbreviation', 'AWAY')

            # Check if this is a favorite team game
            is_favorite = False
            if favorite_teams:
                is_favorite = home_abbr.upper() in [t.upper() for t in favorite_teams] or \
                             away_abbr.upper() in [t.upper() for t in favorite_teams]

            game_data = {
                'id': game_id,
                'league': league_key,
                'home_abbr': home_abbr,
                'away_abbr': away_abbr,
                'home_score': int(home_team.get('score', 0)),
                'away_score': int(away_team.get('score', 0)),
                'period': status.get('period', 0),
                'clock': status.get('displayClock', ''),
                'period_text': status.get('type', {}).get('shortDetail', ''),
                'is_favorite': is_favorite,
                'expanded_stats': is_favorite and favorite_team_expanded_stats,
            }

            # Fetch detailed boxscore for player stats
            if game_id:
                boxscore = self._fetch_game_boxscore(game_id, league_key)
                self.logger.info(f"DEBUG: Boxscore fetch for game {game_id}: {'SUCCESS' if boxscore else 'FAILED'}")
                if boxscore:
                    # Extract stat leaders from boxscore
                    if league_key in ['nba', 'ncaam']:
                        game_data['home_leaders'] = self._extract_boxscore_basketball_leaders(
                            boxscore, home_abbr, expanded_stats=is_favorite and favorite_team_expanded_stats
                        )
                        game_data['away_leaders'] = self._extract_boxscore_basketball_leaders(
                            boxscore, away_abbr, expanded_stats=is_favorite and favorite_team_expanded_stats
                        )
                    elif league_key in ['nfl', 'ncaaf']:
                        game_data['home_leaders'] = self._extract_boxscore_football_leaders(boxscore, 'home')
                        game_data['away_leaders'] = self._extract_boxscore_football_leaders(boxscore, 'away')
                else:
                    # Fallback to scoreboard data (will likely be None)
                    if league_key in ['nba', 'ncaam']:
                        game_data['home_leaders'] = self.extract_basketball_leaders(home_team)
                        game_data['away_leaders'] = self.extract_basketball_leaders(away_team)
                    elif league_key in ['nfl', 'ncaaf']:
                        game_data['home_leaders'] = self.extract_football_leaders(home_team)
                        game_data['away_leaders'] = self.extract_football_leaders(away_team)

            return game_data

        except Exception as e:
            self.logger.warning(f"Error parsing game event: {e}")
            return None

    def _fetch_game_boxscore(self, game_id: str, league_key: str) -> Optional[Dict]:
        """
        Fetch detailed boxscore for a specific game.

        Args:
            game_id: ESPN game ID
            league_key: League identifier

        Returns:
            Boxscore data or None if unavailable
        """
        sport, league = LEAGUE_MAP.get(league_key, (None, None))
        if not sport or not league:
            return None

        try:
            # ESPN boxscore/summary endpoint
            url = f"https://site.web.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary"
            params = {'event': game_id}
            cache_key = f"boxscore_{league_key}_{game_id}"

            response = self.api_helper.get(
                url,
                params=params,
                cache_key=cache_key,
                cache_ttl=60
            )

            return response

        except Exception as e:
            self.logger.debug(f"Error fetching boxscore for game {game_id}: {e}")
            return None

    def _extract_boxscore_basketball_leaders(self, boxscore: Dict, team_abbr: str, expanded_stats: bool = False) -> Optional[Dict]:
        """
        Extract basketball leaders from boxscore data.

        Args:
            boxscore: Boxscore response from ESPN
            team_abbr: Team abbreviation (e.g., 'LAL', 'BOS')
            expanded_stats: If True, include STL and BLK stats

        Returns:
            Leaders dict or None
        """
        try:
            self.logger.info(f"DEBUG: Extracting boxscore leaders for {team_abbr}, expanded_stats={expanded_stats}")

            # Navigate boxscore structure
            # Boxscore typically has: boxscore.players array with team data
            players_section = boxscore.get('boxscore', {}).get('players', [])
            self.logger.info(f"DEBUG: players_section length: {len(players_section)}")

            # Find the team by matching abbreviation
            team_data = None
            self.logger.info(f"DEBUG: Looking for team with abbreviation='{team_abbr}'")
            for idx, team in enumerate(players_section):
                team_info = team.get('team', {})
                team_abbreviation = team_info.get('abbreviation', '')
                self.logger.info(f"DEBUG: Team {idx}: abbreviation='{team_abbreviation}'")
                if team_abbreviation == team_abbr:
                    team_data = team
                    self.logger.info(f"DEBUG: FOUND matching team at index {idx}")
                    break

            if not team_data:
                self.logger.info(f"DEBUG: No team data found for abbreviation {team_abbr} in boxscore")
                return None

            # Get statistics from players
            statistics = team_data.get('statistics', [])
            self.logger.info(f"DEBUG: statistics length: {len(statistics)}")
            if not statistics:
                self.logger.info(f"DEBUG: No statistics found, returning None")
                return None

            # Find the main stats section (usually first one with athletes)
            stats_group = statistics[0] if statistics else None
            if not stats_group:
                self.logger.info(f"DEBUG: No stats_group found, returning None")
                return None

            self.logger.info(f"DEBUG: stats_group keys: {list(stats_group.keys())}")

            # Debug: Log stat labels to understand the order
            stat_labels = stats_group.get('labels', [])
            stat_names = stats_group.get('names', [])
            self.logger.info(f"ESPN boxscore stat labels: {stat_labels}")
            self.logger.info(f"ESPN boxscore stat names: {stat_names}")

            # Dynamically find indices for PTS, REB, AST, STL, BLK based on labels
            pts_idx = None
            reb_idx = None
            ast_idx = None
            stl_idx = None
            blk_idx = None

            # Try to find indices from labels (uppercase)
            for i, label in enumerate(stat_labels):
                label_upper = str(label).upper()
                if label_upper == 'PTS':
                    pts_idx = i
                elif label_upper == 'REB':
                    reb_idx = i
                elif label_upper == 'AST':
                    ast_idx = i
                elif label_upper == 'STL':
                    stl_idx = i
                elif label_upper == 'BLK':
                    blk_idx = i

            self.logger.info(f"Found stat indices - PTS:{pts_idx}, REB:{reb_idx}, AST:{ast_idx}, STL:{stl_idx}, BLK:{blk_idx}")

            # If indices not found, try from stat_names
            if pts_idx is None or reb_idx is None or ast_idx is None:
                for i, name in enumerate(stat_names):
                    name_upper = str(name).upper()
                    if pts_idx is None and 'PTS' in name_upper:
                        pts_idx = i
                    if reb_idx is None and 'REB' in name_upper:
                        reb_idx = i
                    if ast_idx is None and 'AST' in name_upper:
                        ast_idx = i
                    if stl_idx is None and 'STL' in name_upper:
                        stl_idx = i
                    if blk_idx is None and 'BLK' in name_upper:
                        blk_idx = i
                self.logger.info(f"After names check - PTS:{pts_idx}, REB:{reb_idx}, AST:{ast_idx}, STL:{stl_idx}, BLK:{blk_idx}")

            athletes = stats_group.get('athletes', [])
            if not athletes:
                return None

            # Extract leaders for PTS, REB, AST (and STL, BLK if expanded)
            leaders = {}
            max_pts = {'name': None, 'value': 0}
            max_reb = {'name': None, 'value': 0}
            max_ast = {'name': None, 'value': 0}
            max_stl = {'name': None, 'value': 0}
            max_blk = {'name': None, 'value': 0}

            for athlete in athletes:
                # Use displayName (full name) instead of shortName (last name only)
                name = athlete.get('athlete', {}).get('displayName', athlete.get('athlete', {}).get('shortName', 'Unknown'))
                stats = athlete.get('stats', [])

                # Debug logging for first player to see stat structure with indices
                if not max_pts['name']:  # Log only for first player
                    self.logger.info(f"ESPN boxscore stats for {name}:")
                    self.logger.info(f"  Full array (length {len(stats)}): {stats}")
                    # Show each stat with its index for debugging
                    for i, stat_val in enumerate(stats):
                        self.logger.info(f"  Index {i}: {stat_val}")

                # Use dynamic indices found from labels
                if stats:
                    try:
                        # Extract stats using the found indices
                        pts = 0
                        reb = 0
                        ast = 0
                        stl = 0
                        blk = 0

                        if pts_idx is not None and pts_idx < len(stats) and stats[pts_idx]:
                            pts = int(stats[pts_idx])
                        if reb_idx is not None and reb_idx < len(stats) and stats[reb_idx]:
                            reb = int(stats[reb_idx])
                        if ast_idx is not None and ast_idx < len(stats) and stats[ast_idx]:
                            ast = int(stats[ast_idx])
                        if stl_idx is not None and stl_idx < len(stats) and stats[stl_idx]:
                            stl = int(stats[stl_idx])
                        if blk_idx is not None and blk_idx < len(stats) and stats[blk_idx]:
                            blk = int(stats[blk_idx])

                        # Track max values
                        if pts > max_pts['value']:
                            max_pts = {'name': name, 'value': pts}
                        if reb > max_reb['value']:
                            max_reb = {'name': name, 'value': reb}
                        if ast > max_ast['value']:
                            max_ast = {'name': name, 'value': ast}
                        if expanded_stats:
                            if stl > max_stl['value']:
                                max_stl = {'name': name, 'value': stl}
                            if blk > max_blk['value']:
                                max_blk = {'name': name, 'value': blk}
                    except (ValueError, TypeError):
                        self.logger.warning(f"Error parsing stats for {name}: {stats}")
                        continue

            # Wrap single leader dicts in lists to match expected format
            if max_pts['name']:
                leaders['PTS'] = [max_pts]
            if max_reb['name']:
                leaders['REB'] = [max_reb]
            if max_ast['name']:
                leaders['AST'] = [max_ast]
            if expanded_stats:
                if max_stl['name']:
                    leaders['STL'] = [max_stl]
                if max_blk['name']:
                    leaders['BLK'] = [max_blk]

            return leaders if leaders else None

        except Exception as e:
            self.logger.debug(f"Error extracting basketball leaders from boxscore: {e}")
            return None

    def _extract_boxscore_football_leaders(self, boxscore: Dict, home_away: str) -> Optional[Dict]:
        """
        Extract football leaders from boxscore data.

        Args:
            boxscore: Boxscore response from ESPN
            home_away: 'home' or 'away'

        Returns:
            Leaders dict or None
        """
        # Similar structure to basketball, but look for passing/rushing/receiving stats
        # Implementation similar to _extract_boxscore_basketball_leaders
        # For now, return None as football structure may differ
        return None

    def extract_basketball_leaders(self, competitor_data: Dict) -> Optional[Dict]:
        """
        Extract basketball stat leaders from competitor data.

        Finds the top player for PTS, REB, and AST.

        Args:
            competitor_data: Competitor dictionary from ESPN API

        Returns:
            Dictionary with stat leaders {'PTS': {'name': 'L. James', 'value': 24}, ...}
            or None if stats unavailable
        """
        try:
            stats_section = competitor_data.get('statistics', [])
            if not stats_section:
                self.logger.debug(f"No statistics section found for competitor")
                return None

            # Log what stat sections are available
            section_names = [s.get('name') for s in stats_section if isinstance(s, dict)]
            self.logger.debug(f"Available stat sections: {section_names}")

            # Find athletes section
            athletes_data = next((s for s in stats_section if s.get('name') == 'athletes'), None)
            if not athletes_data or 'athletes' not in athletes_data:
                self.logger.debug(f"No athletes section found. Stats structure: {stats_section[:1] if stats_section else 'empty'}")
                return None

            athletes = athletes_data.get('athletes', [])
            if not athletes:
                return None

            leaders = {}

            # Find leader for each stat category
            for stat_type, stat_index in BASKETBALL_STAT_INDICES.items():
                max_value = 0
                top_player = None

                for athlete in athletes:
                    try:
                        stats = athlete.get('stats', [])
                        if len(stats) > stat_index:
                            value = int(stats[stat_index])
                            if value > max_value:
                                max_value = value
                                # Use displayName (full name) instead of shortName (last name only)
                                athlete_info = athlete.get('athlete', {})
                                top_player = athlete_info.get('displayName',
                                            athlete_info.get('shortName', 'Unknown'))
                    except (ValueError, TypeError, IndexError):
                        continue

                if top_player and max_value > 0:
                    leaders[stat_type] = {
                        'name': top_player,
                        'value': max_value
                    }

            return leaders if leaders else None

        except Exception as e:
            self.logger.debug(f"Error extracting basketball leaders: {e}")
            return None

    def extract_football_leaders(self, competitor_data: Dict) -> Optional[Dict]:
        """
        Extract football stat leaders from competitor data.

        Finds the leading QB (passing), WR (receiving), and RB (rushing).

        Args:
            competitor_data: Competitor dictionary from ESPN API

        Returns:
            Dictionary with stat leaders {'QB': {'name': 'Mahomes', 'stats': '245 YDS, 3 TD'}, ...}
            or None if stats unavailable
        """
        try:
            stats_section = competitor_data.get('statistics', [])
            if not stats_section:
                return None

            leaders = {}

            # Extract QB (top passer)
            passing_data = next((s for s in stats_section if s.get('name') == 'passing'), None)
            if passing_data and passing_data.get('athletes'):
                qb = passing_data['athletes'][0]  # Top passer
                qb_stats = qb.get('stats', [])
                if len(qb_stats) >= 4:
                    try:
                        yds = qb_stats[2]  # Passing yards
                        tds = qb_stats[3]  # Passing TDs
                        athlete_info = qb.get('athlete', {})
                        qb_name = self._abbreviate_name(
                            athlete_info.get('displayName', 'Unknown')
                        )
                        leaders['QB'] = {
                            'name': qb_name,
                            'stats': f"{yds} YDS, {tds} TD"
                        }
                    except (ValueError, IndexError):
                        pass

            # Extract WR (top receiver)
            receiving_data = next((s for s in stats_section if s.get('name') == 'receiving'), None)
            if receiving_data and receiving_data.get('athletes'):
                wr = receiving_data['athletes'][0]  # Top receiver
                wr_stats = wr.get('stats', [])
                if len(wr_stats) >= 4:
                    try:
                        yds = wr_stats[1]  # Receiving yards
                        tds = wr_stats[3]  # Receiving TDs
                        athlete_info = wr.get('athlete', {})
                        wr_name = self._abbreviate_name(
                            athlete_info.get('displayName', 'Unknown')
                        )
                        leaders['WR'] = {
                            'name': wr_name,
                            'stats': f"{yds} YDS, {tds} TD"
                        }
                    except (ValueError, IndexError):
                        pass

            # Extract RB (top rusher)
            rushing_data = next((s for s in stats_section if s.get('name') == 'rushing'), None)
            if rushing_data and rushing_data.get('athletes'):
                rb = rushing_data['athletes'][0]  # Top rusher
                rb_stats = rb.get('stats', [])
                if len(rb_stats) >= 4:
                    try:
                        yds = rb_stats[1]  # Rushing yards
                        tds = rb_stats[3]  # Rushing TDs
                        athlete_info = rb.get('athlete', {})
                        rb_name = self._abbreviate_name(
                            athlete_info.get('displayName', 'Unknown')
                        )
                        leaders['RB'] = {
                            'name': rb_name,
                            'stats': f"{yds} YDS, {tds} TD"
                        }
                    except (ValueError, IndexError):
                        pass

            return leaders if leaders else None

        except Exception as e:
            self.logger.debug(f"Error extracting football leaders: {e}")
            return None

    def _abbreviate_name(self, full_name: str) -> str:
        """
        Abbreviate player name for compact display.

        Args:
            full_name: Full player name (e.g., "Patrick Mahomes")

        Returns:
            Abbreviated name (e.g., "P. Mahomes" or "Mahomes")
        """
        parts = full_name.split()

        if len(parts) >= 2:
            # Use last name only if short enough
            if len(parts[-1]) <= 8:
                return parts[-1]
            # Otherwise use "F. Lastname" format
            return f"{parts[0][0]}. {parts[-1]}"

        # Single name or unknown - truncate if too long
        return full_name[:10] if len(full_name) > 10 else full_name

    def _fetch_ncaa_basketball_games(self, max_games: int = 50, power_conferences_only: bool = False,
                                     favorite_teams: List[str] = None, favorite_team_expanded_stats: bool = True) -> List[Dict]:
        """
        Fetch live NCAA Men's Basketball games using NCAA API.

        Args:
            max_games: Maximum number of games to return
            power_conferences_only: Filter to only power conference games
            favorite_teams: List of favorite team abbreviations
            favorite_team_expanded_stats: Show expanded stats for favorite teams

        Returns:
            List of game dictionaries with extracted stats
        """
        if favorite_teams is None:
            favorite_teams = []
        try:
            # Get today's date for scoreboard
            today = datetime.now()
            year = today.year
            month = str(today.month).zfill(2)
            day = str(today.day).zfill(2)

            # NCAA API scoreboard endpoint
            url = f"{NCAA_API_BASE}/scoreboard/basketball-men/d1/{year}/{month}/{day}"
            self.logger.debug(f"Fetching NCAA scoreboard from: {url}")

            # Use requests directly since NCAA API isn't cached by api_helper
            import requests
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            scoreboard = response.json()

            if not scoreboard or 'games' not in scoreboard:
                self.logger.debug("No scoreboard data from NCAA API")
                return []

            # Extract live games
            live_games = []
            total_events = len(scoreboard.get('games', []))
            self.logger.debug(f"Processing {total_events} total NCAA games")

            for game_wrapper in scoreboard.get('games', []):
                # Stop if we've reached max games
                if len(live_games) >= max_games:
                    self.logger.info(f"Reached max_games limit ({max_games}) for NCAA")
                    break

                game = game_wrapper.get('game', {})
                game_state = game.get('gameState', '')
                game_id = game.get('gameID')

                # Log game status for debugging
                away_name = game.get('away', {}).get('names', {}).get('char6', '?')
                home_name = game.get('home', {}).get('names', {}).get('char6', '?')
                self.logger.info(f"NCAA Game: {away_name} @ {home_name}, State: {game_state}")

                # Only process live games
                if game_state != 'live':
                    continue

                # Check power conference filter
                if power_conferences_only and not self._is_power_conference_game(game):
                    self.logger.debug(f"Skipping non-power conference game: {away_name} @ {home_name}")
                    continue

                # Check favorite team filter
                is_favorite_game = False
                if favorite_teams:
                    # Check if either team is a favorite
                    if away_name.upper() in [t.upper() for t in favorite_teams] or \
                       home_name.upper() in [t.upper() for t in favorite_teams]:
                        is_favorite_game = True
                        self.logger.info(f"Found favorite team game: {away_name} @ {home_name}")
                    else:
                        # Skip non-favorite team games when favorites are configured
                        self.logger.debug(f"Skipping non-favorite game: {away_name} @ {home_name}")
                        continue

                # Parse game data
                game_info = self._parse_ncaa_game(game, is_favorite_game, favorite_team_expanded_stats)
                if game_info:
                    live_games.append(game_info)
                    self.logger.info(f"Parsed NCAA game: {game_info.get('away_abbr')} @ {game_info.get('home_abbr')}, "
                                   f"home_leaders: {bool(game_info.get('home_leaders'))}, "
                                   f"away_leaders: {bool(game_info.get('away_leaders'))}")

            self.logger.info(f"Found {len(live_games)} live NCAA games (out of {total_events} total, max={max_games})")
            return live_games

        except Exception as e:
            self.logger.error(f"Error fetching NCAA games: {e}", exc_info=True)
            return []

    def _is_power_conference_game(self, game: Dict) -> bool:
        """
        Check if a game involves at least one power conference team.

        Power Conferences:
        - Big Ten
        - Big 12
        - SEC (Southeastern Conference)
        - ACC (Atlantic Coast Conference)
        - Big East
        - Pac-12

        Args:
            game: NCAA game dictionary

        Returns:
            True if at least one team is from a power conference
        """
        # NCAA API uses conferenceSeo field (conferenceName is often empty)
        power_conference_slugs = {
            'big-ten', 'big-12', 'sec', 'acc', 'big-east', 'pac-12'
        }

        try:
            away = game.get('away', {})
            home = game.get('home', {})

            # Check away team conferences
            away_conferences = away.get('conferences', [])
            for conf in away_conferences:
                conf_seo = conf.get('conferenceSeo', '').lower()
                if conf_seo in power_conference_slugs:
                    return True

            # Check home team conferences
            home_conferences = home.get('conferences', [])
            for conf in home_conferences:
                conf_seo = conf.get('conferenceSeo', '').lower()
                if conf_seo in power_conference_slugs:
                    return True

            return False

        except Exception as e:
            self.logger.debug(f"Error checking power conference: {e}")
            return False  # If can't determine, don't filter out

    def _parse_ncaa_game(self, game: Dict, is_favorite: bool = False, expanded_stats: bool = False) -> Optional[Dict]:
        """
        Parse NCAA game data and fetch boxscore for player stats.

        Args:
            game: Game dictionary from NCAA API scoreboard
            is_favorite: True if this game involves a favorite team
            expanded_stats: True to extract expanded stats (STL, BLK)

        Returns:
            Dictionary with game info and stat leaders, or None if parsing fails
        """
        try:
            game_id = game.get('gameID')
            home = game.get('home', {})
            away = game.get('away', {})

            # Extract basic game info
            game_data = {
                'id': game_id,
                'league': 'ncaam',
                'home_abbr': home.get('names', {}).get('char6', 'HOME'),
                'away_abbr': away.get('names', {}).get('char6', 'AWAY'),
                'home_name': home.get('names', {}).get('short', 'HOME'),
                'away_name': away.get('names', {}).get('short', 'AWAY'),
                'home_record': home.get('description', ''),
                'away_record': away.get('description', ''),
                'home_rank': home.get('rank', ''),
                'away_rank': away.get('rank', ''),
                'home_score': int(home.get('score', 0)),
                'away_score': int(away.get('score', 0)),
                'period': 0,  # NCAA API uses currentPeriod text
                'clock': game.get('contestClock', ''),
                'period_text': game.get('currentPeriod', ''),
                'is_favorite': is_favorite,
                'expanded_stats': is_favorite and expanded_stats,
            }

            # Fetch boxscore for player stats
            if game_id:
                boxscore = self._fetch_ncaa_boxscore(game_id)
                if boxscore:
                    game_data['home_leaders'] = self._extract_ncaa_basketball_leaders(
                        boxscore, is_home=True, expanded_stats=is_favorite and expanded_stats
                    )
                    game_data['away_leaders'] = self._extract_ncaa_basketball_leaders(
                        boxscore, is_home=False, expanded_stats=is_favorite and expanded_stats
                    )

            return game_data

        except Exception as e:
            self.logger.warning(f"Error parsing NCAA game: {e}")
            return None

    def _fetch_ncaa_boxscore(self, game_id: str) -> Optional[Dict]:
        """
        Fetch NCAA boxscore data.

        Args:
            game_id: NCAA game ID

        Returns:
            Boxscore data or None if unavailable
        """
        try:
            url = f"{NCAA_API_BASE}/game/{game_id}/boxscore"
            self.logger.debug(f"Fetching NCAA boxscore from: {url}")

            import requests
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            self.logger.debug(f"Error fetching NCAA boxscore for game {game_id}: {e}")
            return None

    def _extract_ncaa_basketball_leaders(self, boxscore: Dict, is_home: bool, expanded_stats: bool = False) -> Optional[Dict]:
        """
        Extract basketball leaders from NCAA boxscore data.

        Args:
            boxscore: Boxscore response from NCAA API
            is_home: True for home team, False for away team
            expanded_stats: If True, extract STL/BLK and show all players instead of top 2

        Returns:
            Leaders dict with PTS/REB/AST (and STL/BLK if expanded) leaders or None
        """
        try:
            teams_info = boxscore.get('teams', [])
            team_boxscore = boxscore.get('teamBoxscore', [])

            self.logger.debug(f"NCAA boxscore has {len(teams_info)} teams and {len(team_boxscore)} team stats")

            if not teams_info or not team_boxscore:
                self.logger.debug("Missing teams or teamBoxscore data")
                return None

            # Find the correct team index (teams and teamBoxscore are in same order)
            team_index = None
            for idx, team_info in enumerate(teams_info):
                if team_info.get('isHome') == is_home:
                    team_index = idx
                    team_name = team_info.get('nameShort', '?')
                    self.logger.debug(f"Found {'home' if is_home else 'away'} team at index {idx}: {team_name}")
                    break

            if team_index is None or team_index >= len(team_boxscore):
                self.logger.debug(f"Could not find team index for {'home' if is_home else 'away'}")
                return None

            team_data = team_boxscore[team_index]
            player_stats = team_data.get('playerStats', [])

            self.logger.debug(f"Found {len(player_stats)} players for {'home' if is_home else 'away'} team")

            if not player_stats:
                return None

            # Find leaders for PTS, REB, AST (and STL, BLK if expanded)
            pts_list = []
            reb_list = []
            ast_list = []
            stl_list = []
            blk_list = []

            for player in player_stats:
                first_name = player.get('firstName', '')
                last_name = player.get('lastName', '')
                full_name = f"{first_name} {last_name}".strip()

                # Get stats (NCAA API returns strings)
                try:
                    pts = int(player.get('points', 0) or 0)
                    reb = int(player.get('totalRebounds', 0) or 0)
                    ast = int(player.get('assists', 0) or 0)

                    # Use full names instead of abbreviated - renderer will handle splitting
                    pts_list.append({'name': full_name, 'value': pts})
                    reb_list.append({'name': full_name, 'value': reb})
                    ast_list.append({'name': full_name, 'value': ast})

                    # Extract STL and BLK for expanded stats
                    if expanded_stats:
                        stl = int(player.get('steals', 0) or 0)
                        blk = int(player.get('blocks', 0) or 0)
                        stl_list.append({'name': full_name, 'value': stl})
                        blk_list.append({'name': full_name, 'value': blk})

                except (ValueError, TypeError) as e:
                    self.logger.debug(f"Error parsing stats for {full_name}: {e}")
                    continue

            # Determine how many leaders to show
            num_leaders = 10 if expanded_stats else 2

            # Sort and get leaders for each stat
            leaders = {}

            # PTS leaders
            pts_sorted = sorted(pts_list, key=lambda x: x['value'], reverse=True)
            if pts_sorted and pts_sorted[0]['value'] > 0:
                leaders['PTS'] = pts_sorted[:num_leaders]
                pts_str = ', '.join([f"{p['name']} {p['value']}" for p in leaders['PTS'][:3]])
                self.logger.debug(f"PTS leaders: {pts_str}...")

            # REB leaders
            reb_sorted = sorted(reb_list, key=lambda x: x['value'], reverse=True)
            if reb_sorted and reb_sorted[0]['value'] > 0:
                leaders['REB'] = reb_sorted[:num_leaders]
                reb_str = ', '.join([f"{p['name']} {p['value']}" for p in leaders['REB'][:3]])
                self.logger.debug(f"REB leaders: {reb_str}...")

            # AST leaders
            ast_sorted = sorted(ast_list, key=lambda x: x['value'], reverse=True)
            if ast_sorted and ast_sorted[0]['value'] > 0:
                leaders['AST'] = ast_sorted[:num_leaders]
                ast_str = ', '.join([f"{p['name']} {p['value']}" for p in leaders['AST'][:3]])
                self.logger.debug(f"AST leaders: {ast_str}...")

            # STL and BLK for expanded stats
            if expanded_stats:
                stl_sorted = sorted(stl_list, key=lambda x: x['value'], reverse=True)
                if stl_sorted and stl_sorted[0]['value'] > 0:
                    leaders['STL'] = stl_sorted[:num_leaders]
                    stl_str = ', '.join([f"{p['name']} {p['value']}" for p in leaders['STL'][:3]])
                    self.logger.debug(f"STL leaders: {stl_str}...")

                blk_sorted = sorted(blk_list, key=lambda x: x['value'], reverse=True)
                if blk_sorted and blk_sorted[0]['value'] > 0:
                    leaders['BLK'] = blk_sorted[:num_leaders]
                    blk_str = ', '.join([f"{p['name']} {p['value']}" for p in leaders['BLK'][:3]])
                    self.logger.debug(f"BLK leaders: {blk_str}...")

            return leaders if leaders else None

        except Exception as e:
            self.logger.error(f"Error extracting NCAA basketball leaders: {e}", exc_info=True)
            return None
