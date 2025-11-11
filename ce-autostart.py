#!/usr/bin/env python3
"""
CheatEngine auto-start script for Steam games running on Proton.
Run with: uv run ce-autostart.py [command] [args]

Commands:
  start [game_uid]              - Start CheatEngine for a running game (default)
  modify-launchoptions <ID>     - Set LaunchOptions for a specific game
  modify-all-launchoptions      - Set LaunchOptions for all installed games
"""

import subprocess
import sys
from pathlib import Path
import tomllib  # Python 3.11+
import json
import requests
from datetime import datetime, timedelta
import re

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
    config = load_config()

    # Parse command-line arguments
    if len(sys.argv) < 2:
        cmd = "start"
        arg = None
    else:
        cmd = sys.argv[1]
        arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "start":
        cmd_start(arg, config)
    elif cmd == "modify-launchoptions":
        cmd_modify_launchoptions(arg, config)
    elif cmd == "modify-all-launchoptions":
        cmd_modify_all_launchoptions(config)
    else:
        print(f"Error: Unknown command '{cmd}'", file=sys.stderr)
        print("\nUsage:", file=sys.stderr)
        print("  ce-autostart.py [start] [uid]              - Start CheatEngine for a game", file=sys.stderr)
        print("  ce-autostart.py modify-launchoptions <ID>  - Set LaunchOptions for a game", file=sys.stderr)
        print("  ce-autostart.py modify-all-launchoptions   - Set LaunchOptions for all games", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
