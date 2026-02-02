# LivePlayerStats Plugin

Displays live player statistics for NBA, NFL, NCAAM, and NCAAF games on your LED matrix. Shows scrolling stat leaders for each live game with automatic league rotation.

## Features

- **Multi-Sport Support**: NBA, NFL, NCAAM (College Basketball), NCAAF (College Football)
- **Stat Leaders Display**:
  - **Basketball**: Points/Rebounds/Assists (PTS/REB/AST) leaders per team
  - **Football**: Top QB (passing YDS/TD), WR (receiving YDS/TD), RB (rushing YDS/TD) per team
- **Scrolling Display**: Smooth scrolling ticker showing all live games
- **League Rotation**: Automatically switches leagues when no live games found
- **Dynamic Duration**: Display time adjusts based on content width
- **Live Updates**: Refreshes every 60 seconds for live game data

## Configuration

Add to your `config.json`:

```json
{
  "live-player-stats": {
    "enabled": true,
    "display_options": {
      "scroll_speed": 1.0,
      "scroll_delay": 0.02,
      "target_fps": 120
    },
    "data_settings": {
      "update_interval": 60,
      "cache_ttl": 60
    },
    "leagues": {
      "nba": {
        "enabled": true,
        "priority": 1
      },
      "nfl": {
        "enabled": true,
        "priority": 2
      },
      "ncaam": {
        "enabled": false,
        "priority": 3
      },
      "ncaaf": {
        "enabled": false,
        "priority": 4
      }
    }
  }
}
```

### Configuration Options

#### `display_options`
- `scroll_speed` (number, default: 1.0): Scrolling speed in pixels per frame
- `scroll_delay` (number, default: 0.02): Delay between scroll frames in seconds
- `target_fps` (integer, default: 120): Target frames per second for smooth scrolling

#### `data_settings`
- `update_interval` (integer, default: 60): Seconds between data updates from ESPN API
- `cache_ttl` (integer, default: 60): Cache time-to-live in seconds for API responses

#### `leagues`
Each league has:
- `enabled` (boolean): Enable/disable the league
- `priority` (integer): Lower number = higher priority (used for rotation order)

## How It Works

### League Rotation
The plugin checks enabled leagues in priority order. If no live games are found in the current league, it automatically rotates to the next enabled league until live games are found.

**Example:**
1. NBA is priority 1, NFL is priority 2
2. Plugin checks NBA first
3. If no live NBA games, switches to NFL
4. If no live NFL games, cycles back to NBA
5. Shows "No live games" if no games found in any league

### Data Source
Uses ESPN API endpoints:
- NBA: `http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
- NFL: `http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`
- NCAAM: `http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard`
- NCAAF: `http://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard`

### Display Format

#### Basketball Games
```
LAL 98 @ BOS 102  Q3 8:45
LAL: LBJ 24/8/7
BOS: JT 22/6/4
```

#### Football Games
```
KC 21 @ BUF 17  Q4 5:23
KC: Mahomes 245, 3TD
BUF: Allen 198, 2TD
```

## Installation

The plugin should auto-discover when placed in the `plugin-repos` directory. Restart your LEDMatrix system or reload plugins via the web interface.

## Requirements

- LEDMatrix v2.0.0 or higher
- No additional Python dependencies (uses core LEDMatrix libraries)

## Files

- `manifest.json` - Plugin metadata and registration
- `manager.py` - Main plugin class (LivePlayerStatsPlugin)
- `data_fetcher.py` - ESPN API integration and stat extraction
- `stats_renderer.py` - PIL-based rendering of game cards
- `config_schema.json` - Configuration validation schema
- `requirements.txt` - Empty (uses core dependencies)
- `README.md` - This documentation

## Troubleshooting

### No stats showing
- Check that games are actually live (not pregame or final)
- Verify ESPN API is accessible from your network
- Check logs: `tail -f ~/.ledmatrix_logs/ledmatrix.log | grep "live-player-stats"`

### "No live games" displayed
- Normal when no games are in progress
- Plugin will automatically update when games start
- Check enabled leagues in config

### Stats seem delayed
- Default update interval is 60 seconds
- Reduce `update_interval` in `data_settings` for faster updates (minimum: 30 seconds)
- Be mindful of API rate limiting

## Credits

Created for the LEDMatrix project. Uses ESPN public API for sports data.
