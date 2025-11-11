# CheatEngine Auto-Start for Proton Games

Automatically launch CheatEngine for Steam games running on Proton with optional game title lookup using the official Steam API.

## Setup

### Step 1: Install Prerequisites

Please follow the [Prerequisites](#prerequisites) section to install all required tools:
- Python 3.11+
- uv package manager
- protonhax
- CheatEngine
- Steam

### Step 2: Install Project Dependencies

Once all prerequisites are installed, install this project's Python dependencies:

```bash
cd /path/to/protonhax-cheatengine-wrapper
uv sync
```

### Step 3: Configure the Script

Use the interactive configuration wizard:

```bash
uv run ce-autostart.py init
```

This will guide you through:
- Setting the CheatEngine executable path (with validation)
- Configuring your Steam installation directory
- Enabling/disabling the Steam API game title lookup feature

The wizard validates all paths before saving and preserves existing settings.

**Alternative - Manual Configuration:**

Edit `ce-autostart-config.toml` or create `~/.config/ce-autostart/config.toml`:
```toml
[cheatengine]
executable_path = "~/Games/CheatEngine/cheatengine-x86_64.exe"

[steam]
steam_path = "~/.local/share/Steam"
lookup_enabled = true
```

## Usage

### Interactive Setup

```bash
uv run ce-autostart.py init
```

Launches an interactive configuration wizard that:
- Prompts for the CheatEngine executable path with validation
- Asks for the Steam directory location (defaults to Linux Steam path)
- Allows enabling/disabling Steam API game title lookup
- Validates all paths exist before saving
- Re-prompts on invalid input with helpful error messages

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

### Remove LaunchOptions from a single game

```bash
uv run ce-autostart.py remove-launchoptions <GAME_ID>
```

Removes the LaunchOptions from a specific game in localconfig.vdf. Prompts for confirmation if the game currently has LaunchOptions set. The original value is backed up before removal.

### Remove LaunchOptions from all games

```bash
uv run ce-autostart.py remove-all-launchoptions
```

Finds all games that have LaunchOptions configured, prompts for confirmation once, then removes LaunchOptions from all of them. All removed values are backed up before deletion. You'll be asked individually for each game if you want to remove its LaunchOptions.

### Interactive Game Browser and Manager (Menu)

```bash
uv run ce-autostart.py menu
```

Launches an interactive terminal UI to browse, view, and manage your installed Steam games and their LaunchOptions settings. This provides a user-friendly alternative to command-line operations.

#### Menu Navigation and Input Options

**Main Game List Screen:**

The menu displays a table with all installed games showing their ID, name, and LaunchOption status.

| Input | Action |
|-------|--------|
| **↑ Arrow Up** | Move selection up |
| **↓ Arrow Down** | Move selection down |
| **Enter** | Select highlighted game and open options menu |
| **Q** | Quit and exit menu |
| **Esc** | Quit and exit menu |

**Game Options Menu:**

When you select a game, a submenu appears with the following options:

| Input | Action |
|-------|--------|
| **M** | Modify LaunchOptions for the selected game |
| **V** | View current LaunchOptions configuration |
| **R** | Remove LaunchOptions from the selected game |
| **C** | Cancel and return to game list |

The menu provides real-time visual feedback showing the selected row highlighted in blue, making it easy to navigate through your game library.

#### Menu Features

- **Visual Game List**: Displays ID, name, and LaunchOption status in an easy-to-read table format
- **Real-time Status Updates**: Immediately reflects changes to LaunchOption status after modifications
- **View Configuration**: Inspect the exact LaunchOptions command for any game
- **Quick Management**: Modify, remove, or add LaunchOptions without command-line arguments
- **User-Friendly**: Color-coded output with clear navigation hints

#### Usage Workflow Examples

**Example 1: Quick Navigation and Selection**

```
┌─────────────────────────────────────────────────────────────────┐
│ Steam Games                                                     │
├──────────┬──────────────────────────┬────────────────────────────┤
│ ID       │ Game Name                │ LaunchOption Status        │
├──────────┼──────────────────────────┼────────────────────────────┤
│ 1228870  │ Baldur's Gate 3          │ Not Set                    │
│ 2358720  │ Elden Ring               │ Configured                 │
│ 570      │ Deus Ex: Human Revolu... │ Not Set                    │  <- Currently selected
│ 1144200  │ Valheim                  │ Configured                 │
│ 1391110  │ Stalker 2                │ Not Set                    │
└──────────┴──────────────────────────┴────────────────────────────┘

Navigation: Use ↑/↓ to move, Enter to select, Q/Esc to quit
```

**Example 2: Game Options Menu**

After pressing Enter on a game:

```
┌──────────────────────────────────────────────────────────────┐
│ Selected Game: Elden Ring (ID: 2358720)                      │
│ LaunchOption Status: Configured                              │
│                                                              │
│ Options:                                                     │
│ M - Modify LaunchOptions                                    │
│ V - View Current LaunchOptions                              │
│ R - Remove LaunchOptions                                    │
│ C - Cancel (back to menu)                                   │
│                                                              │
│ Choose option: [m/v/r/c] _                                  │
└──────────────────────────────────────────────────────────────┘
```

**Example 3: Viewing LaunchOptions**

After pressing V:

```
┌──────────────────────────────────────────────────────────────┐
│ Current LaunchOptions:                                       │
│                                                              │
│ protonhax init %COMMAND%                                     │
│                                                              │
│                                                              │
│ Press Enter to continue...                                   │
└──────────────────────────────────────────────────────────────┘
```

**Example 4: Modifying LaunchOptions**

After pressing M:

```
┌──────────────────────────────────────────────────────────────┐
│ Game 'Elden Ring' already has LaunchOptions set.             │
│ Do you want to overwrite them? (yes/no)                     │
│                                                              │
│ Original: protonhax init %COMMAND%                          │
│ New:      protonhax init %COMMAND%                          │
│                                                              │
│ Answer: [y/n] _                                             │
└──────────────────────────────────────────────────────────────┘
```

If confirmed:

```
┌──────────────────────────────────────────────────────────────┐
│ LaunchOptions updated.                                       │
│                                                              │
│ ✓ Backup created: launch_options_backup_20251111_150000.md  │
│                                                              │
│ Press Enter to continue...                                   │
└──────────────────────────────────────────────────────────────┘
```

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

The script can automatically configure Steam's LaunchOptions to report running games to protonhax, and can also remove them:

**Setting LaunchOptions:**
- **Single game**: `uv run ce-autostart.py modify-launchoptions <GAME_ID>`
- **All games**: `uv run ce-autostart.py modify-all-launchoptions`

**Removing LaunchOptions:**
- **Single game**: `uv run ce-autostart.py remove-launchoptions <GAME_ID>`
- **All games**: `uv run ce-autostart.py remove-all-launchoptions`

#### How it works

1. **Game Detection**: Automatically finds installed games by reading `appmanifest_*.acf` files from the Steam directory
2. **localconfig.vdf Update**: Modifies your Steam config to set or remove LaunchOptions
3. **Automatic Backups**: Before any modification (add or remove), the script backs up the original values to a timestamped markdown file (e.g., `launch_options_backup_20251111_143022.md`)
4. **User Confirmation**: Prompts you before modifying existing LaunchOptions, letting you skip individual games or confirm all at once
5. **Configuration**: The LaunchOptions template is configurable in the TOML config file as `steam.launch_options_template`
6. **Safe Removal**: Remove commands find games with LaunchOptions already set, so you don't need to specify all games - only the ones you want to modify

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

## Prerequisites

Before using this script, you need to install and configure the following:

### 1. Python 3.11+

The script requires Python 3.11 or newer for `tomllib` support. Check your version:

```bash
python3 --version
```

### 2. uv Package Manager

The script uses `uv` as its package manager for managing Python dependencies.

**Install uv using the official installation script:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, add uv to your PATH if it's not automatically done:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

You can verify the installation:
```bash
uv --version
```

**Using uv with this project:**

Before running the script, install project dependencies using:
```bash
uv sync
```

This creates a virtual environment with all required dependencies. Then run commands with:
```bash
uv run ce-autostart.py [command]
```

The virtual environment is automatically created in `.venv` directory and will be reused for subsequent commands.

### 3. protonhax

protonhax is a tool for managing Proton Wine instances for Steam games.

**Installation:**

Clone the repository and follow the official instructions:
```bash
git clone https://github.com/jcnils/protonhax.git
cd protonhax
# Follow the installation instructions in the repository
```

Ensure the `protonhax` command is available in your PATH. You can test it:
```bash
protonhax ls
```

**GitHub Repository:** [jcnils/protonhax](https://github.com/jcnils/protonhax)

### 4. CheatEngine

CheatEngine needs to be installed or extracted to a location on your PC. The script will ask for the path during configuration.

**Options:**

- **Option A**: Extract CheatEngine to a subdirectory (e.g., `~/Games/CheatEngine/`)
- **Option B**: Install CheatEngine using Wine or Proton
- **Option C**: Use an existing CheatEngine installation

Make sure you have the CheatEngine executable ready. Common names:
- `cheatengine-x86_64.exe` (64-bit)
- `cheatengine-i386.exe` (32-bit)
- `cheatengine.exe`

You can download CheatEngine from: https://www.cheatengine.org/

### 5. Steam

This script requires a working Steam installation on your Linux system. It typically looks for Steam at:
- `~/.local/share/Steam` (default on Linux)

## Dependencies

Python dependencies are automatically installed via `uv sync`:

- `requests>=2.31.0` - HTTP library for fetching from Steam API
- `tomli_w>=1.0.0` - TOML file writing support
- `rich>=13.0.0` - Terminal formatting for interactive UI and colored output
