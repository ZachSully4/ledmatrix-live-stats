"""
Rendering module for LivePlayerStats plugin.

Handles PIL-based rendering of player stat cards for scrolling display.
"""

from typing import Dict, Optional
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import os


# Color scheme
COLOR_WHITE = (255, 255, 255)
COLOR_LIGHT_BLUE = (77, 190, 238)
COLOR_GRAY = (170, 170, 170)
COLOR_BLACK = (0, 0, 0)


class StatsRenderer:
    """Renders player statistics as game cards for scrolling display."""

    def __init__(self, font_manager, logger, display_height=32):
        """
        Initialize stats renderer.

        Args:
            font_manager: FontManager instance for font access
            logger: Logger instance
            display_height: Display height in pixels (default: 32)
        """
        self.font_manager = font_manager
        self.logger = logger
        self.display_height = display_height

        # EXACT copy from odds-ticker: Resolve project root path (plugin_dir -> plugins -> project_root)
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.logger.debug(f"Project root: {self.project_root}")

        # Load fonts - EXACT match to odds-ticker
        # Odds-ticker uses PressStart2P-Regular.ttf at size 8 for all text
        try:
            font_dir = self.project_root / 'assets' / 'fonts'
            font_path = font_dir / 'PressStart2P-Regular.ttf'

            if font_path.exists():
                # Use size 8 for all fonts (matches odds-ticker)
                self.team_font = ImageFont.truetype(str(font_path), 8)
                self.small_font = ImageFont.truetype(str(font_path), 8)
                self.medium_font = ImageFont.truetype(str(font_path), 8)
                self.logger.debug(f"Loaded PressStart2P font at size 8")
            else:
                self.logger.warning(f"Font not found: {font_path}, using default")
                self.team_font = ImageFont.load_default()
                self.small_font = ImageFont.load_default()
                self.medium_font = ImageFont.load_default()

        except Exception as e:
            self.logger.warning(f"Error loading fonts, using defaults: {e}")
            self.team_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()
            self.medium_font = ImageFont.load_default()

    def render_game_card(self, game_data: Dict, card_width: int = 192) -> Image.Image:
        """
        Render a game card with player statistics in 3-panel layout.

        Layout: [Panel 1: Game Info with Logos] [Panel 2: Away Stats] [Panel 3: Home Stats]
        Each panel is 64px wide.

        Args:
            game_data: Game dictionary with team info and stat leaders
            card_width: Width of the card in pixels (default: 192 for 3 panels)

        Returns:
            PIL Image of the game card
        """
        try:
            # Extract game info
            away_abbr = game_data.get('away_abbr', 'AWAY')
            home_abbr = game_data.get('home_abbr', 'HOME')
            away_name = game_data.get('away_name', away_abbr)
            home_name = game_data.get('home_name', home_abbr)
            away_record = game_data.get('away_record', '')
            home_record = game_data.get('home_record', '')
            away_rank = game_data.get('away_rank', '')
            home_rank = game_data.get('home_rank', '')
            away_score = game_data.get('away_score', 0)
            home_score = game_data.get('home_score', 0)
            period_text = game_data.get('period_text', '')
            clock = game_data.get('clock', '')
            away_leaders = game_data.get('away_leaders')
            home_leaders = game_data.get('home_leaders')
            league = game_data.get('league', 'ncaam')
            expanded_stats = game_data.get('expanded_stats', False)

            # --- PANEL 1: Game Info with Logos (dynamically sized) ---
            panel1 = self._render_game_info_panel(away_abbr, home_abbr, away_name, home_name,
                                                  away_record, home_record, away_rank, home_rank,
                                                  away_score, home_score, period_text, clock, league)

            # --- PANEL 2: Combined Stats (stacked top/bottom, dynamically sized) ---
            panel2 = self._render_combined_stats_panel(away_leaders, home_leaders, league, expanded_stats)

            # Calculate total width dynamically
            total_width = panel1.width + panel2.width

            # Create full image with dynamic width
            img = Image.new('RGB', (total_width, self.display_height), color=COLOR_BLACK)

            # Paste panels side by side
            current_x = 0
            img.paste(panel1, (current_x, 0))
            current_x += panel1.width
            img.paste(panel2, (current_x, 0))

            return img

        except Exception as e:
            self.logger.error(f"Error rendering game card: {e}", exc_info=True)
            # Return error card
            return self._create_error_card(card_width)

    def _render_game_info_panel(self, away_abbr: str, home_abbr: str, away_name: str, home_name: str,
                                away_record: str, home_record: str, away_rank: str, home_rank: str,
                                away_score: int, home_score: int, period_text: str, clock: str,
                                league: str) -> Image.Image:
        """
        Render Panel 1: Game info with team logos matching odds-ticker format.

        Args:
            away_abbr: Away team abbreviation (for logo lookup)
            home_abbr: Home team abbreviation (for logo lookup)
            away_name: Away team name (e.g., "Boilermakers")
            home_name: Home team name (e.g., "Terrapins")
            away_record: Away team record (e.g., "(15-4)")
            home_record: Home team record (e.g., "(14-5)")
            away_rank: Away team ranking (e.g., "10" or "")
            home_rank: Home team ranking (e.g., "15" or "")
            away_score: Away team score
            home_score: Home team score
            period_text: Game period/status text
            clock: Game clock
            league: League identifier

        Returns:
            PIL Image of game info panel matching odds-ticker layout
        """
        height = self.display_height

        # EXACT odds-ticker settings
        logo_size = int(height * 1.2)  # Make logos use most of the display height (38px for 32px display)
        h_padding = 4  # Use a consistent horizontal padding

        # Fonts - EXACT match to odds-ticker (PressStart2P at size 8)
        team_font = self.team_font
        score_font = self.team_font
        vs_font = self.team_font  # Same font for "vs." text

        # Get team logos
        away_logo = self._get_team_logo(league, away_abbr)
        home_logo = self._get_team_logo(league, home_abbr)

        if away_logo:
            away_logo = away_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        else:
            # Create fallback text logo when image is missing
            self.logger.debug(f"No logo for {away_abbr}, will use text fallback")

        if home_logo:
            home_logo = home_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        else:
            # Create fallback text logo when image is missing
            self.logger.debug(f"No logo for {home_abbr}, will use text fallback")

        # Format team text: abbreviation with record and rank
        # Example: "PUR (15-4,#10)" or "MD (14-5)"
        def format_team_text(abbr, record, rank):
            # Remove parentheses from record if present
            clean_record = record.strip('()') if record else ''

            # Start with abbreviation (max 4 chars like odds-ticker)
            text = abbr[:4] if abbr else ''

            # Add record and rank in parentheses (compact format, no spaces)
            details = []
            if clean_record:
                details.append(clean_record)
            if rank:
                details.append(f"#{rank}")

            if details:
                text += f" ({','.join(details)})"

            return text

        away_team_text = format_team_text(away_abbr, away_record, away_rank)
        home_team_text = format_team_text(home_abbr, home_record, home_rank)
        away_score_text = str(away_score)
        home_score_text = str(home_score)

        # Calculate column widths (EXACTLY like odds-ticker)
        temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))

        # "vs." text width
        vs_text = "vs."
        vs_width = int(temp_draw.textlength(vs_text, font=team_font))

        # Team names width
        away_team_width = int(temp_draw.textlength(away_team_text, font=team_font))
        home_team_width = int(temp_draw.textlength(home_team_text, font=team_font))
        team_info_width = max(away_team_width, home_team_width)

        # Scores width
        away_score_width = int(temp_draw.textlength(away_score_text, font=score_font))
        home_score_width = int(temp_draw.textlength(home_score_text, font=score_font))
        scores_width = max(away_score_width, home_score_width)

        # Period/clock status width (use team_font like odds-ticker uses datetime_font at size 8)
        period_display = period_text[:8] if period_text else ""
        clock_display = clock[:8] if clock else ""
        period_width = int(temp_draw.textlength(period_display, font=team_font)) if period_display else 0
        clock_width = int(temp_draw.textlength(clock_display, font=team_font)) if clock_display else 0
        status_width = max(period_width, clock_width, 20)  # Min width of 20

        # Calculate total width (EXACTLY like odds-ticker formula)
        total_width = (logo_size * 2) + vs_width + team_info_width + scores_width + status_width + (h_padding * 6)

        # Create the image
        image = Image.new('RGB', (int(total_width), height), color=COLOR_BLACK)
        draw = ImageDraw.Draw(image)

        # --- Draw elements (EXACTLY like odds-ticker) ---
        current_x = 0

        # Away Logo (centered vertically) or fallback text
        if away_logo:
            y_pos = (height - logo_size) // 2  # Center the logo vertically
            image.paste(away_logo, (current_x, y_pos), away_logo if away_logo.mode == 'RGBA' else None)
        else:
            # Draw team abbreviation as fallback
            abbr_text = away_abbr[:4]
            text_width = int(temp_draw.textlength(abbr_text, font=team_font))
            text_x = current_x + (logo_size - text_width) // 2
            text_y = (height - team_font.size) // 2 if hasattr(team_font, 'size') else height // 2 - 4
            draw.text((text_x, text_y), abbr_text, font=team_font, fill=(150, 150, 150))
        current_x += logo_size + h_padding

        # "vs." text (centered vertically)
        draw.text((current_x, height // 2 - 4), vs_text, font=team_font, fill=(255, 255, 255))
        current_x += vs_width + h_padding

        # Home Logo (centered vertically) or fallback text
        if home_logo:
            y_pos = (height - logo_size) // 2  # Center the logo vertically
            image.paste(home_logo, (current_x, y_pos), home_logo if home_logo.mode == 'RGBA' else None)
        else:
            # Draw team abbreviation as fallback
            abbr_text = home_abbr[:4]
            text_width = int(temp_draw.textlength(abbr_text, font=team_font))
            text_x = current_x + (logo_size - text_width) // 2
            text_y = (height - team_font.size) // 2 if hasattr(team_font, 'size') else height // 2 - 4
            draw.text((text_x, text_y), abbr_text, font=team_font, fill=(150, 150, 150))
        current_x += logo_size + h_padding

        # Team names (stacked - EXACTLY like odds-ticker)
        away_y = 2
        home_y = height - 10
        draw.text((current_x, away_y), away_team_text, font=team_font, fill=(255, 255, 255))
        draw.text((current_x, home_y), home_team_text, font=team_font, fill=(255, 255, 255))
        current_x += team_info_width + h_padding

        # Scores (stacked - same y positions as team names)
        draw.text((current_x, away_y), away_score_text, font=score_font, fill=(255, 255, 255))
        draw.text((current_x, home_y), home_score_text, font=score_font, fill=(255, 255, 255))
        current_x += scores_width + h_padding

        # Period/Clock (stacked - same y positions, use team_font like odds-ticker)
        if period_display:
            draw.text((current_x, away_y), period_display, font=team_font, fill=(170, 170, 170))
        if clock_display:
            draw.text((current_x, home_y), clock_display, font=team_font, fill=(170, 170, 170))

        return image

    def _render_combined_stats_panel(self, away_leaders: Optional[Dict], home_leaders: Optional[Dict], league: str, expanded_stats: bool = False) -> Image.Image:
        """
        Render combined stats panel with both teams stacked (top/bottom).

        Format per team: "PTS: Name1 9, Name2 5  REB: Name3 6, Name4 4  AST: Name5 6, Name6 4"
        For expanded stats (favorite team): includes STL and BLK, shows all players

        Args:
            away_leaders: Dictionary of away team stat leaders
            home_leaders: Dictionary of home team stat leaders
            league: League identifier
            expanded_stats: If True, show STL/BLK and all players

        Returns:
            PIL Image of combined stats panel
        """
        # Calculate width needed for stats text
        # Format: "PTS: LastName 9, LastName 5  REB: LastName 6, LastName 4  AST: LastName 6, LastName 4"
        # Estimate: ~120px minimum width for typical stats
        min_width = 200
        height = self.display_height

        panel = Image.new('RGB', (min_width, height), color=COLOR_BLACK)
        draw = ImageDraw.Draw(panel)

        # Helper function to format stat line for one team with column alignment
        def format_stat_line(leaders):
            if not leaders:
                return "No stats"

            # Determine which stats to show
            stat_names = ['PTS', 'REB', 'AST', 'STL', 'BLK'] if expanded_stats else ['PTS', 'REB', 'AST']

            parts = []
            for stat_name in stat_names:
                if stat_name in leaders:
                    stat_leaders = leaders[stat_name]  # List of leaders
                    # Format with fixed-width names for column alignment: "PTS: Name1    9, Name2    5"
                    player_strs = []
                    for leader in stat_leaders:
                        name = leader.get('name', '?')
                        value = leader.get('value', 0)

                        # Skip players with 0 for this stat
                        if value == 0:
                            continue

                        # Use last name only for space
                        last_name = name.split()[-1] if ' ' in name else name
                        # Smart truncation: if name is too long, use first initial + last name
                        if len(last_name) > 8:
                            first_name = name.split()[0] if ' ' in name else ''
                            if first_name:
                                last_name = f"{first_name[0]}.{last_name[:6]}"
                            else:
                                last_name = last_name[:8]
                        # Pad to 8 chars for alignment
                        player_strs.append(f"{last_name:<8}{value:>2}")

                    # Only add stat category if there are players with > 0
                    if player_strs:
                        stat_str = f"{stat_name}: {', '.join(player_strs)}"
                        parts.append(stat_str)

            return "  ".join(parts) if parts else "No stats"

        # Format away team stats (top half, y=2)
        away_y = 2
        away_text = format_stat_line(away_leaders)
        draw.text((2, away_y), away_text, font=self.small_font, fill=COLOR_WHITE)

        # Format home team stats (bottom half, y=height-10)
        home_y = height - 10
        home_text = format_stat_line(home_leaders)
        draw.text((2, home_y), home_text, font=self.small_font, fill=COLOR_WHITE)

        # Calculate actual width needed based on text
        temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        away_width = int(temp_draw.textlength(away_text, font=self.small_font)) + 4
        home_width = int(temp_draw.textlength(home_text, font=self.small_font)) + 4
        actual_width = max(away_width, home_width, min_width)

        # If we need more width, recreate the panel
        if actual_width > min_width:
            panel = Image.new('RGB', (actual_width, height), color=COLOR_BLACK)
            draw = ImageDraw.Draw(panel)
            draw.text((2, away_y), away_text, font=self.small_font, fill=COLOR_WHITE)
            draw.text((2, home_y), home_text, font=self.small_font, fill=COLOR_WHITE)

        return panel

    def _render_stats_panel(self, team_abbr: str, leaders: Optional[Dict], league: str) -> Image.Image:
        """
        Render a stats panel showing PTS/REB/AST leaders for one team.

        Args:
            team_abbr: Team abbreviation
            leaders: Dictionary of stat leaders
            league: League identifier

        Returns:
            PIL Image of stats panel (64x32)
        """
        panel_width = 64
        panel = Image.new('RGB', (panel_width, self.display_height), color=COLOR_BLACK)
        draw = ImageDraw.Draw(panel)

        # Start drawing stats from top (no logo in stats panel)
        y_pos = 2

        # Draw stat leaders
        if leaders and ('PTS' in leaders or 'REB' in leaders or 'AST' in leaders):
            # Points leader
            if 'PTS' in leaders:
                pts_leader = leaders['PTS']
                name = self._abbreviate_display_name(pts_leader.get('name', '?'), max_length=6)
                value = pts_leader.get('value', 0)
                text = f"P:{name} {value}"
                draw.text((2, y_pos), text, font=self.small_font, fill=COLOR_LIGHT_BLUE)
                y_pos += 9

            # Rebounds leader
            if 'REB' in leaders:
                reb_leader = leaders['REB']
                name = self._abbreviate_display_name(reb_leader.get('name', '?'), max_length=6)
                value = reb_leader.get('value', 0)
                text = f"R:{name} {value}"
                draw.text((2, y_pos), text, font=self.small_font, fill=COLOR_LIGHT_BLUE)
                y_pos += 9

            # Assists leader
            if 'AST' in leaders:
                ast_leader = leaders['AST']
                name = self._abbreviate_display_name(ast_leader.get('name', '?'), max_length=6)
                value = ast_leader.get('value', 0)
                text = f"A:{name} {value}"
                draw.text((2, y_pos), text, font=self.small_font, fill=COLOR_LIGHT_BLUE)
        else:
            # No stats
            draw.text((2, y_pos), "No stats", font=self.small_font, fill=COLOR_GRAY)

        return panel

    def _format_leaders_detailed(self, team_abbr: str, leaders: Dict) -> list:
        """
        Format leader stats with one line per stat category.

        Args:
            team_abbr: Team abbreviation
            leaders: Dictionary of stat leaders

        Returns:
            List of formatted strings, one per stat leader
        """
        if not leaders:
            return []

        lines = []

        # Check if this is basketball or football stats
        if 'PTS' in leaders or 'REB' in leaders or 'AST' in leaders:
            # Basketball format: Show each leader separately
            if 'PTS' in leaders:
                pts_leader = leaders['PTS']
                name = self._abbreviate_display_name(pts_leader.get('name', '?'), max_length=10)
                value = pts_leader.get('value', 0)
                lines.append(f"{team_abbr} PTS: {name} {value}")

            if 'REB' in leaders:
                reb_leader = leaders['REB']
                name = self._abbreviate_display_name(reb_leader.get('name', '?'), max_length=10)
                value = reb_leader.get('value', 0)
                lines.append(f"{team_abbr} REB: {name} {value}")

            if 'AST' in leaders:
                ast_leader = leaders['AST']
                name = self._abbreviate_display_name(ast_leader.get('name', '?'), max_length=10)
                value = ast_leader.get('value', 0)
                lines.append(f"{team_abbr} AST: {name} {value}")

        elif 'QB' in leaders or 'WR' in leaders or 'RB' in leaders:
            # Football format: Show each position leader
            if 'QB' in leaders:
                name = leaders['QB'].get('name', '?')
                stats = leaders['QB'].get('stats', '')
                stats_short = stats.replace(' YDS', '').replace(' TD', 'TD')
                lines.append(f"{team_abbr} QB: {name} {stats_short}")

            if 'WR' in leaders:
                name = leaders['WR'].get('name', '?')
                stats = leaders['WR'].get('stats', '')
                stats_short = stats.replace(' YDS', '').replace(' TD', 'TD')
                lines.append(f"{team_abbr} WR: {name} {stats_short}")

            if 'RB' in leaders:
                name = leaders['RB'].get('name', '?')
                stats = leaders['RB'].get('stats', '')
                stats_short = stats.replace(' YDS', '').replace(' TD', 'TD')
                lines.append(f"{team_abbr} RB: {name} {stats_short}")

        return lines

    def _format_leaders(self, team_abbr: str, leaders: Dict) -> str:
        """
        Format leader stats as a compact string (legacy method).

        Args:
            team_abbr: Team abbreviation
            leaders: Dictionary of stat leaders

        Returns:
            Formatted string (e.g., "LAL: LBJ 24/8/7" or "KC: Mahomes 245 YDS")
        """
        if not leaders:
            return ""

        # Check if this is basketball or football stats
        if 'PTS' in leaders:
            # Basketball format: "Team: Name PTS/REB/AST"
            pts = leaders.get('PTS', {}).get('value', 0)
            reb = leaders.get('REB', {}).get('value', 0)
            ast = leaders.get('AST', {}).get('value', 0)
            name = leaders.get('PTS', {}).get('name', 'Unknown')

            # Abbreviate name if too long
            name = self._abbreviate_display_name(name, max_length=8)

            return f"{team_abbr}: {name} {pts}/{reb}/{ast}"

        elif 'QB' in leaders or 'WR' in leaders or 'RB' in leaders:
            # Football format: Show top stat category
            # Priority: QB > WR > RB
            if 'QB' in leaders:
                name = leaders['QB'].get('name', 'Unknown')
                stats = leaders['QB'].get('stats', '')
                # Simplify stats for display
                stats_short = stats.replace(' YDS', '').replace(' TD', 'TD')
                return f"{team_abbr}: {name} {stats_short}"
            elif 'WR' in leaders:
                name = leaders['WR'].get('name', 'Unknown')
                stats = leaders['WR'].get('stats', '')
                stats_short = stats.replace(' YDS', '').replace(' TD', 'TD')
                return f"{team_abbr}: {name} {stats_short}"
            elif 'RB' in leaders:
                name = leaders['RB'].get('name', 'Unknown')
                stats = leaders['RB'].get('stats', '')
                stats_short = stats.replace(' YDS', '').replace(' TD', 'TD')
                return f"{team_abbr}: {name} {stats_short}"

        return ""

    def _abbreviate_display_name(self, name: str, max_length: int = 8) -> str:
        """
        Abbreviate name for display if too long.

        Args:
            name: Full name
            max_length: Maximum length

        Returns:
            Abbreviated name
        """
        if len(name) <= max_length:
            return name

        # Try splitting and using initials
        parts = name.split()
        if len(parts) >= 2:
            # Use initials: "LeBron James" -> "LJ"
            initials = ''.join([p[0] for p in parts[:2]])
            if len(initials) <= max_length:
                return initials

        # Truncate
        return name[:max_length]

    def _create_error_card(self, card_width: int) -> Image.Image:
        """
        Create an error card when rendering fails.

        Args:
            card_width: Width of the card

        Returns:
            PIL Image with error message
        """
        img = Image.new('RGB', (card_width, self.display_height), color=COLOR_BLACK)
        draw = ImageDraw.Draw(img)
        draw.text((2, 12), "Error", font=self.small_font, fill=COLOR_WHITE)
        return img

    def create_no_games_placeholder(self, width: int = 192) -> Image.Image:
        """
        Create a placeholder image when no live games are available.

        Args:
            width: Width of the placeholder image

        Returns:
            PIL Image with "No live games" message
        """
        img = Image.new('RGB', (width, self.display_height), color=COLOR_BLACK)
        draw = ImageDraw.Draw(img)

        message = "No live games"
        # Center the text
        try:
            # Try to get text dimensions for centering
            bbox = draw.textbbox((0, 0), message, font=self.medium_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            # Fallback if textbbox not available
            text_width = len(message) * 6
            text_height = 8

        x = (width - text_width) // 2
        y = (self.display_height - text_height) // 2

        draw.text((x, y), message, font=self.medium_font, fill=COLOR_GRAY)
        return img

    def _get_team_logo(self, league: str, team_abbr: str) -> Optional[Image.Image]:
        """
        Get team logo from assets directory - EXACT copy from odds-ticker + NCAA mapping.

        Args:
            league: League identifier
            team_abbr: Team abbreviation

        Returns:
            PIL Image of team logo, or None if not found
        """
        try:
            # Suppress unused parameter warnings (kept for compatibility)
            _ = None  # team_id placeholder
            _ = None  # logo_dir placeholder

            # Map league names to logo directories
            league_logo_map = {
                'nfl': 'nfl_logos',
                'mlb': 'mlb_logos',
                'nba': 'nba_logos',
                'nhl': 'nhl_logos',
                'ncaa_fb': 'ncaa_logos',
                'ncaam': 'ncaa_logos',
                'ncaaf': 'ncaa_logos',
                'milb': 'milb_logos'
            }

            logo_dir_name = league_logo_map.get(league, '')
            if not logo_dir_name or not team_abbr:
                return None

            # NCAA abbreviation mapping (NCAA API char6 → logo filename)
            # The NCAA API returns 6-char codes but logos use short codes
            if league in ['ncaam', 'ncaaf']:
                ncaa_map = {
                    # Power 5 Conferences
                    'KANSAS': 'KU', 'KANSST': 'KSU', 'BAYLOR': 'BAY', 'TEXAST': 'TEX',
                    'OKLA': 'OU', 'OKLAST': 'OKST', 'TCU': 'TCU', 'TXTECH': 'TTU',
                    'IOWA': 'IOWA', 'IOWAST': 'ISU', 'MINN': 'MINN', 'NEB': 'NEB',
                    'MICHST': 'MSU', 'MICH': 'MICH', 'OHIOST': 'OSU', 'PENNST': 'PSU',
                    'ILL': 'ILL', 'IND': 'IND', 'INDIAN': 'IND', 'MD': 'MD', 'MDLAND': 'MD',
                    'NW': 'NW', 'NRTHW': 'NW', 'PUR': 'PUR', 'PURDUE': 'PUR', 'PURDUW': 'PUR',
                    'RUTG': 'RUTG', 'RUTGER': 'RUTG', 'WISC': 'WISC', 'WISCON': 'WISC',
                    'DUKE': 'DUKE', 'UNC': 'UNC', 'NCSU': 'NCST', 'WAKE': 'WAKE',
                    'BC': 'BC', 'CLEM': 'CLEM', 'FSU': 'FSU', 'LOU': 'LOU', 'MIAMI': 'MIA',
                    'PITT': 'PITT', 'SYR': 'SYR', 'UVA': 'UVA', 'VT': 'VT',
                    'ALA': 'ALA', 'ARK': 'ARK', 'AUB': 'AUB', 'FLA': 'FLA', 'UGA': 'UGA',
                    'KENTKY': 'UK', 'LSU': 'LSU', 'MISS': 'MISS', 'MISST': 'MSST',
                    'MIZZOU': 'MIZ', 'SC': 'SC', 'TENN': 'TENN', 'TEXAM': 'TAMU',
                    'VAND': 'VAND', 'OLEMISS': 'MISS',
                    'ARIZ': 'ARIZ', 'ARIZST': 'ASU', 'CAL': 'CAL', 'COLO': 'COLO',
                    'OREG': 'ORE', 'ORST': 'ORST', 'STAN': 'STAN', 'UCLA': 'UCLA',
                    'USC': 'USC', 'UTAH': 'UTAH', 'WASH': 'WASH', 'WSU': 'WSU',
                    # Big East
                    'GTOWN': 'GTWN', 'NOVA': 'VILL', 'SETON': 'SHU', 'PROV': 'PROV',
                    'MARQ': 'MARQ', 'XAVIE': 'XAV', 'BUTLER': 'BUT', 'CREIGH': 'CRE',
                    'STJOHN': 'SJU', 'DEPAUL': 'DEP',
                    # WCC & Mountain West
                    'GONZ': 'GONZ', 'STMARY': 'SMC', 'BYU': 'BYU', 'BOISE': 'BOIS',
                    'SANDST': 'SDSU', 'UNLV': 'UNLV', 'NEWMEX': 'UNM', 'FRESST': 'FRES',
                    # American & C-USA
                    'SMU': 'SMU', 'HOU': 'HOU', 'CINC': 'CIN', 'UCF': 'UCF', 'TEMPLE': 'TEM',
                    'TULSA': 'TLSA', 'TULANE': 'TUL', 'MEMPH': 'MEM', 'WSTKENT': 'WKU',
                    # A-10 & Mid-Majors
                    'DAYTON': 'DAY', 'VCU': 'VCU', 'DUQUES': 'DUQ', 'SLJOSE': 'SLU',
                    'RHODE': 'URI', 'GMASN': 'GMU', 'FORDHA': 'FOR', 'RICHMO': 'RICH',
                    'DAVIDSON': 'DAV', 'LASALL': 'LAS',
                    # Other Notable Programs
                    'DAME': 'ND', 'ARMY': 'ARMY', 'NAVY': 'NAVY', 'AIRFOR': 'AFA',
                    'RICE': 'RICE', 'SMOUTH': 'SMU', 'VERMON': 'UVM', 'COLUMB': 'COL',
                    'BROWN': 'BRN', 'CORNELL': 'COR', 'DARTMO': 'DAR', 'HARVAR': 'HAR',
                    'PENN': 'PENN', 'PRINCE': 'PRI', 'YALE': 'YALE',
                    # More mid-majors
                    'BELMON': 'BEL', 'MURRAY': 'MUR', 'TNTECH': 'TTU', 'EASTKENT': 'EKU',
                    'AKRON': 'AKR', 'BGSU': 'BGSU', 'BUFFALO': 'BUFF', 'CMICH': 'CMU',
                    'TOLEDO': 'TOL', 'EMICH': 'EMU', 'BALLST': 'BALL', 'KENT': 'KENT'
                }
                original_abbr = team_abbr
                team_abbr = ncaa_map.get(team_abbr, team_abbr)
                if original_abbr != team_abbr:
                    self.logger.info(f"NCAA mapping: {original_abbr} → {team_abbr}")

            # Resolve path relative to project root
            logo_path = self.project_root / "assets" / "sports" / logo_dir_name / f"{team_abbr}.png"
            self.logger.info(f"Looking for logo: {logo_path} (exists: {logo_path.exists()})")

            if logo_path.exists():
                self.logger.info(f"✓ Loading logo: {logo_path}")
                return Image.open(logo_path)
            else:
                self.logger.warning(f"✗ Team logo NOT FOUND: {logo_path}")
                self.logger.warning(f"  Project root: {self.project_root}")
                self.logger.warning(f"  League: {league}, Original abbr: {team_abbr}")
                return None

        except Exception as e:
            self.logger.error(f"Error loading team logo for {team_abbr} in {league}: {e}")
            return None
