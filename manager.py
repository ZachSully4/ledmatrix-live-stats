"""
LivePlayerStats Plugin

Displays live player statistics for NBA, NFL, NCAAM, and NCAAF games.
Shows scrolling stat leaders for each live game with automatic league rotation.
"""

import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.plugin_system.base_plugin import BasePlugin
from src.common.api_helper import APIHelper
from src.common.scroll_helper import ScrollHelper
from PIL import Image

# Add current plugin directory to path for local imports
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# Import plugin modules
import data_fetcher
import stats_renderer
DataFetcher = data_fetcher.DataFetcher
StatsRenderer = stats_renderer.StatsRenderer


class LivePlayerStatsPlugin(BasePlugin):
    """
    Plugin that displays live player statistics for multiple sports leagues.

    Features:
    - Displays stat leaders for live NBA, NFL, NCAAM, and NCAAF games
    - Basketball: Shows PTS/REB/AST leaders
    - Football: Shows QB/WR/RB leaders with YDS/TD
    - Scrolling ticker display with dynamic duration
    - Automatic league rotation when no live games found
    """

    def __init__(self, plugin_id, config, display_manager, cache_manager, plugin_manager):
        """Initialize the LivePlayerStats plugin."""
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)

        # Initialize API helper
        self.api_helper = APIHelper(self.cache_manager, logger=self.logger)

        # Initialize data fetcher
        self.data_fetcher = DataFetcher(
            self.api_helper,
            self.cache_manager,
            self.logger
        )

        # Initialize stats renderer
        self.stats_renderer = StatsRenderer(
            self.plugin_manager.font_manager if hasattr(self.plugin_manager, 'font_manager') else None,
            self.logger,
            display_height=self.display_manager.height
        )

        # Initialize scroll helper
        display_opts = self.config.get('display_options', {})
        self.scroll_helper = ScrollHelper(
            self.display_manager.width,
            self.display_manager.height,
            logger=self.logger
        )

        # Configure scroll settings
        self.scroll_helper.set_frame_based_scrolling(True)
        self.scroll_helper.set_scroll_speed(display_opts.get('scroll_speed', 1.0))
        self.scroll_helper.set_scroll_delay(display_opts.get('scroll_delay', 0.02))
        self.scroll_helper.set_target_fps(display_opts.get('target_fps', 120))

        # Build league rotation order
        self.league_rotation_order = self._build_rotation_order()
        self.current_league_index = 0

        # Plugin state
        self.games_data = []
        self.ticker_image = None
        self.last_data_update = 0  # Track when data was last fetched
        self.needs_initial_update = True  # Flag for first update
        self.completed_cycle_since_update = False  # Track if at least one cycle completed since last data update
        self.last_reset_time = 0  # Track when scroll was last reset

        # Enable high FPS scrolling mode
        self.enable_scrolling = True

        self.logger.info(f"LivePlayerStats initialized with {len(self.league_rotation_order)} enabled leagues")

    def _build_rotation_order(self):
        """
        Build league rotation order sorted by priority.

        Returns:
            List of league dictionaries with keys and configs
        """
        leagues = []
        leagues_config = self.config.get('leagues', {})

        for league_key in ['nba', 'nfl', 'ncaam', 'ncaaf']:
            league_config = leagues_config.get(league_key, {})
            if league_config.get('enabled', False):
                priority = league_config.get('priority', 99)
                leagues.append((priority, league_key, league_config))

        # Sort by priority (lower number = higher priority)
        leagues.sort(key=lambda x: x[0])

        return [{'key': k, 'config': c} for _, k, c in leagues]

    def update(self):
        """
        Update plugin data - fetch live games and render scrolling content.

        Implements league rotation: if no live games found in current league,
        rotates to next enabled league until live games are found.

        Data is only fetched after scroll cycle completes to avoid interrupting scrolling.
        """
        if not self.league_rotation_order:
            self.logger.warning("No leagues enabled")
            self.games_data = []
            self._render_scrolling_content()
            return

        # Check if we should fetch new data
        current_time = time.time()
        data_settings = self.config.get('data_settings', {})
        update_interval = data_settings.get('update_interval', 60)
        time_since_update = current_time - self.last_data_update

        # Only fetch new data if:
        # 1. This is the initial update, OR
        # 2. Update interval has passed AND at least one cycle completed AND current cycle is complete
        should_fetch_data = (
            self.needs_initial_update or
            (time_since_update >= update_interval and
             self.completed_cycle_since_update and
             self.is_cycle_complete())
        )

        if not should_fetch_data:
            # Continue scrolling with existing data
            return

        # Get data settings
        max_games = data_settings.get('max_games_per_league', 50)
        power_conferences_only = data_settings.get('power_conferences_only', False)
        favorite_teams = data_settings.get('favorite_teams', [])
        favorite_team_expanded_stats = data_settings.get('favorite_team_expanded_stats', True)

        # Try current league
        self.logger.info(f"Fetching new data for {self.league_rotation_order[self.current_league_index]['key']}...")
        fetch_start = time.time()
        current = self.league_rotation_order[self.current_league_index]
        live_games = self.data_fetcher.fetch_live_games(
            current['key'],
            max_games=max_games,
            power_conferences_only=power_conferences_only,
            favorite_teams=favorite_teams,
            favorite_team_expanded_stats=favorite_team_expanded_stats
        )
        fetch_duration = time.time() - fetch_start
        self.logger.info(f"Data fetch took {fetch_duration:.2f} seconds ({len(live_games) if live_games else 0} games)")

        if not live_games:
            # Rotate to next league
            original_index = self.current_league_index
            attempts = 0

            while attempts < len(self.league_rotation_order):
                self.current_league_index = (self.current_league_index + 1) % len(self.league_rotation_order)
                next_league = self.league_rotation_order[self.current_league_index]
                live_games = self.data_fetcher.fetch_live_games(
                    next_league['key'],
                    max_games=max_games,
                    power_conferences_only=power_conferences_only,
                    favorite_teams=favorite_teams,
                    favorite_team_expanded_stats=favorite_team_expanded_stats
                )

                if live_games:
                    self.logger.info(f"Rotated from {current['key']} to {next_league['key']} ({len(live_games)} live games)")
                    break

                attempts += 1

            if not live_games:
                # No live games in any league
                self.logger.info("No live games in any enabled league")
                self.games_data = []
                self._render_scrolling_content()
                return

        # Update games data
        self.games_data = live_games

        # Update timing
        self.last_data_update = time.time()
        self.needs_initial_update = False
        self.completed_cycle_since_update = False  # Reset cycle completion flag

        # Render scrolling content
        render_start = time.time()
        self._render_scrolling_content()
        render_duration = time.time() - render_start
        self.logger.info(f"Rendering scrolling content took {render_duration:.2f} seconds")

        # Reset scroll position to start fresh cycle
        self.logger.info("Resetting scroll position to start new cycle")
        self.reset_cycle_state()
        self.logger.info("Scroll reset complete - ready to display")

    def _render_scrolling_content(self):
        """Render scrolling ticker image from game data."""
        if not self.games_data:
            # No games - show placeholder
            self.logger.debug("No games data, creating placeholder")
            placeholder = self.stats_renderer.create_no_games_placeholder(width=192)
            self.scroll_helper.create_scrolling_image(
                content_items=[placeholder],
                item_gap=0,
                element_gap=0
            )
            return

        # Render individual game cards
        game_cards = []
        card_width = 192  # Width per game card (3 panels: 64px each)

        for game in self.games_data:
            try:
                card = self.stats_renderer.render_game_card(game, card_width=card_width)
                game_cards.append(card)
            except Exception as e:
                self.logger.error(f"Error rendering game card: {e}", exc_info=True)

        if not game_cards:
            # Failed to render any cards
            self.logger.warning("Failed to render any game cards")
            placeholder = self.stats_renderer.create_no_games_placeholder(width=192)
            self.scroll_helper.create_scrolling_image(
                content_items=[placeholder],
                item_gap=0,
                element_gap=0
            )
            return

        # Create scrolling image with game cards
        self.scroll_helper.create_scrolling_image(
            content_items=game_cards,
            item_gap=32,  # Gap between games
            element_gap=16  # Internal spacing
        )

        self.logger.debug(f"Created scrolling content with {len(game_cards)} game cards")

    def display(self, force_clear=False):
        """
        Display scrolling player stats.

        Args:
            force_clear: If True, clear display before rendering
        """
        try:
            if force_clear:
                self.display_manager.clear()

            # Update scroll position
            self.scroll_helper.update_scroll_position()

            # Log scroll position occasionally for debugging
            if hasattr(self, '_last_pos_log_time'):
                if time.time() - self._last_pos_log_time > 5:  # Log every 5 seconds
                    scroll_pos = getattr(self.scroll_helper, 'scroll_position', 'unknown')
                    self.logger.debug(f"Scroll position: {scroll_pos}")
                    self._last_pos_log_time = time.time()
            else:
                self._last_pos_log_time = time.time()

            # Check if a cycle just completed
            if self.is_cycle_complete() and not self.completed_cycle_since_update:
                self.completed_cycle_since_update = True
                self.logger.debug("Scroll cycle completed - ready for data update after next cycle completion")

            # Get visible portion of scrolling image
            visible_image = self.scroll_helper.get_visible_portion()

            if visible_image is None:
                self.logger.warning("ScrollHelper returned None for visible portion")
                return

            # Display the visible portion
            if visible_image:
                # Ensure display_manager.image exists
                matrix_width = self.display_manager.width
                matrix_height = self.display_manager.height

                if not hasattr(self.display_manager, 'image') or self.display_manager.image is None:
                    self.display_manager.image = Image.new('RGB', (matrix_width, matrix_height), (0, 0, 0))
                elif self.display_manager.image.size != (matrix_width, matrix_height):
                    self.display_manager.image = Image.new('RGB', (matrix_width, matrix_height), (0, 0, 0))

                # Verify visible_image size matches display
                if visible_image.size == (matrix_width, matrix_height):
                    self.display_manager.image.paste(visible_image, (0, 0))
                else:
                    # Resize if needed (shouldn't happen, but safety check)
                    self.logger.warning(
                        f"Visible image size {visible_image.size} doesn't match display ({matrix_width}, {matrix_height})"
                    )
                    visible_image = visible_image.resize((matrix_width, matrix_height), Image.Resampling.LANCZOS)
                    self.display_manager.image.paste(visible_image, (0, 0))

                self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"Error displaying player stats: {e}", exc_info=True)

    def supports_dynamic_duration(self):
        """Enable dynamic duration based on content width."""
        return True

    def is_cycle_complete(self):
        """Check if scroll cycle is complete."""
        # Don't report complete if we just reset (within last 2 seconds)
        # This prevents false positives right after reset
        time_since_reset = time.time() - self.last_reset_time
        if time_since_reset < 2.0:
            return False

        return self.scroll_helper.is_scroll_complete()

    def reset_cycle_state(self):
        """Reset scroll cycle state."""
        self.scroll_helper.reset_scroll()
        self.last_reset_time = time.time()  # Record reset time

    def get_display_duration(self):
        """Get dynamic display duration based on scroll content."""
        if self.supports_dynamic_duration():
            return self.scroll_helper.get_dynamic_duration()
        return self.config.get('display_duration', 60.0)

    def cleanup(self):
        """Cleanup resources when plugin is unloaded."""
        self.logger.info("Cleaning up LivePlayerStats plugin")
        super().cleanup()
