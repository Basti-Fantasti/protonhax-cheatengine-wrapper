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

```bash
uv run ce-autostart.py
```

The script will:
1. Load configuration from the first available config file
2. Run `protonhax ls` to find the running game's uid
3. (Optional) Look up the game title using the cached Steam app list
4. Launch CheatEngine attached to that game using `protonhax run`

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
# Enable game title lookup from the official Steam API
# If enabled, the script will fetch and cache the Steam app list locally
# The cache is automatically updated once per week
lookup_enabled = true
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
