#!/usr/bin/env python3
"""Simple SSH test - verify we can execute commands on a pod.

Uses a lightweight PyTorch template (faster startup than ComfyUI).
Tests:
1. Create pod with simple template
2. Wait for SSH (with progress bar)
3. Execute nvidia-smi command via SSH
4. Parse CUDA version from output
5. Terminate pod

Expected cost: < $0.01
Startup time: ~30-60 seconds (faster than ComfyUI)
"""

import sys
import time
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from autopod.config import load_config
from autopod.providers import RunPodProvider
from autopod.logging import setup_logging

console = Console()
logger = setup_logging()


def main():
    """Test SSH command execution with simple template."""
    console.print(Panel.fit(
        "[bold yellow]⚠️  Simple SSH Test - REAL API CALLS[/bold yellow]\n"
        "[dim]Testing SSH command execution with PyTorch template[/dim]\n"
        "[dim]Expected cost: < $0.01[/dim]",
        border_style="yellow"
    ))

    pod_id = None

    try:
        # Load config
        config = load_config()
        api_key = config["providers"]["runpod"]["api_key"]
        ssh_key_path = config["providers"]["runpod"]["ssh_key_path"]

        provider = RunPodProvider(api_key=api_key)

        # Create pod with SIMPLE template (faster startup)
        console.print("\n[cyan]Creating pod with PyTorch template...[/cyan]")
        console.print("[dim]Template: runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel[/dim]")

        pod_config = {
            "gpu_type": "RTX A5000",
            "gpu_count": 1,
            "template": "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04",
            "cloud_type": "ALL",
            "disk_size_gb": 10,
        }

        pod_id = provider.create_pod(pod_config)
        console.print(f"[green]✓ Pod created: {pod_id}[/green]")

        # Wait for SSH with progress bar
        console.print("\n[yellow]Waiting for SSH to become available...[/yellow]")
        console.print("[dim]PyTorch templates usually ready in 30-60 seconds[/dim]\n")

        conn_str = None
        max_attempts = 24  # 24 * 5 = 120 seconds (2 minutes)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Waiting for SSH...", total=max_attempts)

            for attempt in range(1, max_attempts + 1):
                try:
                    progress.update(
                        task,
                        completed=attempt,
                        description=f"[cyan]Checking SSH (attempt {attempt}/{max_attempts})..."
                    )

                    conn_str = provider.get_ssh_connection_string(pod_id)

                    # Success!
                    progress.update(task, description="[green]✓ SSH Available!")
                    console.print(f"\n[green]✓ SSH ready after {attempt * 5} seconds[/green]")
                    console.print(f"  Connection: {conn_str}")
                    break

                except RuntimeError as e:
                    if "not available" in str(e) and attempt < max_attempts:
                        time.sleep(5)
                        continue
                    elif attempt >= max_attempts:
                        progress.update(task, description="[red]✗ SSH timeout")
                        raise RuntimeError(f"SSH not available after {max_attempts * 5}s")
                    else:
                        raise

        if not conn_str:
            console.print("[red]✗ Failed to get SSH connection[/red]")
            return

        # Parse SSH connection
        from autopod.ssh import parse_ssh_connection_string
        ssh_info = parse_ssh_connection_string(conn_str)

        # Give SSH service a few extra seconds to fully initialize
        console.print("\n[dim]Waiting 5 seconds for SSH service to fully initialize...[/dim]")
        time.sleep(5)

        # Add SSH key to agent (needed for passphrase-protected keys in non-interactive mode)
        console.print("\n[dim]Adding SSH key to ssh-agent...[/dim]")
        try:
            # Start ssh-agent if not running and add key
            subprocess.run(["ssh-add", ssh_key_path], check=True, capture_output=True)
            console.print("[dim]✓ Key added to ssh-agent[/dim]")
        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]⚠ Could not add key to ssh-agent: {e}[/yellow]")
            console.print("[yellow]SSH may fail if key has passphrase[/yellow]")

        # Test SSH command execution: nvidia-smi
        console.print("\n[cyan]Testing SSH command execution...[/cyan]")
        console.print(f"[dim]Connection: {ssh_info['user']}@{ssh_info['host']}[/dim]")
        console.print(f"[dim]SSH key: {ssh_key_path}[/dim]")
        console.print("[dim]Running: nvidia-smi --query-gpu=name,driver_version,cuda_version --format=csv[/dim]")

        # Build SSH command (RunPod proxy doesn't need -p flag)
        cmd = ["ssh"]

        # Add verbose output for debugging
        cmd.append("-v")

        # Add port if specified (legacy format)
        if ssh_info["port"] is not None:
            cmd.extend(["-p", str(ssh_info["port"])])

        # Add SSH key and options
        cmd.extend([
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10",
            f"{ssh_info['user']}@{ssh_info['host']}",
            "nvidia-smi --query-gpu=name,driver_version,cuda_version --format=csv,noheader"
        ])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            console.print(f"[green]✓ SSH command successful![/green]")
            console.print(f"\n[bold]GPU Info:[/bold]")
            console.print(result.stdout.strip())

            # Parse CUDA version
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 3:
                gpu_name = parts[0]
                driver_ver = parts[1]
                cuda_ver = parts[2]
                console.print(f"\n[cyan]GPU:[/cyan] {gpu_name}")
                console.print(f"[cyan]Driver:[/cyan] {driver_ver}")
                console.print(f"[cyan]CUDA:[/cyan] {cuda_ver}")
        else:
            console.print(f"[red]✗ SSH command failed (exit code {result.returncode})[/red]")
            console.print(f"[dim]stderr: {result.stderr}[/dim]")

        console.print("\n[bold green]✓ SSH test passed![/bold green]")
        console.print("[dim]SSH tunnel and command execution work correctly[/dim]")

    except Exception as e:
        console.print(f"\n[bold red]✗ Test failed:[/bold red]")
        console.print(f"[red]{e}[/red]")

        import traceback
        console.print("\n[dim]Traceback:[/dim]")
        console.print(traceback.format_exc())

    finally:
        # Cleanup
        if pod_id:
            console.print(f"\n[yellow]Terminating pod {pod_id}...[/yellow]")
            try:
                provider.terminate_pod(pod_id)
                console.print("[green]✓ Pod terminated[/green]")
            except:
                console.print("[dim]Error terminating pod (may already be gone)[/dim]")


if __name__ == "__main__":
    console.print("\n[bold]Press Ctrl+C to cancel within 3 seconds...[/bold]")
    try:
        time.sleep(3)
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test cancelled[/yellow]")
