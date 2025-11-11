#!/usr/bin/env python3
"""
CheatEngine auto-start script for Steam games running on Proton.
Run with: uv run ce-autostart.py
"""

import subprocess
import sys
from pathlib import Path
import tomllib  # Python 3.11+
import json
import requests
from datetime import datetime, timedelta

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


def main() -> None:
    """Main entry point."""
    config = load_config()

    # Validate config
    if "cheatengine" not in config or "executable_path" not in config.get("cheatengine", {}):
        print("Error: Missing 'cheatengine.executable_path' in config file.", file=sys.stderr)
        sys.exit(1)

    executable_path = config["cheatengine"]["executable_path"]

    # Get running game uid
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


if __name__ == "__main__":
    main()
