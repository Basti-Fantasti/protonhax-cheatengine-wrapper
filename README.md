# CheatEngine Auto-Start for Proton Games

Automatically launch CheatEngine for Steam games running on Proton with optional game title lookup using the official Steam API.

## Setup

1. **Configure the path** to your CheatEngine executable:

   Edit `ce-autostart-config.toml`:
   ```toml
   [cheatengine]
   executable_path = "~/Games/CheatEngine/cheatengine-x86_64.exe"
   ```

   Or place a config file at `~/.config/ce-autostart/config.toml`

2. **Requirements:**
   - Python 3.11+
   - `uv` package manager installed
   - `protonhax` command available in your PATH
   - A Steam game running on Proton

## Usage

### Start CheatEngine (default)

```bash
uv run ce-autostart.py
# or explicitly:
uv run ce-autostart.py start
```

The script will:
1. Load configuration from the first available config file
2. Run `protonhax ls` to find the running game's uid
3. (Optional) Look up the game title using the cached Steam app list
4. Launch CheatEngine attached to that game using `protonhax run`

### Set LaunchOptions for a single game

```bash
uv run ce-autostart.py modify-launchoptions <GAME_ID>
```

Prompts you to confirm before modifying (if LaunchOptions already exist for this game), then sets the LaunchOptions in localconfig.vdf to the configured template. Original values are backed up to a timestamped markdown file.

### Set LaunchOptions for all installed games

```bash
uv run ce-autostart.py modify-all-launchoptions
```

Automatically detects all installed games from Steam's appmanifest files, prompts for confirmation once, then sets LaunchOptions for all games. All existing LaunchOptions are backed up before modification. You'll be asked individually for each game if it already has LaunchOptions set.

## Configuration

The script looks for config files in this order:
1. `~/.config/ce-autostart/config.toml`
2. `./ce-autostart-config.toml` (current directory)
3. `./config.toml` (current directory)

### Config Format (TOML)

```toml
[cheatengine]
# Path to the CheatEngine executable (supports ~ for home directory)
executable_path = "~/Games/CheatEngine/cheatengine-x86_64.exe"

[steam]
# Path to Steam installation directory
# Default: ~/.local/share/Steam/steamapps
steam_path = "~/.local/share/Steam/steamapps"

# Enable game title lookup from the official Steam API
# If enabled, the script will fetch and cache the Steam app list locally
# The cache is automatically updated once per week
lookup_enabled = true

# Launch options template for protonhax
# The %COMMAND% placeholder will be preserved for Steam to replace with the actual command
launch_options_template = "protonhax init %COMMAND%"
```

### LaunchOptions Management

The script can automatically configure Steam's LaunchOptions to report running games to protonhax:

- **Single game**: `uv run ce-autostart.py modify-launchoptions <GAME_ID>`
- **All games**: `uv run ce-autostart.py modify-all-launchoptions`

#### How it works

1. **Game Detection**: Automatically finds installed games by reading `appmanifest_*.acf` files from the Steam directory
2. **localconfig.vdf Update**: Modifies your Steam config to set LaunchOptions to the configured template (default: `protonhax init %COMMAND%`)
3. **Automatic Backups**: Before modifying any existing LaunchOptions, the script backs up the original values to a timestamped markdown file (e.g., `launch_options_backup_20251111_143022.md`)
4. **User Confirmation**: Prompts you before replacing existing LaunchOptions, letting you skip individual games or confirm all at once
5. **Configuration**: The LaunchOptions template is configurable in the TOML config file as `steam.launch_options_template`

#### Backup Format

Backups are stored as markdown tables for easy reference:

```markdown
# Launch Options Backup

Generated: 2025-11-11T14:30:22.123456

| Game ID | Original LaunchOptions |
|---------|------------------------|
| 2144640 | some_old_value |
| 2661300 | another_old_value |
```

### Steam API Game Title Lookup

When `steam.lookup_enabled = true`, the script will:
1. Check if the cached Steam app list is still valid (updated weekly)
2. If needed, fetch the latest app list from the official Steam API
3. Look up the game title by app ID from the cache
4. Display the game name before launching CheatEngine

**Advantages over web scraping:**
- ✅ Uses official Steam API (no web scraping)
- ✅ No Cloudflare protection to bypass
- ✅ Fast local lookups using cached data
- ✅ Automatic weekly cache updates
- ✅ No external dependencies like `cloudscraper`

**Cache Details:**
- Location: `~/.cache/ce-autostart/steam_apps.json`
- Updated weekly or on first run
- Metadata: `~/.cache/ce-autostart/cache_metadata.json` (tracks last update time)
- Size: ~30-40MB (compressed list of all Steam apps)

## Error Handling

- **No running game**: Script exits with error if `protonhax ls` returns empty output
- **Missing config**: Script lists all checked paths and exits
- **Invalid executable path**: Script verifies the file exists before launching
- **Missing protonhax**: Script checks if `protonhax` is available in PATH
- **Game lookup fails**: Script continues with launch (lookup is optional)
- **Cache update fails**: Script uses existing cache or continues without lookup

## Requirements

- Python 3.11+ (for `tomllib` support)
- External dependencies (installed via `uv`):
  - `requests>=2.31.0` - HTTP library for fetching from Steam API
