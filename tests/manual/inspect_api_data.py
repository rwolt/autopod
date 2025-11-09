#!/usr/bin/env python3
"""Inspect raw RunPod API responses - no interactive prompts.

This shows exactly what data RunPod returns for GPUs, pods, etc.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from autopod.config import load_config
from autopod.providers import RunPodProvider
from autopod.logging import setup_logging

console = Console()
logger = setup_logging()


def inspect_gpus():
    """Show raw GPU data from RunPod API."""
    console.print("\n[bold cyan]═══ Raw GPU Data from RunPod API ═══[/bold cyan]\n")

    try:
        config = load_config()
        api_key = config["providers"]["runpod"]["api_key"]
        provider = RunPodProvider(api_key=api_key)

        # Import runpod directly to get raw data
        import runpod
        runpod.api_key = api_key

        # Get all GPUs
        gpus = runpod.get_gpus()

        console.print(f"[green]Found {len(gpus)} GPU types[/green]\n")

        # Show first 3 GPUs in detail
        for i, gpu in enumerate(gpus[:3], 1):
            # Pretty print JSON
            gpu_json = json.dumps(gpu, indent=2)
            syntax = Syntax(gpu_json, "json", theme="monokai", line_numbers=True)

            console.print(Panel(
                syntax,
                title=f"[cyan]GPU #{i}: {gpu.get('displayName', 'Unknown')}[/cyan]",
                border_style="cyan"
            ))
            console.print()

        # Show summary of all GPUs
        console.print("\n[bold cyan]═══ All Available GPUs (Summary) ═══[/bold cyan]\n")

        for gpu in gpus:
            name = gpu.get('displayName', 'Unknown')
            gpu_id = gpu.get('id', 'N/A')
            memory = gpu.get('memoryInGb', 'N/A')

            # Pricing info
            pricing = "N/A"
            if 'lowestPrice' in gpu and gpu['lowestPrice']:
                pricing = gpu['lowestPrice']

            # CUDA info
            cuda = "N/A"
            if 'cudaVersion' in gpu:
                cuda = gpu['cudaVersion']

            console.print(f"[cyan]{name}[/cyan]")
            console.print(f"  ID: {gpu_id}")
            console.print(f"  Memory: {memory} GB")
            console.print(f"  CUDA: {cuda}")
            console.print(f"  Pricing: {pricing}")
            console.print()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


def inspect_pods():
    """Show raw pod data from RunPod API."""
    console.print("\n[bold cyan]═══ Your Current Pods ═══[/bold cyan]\n")

    try:
        config = load_config()
        api_key = config["providers"]["runpod"]["api_key"]

        import runpod
        runpod.api_key = api_key

        # Get all pods
        pods = runpod.get_pods()

        if not pods:
            console.print("[yellow]No pods found[/yellow]")
            return

        console.print(f"[green]Found {len(pods)} pod(s)[/green]\n")

        # Show each pod in detail
        for i, pod in enumerate(pods, 1):
            pod_json = json.dumps(pod, indent=2)
            syntax = Syntax(pod_json, "json", theme="monokai", line_numbers=True)

            console.print(Panel(
                syntax,
                title=f"[cyan]Pod #{i}: {pod.get('name', 'Unknown')}[/cyan]",
                border_style="cyan"
            ))
            console.print()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


def main():
    """Inspect all RunPod API data."""
    console.print(Panel.fit(
        "[bold green]RunPod API Data Inspector[/bold green]\n"
        "[dim]No interactive prompts - just shows raw API responses[/dim]",
        border_style="green"
    ))

    # Inspect GPUs
    inspect_gpus()

    # Inspect current pods
    inspect_pods()

    console.print("\n[bold green]✓ Inspection complete[/bold green]")
    console.print(f"[dim]Full logs: ~/.autopod/logs/autopod.log[/dim]")


if __name__ == "__main__":
    main()
