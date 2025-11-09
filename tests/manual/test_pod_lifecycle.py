#!/usr/bin/env python3
"""Test actual pod lifecycle operations - CREATE, STATUS, TERMINATE.

This script makes REAL API calls and will create a real pod.
Uses RTX A5000 (cheapest GPU at ~$0.11/hr spot).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from autopod.config import load_config
from autopod.providers import RunPodProvider
from autopod.logging import setup_logging

console = Console()
logger = setup_logging()


def main():
    """Test pod lifecycle: create → status → terminate."""
    console.print(Panel.fit(
        "[bold yellow]⚠️  Pod Lifecycle Test - REAL API CALLS[/bold yellow]\n"
        "[dim]This will create a real pod with RTX A5000 and terminate it[/dim]",
        border_style="yellow"
    ))

    try:
        # Load config and create provider
        config = load_config()
        provider = RunPodProvider(api_key=config["providers"]["runpod"]["api_key"])

        console.print("\n[cyan]Step 1: Checking RTX A5000 availability...[/cyan]")
        gpu_info = provider.get_gpu_availability("RTX A5000")

        if not gpu_info["available"]:
            console.print("[red]✗ RTX A5000 not available. Aborting.[/red]")
            return

        console.print(f"[green]✓ RTX A5000 available[/green]")
        console.print(f"  Cost: ${gpu_info['spot_price']:.2f}/hr (spot)")
        console.print(f"  VRAM: {gpu_info['memory_gb']} GB")

        # Create pod configuration
        pod_config = {
            "gpu_type": "RTX A5000",
            "gpu_count": 1,
            "template": "runpod/pytorch:latest",  # Minimal template
            "cloud_type": "ALL",  # Allow both secure and community
            "disk_size_gb": 10,  # Minimal disk
        }

        console.print(f"\n[cyan]Step 2: Creating pod...[/cyan]")
        console.print(f"  Template: {pod_config['template']}")
        console.print(f"  Disk: {pod_config['disk_size_gb']} GB")

        pod_id = provider.create_pod(pod_config)

        console.print(f"[bold green]✓ Pod created: {pod_id}[/bold green]")

        # Wait a moment for pod to initialize
        console.print("\n[cyan]Step 3: Waiting 5 seconds for pod to initialize...[/cyan]")
        time.sleep(5)

        # Get pod status
        console.print("\n[cyan]Step 4: Getting pod status...[/cyan]")
        status = provider.get_pod_status(pod_id)

        console.print(f"[green]✓ Pod status retrieved[/green]")
        console.print(f"  Status: {status['status']}")
        console.print(f"  GPU: {status['gpu_count']}x {status['gpu_type']}")
        console.print(f"  Cost: ${status['cost_per_hour']:.2f}/hr")
        console.print(f"  Runtime: {status['runtime_minutes']:.2f} minutes")
        console.print(f"  Total cost so far: ${status['total_cost']:.4f}")

        if status['ssh_host'] and status['ssh_port']:
            console.print(f"  SSH: {status['ssh_host']}:{status['ssh_port']}")
        else:
            console.print("  SSH: Not ready yet")

        # Terminate pod
        console.print(f"\n[cyan]Step 5: Terminating pod {pod_id}...[/cyan]")

        if provider.terminate_pod(pod_id):
            console.print("[bold green]✓ Pod terminated successfully[/bold green]")
        else:
            console.print("[red]✗ Pod termination failed[/red]")
            console.print(f"[yellow]Please manually terminate pod {pod_id} in RunPod console[/yellow]")

        # Final status check
        console.print("\n[cyan]Step 6: Verifying termination...[/cyan]")
        time.sleep(2)

        try:
            final_status = provider.get_pod_status(pod_id)
            console.print(f"  Final status: {final_status['status']}")
            console.print(f"  Total cost: ${final_status['total_cost']:.4f}")
        except Exception as e:
            console.print(f"  (Pod may be deleted: {e})")

        console.print("\n[bold green]✓ Pod lifecycle test complete![/bold green]")
        console.print(f"[dim]Check your RunPod console to verify pod is gone[/dim]")

    except Exception as e:
        console.print(f"\n[bold red]✗ Error during test:[/bold red]")
        console.print(f"[red]{e}[/red]")

        import traceback
        console.print("\n[dim]Full traceback:[/dim]")
        console.print(traceback.format_exc())

        console.print(f"\n[yellow]If a pod was created, please check your RunPod console and terminate it manually[/yellow]")


if __name__ == "__main__":
    console.print("\n[bold]Press Ctrl+C to cancel before pod creation[/bold]")
    console.print("[dim]Starting in 3 seconds...[/dim]\n")

    try:
        time.sleep(3)
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test cancelled by user[/yellow]")
