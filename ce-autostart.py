#!/usr/bin/env python3
"""
CheatEngine auto-start script for Steam games running on Proton.
Run with: uv run ce-autostart.py [command] [args]

Commands:
  init                          - Interactive configuration setup
  start [game_uid]              - Start CheatEngine for a running game (default)
  menu                          - Interactive game browser and manager
  modify-launchoptions <ID>     - Set LaunchOptions for a specific game
  modify-all-launchoptions      - Set LaunchOptions for all installed games
  remove-launchoptions <ID>     - Remove LaunchOptions from a specific game
  remove-all-launchoptions      - Remove LaunchOptions from all games with them set
"""

import subprocess
import sys
from pathlib import Path
import tomllib  # Python 3.11+
import tomli_w
import json
import requests
from datetime import datetime, timedelta
import re
from rich.table import Table
from rich.console import Console
from rich.text import Text

CONFIG_PATHS = [
    Path.home() / ".config" / "ce-autostart" / "config.toml",
    Path.cwd() / "ce-autostart-config.toml",
    Path.cwd() / "config.toml",
]

CACHE_DIR = Path.home() / ".cache" / "ce-autostart"
CACHE_FILE = CACHE_DIR / "steam_apps.json"
CACHE_METADATA_FILE = CACHE_DIR / "cache_metadata.json"
STEAM_API_URL = "https://api.steampowered.com/ISteamApps/GetAppList/v1/"
CACHE_VALIDITY_DAYS = 7


def load_config() -> dict:
    """Load configuration from TOML file."""
    for config_path in CONFIG_PATHS:
        if config_path.exists():
            print(f"Loading config from: {config_path}")
            with open(config_path, "rb") as f:
                return tomllib.load(f)

    print("Error: No config file found. Checked:", file=sys.stderr)
    for path in CONFIG_PATHS:
        print(f"  - {path}", file=sys.stderr)
    sys.exit(1)


def get_running_game_uid() -> str:
    """Run 'protonhax ls' and parse the uid of the running game."""
    try:
        result = subprocess.run(
            ["protonhax", "ls"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print("Error: 'protonhax' command not found. Is protonhax installed?", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running 'protonhax ls': {e.stderr}", file=sys.stderr)
        sys.exit(1)

    output = result.stdout.strip()

    if not output:
        print("Error: No running game found.", file=sys.stderr)
        sys.exit(1)

    # Parse the uid from output
    uid = output.split()[-1] if output else None

    if not uid or not uid.isdigit():
        print(f"Error: Could not parse valid uid from output: {output}", file=sys.stderr)
        sys.exit(1)

    return uid


def is_cache_valid() -> bool:
    """Check if the cached Steam app list is still valid."""
    if not CACHE_METADATA_FILE.exists():
        return False

    try:
        with open(CACHE_METADATA_FILE, "r") as f:
            metadata = json.load(f)

        last_update = datetime.fromisoformat(metadata.get("last_update", ""))
        age = datetime.now() - last_update

        return age < timedelta(days=CACHE_VALIDITY_DAYS)
    except (json.JSONDecodeError, ValueError, KeyError):
        return False


def update_steam_app_cache() -> bool:
    """Fetch and cache the Steam app list from the official API."""
    try:
        print("Updating Steam app list cache...")
        response = requests.get(STEAM_API_URL, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Ensure cache directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Save the app list
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)

        # Save metadata
        metadata = {
            "last_update": datetime.now().isoformat(),
            "app_count": len(data.get("applist", {}).get("apps", {}).get("app", [])),
        }
        with open(CACHE_METADATA_FILE, "w") as f:
            json.dump(metadata, f)

        print(f"✓ Cache updated with {metadata['app_count']} apps")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to update Steam app cache: {e}", file=sys.stderr)
        return False


def load_app_cache() -> dict | None:
    """Load the cached Steam app list."""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def lookup_game_from_manifest(app_id: str, steam_path: str) -> str | None:
    """
    Look up game info from local Steam manifest file.
    Returns game title if found, None otherwise.
    """
    steam_dir = Path(steam_path).expanduser()
    manifest_file = steam_dir / f"appmanifest_{app_id}.acf"

    if not manifest_file.exists():
        return None

    try:
        with open(manifest_file, "r") as f:
            content = f.read()

        # Parse the manifest file (it's a simple key-value format)
        # Looking for the "name" field which contains the game title
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith('"name"'):
                # Extract the value between quotes
                # Format: "name"		"Game Title"
                parts = line.split('"', 3)
                if len(parts) >= 4:
                    # Remove the trailing quote if present
                    game_title = parts[3].rstrip('"')
                    return game_title

        return None

    except (IOError, OSError) as e:
        print(f"Warning: Could not read manifest file {manifest_file}: {e}", file=sys.stderr)
        return None


def lookup_game_title(app_id: str, steam_path: str | None = None) -> str | None:
    """
    Look up the game title, first from local Steam manifest, then from Steam API cache.

    Args:
        app_id: The Steam application ID
        steam_path: Path to Steam steamapps directory (if None, skips local lookup)

    Returns:
        Game title if found, None otherwise
    """
    # First, try to lookup from local Steam manifest
    if steam_path:
        print(f"Looking up game title from local Steam manifest...")
        game_title = lookup_game_from_manifest(app_id, steam_path)
        if game_title:
            print(f"✓ Found game in local manifest: {game_title}")
            return game_title
        else:
            print(f"Game not found in local Steam folder")

    # Fall back to Steam API cache
    print(f"Looking up game title from Steam API cache...")

    # Check if cache needs update
    if not is_cache_valid():
        update_steam_app_cache()

    # Load cache
    data = load_app_cache()
    if not data:
        print("Warning: No cached Steam app list available", file=sys.stderr)
        return None

    # Search for the app
    try:
        app_id_int = int(app_id)
        for app in data.get("applist", {}).get("apps", {}).get("app", []):
            if app.get("appid") == app_id_int:
                game_title = app.get("name")
                if game_title:
                    print(f"✓ Found game in Steam API cache: {game_title}")
                    return game_title
    except (ValueError, KeyError):
        pass

    print(f"Warning: Could not find game with app ID {app_id} in Steam database", file=sys.stderr)
    return None


def launch_cheatengine(uid: str, executable_path: str) -> None:
    """Launch CheatEngine using protonhax run."""
    exe_path = Path(executable_path).expanduser()

    if not exe_path.exists():
        print(f"Error: CheatEngine executable not found at: {exe_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Launching CheatEngine for game uid: {uid}")
    print(f"Using executable: {exe_path}")

    try:
        subprocess.run(
            ["protonhax", "run", uid, str(exe_path)],
            check=False,  # Don't fail if protonhax returns non-zero
        )
    except FileNotFoundError:
        print("Error: 'protonhax' command not found.", file=sys.stderr)
        sys.exit(1)


def find_localconfig_vdf(steam_path: str | None = None) -> Path | None:
    """
    Find the localconfig.vdf file by recursively searching userdata subdirectories.
    Returns the path to localconfig.vdf if found, None otherwise.
    """
    if steam_path is None:
        steam_path = "~/.local/share/Steam"

    steam_dir = Path(steam_path).expanduser()
    userdata_dir = steam_dir / "userdata"

    if not userdata_dir.exists():
        print(f"Warning: Steam userdata directory not found: {userdata_dir}", file=sys.stderr)
        return None

    # Recursively search for localconfig.vdf
    for localconfig in userdata_dir.rglob("localconfig.vdf"):
        return localconfig

    print(f"Warning: Could not find localconfig.vdf in {userdata_dir}", file=sys.stderr)
    return None


def parse_vdf(content: str) -> dict:
    """
    Parse VDF format file content into a Python dictionary.
    VDF format uses quoted keys and values with nested braces.
    """
    def tokenize(text):
        """Tokenize VDF content."""
        tokens = []
        i = 0
        while i < len(text):
            # Skip whitespace
            if text[i].isspace():
                i += 1
                continue
            # Handle comments
            if text[i:i+2] == '//':
                while i < len(text) and text[i] != '\n':
                    i += 1
                continue
            # Handle quoted strings
            if text[i] == '"':
                i += 1
                start = i
                while i < len(text) and text[i] != '"':
                    i += 1
                tokens.append(('STRING', text[start:i]))
                i += 1
            # Handle braces and tabs
            elif text[i] in '{}':
                tokens.append(('BRACE', text[i]))
                i += 1
            else:
                i += 1
        return tokens

    def parse_tokens(tokens, index=0):
        """Recursively parse tokens into a dictionary."""
        result = {}
        while index < len(tokens):
            token_type, token_value = tokens[index]

            if token_type == 'STRING':
                key = token_value
                index += 1

                # Skip tabs
                while index < len(tokens) and tokens[index][0] == 'STRING' and tokens[index][1] == '':
                    index += 1

                if index < len(tokens):
                    next_type, next_value = tokens[index]

                    if next_type == 'BRACE' and next_value == '{':
                        # Nested dict
                        index += 1
                        nested, index = parse_tokens(tokens, index)
                        result[key] = nested
                    elif next_type == 'STRING':
                        # Key-value pair
                        result[key] = next_value
                        index += 1
                    elif next_type == 'BRACE' and next_value == '}':
                        break
            elif token_type == 'BRACE' and token_value == '}':
                index += 1
                break
            else:
                index += 1

        return result, index

    tokens = tokenize(content)
    parsed, _ = parse_tokens(tokens)
    return parsed


def write_vdf(data: dict, indent: int = 0) -> str:
    """
    Write a dictionary back to VDF format.
    """
    lines = []
    indent_str = "\t" * indent

    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'{indent_str}"{key}"')
            lines.append(f'{indent_str}{{')
            lines.append(write_vdf(value, indent + 1).rstrip())
            lines.append(f'{indent_str}}}')
        else:
            lines.append(f'{indent_str}"{key}"\t\t"{value}"')

    return '\n'.join(lines) + '\n'


def get_installed_games(steam_path: str | None = None) -> list[str]:
    """
    Get list of installed game IDs by reading appmanifest_*.acf files.
    Returns list of app IDs as strings.
    """
    if steam_path is None:
        steam_path = "~/.local/share/Steam/steamapps"

    steamapps_dir = Path(steam_path).expanduser()

    if not steamapps_dir.exists():
        print(f"Warning: Steam steamapps directory not found: {steamapps_dir}", file=sys.stderr)
        return []

    app_ids = []
    for manifest_file in steamapps_dir.glob("appmanifest_*.acf"):
        # Extract ID from filename
        app_id = manifest_file.stem.replace("appmanifest_", "")
        if app_id.isdigit():
            app_ids.append(app_id)

    return sorted(app_ids)


def get_game_info(app_id: str, steam_path: str | None = None) -> dict:
    """
    Get detailed game information including name and other metadata.
    Returns a dict with keys: app_id, name, executable, install_dir
    """
    if steam_path is None:
        steam_path = "~/.local/share/Steam/steamapps"

    steamapps_dir = Path(steam_path).expanduser()
    manifest_file = steamapps_dir / f"appmanifest_{app_id}.acf"

    game_info = {
        "app_id": app_id,
        "name": f"Game {app_id}",
        "executable": "",
        "install_dir": "",
    }

    if not manifest_file.exists():
        return game_info

    try:
        with open(manifest_file, "r") as f:
            content = f.read()

        # Parse the manifest file for game metadata
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith('"name"'):
                # Extract game name: "name"		"Game Title"
                parts = line.split('"', 3)
                if len(parts) >= 4:
                    game_info["name"] = parts[3].rstrip('"')
            elif line.startswith('"executable"'):
                # Extract executable path
                parts = line.split('"', 3)
                if len(parts) >= 4:
                    game_info["executable"] = parts[3].rstrip('"')
            elif line.startswith('"installdir"'):
                # Extract install directory
                parts = line.split('"', 3)
                if len(parts) >= 4:
                    game_info["install_dir"] = parts[3].rstrip('"')

        return game_info

    except (IOError, OSError) as e:
        print(f"Warning: Could not read manifest file {manifest_file}: {e}", file=sys.stderr)
        return game_info


def get_launchoption_status(app_id: str, steam_path: str | None = None) -> str:
    """
    Check the LaunchOption status for a game.
    Returns one of: "Configured", "Not Set", or "Error"
    """
    if steam_path is None:
        steam_path = "~/.local/share/Steam"

    try:
        localconfig_path = find_localconfig_vdf(steam_path)
        if not localconfig_path:
            return "Error"

        with open(localconfig_path, "r") as f:
            content = f.read()

        localconfig_data = parse_vdf(content)

        # Navigate to the app section
        try:
            apps = (
                localconfig_data
                .get("Software", {})
                .get("Valve", {})
                .get("Steam", {})
                .get("apps", {})
            )

            if app_id in apps and isinstance(apps[app_id], dict):
                if "LaunchOptions" in apps[app_id]:
                    return "Configured"
                else:
                    return "Not Set"
            else:
                return "Not Set"

        except (KeyError, TypeError, AttributeError):
            return "Error"

    except Exception:
        return "Error"


def get_game_title(app_id: str, localconfig_data: dict) -> str | None:
    """
    Extract game title from localconfig.vdf data for a given app ID.
    """
    try:
        # Navigate the structure: Software -> Valve -> Steam -> apps -> <app_id>
        software = localconfig_data.get("Software", {})
        valve = software.get("Valve", {})
        steam = valve.get("Steam", {})
        apps = steam.get("apps", {})

        if app_id in apps:
            # Get the game entry
            game_entry = apps[app_id]
            # In localconfig.vdf, the app ID might be nested as a key with game info
            # We'll return app_id as display name, actual title lookup can use steam api
            return f"Game {app_id}"
    except (KeyError, TypeError):
        pass

    return None


def create_backup(game_id: str, original_value: str) -> None:
    """
    Create a backup of the original LaunchOptions value.
    Backup file is stored with timestamp in the current directory.
    """
    backup_dir = Path.cwd()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"launch_options_backup_{timestamp}.md"

    # Append to backup file if it exists, create if not
    backup_content = f"| {game_id} | {original_value} |\n"

    if backup_file.exists():
        with open(backup_file, "a") as f:
            f.write(backup_content)
    else:
        # Create with header
        with open(backup_file, "w") as f:
            f.write("# Launch Options Backup\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write("| Game ID | Original LaunchOptions |\n")
            f.write("|---------|------------------------|\n")
            f.write(backup_content)

    print(f"✓ Backed up original value to {backup_file}")


def modify_launch_options(
    app_id: str,
    new_launch_options: str,
    localconfig_path: Path,
    ask_if_exists: bool = True
) -> bool:
    """
    Modify LaunchOptions for a specific game in localconfig.vdf.
    Returns True if modified, False otherwise.
    """
    try:
        with open(localconfig_path, "r") as f:
            content = f.read()

        localconfig_data = parse_vdf(content)

        # Navigate to the app section
        # Structure: Software -> Valve -> Steam -> apps -> <app_id>
        try:
            apps = (
                localconfig_data
                .setdefault("Software", {})
                .setdefault("Valve", {})
                .setdefault("Steam", {})
                .setdefault("apps", {})
            )

            app_section = apps.setdefault(app_id, {})
        except (KeyError, TypeError, AttributeError):
            print(f"Error: Could not navigate to app {app_id} in localconfig.vdf", file=sys.stderr)
            return False

        # Check if LaunchOptions already exists
        if "LaunchOptions" in app_section:
            current_value = app_section["LaunchOptions"]
            if current_value == new_launch_options:
                print(f"ℹ Game {app_id}: LaunchOptions already set to {new_launch_options}")
                return False

            if ask_if_exists:
                print(f"\n⚠ Game {app_id}:")
                print(f"  Current value: {current_value}")
                response = input(f"  Replace with '{new_launch_options}'? (y/n/skip): ").strip().lower()

                if response == "skip" or response == "n":
                    print(f"  Skipped")
                    return False
                elif response != "y":
                    print(f"  Invalid input, skipping")
                    return False

            # Backup the original value
            create_backup(app_id, current_value)

        # Set the new LaunchOptions
        app_section["LaunchOptions"] = new_launch_options

        # Write back to file
        vdf_output = write_vdf(localconfig_data)
        with open(localconfig_path, "w") as f:
            f.write(vdf_output)

        print(f"✓ Modified game {app_id}: LaunchOptions set to '{new_launch_options}'")
        return True

    except Exception as e:
        print(f"Error modifying LaunchOptions for {app_id}: {e}", file=sys.stderr)
        return False


def cmd_modify_launchoptions(game_id: str, config: dict) -> None:
    """Handle modify-launchoptions command for a single game."""
    if not game_id:
        print("Error: Game ID required for modify-launchoptions command", file=sys.stderr)
        sys.exit(1)

    steam_config = config.get("steam", {})
    steam_path = steam_config.get("steam_path", "~/.local/share/Steam")
    launch_options_template = steam_config.get("launch_options_template", "protonhax init %COMMAND%")

    localconfig_path = find_localconfig_vdf(steam_path)
    if not localconfig_path:
        print("Error: Could not find localconfig.vdf", file=sys.stderr)
        sys.exit(1)

    print(f"Found localconfig.vdf at: {localconfig_path}")

    if modify_launch_options(game_id, launch_options_template, localconfig_path, ask_if_exists=True):
        print(f"\n✓ Successfully modified LaunchOptions for game {game_id}")
    else:
        print(f"\n✗ Failed to modify LaunchOptions for game {game_id}")
        sys.exit(1)


def cmd_modify_all_launchoptions(config: dict) -> None:
    """Handle modify-all-launchoptions command for all installed games."""
    steam_config = config.get("steam", {})
    steam_path = steam_config.get("steam_path", "~/.local/share/Steam")
    launch_options_template = steam_config.get("launch_options_template", "protonhax init %COMMAND%")

    localconfig_path = find_localconfig_vdf(steam_path)
    if not localconfig_path:
        print("Error: Could not find localconfig.vdf", file=sys.stderr)
        sys.exit(1)

    print(f"Found localconfig.vdf at: {localconfig_path}")

    # Get installed games
    installed_games = get_installed_games(steam_path)
    if not installed_games:
        print("Warning: No installed games found", file=sys.stderr)
        return

    print(f"\nFound {len(installed_games)} installed games")
    print(f"Launch options template: {launch_options_template}")
    print(f"\n⚠ WARNING: All existing LaunchOptions will be backed up before modification.")

    response = input(f"\nModify LaunchOptions for all {len(installed_games)} games? (y/n): ").strip().lower()
    if response != "y":
        print("Cancelled")
        return

    modified_count = 0
    skipped_count = 0

    for app_id in installed_games:
        if modify_launch_options(app_id, launch_options_template, localconfig_path, ask_if_exists=True):
            modified_count += 1
        else:
            skipped_count += 1

    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  Modified: {modified_count}")
    print(f"  Skipped:  {skipped_count}")
    print(f"  Total:    {len(installed_games)}")
    print(f"{'='*50}")


def remove_launch_options(
    app_id: str,
    localconfig_path: Path,
    ask_if_exists: bool = True
) -> bool:
    """
    Remove LaunchOptions for a specific game in localconfig.vdf.
    Returns True if removed, False otherwise.
    """
    try:
        with open(localconfig_path, "r") as f:
            content = f.read()

        localconfig_data = parse_vdf(content)

        # Navigate to the app section
        # Structure: Software -> Valve -> Steam -> apps -> <app_id>
        try:
            apps = (
                localconfig_data
                .get("Software", {})
                .get("Valve", {})
                .get("Steam", {})
                .get("apps", {})
            )

            if app_id not in apps:
                print(f"ℹ Game {app_id}: Not found in localconfig.vdf")
                return False

            app_section = apps[app_id]

            if not isinstance(app_section, dict):
                print(f"ℹ Game {app_id}: Invalid app section structure")
                return False

        except (KeyError, TypeError, AttributeError):
            print(f"Error: Could not navigate to app {app_id} in localconfig.vdf", file=sys.stderr)
            return False

        # Check if LaunchOptions exists
        if "LaunchOptions" not in app_section:
            print(f"ℹ Game {app_id}: No LaunchOptions to remove")
            return False

        current_value = app_section["LaunchOptions"]

        if ask_if_exists:
            print(f"\n⚠ Game {app_id}:")
            print(f"  Current value: {current_value}")
            response = input(f"  Remove LaunchOptions? (y/n/skip): ").strip().lower()

            if response == "skip" or response == "n":
                print(f"  Skipped")
                return False
            elif response != "y":
                print(f"  Invalid input, skipping")
                return False

        # Backup the value being removed
        create_backup(app_id, current_value)

        # Remove the LaunchOptions
        del app_section["LaunchOptions"]

        # Write back to file
        vdf_output = write_vdf(localconfig_data)
        with open(localconfig_path, "w") as f:
            f.write(vdf_output)

        print(f"✓ Removed game {app_id}: LaunchOptions deleted")
        return True

    except Exception as e:
        print(f"Error removing LaunchOptions for {app_id}: {e}", file=sys.stderr)
        return False


def cmd_remove_launchoptions(game_id: str, config: dict) -> None:
    """Handle remove-launchoptions command for a single game."""
    if not game_id:
        print("Error: Game ID required for remove-launchoptions command", file=sys.stderr)
        sys.exit(1)

    steam_config = config.get("steam", {})
    steam_path = steam_config.get("steam_path", "~/.local/share/Steam")

    localconfig_path = find_localconfig_vdf(steam_path)
    if not localconfig_path:
        print("Error: Could not find localconfig.vdf", file=sys.stderr)
        sys.exit(1)

    print(f"Found localconfig.vdf at: {localconfig_path}")

    if remove_launch_options(game_id, localconfig_path, ask_if_exists=True):
        print(f"\n✓ Successfully removed LaunchOptions for game {game_id}")
    else:
        print(f"\nℹ No action taken for game {game_id}")


def cmd_remove_all_launchoptions(config: dict) -> None:
    """Handle remove-all-launchoptions command for all games with LaunchOptions."""
    steam_config = config.get("steam", {})
    steam_path = steam_config.get("steam_path", "~/.local/share/Steam")

    localconfig_path = find_localconfig_vdf(steam_path)
    if not localconfig_path:
        print("Error: Could not find localconfig.vdf", file=sys.stderr)
        sys.exit(1)

    print(f"Found localconfig.vdf at: {localconfig_path}")

    # Parse the file to find games with LaunchOptions
    with open(localconfig_path, "r") as f:
        content = f.read()

    localconfig_data = parse_vdf(content)

    try:
        apps = (
            localconfig_data
            .get("Software", {})
            .get("Valve", {})
            .get("Steam", {})
            .get("apps", {})
        )

        games_with_options = []
        for app_id, app_data in apps.items():
            if isinstance(app_data, dict) and "LaunchOptions" in app_data:
                games_with_options.append(app_id)

    except (KeyError, TypeError, AttributeError):
        print("Error: Could not read app data from localconfig.vdf", file=sys.stderr)
        sys.exit(1)

    if not games_with_options:
        print("No games with LaunchOptions found")
        return

    print(f"\nFound {len(games_with_options)} games with LaunchOptions set")
    print(f"⚠ WARNING: All LaunchOptions will be backed up before removal.")

    response = input(f"\nRemove LaunchOptions for all {len(games_with_options)} games? (y/n): ").strip().lower()
    if response != "y":
        print("Cancelled")
        return

    removed_count = 0
    skipped_count = 0

    for app_id in sorted(games_with_options):
        if remove_launch_options(app_id, localconfig_path, ask_if_exists=True):
            removed_count += 1
        else:
            skipped_count += 1

    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  Removed: {removed_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Total:   {len(games_with_options)}")
    print(f"{'='*50}")


def get_config_path() -> Path:
    """
    Get the path to the config file that should be written.
    Prefers the current directory config if it exists, otherwise uses user config directory.
    """
    cwd_config = Path.cwd() / "ce-autostart-config.toml"
    if cwd_config.exists():
        return cwd_config

    user_config = Path.home() / ".config" / "ce-autostart" / "config.toml"
    return user_config


def validate_executable_path(path_str: str) -> bool:
    """
    Validate that the executable path exists and is readable.
    """
    try:
        exe_path = Path(path_str).expanduser()
        if not exe_path.exists():
            return False
        if not exe_path.is_file():
            return False
        return True
    except (OSError, ValueError):
        return False


def validate_steam_path(path_str: str) -> bool:
    """
    Validate that the Steam path exists and is readable.
    """
    try:
        steam_path = Path(path_str).expanduser()
        if not steam_path.exists():
            return False
        if not steam_path.is_dir():
            return False
        return True
    except (OSError, ValueError):
        return False


def display_interactive_menu(config: dict) -> None:
    """
    Display an interactive menu to browse and modify Steam games.
    Uses arrow keys to navigate and Enter to select.
    """
    steam_config = config.get("steam", {})
    steam_path = steam_config.get("steam_path", "~/.local/share/Steam")
    launch_options_template = steam_config.get("launch_options_template", "protonhax init %COMMAND%")

    # Get installed games
#    steamapps_path = Path(steam_path).expanduser().parent / "steamapps"
    steamapps_path = Path(steam_path).expanduser() / "steamapps"
    installed_games = get_installed_games(str(steamapps_path))

    if not installed_games:
        print("No installed games found", file=sys.stderr)
        return

    # Prepare game data with status
    games_data = []
    for app_id in installed_games:
        game_info = get_game_info(app_id, str(steamapps_path))
        status = get_launchoption_status(app_id, steam_path)
        games_data.append({
            "app_id": app_id,
            "name": game_info["name"],
            "status": status
        })

    # Create console for output
    console = Console()

    # Create the interactive table
    current_selection = 0

    while True:
        console.clear()

        # Create table
        table = Table(title="Steam Games", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Game Name", style="green")
        table.add_column("LaunchOption Status", style="yellow")

        # Add rows with highlighting for selected row
        for idx, game in enumerate(games_data):
            if idx == current_selection:
                # Highlight selected row
                id_text = Text(game["app_id"], style="bold white on blue")
                name_text = Text(game["name"], style="bold white on blue")
                status_text = Text(game["status"], style="bold white on blue")
            else:
                id_text = Text(game["app_id"])
                name_text = Text(game["name"])
                status_text = Text(game["status"])

            table.add_row(id_text, name_text, status_text)

        console.print(table)
        console.print("\n[cyan]Navigation:[/cyan] Use [bold]↑[/bold]/[bold]↓[/bold] to move, [bold]Enter[/bold] to select, [bold]Q[/bold]/[bold]Esc[/bold] to quit")

        # Get keyboard input
        try:
            key = get_key()

            if key == "up":
                current_selection = max(0, current_selection - 1)
            elif key == "down":
                current_selection = min(len(games_data) - 1, current_selection + 1)
            elif key == "enter":
                selected_game = games_data[current_selection]
                handle_game_selection(selected_game, config, steam_path, launch_options_template)
                current_selection = 0  # Reset selection after action
            elif key in ["q", "esc"]:
                console.print("[yellow]Exiting menu...[/yellow]")
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]Menu cancelled[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            break


def get_key() -> str:
    """
    Get keyboard input from user.
    Returns: 'up', 'down', 'enter', 'q', 'esc', or the character
    """
    import sys
    import tty
    import termios

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        if ch == '\x1b':  # Escape sequence
            next_chars = sys.stdin.read(2)
            if next_chars == '[A':
                return 'up'
            elif next_chars == '[B':
                return 'down'
            elif next_chars == '[':
                # Handle other escape sequences
                ch2 = sys.stdin.read(1)
                if ch2 == 'Z':  # Shift+Tab
                    return 'up'
                return 'unknown'
            return 'esc'
        elif ch == '\r' or ch == '\n':
            return 'enter'
        elif ch.lower() == 'q':
            return 'q'
        else:
            return ch.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def handle_game_selection(game: dict, config: dict, steam_path: str, launch_options_template: str) -> None:
    """
    Handle the menu options for a selected game.
    """
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()

    while True:
        console.clear()
        console.print(f"\n[bold blue]Selected Game:[/bold blue] {game['name']} (ID: {game['app_id']})")
        console.print(f"[yellow]LaunchOption Status: {game['status']}[/yellow]\n")

        console.print("[cyan]Options:[/cyan]")
        console.print("[bold]M[/bold] - Modify LaunchOptions")
        console.print("[bold]V[/bold] - View Current LaunchOptions")
        console.print("[bold]R[/bold] - Remove LaunchOptions")
        console.print("[bold]C[/bold] - Cancel (back to menu)\n")

        choice = Prompt.ask("[cyan]Choose option[/cyan]", choices=["m", "v", "r", "c"], show_default=False).lower()

        if choice == "m":
            localconfig_path = find_localconfig_vdf(steam_path)
            if localconfig_path:
                modify_launch_options(game["app_id"], launch_options_template, localconfig_path, ask_if_exists=True)
                game["status"] = get_launchoption_status(game["app_id"], steam_path)
                console.print("\n[green]LaunchOptions updated.[/green]")
                input("Press Enter to continue...")
            else:
                console.print("[red]Error: Could not find localconfig.vdf[/red]")
                input("Press Enter to continue...")
        elif choice == "v":
            localconfig_path = find_localconfig_vdf(steam_path)
            if localconfig_path:
                try:
                    with open(localconfig_path, "r") as f:
                        content = f.read()
                    localconfig_data = parse_vdf(content)

                    apps = (
                        localconfig_data
                        .get("Software", {})
                        .get("Valve", {})
                        .get("Steam", {})
                        .get("apps", {})
                    )

                    if game["app_id"] in apps and "LaunchOptions" in apps[game["app_id"]]:
                        launch_options = apps[game["app_id"]]["LaunchOptions"]
                        console.print(f"\n[green]Current LaunchOptions:[/green]\n{launch_options}")
                    else:
                        console.print("\n[yellow]No LaunchOptions configured for this game[/yellow]")

                    input("\nPress Enter to continue...")
                except Exception as e:
                    console.print(f"[red]Error reading LaunchOptions: {e}[/red]")
                    input("Press Enter to continue...")
            else:
                console.print("[red]Error: Could not find localconfig.vdf[/red]")
                input("Press Enter to continue...")
        elif choice == "r":
            localconfig_path = find_localconfig_vdf(steam_path)
            if localconfig_path:
                remove_launch_options(game["app_id"], localconfig_path, ask_if_exists=True)
                game["status"] = get_launchoption_status(game["app_id"], steam_path)
                console.print("\n[green]LaunchOptions removed if they existed.[/green]")
                input("Press Enter to continue...")
            else:
                console.print("[red]Error: Could not find localconfig.vdf[/red]")
                input("Press Enter to continue...")
        elif choice == "c":
            console.print("[cyan]Returning to game list...[/cyan]")
            break


def validate_protonhax_installed() -> str:
    """
    Validate that protonhax is installed by executing 'which protonhax'.
    Returns the path if found, otherwise exits with error.
    """
    try:
        result = subprocess.run(
            ["which", "protonhax"],
            capture_output=True,
            text=True,
            check=True,
        )
        path = result.stdout.strip()

        # Verify it's the expected path
        if path == "/usr/bin/protonhax":
            return path
        else:
            # Allow other paths but warn the user
            print(f"⚠ Warning: protonhax found at {path}, expected /usr/bin/protonhax", file=sys.stderr)
            return path

    except subprocess.CalledProcessError:
        print("Error: 'protonhax' command not found in PATH", file=sys.stderr)
        print("\nPlease install protonhax from: https://github.com/mikeslattery/protonhax", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'which' command not found", file=sys.stderr)
        print("\nPlease ensure protonhax is installed from: https://github.com/mikeslattery/protonhax", file=sys.stderr)
        sys.exit(1)


def cmd_init() -> None:
    """Handle init command for guided configuration setup."""
    print("=" * 60)
    print("CheatEngine Auto-Start Configuration Setup")
    print("=" * 60)

    # Validate protonhax is installed
    print("\nValidating protonhax installation...")
    protonhax_path = validate_protonhax_installed()
    print(f"✓ Found protonhax at: {protonhax_path}")

    # Determine config file location
    config_path = get_config_path()
    print(f"\nConfig file will be saved to: {config_path}")

    # Try to load existing config for defaults
    existing_config = {}
    try:
        with open(config_path, "rb") as f:
            existing_config = tomllib.load(f)
    except (FileNotFoundError, OSError):
        pass

    # Initialize new config structure
    config = {
        "cheatengine": existing_config.get("cheatengine", {}),
        "steam": existing_config.get("steam", {}),
    }

    # Get CheatEngine executable path
    print("\n" + "-" * 60)
    print("CheatEngine Configuration")
    print("-" * 60)

    default_ce_path = config["cheatengine"].get("executable_path", "~/Games/CheatEngine/cheatengine-x86_64.exe")
    print(f"\nEnter the path to the CheatEngine executable.")
    print(f"Default: {default_ce_path}")

    while True:
        user_input = input("CheatEngine executable path [press Enter for default]: ").strip()

        if not user_input:
            ce_path = default_ce_path
        else:
            ce_path = user_input

        if validate_executable_path(ce_path):
            config["cheatengine"]["executable_path"] = ce_path
            print(f"✓ Valid path: {ce_path}")
            break
        else:
            print(f"✗ Error: Could not find file at {ce_path}")
            print("  Please try again or use the full path with ~ for home directory")

    # Get Steam path
    print("\n" + "-" * 60)
    print("Steam Configuration")
    print("-" * 60)

    default_steam_path = config["steam"].get("steam_path", "~/.local/share/Steam")
    print(f"\nEnter the path to your Steam installation directory.")
    print(f"Default: {default_steam_path}")
    print(f"(This is typically ~/.local/share/Steam on Linux)")

    while True:
        user_input = input("Steam path [press Enter for default]: ").strip()

        if not user_input:
            steam_path = default_steam_path
        else:
            steam_path = user_input

        if validate_steam_path(steam_path):
            config["steam"]["steam_path"] = steam_path
            print(f"✓ Valid path: {steam_path}")
            break
        else:
            print(f"✗ Error: Could not find directory at {steam_path}")
            print("  Please try again or use the full path with ~ for home directory")

    # Get lookup_enabled preference
    print("\n" + "-" * 60)
    print("Steam API Lookup")
    print("-" * 60)

    default_lookup = config["steam"].get("lookup_enabled", True)
    print(f"\nEnable Steam API game title lookup?")
    print(f"This will cache the Steam app list locally and look up game names.")
    print(f"Cache is updated weekly.")

    while True:
        response = input(f"Enable lookup? (y/n) [default: {'y' if default_lookup else 'n'}]: ").strip().lower()

        if not response:
            lookup_enabled = default_lookup
        elif response in ['y', 'yes']:
            lookup_enabled = True
        elif response in ['n', 'no']:
            lookup_enabled = False
        else:
            print("Please answer 'y' or 'n'")
            continue

        config["steam"]["lookup_enabled"] = lookup_enabled
        status = "enabled" if lookup_enabled else "disabled"
        print(f"✓ Lookup {status}")
        break

    # Preserve launch_options_template if it exists
    if "launch_options_template" in existing_config.get("steam", {}):
        config["steam"]["launch_options_template"] = existing_config["steam"]["launch_options_template"]
    else:
        # Set default if not present
        config["steam"]["launch_options_template"] = "protonhax init %COMMAND%"

    # Write config file
    print("\n" + "-" * 60)
    print("Saving Configuration")
    print("-" * 60)

    try:
        # Create parent directories if needed
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)

        print(f"\n✓ Configuration saved to: {config_path}")
        print("\nSetup complete! You can now run:")
        print(f"  uv run ce-autostart.py")
        print(f"\nTo modify individual settings later, edit the config file:")
        print(f"  {config_path}")

    except (IOError, OSError) as e:
        print(f"\n✗ Error saving config file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_start(uid: str | None, config: dict) -> None:
    """Handle start command to launch CheatEngine."""
    if "cheatengine" not in config or "executable_path" not in config.get("cheatengine", {}):
        print("Error: Missing 'cheatengine.executable_path' in config file.", file=sys.stderr)
        sys.exit(1)

    executable_path = config["cheatengine"]["executable_path"]

    # Get running game uid if not provided
    if not uid:
        uid = get_running_game_uid()

    # Look up game title if enabled
    steam_config = config.get("steam", {})
    if steam_config.get("lookup_enabled", False):
        # Get Steam path from config, with default fallback
        steam_path = steam_config.get("steam_path", "~/.local/share/Steam/steamapps")
        print(f"Looking up game title...")
        game_title = lookup_game_title(uid, steam_path)
        if game_title:
            print(f"Found game: {game_title}")
        else:
            print(f"Could not find game title for uid {uid}")

    # Launch CheatEngine
    launch_cheatengine(uid, executable_path)


def main() -> None:
    """Main entry point."""
    # Parse command-line arguments
    if len(sys.argv) < 2:
        cmd = "start"
        arg = None
    else:
        cmd = sys.argv[1]
        arg = sys.argv[2] if len(sys.argv) > 2 else None

    # Handle init command separately (doesn't need config)
    if cmd == "init":
        cmd_init()
        return

    # Load config for all other commands
    config = load_config()

    if cmd == "start":
        cmd_start(arg, config)
    elif cmd == "menu":
        display_interactive_menu(config)
    elif cmd == "modify-launchoptions":
        cmd_modify_launchoptions(arg, config)
    elif cmd == "modify-all-launchoptions":
        cmd_modify_all_launchoptions(config)
    elif cmd == "remove-launchoptions":
        cmd_remove_launchoptions(arg, config)
    elif cmd == "remove-all-launchoptions":
        cmd_remove_all_launchoptions(config)
    else:
        print(f"Error: Unknown command '{cmd}'", file=sys.stderr)
        print("\nUsage:", file=sys.stderr)
        print("  ce-autostart.py init                       - Interactive configuration setup", file=sys.stderr)
        print("  ce-autostart.py [start] [uid]              - Start CheatEngine for a game", file=sys.stderr)
        print("  ce-autostart.py menu                       - Interactive game browser and manager", file=sys.stderr)
        print("  ce-autostart.py modify-launchoptions <ID>  - Set LaunchOptions for a game", file=sys.stderr)
        print("  ce-autostart.py modify-all-launchoptions   - Set LaunchOptions for all games", file=sys.stderr)
        print("  ce-autostart.py remove-launchoptions <ID>  - Remove LaunchOptions from a game", file=sys.stderr)
        print("  ce-autostart.py remove-all-launchoptions   - Remove LaunchOptions from all games", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
