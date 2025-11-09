"""Configuration management for autopod.

This module handles loading, saving, and validating autopod configuration,
including API keys, SSH keys, and default preferences.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, List
from rich.console import Console
from rich.prompt import Prompt, Confirm

console = Console()


def get_config_dir() -> Path:
    """Get the autopod configuration directory path.

    Returns:
        Path to ~/.autopod directory
    """
    return Path.home() / ".autopod"


def get_config_path() -> Path:
    """Get the autopod configuration file path.

    Returns:
        Path to ~/.autopod/config.json
    """
    return get_config_dir() / "config.json"


def ensure_config_dir() -> None:
    """Create configuration directory if it doesn't exist."""
    config_dir = get_config_dir()
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]Created config directory: {config_dir}[/green]")


def get_default_config() -> Dict:
    """Get default configuration template.

    Returns:
        Dictionary with default configuration values
    """
    return {
        "providers": {
            "runpod": {
                "api_key": "",
                "ssh_key_path": "",
                "default_template": "runpod/comfyui:latest",
                "default_region": "NA-US",
                "cloud_type": "secure"
            }
        },
        "defaults": {
            "gpu_preferences": ["RTX A40", "RTX A6000", "RTX A5000"],
            "gpu_count": 1
        }
    }


def load_config() -> Dict:
    """Load configuration from ~/.autopod/config.json.

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is malformed
    """
    config_path = get_config_path()

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}. "
            "Run 'autopod config init' to create it."
        )

    with open(config_path, 'r') as f:
        config = json.load(f)

    return config


def save_config(config: Dict) -> None:
    """Save configuration to ~/.autopod/config.json with chmod 600.

    Args:
        config: Configuration dictionary to save
    """
    ensure_config_dir()
    config_path = get_config_path()

    # Write config file
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    # Set permissions to 600 (owner read/write only)
    os.chmod(config_path, 0o600)

    console.print(f"[green]Configuration saved to {config_path}[/green]")


def validate_config(config: Dict) -> bool:
    """Validate configuration structure and required fields.

    Args:
        config: Configuration dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    # Check top-level keys
    if "providers" not in config or "defaults" not in config:
        console.print("[red]Invalid config: missing 'providers' or 'defaults'[/red]")
        return False

    # Check RunPod provider config
    if "runpod" not in config["providers"]:
        console.print("[red]Invalid config: missing 'runpod' provider[/red]")
        return False

    runpod_config = config["providers"]["runpod"]
    required_fields = ["api_key", "ssh_key_path", "default_template"]

    for field in required_fields:
        if field not in runpod_config:
            console.print(f"[red]Invalid config: missing '{field}' in runpod provider[/red]")
            return False

    # Check that API key is not empty
    if not runpod_config["api_key"]:
        console.print("[yellow]Warning: RunPod API key is empty[/yellow]")
        return False

    return True


def detect_ssh_keys() -> List[Path]:
    """Detect existing SSH keys in ~/.ssh directory.

    Returns:
        List of paths to SSH private keys found
    """
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        return []

    # Common SSH key names
    key_names = ["id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"]
    found_keys = []

    for key_name in key_names:
        key_path = ssh_dir / key_name
        if key_path.exists():
            found_keys.append(key_path)

    return found_keys


def prompt_ssh_key_setup() -> str:
    """Interactive prompt to set up SSH key.

    Returns:
        Path to SSH key as string
    """
    console.print("\n[bold cyan]SSH Key Setup[/bold cyan]")

    # Check for existing keys
    existing_keys = detect_ssh_keys()

    if existing_keys:
        console.print(f"[green]Found {len(existing_keys)} existing SSH key(s):[/green]")
        for i, key in enumerate(existing_keys, 1):
            console.print(f"  {i}. {key}")

        # Ask if user wants to use one of them
        use_existing = Confirm.ask("Use one of these keys?", default=True)

        if use_existing:
            if len(existing_keys) == 1:
                return str(existing_keys[0])
            else:
                choice = Prompt.ask(
                    "Which key?",
                    choices=[str(i) for i in range(1, len(existing_keys) + 1)],
                    default="1"
                )
                return str(existing_keys[int(choice) - 1])

    # No existing keys or user doesn't want to use them
    console.print("\n[yellow]No suitable SSH key found or selected.[/yellow]")
    console.print("You have two options:")
    console.print("  1. Generate a new SSH key pair")
    console.print("  2. Manually specify the path to an existing key")

    choice = Prompt.ask("Choose an option", choices=["1", "2"], default="1")

    if choice == "1":
        console.print("\n[cyan]To generate a new SSH key, run:[/cyan]")
        console.print("  ssh-keygen -t ed25519 -C 'your_email@example.com'")
        console.print("\n[cyan]Then add the public key to RunPod:[/cyan]")
        console.print("  https://www.runpod.io/console/user/settings")

        key_path = Prompt.ask(
            "\nEnter the path to the SSH private key",
            default=str(Path.home() / ".ssh" / "id_ed25519")
        )
        return key_path
    else:
        key_path = Prompt.ask("Enter the path to your SSH private key")

        # Validate that the path exists
        if not Path(key_path).exists():
            console.print(f"[yellow]Warning: {key_path} does not exist yet[/yellow]")

        return key_path


def config_init_wizard() -> Dict:
    """Interactive configuration wizard for first-time setup.

    Returns:
        Complete configuration dictionary
    """
    console.print("\n[bold green]Welcome to autopod configuration![/bold green]\n")

    # Start with default config
    config = get_default_config()

    # Get RunPod API key
    console.print("[bold cyan]RunPod API Key[/bold cyan]")
    console.print("You can find your API key at: https://www.runpod.io/console/user/settings")
    api_key = Prompt.ask("Enter your RunPod API key", password=True)
    config["providers"]["runpod"]["api_key"] = api_key

    # Set up SSH key
    ssh_key_path = prompt_ssh_key_setup()
    config["providers"]["runpod"]["ssh_key_path"] = ssh_key_path

    # GPU preferences
    console.print("\n[bold cyan]GPU Preferences[/bold cyan]")
    console.print("Default GPU preference order: RTX A40 → RTX A6000 → RTX A5000")
    use_defaults = Confirm.ask("Use these defaults?", default=True)

    if not use_defaults:
        console.print("Enter GPU types in order of preference (comma-separated):")
        console.print("Example: RTX A40, RTX A6000, RTX 4090")
        gpu_prefs = Prompt.ask("GPU preferences")
        config["defaults"]["gpu_preferences"] = [
            gpu.strip() for gpu in gpu_prefs.split(",")
        ]

    # Save the configuration
    save_config(config)

    console.print("\n[bold green]✓ Configuration complete![/bold green]")
    console.print(f"Config saved to: {get_config_path()}")

    return config
