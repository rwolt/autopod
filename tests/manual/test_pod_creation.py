#!/usr/bin/env python3
"""Manual test script for RunPod provider with real API calls.

IMPORTANT: This script makes real API calls to RunPod and may incur costs.
Only run this when you're ready to test with your actual RunPod account.

Usage:
    python tests/manual/test_pod_creation.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm
from autopod.config import load_config
from autopod.providers import RunPodProvider
from autopod.logging import setup_logging

console = Console()
logger = setup_logging()


def run_authentication_test():
    """Test RunPod authentication."""
    console.print("\n[bold cyan]1. Testing Authentication[/bold cyan]")

    try:
        config = load_config()
        api_key = config["providers"]["runpod"]["api_key"]

        provider = RunPodProvider(api_key=api_key)

        if provider.authenticate(api_key):
            console.print("[green]✓ Authentication successful[/green]")
            return provider
        else:
            console.print("[red]✗ Authentication failed[/red]")
            return None

    except FileNotFoundError as e:
        console.print(f"[red]✗ Config not found: {e}[/red]")
        console.print("\n[yellow]Run 'python -c \"from autopod.config import config_init_wizard; config_init_wizard()\"' to set up your config[/yellow]")
        return None
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        return None


def run_gpu_availability_test(provider: RunPodProvider):
    """Test GPU availability checking."""
    console.print("\n[bold cyan]2. Testing GPU Availability[/bold cyan]")

    # GPU types to test
    gpu_types = ["RTX A40", "RTX A6000", "RTX A5000", "RTX 4090"]

    # Create table for results
    table = Table(title="GPU Availability & Pricing")
    table.add_column("GPU", style="cyan", no_wrap=True)
    table.add_column("VRAM", justify="right", style="blue")
    table.add_column("Secure", justify="right", style="green")
    table.add_column("Community", justify="right", style="yellow")
    table.add_column("Spot", justify="right", style="magenta")
    table.add_column("Max GPUs", justify="center", style="dim")

    for gpu_type in gpu_types:
        info = provider.get_gpu_availability(gpu_type)

        if info["available"]:
            vram = f"{info['memory_gb']} GB"
            secure = f"${info['secure_price']:.2f}/hr" if info['secure_cloud'] else "N/A"
            community = f"${info['community_price']:.2f}/hr" if info['community_cloud'] else "N/A"
            spot = f"${info['spot_price']:.2f}/hr" if info['spot_price'] > 0 else "N/A"
            max_gpus = str(info['max_gpu_count'])
        else:
            vram = "-"
            secure = "-"
            community = "-"
            spot = "-"
            max_gpus = "-"

        table.add_row(gpu_type, vram, secure, community, spot, max_gpus)

    console.print(table)


def run_pod_creation_test(provider: RunPodProvider, config: dict):
    """Test pod creation (with confirmation)."""
    console.print("\n[bold cyan]3. Test Pod Creation[/bold cyan]")

    # Get GPU preferences from config
    gpu_preferences = config["defaults"]["gpu_preferences"]

    console.print(f"\n[yellow]This will attempt to create a pod with GPU fallback:[/yellow]")
    for i, gpu in enumerate(gpu_preferences, 1):
        console.print(f"  {i}. {gpu}")

    # Check availability of each preferred GPU
    console.print("\n[dim]Checking availability...[/dim]")
    available_gpu = None

    for gpu_type in gpu_preferences:
        info = provider.get_gpu_availability(gpu_type)
        if info["available"]:
            available_gpu = info
            console.print(f"[green]✓ {gpu_type} available at ${info['cost_per_hour']:.2f}/hr[/green]")
            break
        else:
            console.print(f"[red]✗ {gpu_type} not available[/red]")

    if not available_gpu:
        console.print("[red]No preferred GPUs available. Skipping pod creation test.[/red]")
        return

    # Show cost estimate
    estimated_cost_per_minute = available_gpu['cost_per_hour'] / 60
    console.print(f"\n[bold yellow]Cost Estimate:[/bold yellow]")
    console.print(f"  ${available_gpu['cost_per_hour']:.2f}/hr = ${estimated_cost_per_minute:.4f}/min")
    console.print(f"  [dim]Minimum charge: ~$0.10 (pod creation + 1-2 minutes runtime)[/dim]")

    # Ask for confirmation
    if not Confirm.ask("\n[bold red]Create a test pod? This will incur costs.[/bold red]", default=False):
        console.print("[yellow]Pod creation test skipped[/yellow]")
        return

    # Create pod configuration
    pod_config = {
        "gpu_type": available_gpu["display_name"],
        "gpu_count": 1,
        "template": config["providers"]["runpod"]["default_template"],
        "region": config["providers"]["runpod"].get("default_region", "NA-US"),
        "cloud_type": config["providers"]["runpod"].get("cloud_type", "secure"),
    }

    console.print("\n[cyan]Creating pod...[/cyan]")
    console.print(f"  GPU: {pod_config['gpu_type']}")
    console.print(f"  Template: {pod_config['template']}")
    console.print(f"  Region: {pod_config['region']}")

    try:
        pod_id = provider.create_pod(pod_config)
        console.print(f"\n[green]✓ Pod created: {pod_id}[/green]")

        # Get pod status
        console.print("\n[cyan]Fetching pod status...[/cyan]")
        status = provider.get_pod_status(pod_id)

        # Display status in a panel
        status_text = f"""
[bold]Pod ID:[/bold] {status['pod_id']}
[bold]Status:[/bold] {status['status']}
[bold]GPU:[/bold] {status['gpu_count']}x {status['gpu_type']}
[bold]Cost:[/bold] ${status['cost_per_hour']:.2f}/hr
[bold]Runtime:[/bold] {status['runtime_minutes']:.1f} minutes
[bold]Total Cost:[/bold] ${status['total_cost']:.4f}
        """

        console.print(Panel(status_text, title="Pod Status", border_style="green"))

        # Ask if user wants to terminate
        if Confirm.ask("\n[yellow]Terminate pod now?[/yellow]", default=True):
            console.print("[cyan]Terminating pod...[/cyan]")
            if provider.terminate_pod(pod_id):
                console.print("[green]✓ Pod terminated[/green]")
            else:
                console.print("[red]✗ Failed to terminate pod[/red]")
                console.print(f"[yellow]Please manually terminate pod {pod_id} via RunPod console[/yellow]")
        else:
            console.print(f"[yellow]Pod {pod_id} left running. Don't forget to terminate it![/yellow]")

    except NotImplementedError:
        console.print("[yellow]Pod creation not yet implemented (task 5.2)[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Error creating pod: {e}[/red]")


def main():
    """Run all manual tests."""
    console.print(Panel.fit(
        "[bold green]RunPod Provider Manual Test[/bold green]\n"
        "[yellow]This script makes REAL API calls to RunPod[/yellow]",
        border_style="cyan"
    ))

    # Load config
    try:
        config = load_config()
    except FileNotFoundError:
        console.print("\n[red]Config file not found![/red]")
        console.print("Run: [cyan]python -c \"from autopod.config import config_init_wizard; config_init_wizard()\"[/cyan]")
        return

    # Test authentication
    provider = run_authentication_test()
    if not provider:
        return

    # Test GPU availability
    run_gpu_availability_test(provider)

    # Test pod creation (with confirmation)
    run_pod_creation_test(provider, config)

    console.print("\n[bold green]✓ Manual tests complete[/bold green]")


if __name__ == "__main__":
    main()
