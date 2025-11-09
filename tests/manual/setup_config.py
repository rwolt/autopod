#!/usr/bin/env python3
"""Quick config setup script for manual testing.

This bypasses the interactive prompts for use in non-interactive environments.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from autopod.config import save_config, get_default_config

# Edit these values:
RUNPOD_API_KEY = "YOUR_API_KEY_HERE"  # Get from https://www.runpod.io/console/user/settings
SSH_KEY_PATH = str(Path.home() / ".ssh" / "id_ed25519")  # Or id_rsa, etc.

def setup():
    """Create config file with provided credentials."""
    config = get_default_config()

    # Set your credentials
    config["providers"]["runpod"]["api_key"] = RUNPOD_API_KEY
    config["providers"]["runpod"]["ssh_key_path"] = SSH_KEY_PATH

    # Save config
    save_config(config)

    print("✓ Config saved successfully!")
    print(f"  API Key: {RUNPOD_API_KEY[:10]}...")
    print(f"  SSH Key: {SSH_KEY_PATH}")

if __name__ == "__main__":
    if RUNPOD_API_KEY == "YOUR_API_KEY_HERE":
        print("Error: Please edit setup_config.py and set your RUNPOD_API_KEY")
        print("Get your API key from: https://www.runpod.io/console/user/settings")
        sys.exit(1)

    setup()
