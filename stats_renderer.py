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
COLOR_GOLD = (255, 215, 0)
COLOR_GREEN = (0, 255, 0)


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

        # Load fonts
        try:
            font_dir = self.project_root / 'assets' / 'fonts'
            font_path = font_dir / 'PressStart2P-Regular.ttf'

            if font_path.exists():
                self.team_font = ImageFont.truetype(str(font_path), 8)
                self.small_font = ImageFont.truetype(str(font_path), 6)
                self.medium_font = ImageFont.truetype(str(font_path), 8)
                self.stat_label_font = ImageFont.truetype(str(font_path), 8)
                self.number_font = ImageFont.truetype(str(font_path), 10)
            else:
                self.logger.warning(f"Font not found: {font_path}, using default")
                self.team_font = ImageFont.load_default()
                self.small_font = ImageFont.load_default()
                self.medium_font = ImageFont.load_default()
                self.stat_label_font = ImageFont.load_default()
                self.number_font = ImageFont.load_default()

        except Exception as e:
            self.logger.warning(f"Error loading fonts, using defaults: {e}")
            self.team_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()
            self.medium_font = ImageFont.load_default()
            self.stat_label_font = ImageFont.load_default()
            self.number_font = ImageFont.load_default()

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

            if league in ['nfl', 'ncaaf']:
                # NFL/NCAAF layout: [Game Info] [gap] [Away Logo] [Away Stats] [gap] [Home Logo] [Home Stats]
                gap = 16
                away_logo_panel = self._render_team_logo_panel(league, away_abbr)
                away_stats_panel = self._render_nfl_team_stats(away_leaders)
                home_logo_panel = self._render_team_logo_panel(league, home_abbr)
                home_stats_panel = self._render_nfl_team_stats(home_leaders)

                total_width = (panel1.width + gap
                               + away_logo_panel.width + away_stats_panel.width + gap
                               + home_logo_panel.width + home_stats_panel.width)

                img = Image.new('RGB', (total_width, self.display_height), color=COLOR_BLACK)
                current_x = 0
                img.paste(panel1, (current_x, 0))
                current_x += panel1.width + gap
                img.paste(away_logo_panel, (current_x, 0))
                current_x += away_logo_panel.width
                img.paste(away_stats_panel, (current_x, 0))
                current_x += away_stats_panel.width + gap
                img.paste(home_logo_panel, (current_x, 0))
                current_x += home_logo_panel.width
                img.paste(home_stats_panel, (current_x, 0))
            else:
                # Basketball layout: [Game Info] [Combined Stats (stacked top/bottom)]
                panel2 = self._render_combined_stats_panel(away_leaders, home_leaders, league, expanded_stats)

                total_width = panel1.width + panel2.width
                img = Image.new('RGB', (total_width, self.display_height), color=COLOR_BLACK)
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

        # Scores (stacked - same y positions as team names, green for live games)
        draw.text((current_x, away_y), away_score_text, font=score_font, fill=COLOR_GREEN)
        draw.text((current_x, home_y), home_score_text, font=score_font, fill=COLOR_GREEN)
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

        New layout with full names and large gold numbers:
        - Away team occupies top half (0-16px)
          - First names: 0-8px
          - Last names: 8-16px
        - Home team occupies bottom half (16-32px)
          - First names: 16-24px
          - Last names: 24-32px
        - Numbers: Large gold text (size 12) spanning both name lines

        Args:
            away_leaders: Dictionary of away team stat leaders
            home_leaders: Dictionary of home team stat leaders
            league: League identifier
            expanded_stats: If True, show STL/BLK and all players

        Returns:
            PIL Image of combined stats panel
        """
        min_width = 200
        height = self.display_height

        # Determine which stats to show based on league
        if league in ['nfl', 'ncaaf']:
            stat_names = ['PASS', 'RUSH', 'REC']
        elif expanded_stats:
            stat_names = ['PTS', 'REB', 'AST', 'STL', 'BLK']
        else:
            stat_names = ['PTS', 'REB', 'AST']

        # Create temporary image for width calculation
        temp_img = Image.new('RGB', (2000, height), color=COLOR_BLACK)
        temp_draw = ImageDraw.Draw(temp_img)

        # Calculate layout for each stat category with centered labels
        stat_layouts = {}
        for stat_name in stat_names:
            # Calculate stat label width (bigger font, centered)
            label_text = f"{stat_name}:"
            label_width = int(temp_draw.textlength(label_text, font=self.stat_label_font))

            # Find max name width and max number width across both teams
            max_name_width = 0
            max_number_width = 0
            max_players = 0

            for leaders in [away_leaders, home_leaders]:
                if leaders and stat_name in leaders:
                    non_zero_leaders = [l for l in leaders[stat_name] if l.get('value', 0) > 0]
                    max_players = max(max_players, len(non_zero_leaders))

                    for leader in non_zero_leaders:
                        name = leader.get('name', '?')
                        value = leader.get('value', 0)

                        # Split name
                        parts = name.split()
                        first_name = parts[0] if len(parts) > 0 else name
                        last_name = parts[-1] if len(parts) > 1 else ''

                        # Track max widths
                        first_w = int(temp_draw.textlength(first_name, font=self.small_font))
                        last_w = int(temp_draw.textlength(last_name, font=self.small_font))
                        max_name_width = max(max_name_width, first_w, last_w)

                        number_w = int(temp_draw.textlength(str(value), font=self.number_font))
                        max_number_width = max(max_number_width, number_w)

            # Calculate total width for this stat category
            # Width = label + padding + (number + 12px num-name gap + name + 16px player gap) * players + padding
            stat_width = label_width + 4 + (max_name_width + max_number_width + 28) * max(max_players, 1) + 4

            stat_layouts[stat_name] = {
                'width': max(stat_width, 40),  # Minimum 40px per stat
                'label_width': label_width,
                'name_width': max_name_width,
                'number_width': max_number_width
            }

        # Calculate total width (including 8px gaps between categories)
        total_width = 4  # Starting padding
        num_stats = 0
        for stat_name in stat_names:
            if stat_name in stat_layouts:
                total_width += stat_layouts[stat_name]['width']
                num_stats += 1
        # Add gaps between stat categories (8px between each pair)
        if num_stats > 1:
            total_width += (num_stats - 1) * 8
        total_width = max(total_width, min_width)

        # Create panel
        panel = Image.new('RGB', (total_width, height), color=COLOR_BLACK)
        draw = ImageDraw.Draw(panel)

        # Draw centered stat labels and both teams' stats
        x_pos = 4
        for stat_name in stat_names:
            layout = stat_layouts.get(stat_name)
            if not layout:
                continue

            stat_width = layout['width']
            label_width = layout['label_width']

            # Draw stat label centered vertically (y=14)
            label_text = f"{stat_name}:"
            label_x = x_pos
            label_y = 14
            draw.text((label_x, label_y), label_text, font=self.stat_label_font, fill=COLOR_LIGHT_BLUE)

            # Calculate where player names start (after label)
            names_start_x = x_pos + label_width + 4

            # Draw away team players (y=2 first names, y=10 last names)
            if away_leaders and stat_name in away_leaders:
                non_zero = [l for l in away_leaders[stat_name] if l.get('value', 0) > 0]
                player_x = names_start_x
                for leader in non_zero:
                    name = leader.get('name', '?')
                    value = leader.get('value', 0)

                    parts = name.split()
                    first_name = parts[0] if len(parts) > 0 else name
                    last_name = parts[-1] if len(parts) > 1 else ''

                    # Draw number first (gold)
                    number_text = str(value)
                    draw.text((player_x, 3), number_text, font=self.number_font, fill=COLOR_GOLD)

                    # Draw names after number (12px gap)
                    number_width = layout['number_width']
                    name_x = player_x + number_width + 12
                    draw.text((name_x, 2), first_name, font=self.small_font, fill=COLOR_WHITE)
                    draw.text((name_x, 10), last_name, font=self.small_font, fill=COLOR_WHITE)

                    # Move to next player (16px visible gap after name)
                    name_width = layout['name_width']
                    player_x += number_width + 12 + name_width + 16

            # Draw home team players (y=18 first names, y=26 last names)
            if home_leaders and stat_name in home_leaders:
                non_zero = [l for l in home_leaders[stat_name] if l.get('value', 0) > 0]
                player_x = names_start_x
                for leader in non_zero:
                    name = leader.get('name', '?')
                    value = leader.get('value', 0)

                    parts = name.split()
                    first_name = parts[0] if len(parts) > 0 else name
                    last_name = parts[-1] if len(parts) > 1 else ''

                    # Draw number first (gold)
                    number_text = str(value)
                    draw.text((player_x, 19), number_text, font=self.number_font, fill=COLOR_GOLD)

                    # Draw names after number (12px gap)
                    number_width = layout['number_width']
                    name_x = player_x + number_width + 12
                    draw.text((name_x, 18), first_name, font=self.small_font, fill=COLOR_WHITE)
                    draw.text((name_x, 26), last_name, font=self.small_font, fill=COLOR_WHITE)

                    # Move to next player (16px visible gap after name)
                    name_width = layout['name_width']
                    player_x += number_width + 12 + name_width + 16

            # Move to next stat category with extra spacing
            x_pos += stat_width + 8  # Add 8px gap between categories

        return panel

    def _render_team_logo_panel(self, league: str, team_abbr: str) -> Image.Image:
        """
        Render a single team logo centered in a panel.

        Args:
            league: League identifier for logo lookup
            team_abbr: Team abbreviation

        Returns:
            PIL Image (38x32) with centered team logo
        """
        logo_size = int(self.display_height * 1.2)  # 38px for 32px display
        panel = Image.new('RGB', (logo_size, self.display_height), color=COLOR_BLACK)

        logo = self._get_team_logo(league, team_abbr)
        if logo:
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            y_pos = (self.display_height - logo_size) // 2
            panel.paste(logo, (0, y_pos), logo if logo.mode == 'RGBA' else None)
        else:
            # Fallback: draw team abbreviation
            draw = ImageDraw.Draw(panel)
            abbr_text = team_abbr[:4]
            text_width = int(draw.textlength(abbr_text, font=self.team_font))
            text_x = (logo_size - text_width) // 2
            text_y = (self.display_height - 8) // 2
            draw.text((text_x, text_y), abbr_text, font=self.team_font, fill=COLOR_GRAY)

        return panel

    def _render_nfl_team_stats(self, leaders: Optional[Dict]) -> Image.Image:
        """
        Render one NFL team's stats panel using full 32px height with 3 rows.

        Layout:
            Row 0 (y=2):  QB:   Smith 215YDS
            Row 1 (y=12): RUSH: 142YDS  Walker 87YDS 1TD
            Row 2 (y=22): REC:  215YDS  Metcalf 68YDS 2TD

        Args:
            leaders: Dict with PASS/RUSH/REC data in richer format

        Returns:
            PIL Image of the stats panel
        """
        height = self.display_height
        row_y = [2, 12, 22]

        if not leaders:
            panel = Image.new('RGB', (100, height), color=COLOR_BLACK)
            draw = ImageDraw.Draw(panel)
            draw.text((2, 12), "No stats", font=self.small_font, fill=COLOR_GRAY)
            return panel

        # Build text elements for each row to calculate width
        temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        rows = []

        # Row 0: QB line
        pass_data = leaders.get('PASS', {})
        qb_label = "QB:"
        qb_name = pass_data.get('leader_name', 'TBD')
        # Use last name only
        qb_parts = qb_name.split()
        qb_last = qb_parts[-1] if len(qb_parts) > 1 else qb_name
        qb_yards = str(pass_data.get('leader_yards', 0))
        rows.append({'label': qb_label, 'segments': [
            {'text': qb_last, 'font': self.small_font, 'color': COLOR_WHITE},
            {'text': ' ', 'font': self.small_font, 'color': COLOR_WHITE},
            {'text': f"{qb_yards}YDS", 'font': self.stat_label_font, 'color': COLOR_GOLD},
        ]})

        # Row 1: RUSH line
        rush_data = leaders.get('RUSH', {})
        rush_label = "RUSH:"
        rush_total = str(rush_data.get('team_total_yards', 0))
        rush_name = rush_data.get('leader_name', 'TBD')
        rush_parts = rush_name.split()
        rush_last = rush_parts[-1] if len(rush_parts) > 1 else rush_name
        rush_yards = str(rush_data.get('leader_yards', 0))
        rush_tds = rush_data.get('leader_tds', 0)
        rush_segments = [
            {'text': f"{rush_total}YDS", 'font': self.stat_label_font, 'color': COLOR_GOLD},
            {'text': '  ', 'font': self.small_font, 'color': COLOR_WHITE},
            {'text': rush_last, 'font': self.small_font, 'color': COLOR_WHITE},
            {'text': ' ', 'font': self.small_font, 'color': COLOR_WHITE},
            {'text': f"{rush_yards}YDS", 'font': self.stat_label_font, 'color': COLOR_GOLD},
        ]
        if rush_tds > 0:
            rush_segments.append({'text': ' ', 'font': self.small_font, 'color': COLOR_WHITE})
            rush_segments.append({'text': f"{rush_tds}TD", 'font': self.stat_label_font, 'color': COLOR_GOLD})
        rows.append({'label': rush_label, 'segments': rush_segments})

        # Row 2: REC line
        rec_data = leaders.get('REC', {})
        rec_label = "REC:"
        rec_total = str(rec_data.get('team_total_yards', 0))
        rec_name = rec_data.get('leader_name', 'TBD')
        rec_parts = rec_name.split()
        rec_last = rec_parts[-1] if len(rec_parts) > 1 else rec_name
        rec_yards = str(rec_data.get('leader_yards', 0))
        rec_tds = rec_data.get('leader_tds', 0)
        rec_segments = [
            {'text': f"{rec_total}YDS", 'font': self.stat_label_font, 'color': COLOR_GOLD},
            {'text': '  ', 'font': self.small_font, 'color': COLOR_WHITE},
            {'text': rec_last, 'font': self.small_font, 'color': COLOR_WHITE},
            {'text': ' ', 'font': self.small_font, 'color': COLOR_WHITE},
            {'text': f"{rec_yards}YDS", 'font': self.stat_label_font, 'color': COLOR_GOLD},
        ]
        if rec_tds > 0:
            rec_segments.append({'text': ' ', 'font': self.small_font, 'color': COLOR_WHITE})
            rec_segments.append({'text': f"{rec_tds}TD", 'font': self.stat_label_font, 'color': COLOR_GOLD})
        rows.append({'label': rec_label, 'segments': rec_segments})

        # Calculate max width needed
        max_width = 0
        label_gap = 4  # gap after label
        for row in rows:
            label_w = int(temp_draw.textlength(row['label'], font=self.stat_label_font))
            content_w = sum(int(temp_draw.textlength(seg['text'], font=seg['font'])) for seg in row['segments'])
            total_w = label_w + label_gap + content_w
            max_width = max(max_width, total_w)

        panel_width = max_width + 8  # padding
        panel = Image.new('RGB', (panel_width, height), color=COLOR_BLACK)
        draw = ImageDraw.Draw(panel)

        # Draw each row
        for i, row in enumerate(rows):
            y = row_y[i]
            x = 2

            # Draw label in light blue
            draw.text((x, y), row['label'], font=self.stat_label_font, fill=COLOR_LIGHT_BLUE)
            x += int(draw.textlength(row['label'], font=self.stat_label_font)) + label_gap

            # Draw each segment
            for seg in row['segments']:
                draw.text((x, y), seg['text'], font=seg['font'], fill=seg['color'])
                x += int(draw.textlength(seg['text'], font=seg['font']))

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
