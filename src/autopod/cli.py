"""Rich-based CLI interface for autopod.

This module provides the main command-line interface for managing RunPod pods,
including creation, monitoring, SSH access, and lifecycle management.
"""

import sys
import signal
import logging
import time
from typing import Optional
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.status import Status

from autopod.config import (
    load_config,
    config_init_wizard,
    get_config_path,
)
from autopod.providers import RunPodProvider
from autopod.pod_manager import PodManager
from autopod.logging import setup_logging
from autopod.tunnel import TunnelManager, SSHTunnel
from autopod.comfyui import ComfyUIClient

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
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging output")
@click.pass_context
def cli(ctx, verbose):
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
    # Store verbose flag in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose

    # If verbose flag set, enable verbose logging
    if verbose:
        import os
        os.environ['AUTOPOD_DEBUG'] = '1'
        # Reinitialize logger with verbose output
        from autopod.logging import setup_logging
        import logging
        setup_logging(console_level=logging.INFO)


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
@click.option("--volume-id", type=str, help="Network volume ID to attach")
@click.option("--volume-mount", type=str, default="/workspace", help="Volume mount path (default: /workspace)")
@click.option("--template", type=str, help="Docker template (overrides config default)")
@click.option("--cloud-type", type=click.Choice(["SECURE", "COMMUNITY", "ALL"], case_sensitive=False),
              help="Cloud type (default: SECURE)")
@click.option("--expose", "expose_ports", multiple=True, type=str, help="Expose port via HTTP proxy. Format: PORT or PORT:LABEL (e.g., 8080:filebrowser)")
@click.option("--expose-all", is_flag=True, help="Expose all ports defined in config for this template")
@click.option("--dry-run", is_flag=True, help="Show what would be created without creating")
@click.option("--interactive", is_flag=True, help="Interactive mode with prompts")
def connect(gpu, gpu_count, disk_size, datacenter, volume_id, volume_mount, template, cloud_type, expose_ports, expose_all, dry_run, interactive):
    """Create and connect to a new pod.

    By default, uses GPU preferences from config with smart fallback.

    Examples:
        autopod connect                           # Use config preferences
        autopod connect --gpu "RTX A40"           # Specific GPU
        autopod connect --expose-all              # Expose all template ports
        autopod connect --expose 8188 --expose 8080:filebrowser  # Expose specific ports
        autopod connect --dry-run                 # Preview without creating
        autopod connect --interactive             # Interactive prompts
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

        # Determine volume (CLI flag > config > none)
        volume_id_value = volume_id or runpod_config.get("default_volume_id")
        if volume_id_value:
            volume_mount_value = volume_mount  # CLI flag provides default /workspace
        else:
            volume_mount_value = None

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

        # Add volume if specified
        if volume_id_value:
            pod_config["volume_id"] = volume_id_value
            pod_config["volume_mount"] = volume_mount_value

        # Parse port exposure with optional labels
        # Format: "8188" or "8080:filebrowser"
        port_map = {}  # {port_number: label or None}

        # Get template name and port templates from config
        template_name = pod_config["template"]
        port_templates = config.get("port_templates", {})
        template_ports = port_templates.get(template_name, {})

        # Handle --expose-all flag
        if expose_all:
            if template_ports:
                # Add all ports from template config
                for port_str, label in template_ports.items():
                    port_map[int(port_str)] = label
                console.print(f"[dim]Exposing all ports for template '{template_name}': {', '.join(template_ports.keys())}[/dim]")
            else:
                console.print(f"[yellow]Warning: No ports defined for template '{template_name}' in config[/yellow]")
                console.print("[dim]Add to ~/.autopod/config.json 'port_templates' or use --expose PORT[/dim]")

        # Parse user-provided --expose flags (these override template defaults)
        for port_spec in (expose_ports or []):
            if ":" in port_spec:
                port_str, label = port_spec.split(":", 1)
                try:
                    port = int(port_str)
                    port_map[port] = label
                except ValueError:
                    console.print(f"[yellow]Warning: Invalid port number '{port_str}', skipping[/yellow]")
            else:
                try:
                    port = int(port_spec)
                    # Auto-label from template if available
                    auto_label = template_ports.get(str(port))
                    port_map[port] = auto_label
                except ValueError:
                    console.print(f"[yellow]Warning: Invalid port number '{port_spec}', skipping[/yellow]")

        # Build RunPod ports string and metadata
        if port_map:
            # Format for RunPod API: "8188/http,8080/http,8888/http"
            port_strings = [f"{port}/http" for port in sorted(port_map.keys())]
            pod_config["ports"] = ",".join(port_strings)
            # Store port labels in metadata for later retrieval
            pod_config["port_labels"] = {p: lbl for p, lbl in port_map.items() if lbl}

        # Show configuration
        console.print("\n[bold cyan]Pod Configuration:[/bold cyan]")
        console.print(f"  GPU:        {pod_config['gpu_count']}x {pod_config['gpu_type']}")
        console.print(f"  Disk:       {pod_config['disk_size_gb']} GB")
        console.print(f"  Template:   {pod_config['template']}")
        console.print(f"  Cloud:      {pod_config['cloud_type']}")
        if datacenter_value:
            console.print(f"  Datacenter: {datacenter_value}")
        if volume_id_value:
            console.print(f"  Volume:     {volume_id_value} → {volume_mount_value}")
        if port_map:
            console.print(f"  HTTP Ports: [yellow]{len(port_map)} port(s) exposed via HTTP proxy[/yellow]")
            for port in sorted(port_map.keys()):
                label = port_map[port]
                if label:
                    console.print(f"    • {port} ({label})")
                else:
                    console.print(f"    • {port}")

        # Show security warning if exposing HTTP
        if port_map:
            console.print("\n[bold yellow]⚠️  Security Warning:[/bold yellow]")
            console.print(f"[yellow]{len(port_map)} port(s) will be accessible via RunPod HTTP proxy.[/yellow]")
            console.print("[dim]• Anyone with the URL can access these services (no authentication)[/dim]")
            console.print("[dim]• URL format: https://[pod-id]-[port].proxy.runpod.net[/dim]")
            console.print("[dim]• Traffic is HTTPS encrypted but RunPod can inspect it[/dim]")
            console.print("[dim]• Recommended: Only expose ports you need, terminate pod when not in use[/dim]")
            console.print("[dim]• Read more: https://docs.runpod.io/pods/configuration/expose-ports[/dim]\n")

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

        # Show HTTP proxy URLs for all exposed ports with labels
        if port_map:
            console.print(f"\n[bold]🌐 HTTP Proxy Access:[/bold]")
            for port in sorted(port_map.keys()):
                http_url = f"https://{pod_id}-{port}.proxy.runpod.net"
                label = port_map[port]
                if label:
                    console.print(f"  {label}: [cyan]{http_url}[/cyan]")
                else:
                    console.print(f"  Port {port}: [cyan]{http_url}[/cyan]")
            console.print(f"  [dim](Services may take 30-60s to start)[/dim]")

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
    """Show comprehensive information about a pod.

    Displays pod status, HTTP proxy URLs with health checks, SSH access,
    and volume information. Works with any Docker template.

    If pod_id is not provided and only one pod exists, it will be auto-selected.

    Examples:
        autopod info abc-123         # Show info for specific pod
        autopod info                 # Auto-select if only one pod
    """
    try:
        config = load_config()
        provider = load_provider()
        manager = PodManager(provider, console)

        # Auto-select if no pod_id provided
        if not pod_id:
            pod_id = get_single_pod_id(manager)
            if not pod_id:
                sys.exit(1)
            console.print(f"[dim]Auto-selected pod: {pod_id}[/dim]\n")

        # Get pod status from provider
        status = provider.get_pod_status(pod_id)
        if not status:
            console.print(f"[red]✗ Pod {pod_id} not found[/red]")
            console.print("[dim]Run 'autopod ls' to see available pods.[/dim]")
            sys.exit(1)

        # Get raw pod data for port information
        import runpod
        pod_data = runpod.get_pod(pod_id)
        if not pod_data:
            console.print(f"[red]✗ Pod {pod_id} not found.[/red]")
            sys.exit(1)

        # Get metadata with port labels
        metadata = provider._load_pod_metadata(pod_id)
        port_labels = metadata.get("port_labels", {})

        # Build info display
        pod_status = status.get("status", "UNKNOWN")
        gpu_count = status.get("gpu_count", 0)
        gpu_type = status.get("gpu_type", "Unknown GPU")
        cost_per_hour = status.get("cost_per_hour", 0.0)
        runtime_minutes = status.get("runtime_minutes", 0.0)
        total_cost = status.get("total_cost", 0.0)

        # Format GPU display
        if gpu_count > 0:
            gpu_display = f"{gpu_count}x {gpu_type}"
        else:
            gpu_display = "N/A"

        # Basic pod information
        info_lines = [
            f"[bold]Status:[/bold]       {pod_status}",
            f"[bold]GPU:[/bold]          {gpu_display}",
            f"[bold]Cost/hour:[/bold]    ${cost_per_hour:.2f}",
            f"[bold]Runtime:[/bold]      {runtime_minutes:.1f} minutes",
            f"[bold]Total cost:[/bold]   ${total_cost:.4f}",
        ]

        # Get exposed ports from runtime
        exposed_ports = []
        runtime = pod_data.get("runtime", {})
        if runtime and "ports" in runtime:
            for p in runtime["ports"]:
                # HTTP proxy ports are indicated by type='http'
                if p.get("type") == "http":
                    port = p.get("privatePort")
                    if port:
                        exposed_ports.append(port)

        # Show HTTP proxy services with health checks
        if exposed_ports:
            info_lines.append("")
            info_lines.append("[bold]🌐 HTTP Proxy Services:[/bold]")

            for port in sorted(exposed_ports):
                url = f"https://{pod_id}-{port}.proxy.runpod.net"
                label = port_labels.get(str(port), f"Port {port}")

                # Add note for unknown RunPod-added ports
                if str(port) not in port_labels and port == 19123:
                    label = f"Port {port} [dim](RunPod Web Terminal - disabled by default)[/dim]"

                # Health check with timeout
                try:
                    import requests
                    response = requests.get(url, timeout=3)
                    if response.status_code < 400:
                        info_lines.append(f"  ✓ {label}: [cyan]{url}[/cyan] [dim](online)[/dim]")
                    else:
                        info_lines.append(f"  ✗ {label}: [cyan]{url}[/cyan] [yellow](error {response.status_code})[/yellow]")
                except requests.Timeout:
                    info_lines.append(f"  ⏳ {label}: [cyan]{url}[/cyan] [dim](timeout - may be starting)[/dim]")
                except requests.ConnectionError:
                    info_lines.append(f"  ⏳ {label}: [cyan]{url}[/cyan] [dim](not ready yet)[/dim]")
                except Exception as e:
                    info_lines.append(f"  ? {label}: [cyan]{url}[/cyan] [dim](check failed: {e})[/dim]")

        # Show volume info if available
        if status.get("volume_id"):
            volume_id = status.get("volume_id")
            volume_mount = status.get("volume_mount", "/workspace")
            info_lines.append("")
            info_lines.append(f"[bold]📁 Volume:[/bold]       {volume_id} → {volume_mount}")

        # Show ready-to-use SSH command
        if status.get("ssh_ready"):
            ssh_key = config["providers"]["runpod"]["ssh_key_path"]
            conn_string = provider.get_ssh_connection_string(pod_id)

            info_lines.append("")
            info_lines.append("[bold]🔑 SSH Access:[/bold]")
            info_lines.append(f"  [dim]# Quick access:[/dim] [cyan]autopod ssh {pod_id}[/cyan]")
            info_lines.append(f"  [dim]# Or paste this command:[/dim]")
            info_lines.append(f"  [cyan]ssh {conn_string} -i {ssh_key}[/cyan]")
        else:
            info_lines.append("")
            info_lines.append("[bold]SSH:[/bold]          Not ready")

        info_text = "\n".join(info_lines)

        # Color code panel based on status
        if pod_status == "RUNNING":
            border_style = "green"
        elif pod_status == "STOPPED":
            border_style = "yellow"
        elif pod_status == "TERMINATED":
            border_style = "red"
        else:
            border_style = "dim"

        panel = Panel(
            info_text,
            title=f"[bold]Pod Information: {pod_id}[/bold]",
            border_style=border_style,
        )

        console.print(panel)

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


# ============================================================================
# Tunnel Management Commands
# ============================================================================


@cli.group()
def tunnel():
    """Manage SSH tunnels to pods manually.

    Tunnels are no longer created automatically. Use 'tunnel start' to create
    a persistent tunnel and 'tunnel stop' to remove it.
    """
    pass


@tunnel.command("start")
@click.argument("pod_id")
@click.option("--local-port", type=int, default=8188, help="Local port to bind (default: 8188)")
@click.option("--remote-port", type=int, default=8188, help="Remote port to forward (default: 8188)")
@click.option("--ssh-key", type=str, help="Path to SSH private key")
def tunnel_start(pod_id, local_port, remote_port, ssh_key):
    """Start an SSH tunnel to a pod.

    Creates a persistent SSH tunnel that forwards a local port to a remote
    port on the pod. The tunnel continues running even after autopod exits.

    Example:
        autopod tunnel start pod-abc --local-port 8188 --remote-port 8188

    Then access ComfyUI at: http://localhost:8188
    """
    try:
        # Load config
        config = load_config()

        # Initialize provider and manager
        provider = RunPodProvider(
            api_key=config["providers"]["runpod"]["api_key"]
        )
        manager = PodManager(provider)

        console.print(f"\n[bold]Starting SSH tunnel for pod {pod_id}[/bold]")
        console.print(f"  Local port:  {local_port}")
        console.print(f"  Remote port: {remote_port}\n")

        # Get pod status to get SSH connection string
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Getting pod info...", total=None)

            pod = manager.get_pod_info(pod_id)

            if not pod:
                console.print(f"[red]✗ Pod {pod_id} not found[/red]")
                sys.exit(1)

            if not pod.get("ssh_ready"):
                console.print(f"[red]✗ Pod {pod_id} SSH is not ready[/red]")
                console.print("[dim]Wait for pod to finish starting, then try again[/dim]")
                sys.exit(1)

        # Get SSH connection string using provider method
        try:
            ssh_connection_string = provider.get_ssh_connection_string(pod_id)
        except RuntimeError as e:
            console.print(f"[red]✗ {e}[/red]")
            sys.exit(1)

        console.print(f"SSH connection: {ssh_connection_string}\n")

        # Use SSH key from config if not specified
        if not ssh_key:
            ssh_key = config["providers"]["runpod"].get("ssh_key_path")

        # Create tunnel
        tunnel_manager = TunnelManager()

        try:
            tunnel_obj = tunnel_manager.create_tunnel(
                pod_id=pod_id,
                ssh_connection_string=ssh_connection_string,
                local_port=local_port,
                remote_port=remote_port,
                ssh_key_path=ssh_key
            )
        except RuntimeError as e:
            console.print(f"[red]✗ {e}[/red]")
            sys.exit(1)

        # Start tunnel
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Establishing SSH tunnel...", total=None)

            if not tunnel_obj.start():
                console.print("[red]✗ Failed to start SSH tunnel[/red]")
                console.print("[dim]Check logs for details[/dim]")
                sys.exit(1)

        # Save state
        tunnel_manager._save_state()

        # Test connectivity
        console.print("\n[yellow]Testing tunnel connectivity...[/yellow]")

        time.sleep(1)  # Give tunnel a moment

        if tunnel_obj.test_connectivity(timeout=10):
            console.print("[green]✓ Tunnel is working![/green]")
        else:
            console.print("[yellow]⚠️  Tunnel started but connectivity test failed[/yellow]")
            console.print("[dim]The remote service might not be running yet[/dim]")

        # Show success message
        console.print(f"\n[green]✓ SSH tunnel started successfully[/green]")
        console.print(f"\n[bold]Access your service at:[/bold] http://localhost:{local_port}")
        console.print(f"[dim]Tunnel PID: {tunnel_obj.pid}[/dim]")
        console.print(f"\n[dim]The tunnel will persist even after you close this terminal.[/dim]")
        console.print(f"[dim]Use 'autopod tunnel stop {pod_id}' to stop the tunnel.[/dim]\n")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logger.exception("Failed to start tunnel")
        sys.exit(1)


@tunnel.command("stop")
@click.argument("pod_id")
def tunnel_stop(pod_id):
    """Stop an SSH tunnel.

    Terminates the SSH tunnel process for the specified pod.

    Example:
        autopod tunnel stop pod-abc
    """
    try:
        tunnel_manager = TunnelManager()
        tunnel_obj = tunnel_manager.get_tunnel(pod_id)

        if not tunnel_obj:
            console.print(f"[yellow]⚠️  No tunnel found for pod {pod_id}[/yellow]")
            sys.exit(1)

        if not tunnel_obj.is_active():
            console.print(f"[yellow]⚠️  Tunnel for pod {pod_id} is not running[/yellow]")
            tunnel_manager.remove_tunnel(pod_id)
            sys.exit(0)

        console.print(f"\n[bold]Stopping SSH tunnel for pod {pod_id}[/bold]")
        console.print(f"  PID: {tunnel_obj.pid}")
        console.print(f"  Port: {tunnel_obj.local_port}\n")

        if tunnel_obj.stop():
            tunnel_manager.remove_tunnel(pod_id)
            console.print("[green]✓ Tunnel stopped successfully[/green]\n")
        else:
            console.print("[red]✗ Failed to stop tunnel[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logger.exception("Failed to stop tunnel")
        sys.exit(1)


@tunnel.command("list")
def tunnel_list():
    """List all SSH tunnels.

    Shows active and stale tunnels with their status.

    Example:
        autopod tunnel list
    """
    try:
        tunnel_manager = TunnelManager()
        tunnels = tunnel_manager.list_tunnels()

        if not tunnels:
            console.print("\n[dim]No tunnels found[/dim]\n")
            return

        # Create table
        table = Table(title="SSH Tunnels", show_header=True, header_style="bold cyan")
        table.add_column("Pod ID", style="cyan")
        table.add_column("Local Port", justify="right")
        table.add_column("Remote Port", justify="right")
        table.add_column("Status")
        table.add_column("PID", justify="right")
        table.add_column("Connection")

        for tunnel_obj in tunnels:
            status = tunnel_obj.get_status()

            if status["active"]:
                status_str = "[green]●[/green] Active"
            else:
                status_str = "[red]●[/red] Dead"

            table.add_row(
                status["pod_id"],
                str(status["local_port"]),
                str(status["remote_port"]),
                status_str,
                str(status["pid"]) if status["pid"] else "-",
                status["ssh_connection"]
            )

        console.print()
        console.print(table)
        console.print()

        # Show cleanup suggestion if there are dead tunnels
        dead_count = sum(1 for t in tunnels if not t.is_active())
        if dead_count > 0:
            console.print(f"[dim]Tip: Run 'autopod tunnel cleanup' to remove {dead_count} dead tunnel(s)[/dim]\n")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logger.exception("Failed to list tunnels")
        sys.exit(1)


@tunnel.command("cleanup")
def tunnel_cleanup():
    """Clean up stale/dead tunnels.

    Removes tunnels for SSH processes that are no longer running.

    Example:
        autopod tunnel cleanup
    """
    try:
        console.print("\n[bold]Cleaning up stale tunnels...[/bold]\n")

        tunnel_manager = TunnelManager()
        count = tunnel_manager.cleanup_stale_tunnels()

        if count > 0:
            console.print(f"[green]✓ Removed {count} stale tunnel(s)[/green]\n")
        else:
            console.print("[dim]No stale tunnels found[/dim]\n")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logger.exception("Failed to cleanup tunnels")
        sys.exit(1)


@tunnel.command("stop-all")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def tunnel_stop_all(yes):
    """Stop all active tunnels.

    Terminates all SSH tunnel processes.

    Example:
        autopod tunnel stop-all --yes
    """
    try:
        tunnel_manager = TunnelManager()
        tunnels = tunnel_manager.list_tunnels()
        active_count = sum(1 for t in tunnels if t.is_active())

        if active_count == 0:
            console.print("\n[dim]No active tunnels to stop[/dim]\n")
            return

        # Confirm
        if not yes:
            console.print(f"\n[yellow]⚠️  This will stop {active_count} active tunnel(s)[/yellow]")
            confirm = click.confirm("Are you sure?", default=False)
            if not confirm:
                console.print("[dim]Cancelled[/dim]\n")
                return

        console.print(f"\n[bold]Stopping {active_count} tunnel(s)...[/bold]\n")

        stopped = tunnel_manager.stop_all_tunnels()

        console.print(f"[green]✓ Stopped {stopped} tunnel(s)[/green]\n")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        logger.exception("Failed to stop all tunnels")
        sys.exit(1)


# Removed ComfyUI-specific commands - use `autopod info` instead


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
