"""Rich-based CLI interface for autopod.

This module provides the main command-line interface for managing RunPod pods,
including creation, monitoring, SSH access, and lifecycle management.
"""

import sys
import signal
import logging
from typing import Optional
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from autopod.config import (
    load_config,
    config_init_wizard,
    get_config_path,
)
from autopod.providers import RunPodProvider
from autopod.pod_manager import PodManager
from autopod.logging import setup_logging

console = Console()
logger = setup_logging()

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global shutdown_requested
    shutdown_requested = True
    console.print("\n[yellow]⚠️  Shutdown requested. Finishing current operation...[/yellow]")
    console.print("[dim]Press Ctrl+C again to force quit[/dim]")

    # Set up handler for second Ctrl+C
    signal.signal(signal.SIGINT, force_shutdown_handler)


def force_shutdown_handler(signum, frame):
    """Force shutdown on second Ctrl+C."""
    console.print("\n[red]✗ Force quit[/red]")
    sys.exit(1)


# Set up signal handler
signal.signal(signal.SIGINT, signal_handler)


def load_provider() -> RunPodProvider:
    """Load RunPod provider from config.

    Returns:
        Configured RunPodProvider instance

    Raises:
        SystemExit: If config not found or invalid
    """
    try:
        config = load_config()
        api_key = config["providers"]["runpod"]["api_key"]
        return RunPodProvider(api_key=api_key)
    except FileNotFoundError:
        console.print("[red]✗ Configuration not found[/red]")
        console.print(f"Run [cyan]autopod config init[/cyan] to set up autopod")
        sys.exit(1)
    except KeyError as e:
        console.print(f"[red]✗ Invalid configuration: missing {e}[/red]")
        console.print(f"Config file: {get_config_path()}")
        sys.exit(1)


def get_single_pod_id(manager: PodManager) -> Optional[str]:
    """Get pod ID when only one pod is running (for auto-select).

    Args:
        manager: PodManager instance

    Returns:
        Pod ID if exactly one pod exists, None otherwise
    """
    pods = manager.list_pods(show_table=False)

    if len(pods) == 0:
        console.print("[yellow]No pods found[/yellow]")
        return None
    elif len(pods) == 1:
        return pods[0]["pod_id"]
    else:
        console.print(f"[yellow]Multiple pods found ({len(pods)}). Please specify pod ID.[/yellow]")
        console.print("\nAvailable pods:")
        manager._print_pods_table(pods)
        return None


@click.group()
@click.version_option(version="1.0.0", prog_name="autopod")
def cli():
    """autopod - Lightweight CLI controller for RunPod instances.

    Manage RunPod pods, SSH access, and pod lifecycle with ease.

    \b
    Examples:
      autopod config init       Set up configuration
      autopod connect           Create pod with defaults
      autopod ls                List all pods
      autopod ssh               SSH into pod (auto-select)
      autopod kill <pod-id>     Terminate pod
    """
    pass


@cli.group()
def config():
    """Configuration management commands."""
    pass


@config.command("init")
def config_init():
    """Run interactive configuration wizard.

    Sets up RunPod API key, SSH key, and preferences.

    Example:
        autopod config init
    """
    console.print(Panel.fit(
        "[bold cyan]autopod Configuration Setup[/bold cyan]\n"
        "[dim]This wizard will guide you through initial setup[/dim]",
        border_style="cyan"
    ))

    try:
        config_init_wizard()
        console.print("\n[green]✓ Ready to use autopod![/green]")
        console.print("\nNext steps:")
        console.print("  [cyan]autopod connect[/cyan]           # Create a pod")
        console.print("  [cyan]autopod ls[/cyan]                # List pods")
        console.print("  [cyan]autopod --help[/cyan]            # See all commands")
    except KeyboardInterrupt:
        console.print("\n[yellow]Configuration cancelled[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ Configuration failed: {e}[/red]")
        logger.exception("Config init failed")
        sys.exit(1)


@cli.command()
@click.option("--gpu", type=str, help="GPU type (e.g., 'RTX A40', 'RTX A5000')")
@click.option("--gpu-count", type=int, default=1, help="Number of GPUs (default: 1)")
@click.option("--disk-size", type=int, default=50, help="Disk size in GB (default: 50)")
@click.option("--datacenter", type=str, help="Datacenter region (e.g., 'CA-MTL-1', 'US-GA-1')")
@click.option("--template", type=str, help="Docker template (overrides config default)")
@click.option("--cloud-type", type=click.Choice(["SECURE", "COMMUNITY", "ALL"], case_sensitive=False),
              help="Cloud type (default: SECURE)")
@click.option("--dry-run", is_flag=True, help="Show what would be created without creating")
@click.option("--interactive", is_flag=True, help="Interactive mode with prompts")
def connect(gpu, gpu_count, disk_size, datacenter, template, cloud_type, dry_run, interactive):
    """Create and connect to a new pod.

    By default, uses GPU preferences from config with smart fallback.

    Examples:
        autopod connect                      # Use config preferences
        autopod connect --gpu "RTX A40"      # Specific GPU
        autopod connect --dry-run            # Preview without creating
        autopod connect --interactive        # Interactive prompts
    """
    try:
        config = load_config()
        provider = load_provider()

        # Get configuration values
        runpod_config = config["providers"]["runpod"]
        defaults = config["defaults"]

        # Determine GPU type
        if interactive:
            console.print("[cyan]Interactive mode - answering questions...[/cyan]")
            # TODO: Implement interactive prompts for V1.1
            console.print("[yellow]Interactive mode not yet implemented, using defaults[/yellow]")

        # Use provided GPU or fall back to preferences
        if gpu:
            gpu_type = gpu
            fallback_enabled = False
        else:
            # Use first preference from config
            gpu_preferences = defaults.get("gpu_preferences", ["RTX A40", "RTX A6000", "RTX A5000"])
            gpu_type = gpu_preferences[0]
            fallback_enabled = True
            console.print(f"[dim]Using GPU preference: {gpu_type}[/dim]")

        # Determine datacenter (CLI flag > config > none)
        datacenter_value = datacenter or runpod_config.get("default_datacenter")

        # Build pod configuration
        pod_config = {
            "gpu_type": gpu_type,
            "gpu_count": gpu_count,
            "disk_size_gb": disk_size,
            "template": template or runpod_config.get("default_template", "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04"),
            "cloud_type": (cloud_type or runpod_config.get("cloud_type", "SECURE")).upper(),
        }

        # Add datacenter if specified (use RunPod API parameter name)
        if datacenter_value:
            pod_config["data_center_id"] = datacenter_value

        # Show configuration
        console.print("\n[bold cyan]Pod Configuration:[/bold cyan]")
        console.print(f"  GPU:        {pod_config['gpu_count']}x {pod_config['gpu_type']}")
        console.print(f"  Disk:       {pod_config['disk_size_gb']} GB")
        console.print(f"  Template:   {pod_config['template']}")
        console.print(f"  Cloud:      {pod_config['cloud_type']}")
        if datacenter_value:
            console.print(f"  Datacenter: {datacenter_value}")

        if dry_run:
            console.print("\n[yellow]DRY RUN - No pod will be created[/yellow]")

            # Check availability
            console.print("\n[cyan]Checking GPU availability...[/cyan]")
            try:
                availability = provider.get_gpu_availability(gpu_type)
                if availability.get("available"):
                    count = availability.get("available_count", "unknown")
                    cost = availability.get("min_cost_per_hour", "unknown")
                    console.print(f"[green]✓ {gpu_type} available ({count} units, ${cost}/hr)[/green]")
                else:
                    console.print(f"[yellow]✗ {gpu_type} not currently available[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Could not check availability: {e}[/yellow]")

            return

        # Create pod with progress
        console.print("\n[cyan]Creating pod...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Checking GPU availability...", total=None)

            # Try to create pod (with fallback if enabled)
            try:
                pod_id = provider.create_pod(pod_config)
                progress.update(task, description="[green]✓ Pod created!")
            except Exception as e:
                if fallback_enabled and "not available" in str(e).lower():
                    # Try fallback GPUs
                    progress.update(task, description=f"[yellow]{gpu_type} unavailable, trying fallback...[/yellow]")

                    gpu_preferences = defaults.get("gpu_preferences", ["RTX A40", "RTX A6000", "RTX A5000"])
                    for fallback_gpu in gpu_preferences[1:]:  # Skip first (already tried)
                        try:
                            console.print(f"[dim]Trying fallback: {fallback_gpu}[/dim]")
                            pod_config["gpu_type"] = fallback_gpu
                            pod_id = provider.create_pod(pod_config)
                            progress.update(task, description=f"[green]✓ Pod created with {fallback_gpu}!")
                            break
                        except Exception:
                            continue
                    else:
                        raise RuntimeError(f"No GPUs available from preferences: {gpu_preferences}")
                else:
                    raise

        console.print(f"\n[green]✓ Pod created successfully: {pod_id}[/green]")

        # Show next steps
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"  [cyan]autopod info {pod_id}[/cyan]      # View pod details")
        console.print(f"  [cyan]autopod ssh {pod_id}[/cyan]       # SSH into pod")
        console.print(f"  [cyan]autopod kill {pod_id}[/cyan]      # Terminate pod")

    except KeyboardInterrupt:
        console.print("\n[yellow]✗ Pod creation cancelled[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ Failed to create pod: {e}[/red]")
        logger.exception("Pod creation failed")
        sys.exit(1)


@cli.command()
@click.option("--all", "show_all", is_flag=True, help="Show all pods (including non-autopod)")
def list(show_all):
    """List all pods.

    Aliases: ls, ps

    Examples:
        autopod list                 # List all autopod-managed pods
        autopod ls                   # Short alias
        autopod list --all           # Show all pods (future)
    """
    try:
        provider = load_provider()
        manager = PodManager(provider, console)

        pods = manager.list_pods(show_table=True)

        if pods:
            console.print(f"\n[dim]Total: {len(pods)} pod(s)[/dim]")

    except Exception as e:
        console.print(f"[red]✗ Failed to list pods: {e}[/red]")
        logger.exception("List pods failed")
        sys.exit(1)


# Add aliases
@cli.command("ls")
@click.option("--all", "show_all", is_flag=True, help="Show all pods")
def ls_alias(show_all):
    """Alias for 'list' command."""
    from click.testing import CliRunner
    runner = CliRunner()
    runner.invoke(list, ["--all"] if show_all else [])


@cli.command("ps")
def ps_alias():
    """Alias for 'list' command (Docker-like)."""
    from click.testing import CliRunner
    runner = CliRunner()
    runner.invoke(list)


@cli.command()
@click.argument("pod_id", required=False)
def info(pod_id):
    """Show detailed information about a pod.

    If pod_id is not provided and only one pod exists, it will be auto-selected.

    Examples:
        autopod info abc-123         # Show info for specific pod
        autopod info                 # Auto-select if only one pod
    """
    try:
        provider = load_provider()
        manager = PodManager(provider, console)

        # Auto-select if no pod_id provided
        if not pod_id:
            pod_id = get_single_pod_id(manager)
            if not pod_id:
                sys.exit(1)
            console.print(f"[dim]Auto-selected pod: {pod_id}[/dim]\n")

        manager.get_pod_info(pod_id, show_panel=True)

    except Exception as e:
        console.print(f"[red]✗ Failed to get pod info: {e}[/red]")
        logger.exception("Get pod info failed")
        sys.exit(1)


@cli.command()
@click.argument("pod_id", required=False)
@click.option("--command", "-c", type=str, help="Execute command instead of interactive shell")
def ssh(pod_id, command):
    """Open SSH shell to a pod.

    If pod_id is not provided and only one pod exists, it will be auto-selected.

    Aliases: shell

    Examples:
        autopod ssh abc-123                  # Interactive shell
        autopod ssh                          # Auto-select if only one pod
        autopod ssh abc-123 -c "nvidia-smi"  # Execute command
    """
    try:
        provider = load_provider()
        manager = PodManager(provider, console)
        config = load_config()
        ssh_key_path = config["providers"]["runpod"]["ssh_key_path"]

        # Auto-select if no pod_id provided
        if not pod_id:
            pod_id = get_single_pod_id(manager)
            if not pod_id:
                sys.exit(1)
            console.print(f"[dim]Auto-selected pod: {pod_id}[/dim]\n")

        if command:
            # Execute command via SSH
            console.print(f"[cyan]Executing command on {pod_id}...[/cyan]")
            console.print(f"[dim]Command: {command}[/dim]\n")

            # Check if SSH key is available in ssh-agent (for passphrase-protected keys)
            import subprocess
            from pathlib import Path

            # Check if key has passphrase by attempting to read it
            key_has_passphrase = False
            try:
                result = subprocess.run(
                    ["ssh-keygen", "-y", "-P", "", "-f", ssh_key_path],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                key_has_passphrase = result.returncode != 0
            except Exception:
                # If we can't determine, assume it might have one
                key_has_passphrase = True

            # If key has passphrase, check if it's in ssh-agent
            if key_has_passphrase:
                try:
                    result = subprocess.run(
                        ["ssh-add", "-l"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )

                    # Get the public key fingerprint to check if this specific key is loaded
                    key_loaded = False
                    if result.returncode == 0:
                        # Try to get the fingerprint of our key
                        fingerprint_result = subprocess.run(
                            ["ssh-keygen", "-lf", ssh_key_path],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if fingerprint_result.returncode == 0:
                            our_fingerprint = fingerprint_result.stdout.split()[1]
                            key_loaded = our_fingerprint in result.stdout

                    if not key_loaded:
                        console.print("[yellow]⚠ SSH key has passphrase but isn't loaded in ssh-agent[/yellow]")
                        console.print("[dim]To avoid passphrase prompts with '-c' flag, add your key:[/dim]")
                        console.print(f"[dim]  ssh-add {ssh_key_path}[/dim]\n")

                except Exception:
                    # If we can't check, just continue (user will see auth errors if it fails)
                    pass

            # Get SSH connection string
            conn_str = provider.get_ssh_connection_string(pod_id)
            from autopod.ssh import parse_ssh_connection_string
            ssh_info = parse_ssh_connection_string(conn_str)

            # Build SSH command
            cmd = ["ssh"]
            # Disable PTY allocation for command execution (RunPod proxy doesn't support it)
            cmd.append("-T")
            if ssh_info["port"] is not None:
                cmd.extend(["-p", str(ssh_info["port"])])
            cmd.extend([
                "-i", ssh_key_path,
                "-o", "StrictHostKeyChecking=accept-new",
                f"{ssh_info['user']}@{ssh_info['host']}",
                command
            ])

            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        else:
            # Interactive shell
            exit_code = manager.shell_into_pod(pod_id, ssh_key_path)
            sys.exit(exit_code)

    except Exception as e:
        console.print(f"[red]✗ SSH failed: {e}[/red]")
        logger.exception("SSH failed")
        sys.exit(1)


@cli.command("shell")
@click.argument("pod_id", required=False)
@click.option("--command", "-c", type=str, help="Execute command instead of interactive shell")
def shell_alias(pod_id, command):
    """Alias for 'ssh' command."""
    from click.testing import CliRunner
    runner = CliRunner()
    args = []
    if pod_id:
        args.append(pod_id)
    if command:
        args.extend(["--command", command])
    runner.invoke(ssh, args)


@cli.command()
@click.argument("pod_id", required=False)
def stop(pod_id):
    """Stop (pause) a pod.

    Stopped pods do not incur compute charges but retain disk state.

    Examples:
        autopod stop abc-123         # Stop specific pod
        autopod stop                 # Auto-select if only one pod
    """
    try:
        provider = load_provider()
        manager = PodManager(provider, console)

        # Auto-select if no pod_id provided
        if not pod_id:
            pod_id = get_single_pod_id(manager)
            if not pod_id:
                sys.exit(1)
            console.print(f"[dim]Auto-selected pod: {pod_id}[/dim]\n")

        success = manager.stop_pod(pod_id)
        sys.exit(0 if success else 1)

    except Exception as e:
        console.print(f"[red]✗ Stop failed: {e}[/red]")
        logger.exception("Stop pod failed")
        sys.exit(1)


@cli.command()
@click.argument("pod_id", required=False)
def start(pod_id):
    """Start (resume) a stopped pod.

    Resumes a previously stopped pod. GPU availability is not guaranteed -
    the pod may restart with a different GPU or as CPU-only.

    Aliases: resume

    Examples:
        autopod start abc-123        # Start specific pod
        autopod start                # Auto-select if only one pod
    """
    try:
        provider = load_provider()
        manager = PodManager(provider, console)

        # Auto-select if no pod_id provided
        if not pod_id:
            pod_id = get_single_pod_id(manager)
            if not pod_id:
                sys.exit(1)
            console.print(f"[dim]Auto-selected pod: {pod_id}[/dim]\n")

        success = manager.start_pod(pod_id)

        # Show pod info after starting to verify GPU type
        if success:
            console.print("\n[cyan]Checking pod status...[/cyan]")
            import time
            time.sleep(3)  # Brief pause for pod to initialize
            manager.get_pod_info(pod_id, show_panel=True)

        sys.exit(0 if success else 1)

    except Exception as e:
        console.print(f"[red]✗ Start failed: {e}[/red]")
        logger.exception("Start pod failed")
        sys.exit(1)


@cli.command("resume")
@click.argument("pod_id", required=False)
def resume_alias(pod_id):
    """Alias for 'start' command."""
    from click.testing import CliRunner
    runner = CliRunner()
    args = []
    if pod_id:
        args.append(pod_id)
    runner.invoke(start, args)


@cli.command()
@click.argument("pod_id", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def kill(pod_id, yes):
    """Terminate (destroy) a pod permanently.

    WARNING: This is destructive and cannot be undone.

    Aliases: terminate, rm

    Examples:
        autopod kill abc-123         # Terminate with confirmation
        autopod kill abc-123 -y      # Skip confirmation
        autopod kill                 # Auto-select if only one pod
    """
    try:
        provider = load_provider()
        manager = PodManager(provider, console)

        # Auto-select if no pod_id provided
        if not pod_id:
            pod_id = get_single_pod_id(manager)
            if not pod_id:
                sys.exit(1)
            console.print(f"[dim]Auto-selected pod: {pod_id}[/dim]\n")

        success = manager.terminate_pod(pod_id, confirm=yes)
        sys.exit(0 if success else 1)

    except Exception as e:
        console.print(f"[red]✗ Terminate failed: {e}[/red]")
        logger.exception("Terminate pod failed")
        sys.exit(1)


@cli.command("terminate")
@click.argument("pod_id", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def terminate_alias(pod_id, yes):
    """Alias for 'kill' command."""
    from click.testing import CliRunner
    runner = CliRunner()
    args = []
    if pod_id:
        args.append(pod_id)
    if yes:
        args.append("--yes")
    runner.invoke(kill, args)


@cli.command("rm")
@click.argument("pod_id", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def rm_alias(pod_id, yes):
    """Alias for 'kill' command (Docker-like)."""
    from click.testing import CliRunner
    runner = CliRunner()
    args = []
    if pod_id:
        args.append(pod_id)
    if yes:
        args.append("--yes")
    runner.invoke(kill, args)


def main():
    """Main entry point for autopod CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]✗ Cancelled[/yellow]")
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        console.print(f"\n[red]✗ Unexpected error: {e}[/red]")
        logger.exception("Unexpected error in CLI")
        sys.exit(1)


if __name__ == "__main__":
    main()
