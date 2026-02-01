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

        # Load fonts (using compact fonts for small display)
        try:
            # Try to get 4x6 font for compact display
            self.small_font = ImageFont.load_default()
            self.medium_font = ImageFont.load_default()

            # Attempt to load better fonts if available
            font_dir = self.project_root / 'assets' / 'fonts'

            try:
                font_path_4x6 = font_dir / '4x6-font.ttf'
                if font_path_4x6.exists():
                    self.small_font = ImageFont.truetype(str(font_path_4x6), 6)
                    self.medium_font = ImageFont.truetype(str(font_path_4x6), 8)
            except Exception as e:
                self.logger.debug(f"Could not load custom fonts: {e}")
                pass

        except Exception as e:
            self.logger.warning(f"Error loading fonts, using defaults: {e}")
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
            away_score = game_data.get('away_score', 0)
            home_score = game_data.get('home_score', 0)
            period_text = game_data.get('period_text', '')
            clock = game_data.get('clock', '')
            away_leaders = game_data.get('away_leaders')
            home_leaders = game_data.get('home_leaders')
            league = game_data.get('league', 'ncaam')

            # Panel dimensions
            panel_width = 64
            total_width = panel_width * 3  # 3 panels

            # Create full image
            img = Image.new('RGB', (total_width, self.display_height), color=COLOR_BLACK)
            draw = ImageDraw.Draw(img)

            # --- PANEL 1: Game Info with Logos (Left) ---
            panel1_x = 0
            panel1 = self._render_game_info_panel(away_abbr, home_abbr, away_score, home_score,
                                                  period_text, clock, league)
            img.paste(panel1, (panel1_x, 0))

            # --- PANEL 2: Away Team Stats (Middle) ---
            panel2_x = panel_width
            panel2 = self._render_stats_panel(away_abbr, away_leaders, league)
            img.paste(panel2, (panel2_x, 0))

            # --- PANEL 3: Home Team Stats (Right) ---
            panel3_x = panel_width * 2
            panel3 = self._render_stats_panel(home_abbr, home_leaders, league)
            img.paste(panel3, (panel3_x, 0))

            return img

        except Exception as e:
            self.logger.error(f"Error rendering game card: {e}", exc_info=True)
            # Return error card
            return self._create_error_card(card_width)

    def _render_game_info_panel(self, away_abbr: str, home_abbr: str, away_score: int,
                                home_score: int, period_text: str, clock: str, league: str) -> Image.Image:
        """
        Render Panel 1: Game info with team logos (EXACTLY copied from odds-ticker).

        Args:
            away_abbr: Away team abbreviation
            home_abbr: Home team abbreviation
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
        logo_size = int(height * 1.2)  # Make logos use most of the display height
        h_padding = 4  # Use a consistent horizontal padding

        # Fonts
        team_font = self.medium_font
        score_font = self.medium_font

        # Get team logos
        away_logo = self._get_team_logo(league, away_abbr)
        home_logo = self._get_team_logo(league, home_abbr)

        if away_logo:
            away_logo = away_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        if home_logo:
            home_logo = home_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # Format team names and scores (truncate team names to 4 chars like odds-ticker)
        away_team_text = away_abbr[:4]
        home_team_text = home_abbr[:4]
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

        # Period/clock status width
        period_display = period_text[:8] if period_text else ""
        clock_display = clock[:8] if clock else ""
        period_width = int(temp_draw.textlength(period_display, font=self.small_font)) if period_display else 0
        clock_width = int(temp_draw.textlength(clock_display, font=self.small_font)) if clock_display else 0
        status_width = max(period_width, clock_width, 20)  # Min width of 20

        # Calculate total width (EXACTLY like odds-ticker formula)
        total_width = (logo_size * 2) + vs_width + team_info_width + scores_width + status_width + (h_padding * 6)

        # Create the image
        image = Image.new('RGB', (int(total_width), height), color=COLOR_BLACK)
        draw = ImageDraw.Draw(image)

        # --- Draw elements (EXACTLY like odds-ticker) ---
        current_x = 0

        # Away Logo (centered vertically)
        if away_logo:
            y_pos = (height - logo_size) // 2  # Center the logo vertically
            image.paste(away_logo, (current_x, y_pos), away_logo if away_logo.mode == 'RGBA' else None)
        current_x += logo_size + h_padding

        # "vs." text (centered vertically)
        draw.text((current_x, height // 2 - 4), vs_text, font=team_font, fill=(255, 255, 255))
        current_x += vs_width + h_padding

        # Home Logo (centered vertically)
        if home_logo:
            y_pos = (height - logo_size) // 2  # Center the logo vertically
            image.paste(home_logo, (current_x, y_pos), home_logo if home_logo.mode == 'RGBA' else None)
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

        # Period/Clock (stacked - same y positions)
        if period_display:
            draw.text((current_x, away_y), period_display, font=self.small_font, fill=(170, 170, 170))
        if clock_display:
            draw.text((current_x, home_y), clock_display, font=self.small_font, fill=(170, 170, 170))

        return image

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

        # Team logo at top
        logo = self._get_team_logo(league, team_abbr)
        if logo:
            logo_size = 14
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            logo_x = (panel_width - logo_size) // 2
            panel.paste(logo, (logo_x, 1), logo if logo.mode == 'RGBA' else None)

        #y_pos = 0

        # Draw stat leaders
        if leaders and ('PTS' in leaders or 'REB' in leaders or 'AST' in leaders):
            # Points leader
            if 'PTS' in leaders:
                pts_leader = leaders['PTS']
                name = self._abbreviate_display_name(pts_leader.get('name', '?'), max_length=6)
                value = pts_leader.get('value', 0)
                text = f"P:{name} {value}"
                draw.text((2, 1), text, font=self.small_font, fill=COLOR_LIGHT_BLUE)
                y_pos += 0

            # Rebounds leader
            if 'REB' in leaders:
                reb_leader = leaders['REB']
                name = self._abbreviate_display_name(reb_leader.get('name', '?'), max_length=6)
                value = reb_leader.get('value', 0)
                text = f"R:{name} {value}"
                draw.text((2, 9), text, font=self.small_font, fill=COLOR_LIGHT_BLUE)
                y_pos += 0

            # Assists leader
            if 'AST' in leaders:
                ast_leader = leaders['AST']
                name = self._abbreviate_display_name(ast_leader.get('name', '?'), max_length=6)
                value = ast_leader.get('value', 0)
                text = f"A:{name} {value}"
                draw.text((2, 18), text, font=self.small_font, fill=COLOR_LIGHT_BLUE)
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
                    'ILL': 'ILL', 'IND': 'IND', 'MD': 'MD', 'NW': 'NW', 'PUR': 'PUR',
                    'RUTG': 'RUTG', 'WISC': 'WISC',
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
