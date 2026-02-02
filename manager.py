"""
LivePlayerStats Plugin

Displays live player statistics for NBA, NFL, NCAAM, and NCAAF games.
Shows scrolling stat leaders for each live game with automatic league rotation.
"""

import sys
import os
import time
import threading

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
    - Continuous scrolling ticker with seamless looping
    - Background data updates applied at natural scroll break points
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

        # Enable continuous scrolling (no freeze/clamp at end of cycle)
        self.scroll_helper.continuous_mode = True

        # Build league rotation order
        self.league_rotation_order = self._build_rotation_order()
        self.current_league_index = 0

        # Plugin state
        self.games_data = []
        self.ticker_image = None
        self.last_data_update = 0
        self.needs_initial_update = True

        # Background data fetching
        self._pending_games_data = None
        self._pending_data_ready = False
        self._fetch_in_progress = False
        self._fetch_lock = threading.Lock()

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
        Update plugin data - fetch live games for display.

        On initial call, fetches synchronously to have data ready.
        On subsequent calls, fetches in a background thread to avoid
        blocking the display loop. New data is applied at the next
        scroll wrap-around for a seamless visual transition.
        """
        if not self.league_rotation_order:
            self.logger.warning("No leagues enabled")
            self.games_data = []
            self._render_scrolling_content()
            return

        # Initial update: fetch synchronously (need data before first display)
        if self.needs_initial_update:
            self._fetch_data_sync()
            return

        # Subsequent updates: start background fetch if interval has passed
        current_time = time.time()
        data_settings = self.config.get('data_settings', {})
        update_interval = data_settings.get('update_interval', 60)
        time_since_update = current_time - self.last_data_update

        if time_since_update >= update_interval and not self._fetch_in_progress:
            self.logger.info(
                "Starting background data fetch (%.1fs since last update)",
                time_since_update
            )
            self._start_background_fetch()

    def _fetch_data_sync(self):
        """Perform initial synchronous data fetch."""
        self.logger.info("Performing initial synchronous data fetch")
        fetch_start = time.time()
        live_games = self._fetch_games()
        fetch_duration = time.time() - fetch_start

        self.games_data = live_games if live_games else []
        self.last_data_update = time.time()
        self.needs_initial_update = False

        self.logger.info(
            "Initial fetch completed in %.2fs (%d games)",
            fetch_duration, len(self.games_data)
        )
        self._render_scrolling_content()

    def _start_background_fetch(self):
        """Start a background thread to fetch new game data."""
        self._fetch_in_progress = True
        thread = threading.Thread(target=self._background_fetch_data, daemon=True)
        thread.start()

    def _background_fetch_data(self):
        """Background thread: fetch game data and store as pending."""
        try:
            fetch_start = time.time()
            live_games = self._fetch_games()
            fetch_duration = time.time() - fetch_start

            with self._fetch_lock:
                self._pending_games_data = live_games if live_games else []
                self._pending_data_ready = True

            self.last_data_update = time.time()
            self.logger.info(
                "Background fetch completed in %.2fs (%d games, pending swap at next wrap)",
                fetch_duration,
                len(self._pending_games_data) if self._pending_games_data else 0
            )
        except Exception as e:
            self.logger.error(f"Background data fetch error: {e}", exc_info=True)
        finally:
            self._fetch_in_progress = False

    def _fetch_games(self):
        """
        Fetch live games, rotating through leagues if needed.

        Returns:
            List of game dictionaries, or empty list if no games found
        """
        data_settings = self.config.get('data_settings', {})
        max_games = data_settings.get('max_games_per_league', 50)
        power_conferences_only = data_settings.get('power_conferences_only', False)
        favorite_teams = data_settings.get('favorite_teams', [])
        favorite_team_expanded_stats = data_settings.get('favorite_team_expanded_stats', True)

        # Try current league first
        current = self.league_rotation_order[self.current_league_index]
        self.logger.info(f"Fetching data for {current['key']}...")

        live_games = self.data_fetcher.fetch_live_games(
            current['key'],
            max_games=max_games,
            power_conferences_only=power_conferences_only,
            favorite_teams=favorite_teams,
            favorite_team_expanded_stats=favorite_team_expanded_stats
        )

        if live_games:
            self.logger.info(
                f"Found {len(live_games)} live games in {current['key']}"
            )
            return live_games

        # No games in current league - rotate through others
        attempts = 0
        while attempts < len(self.league_rotation_order):
            self.current_league_index = (
                (self.current_league_index + 1) % len(self.league_rotation_order)
            )
            next_league = self.league_rotation_order[self.current_league_index]

            live_games = self.data_fetcher.fetch_live_games(
                next_league['key'],
                max_games=max_games,
                power_conferences_only=power_conferences_only,
                favorite_teams=favorite_teams,
                favorite_team_expanded_stats=favorite_team_expanded_stats
            )

            if live_games:
                self.logger.info(
                    f"Rotated to {next_league['key']} ({len(live_games)} live games)"
                )
                return live_games

            attempts += 1

        self.logger.info("No live games found in any enabled league")
        return []

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
        self.logger.info(f"Creating scrolling content with {len(game_cards)} game cards")
        self.scroll_helper.create_scrolling_image(
            content_items=game_cards,
            item_gap=32,  # Gap between games
            element_gap=16  # Internal spacing
        )

        # Verify scrolling image was created
        if hasattr(self.scroll_helper, 'cached_image') and self.scroll_helper.cached_image:
            scroll_width = self.scroll_helper.cached_image.width
            self.logger.info(f"Scrolling content created - width: {scroll_width}px")
        else:
            self.logger.error("Scrolling image was NOT created by scroll_helper!")

    def display(self, force_clear=False):
        """
        Display scrolling player stats.

        Handles continuous scrolling with seamless data updates:
        - Scroll wraps naturally at end of content
        - At wrap-around, pending data (from background fetch) is applied
        - No visual jumps or black screens during updates

        Args:
            force_clear: If True, clear display before rendering
        """
        try:
            if force_clear:
                self.display_manager.clear()

            # Record position before update for wrap detection
            old_pos = self.scroll_helper.scroll_position

            # Update scroll position
            self.scroll_helper.update_scroll_position()

            # Detect wrap-around (position jumped backward significantly)
            new_pos = self.scroll_helper.scroll_position
            wrapped = (old_pos - new_pos) > self.scroll_helper.display_width

            if wrapped:
                self.logger.info(
                    "Scroll wrap detected (%.0f -> %.0f)", old_pos, new_pos
                )

                # Check for pending data from background fetch
                with self._fetch_lock:
                    if self._pending_data_ready:
                        self.games_data = self._pending_games_data
                        self._pending_games_data = None
                        self._pending_data_ready = False

                        # Re-render with new data (resets scroll to position 0)
                        self._render_scrolling_content()
                        self.logger.info(
                            "Applied pending data update (%d games)",
                            len(self.games_data)
                        )
                    else:
                        # No pending data - reset tracking for next cycle
                        self.scroll_helper.scroll_complete = False
                        self.scroll_helper.total_distance_scrolled = 0.0

            # Get visible portion of scrolling image
            visible_image = self.scroll_helper.get_visible_portion()

            if visible_image is None:
                return False

            # Display the visible portion
            if visible_image:
                matrix_width = self.display_manager.width
                matrix_height = self.display_manager.height

                if not hasattr(self.display_manager, 'image') or self.display_manager.image is None:
                    self.display_manager.image = Image.new(
                        'RGB', (matrix_width, matrix_height), (0, 0, 0)
                    )
                elif self.display_manager.image.size != (matrix_width, matrix_height):
                    self.display_manager.image = Image.new(
                        'RGB', (matrix_width, matrix_height), (0, 0, 0)
                    )

                if visible_image.size == (matrix_width, matrix_height):
                    self.display_manager.image.paste(visible_image, (0, 0))
                else:
                    visible_image = visible_image.resize(
                        (matrix_width, matrix_height), Image.Resampling.LANCZOS
                    )
                    self.display_manager.image.paste(visible_image, (0, 0))

                self.display_manager.update_display()
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error displaying player stats: {e}", exc_info=True)
            return False

    def supports_dynamic_duration(self):
        """Enable dynamic duration based on content width."""
        return True

    def is_cycle_complete(self):
        """
        Always returns False for continuous scrolling mode.

        The plugin manages scroll cycles internally via wrap detection.
        The display controller uses target_duration to manage display time.
        """
        return False

    def has_live_content(self):
        """Check if there are live games to display."""
        return bool(self.games_data)

    def has_live_priority(self):
        """Keep display on this plugin while live games are active."""
        return bool(self.games_data)

    def reset_cycle_state(self):
        """
        Reset scroll cycle state.

        Called by display controller on mode switches.
        Performs a full scroll reset for clean start on new mode entry.
        """
        self.logger.info("Resetting scroll cycle state (mode switch)")
        self.scroll_helper.reset_scroll()

    def get_display_duration(self):
        """Get dynamic display duration based on scroll content."""
        if self.supports_dynamic_duration():
            return self.scroll_helper.get_dynamic_duration()
        return self.config.get('display_duration', 60.0)

    def cleanup(self):
        """Cleanup resources when plugin is unloaded."""
        self.logger.info("Cleaning up LivePlayerStats plugin")
        super().cleanup()
