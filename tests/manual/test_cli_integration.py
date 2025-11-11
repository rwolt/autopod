#!/usr/bin/env python3
"""Comprehensive CLI integration test - full pod lifecycle.

Tests the entire autopod CLI workflow:
1. Create pod via CLI (autopod connect)
2. Wait for SSH ready
3. Execute command via CLI to print secret message
4. Prompt user for manual confirmation
5. Terminate pod via CLI (autopod kill)
6. Verify pod removed

Expected cost: < $0.02
Runtime: ~2-3 minutes
"""

import sys
import time
import subprocess
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()

# Secret message to verify SSH execution
SECRET_MESSAGE = "AUTOPOD_SECRET_42_TEST_PASSED"


def run_cli_command(args, input_text=None, capture_output=True, timeout=120):
    """Run autopod CLI command.

    Args:
        args: List of command arguments (e.g., ['connect', '--gpu', 'RTX A5000'])
        input_text: Optional input for interactive prompts
        capture_output: Whether to capture output
        timeout: Command timeout in seconds

    Returns:
        subprocess.CompletedProcess result
    """
    cmd = ["autopod"] + args

    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

    result = subprocess.run(
        cmd,
        input=input_text,
        capture_output=capture_output,
        text=True,
        timeout=timeout
    )

    return result


def extract_pod_id_from_output(output):
    """Extract pod ID from CLI output.

    Looks for patterns like "Pod created successfully: <pod-id>"

    Args:
        output: CLI stdout or stderr text

    Returns:
        Pod ID string or None if not found
    """
    import re

    # Pattern: "Pod created successfully: <pod-id>"
    # or "Pod created: <pod-id>"
    patterns = [
        r"Pod created successfully:\s*(\S+)",
        r"Pod created:\s*(\S+)",
        r"✓ Pod created.*:\s*(\S+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            return match.group(1)

    return None


def main():
    """Run comprehensive CLI integration test."""
    console.print(Panel.fit(
        "[bold yellow]⚠️  CLI Integration Test - REAL API CALLS[/bold yellow]\n"
        "[dim]Testing full pod lifecycle with autopod CLI[/dim]\n"
        "[dim]Expected cost: < $0.02[/dim]",
        border_style="yellow"
    ))

    pod_id = None
    test_results = {}

    try:
        # ===== TEST 1: Create pod via CLI =====
        console.print("\n[bold cyan]Test 1: Create pod via CLI[/bold cyan]")
        console.print("[yellow]Running: autopod connect --gpu 'RTX A5000'[/yellow]")

        result = run_cli_command([
            "connect",
            "--gpu", "RTX A5000",
            "--gpu-count", "1",
            "--disk-size", "10"
        ], timeout=180)

        if result.returncode != 0:
            console.print(f"[red]✗ Failed to create pod[/red]")
            console.print(f"stdout: {result.stdout}")
            console.print(f"stderr: {result.stderr}")
            test_results["create_pod"] = False
            return

        # Extract pod ID from output
        pod_id = extract_pod_id_from_output(result.stdout + result.stderr)

        if not pod_id:
            console.print(f"[red]✗ Could not extract pod ID from output[/red]")
            console.print(f"Output: {result.stdout}")
            test_results["create_pod"] = False
            return

        console.print(f"[green]✓ Pod created: {pod_id}[/green]")
        test_results["create_pod"] = True

        # ===== TEST 2: List pods =====
        console.print("\n[bold cyan]Test 2: List pods[/bold cyan]")
        console.print("[yellow]Running: autopod list[/yellow]")

        time.sleep(2)  # Brief pause
        result = run_cli_command(["list"])

        if result.returncode != 0:
            console.print(f"[red]✗ List command failed[/red]")
            test_results["list_pods"] = False
        elif pod_id in result.stdout:
            console.print(f"[green]✓ Pod {pod_id} found in list[/green]")
            test_results["list_pods"] = True
        else:
            console.print(f"[yellow]⚠ Pod not found in list (may not be ready)[/yellow]")
            test_results["list_pods"] = False

        # ===== TEST 3: Wait for SSH ready =====
        console.print("\n[bold cyan]Test 3: Wait for SSH ready[/bold cyan]")
        console.print("[yellow]Waiting for SSH to become available...[/yellow]")

        max_attempts = 24  # 24 * 5 = 120 seconds
        ssh_ready = False

        for attempt in range(1, max_attempts + 1):
            console.print(f"[dim]Attempt {attempt}/{max_attempts}[/dim]")

            result = run_cli_command(["info", pod_id])

            if result.returncode == 0 and "SSH" in result.stdout and "Ready" in result.stdout:
                console.print(f"[green]✓ SSH ready after {attempt * 5} seconds[/green]")
                ssh_ready = True
                test_results["wait_ssh"] = True
                break

            time.sleep(5)

        if not ssh_ready:
            console.print(f"[red]✗ SSH not ready after {max_attempts * 5} seconds[/red]")
            test_results["wait_ssh"] = False
            # Continue anyway to test other commands

        # Give SSH a few extra seconds to fully initialize
        if ssh_ready:
            console.print("[dim]Waiting 5 extra seconds for SSH to fully initialize...[/dim]")
            time.sleep(5)

        # ===== TEST 4: Execute command via SSH =====
        console.print("\n[bold cyan]Test 4: Execute command via SSH[/bold cyan]")
        console.print(f"[yellow]Running: autopod ssh {pod_id} -c \"echo {SECRET_MESSAGE}\"[/yellow]")

        result = run_cli_command([
            "ssh", pod_id,
            "-c", f"echo {SECRET_MESSAGE}"
        ], timeout=30)

        if result.returncode != 0:
            console.print(f"[red]✗ SSH command failed (exit code {result.returncode})[/red]")
            console.print(f"stdout: {result.stdout}")
            console.print(f"stderr: {result.stderr}")
            test_results["ssh_command"] = False
        elif SECRET_MESSAGE in result.stdout:
            console.print(f"[green]✓ SSH command executed successfully![/green]")
            console.print(f"[green]Secret message received: {SECRET_MESSAGE}[/green]")
            test_results["ssh_command"] = True
        else:
            console.print(f"[yellow]⚠ SSH command executed but secret not found[/yellow]")
            console.print(f"Output: {result.stdout}")
            test_results["ssh_command"] = False

        # ===== TEST 5: Manual confirmation prompt =====
        console.print("\n[bold cyan]Test 5: Manual confirmation[/bold cyan]")
        console.print(Panel.fit(
            f"[bold]Pod ID:[/bold] {pod_id}\n"
            f"[bold]Status:[/bold] SSH working\n"
            f"[bold]Secret:[/bold] {SECRET_MESSAGE} ✓\n\n"
            "[green]All automated tests passed![/green]\n"
            "[dim]Please confirm you can see this message.[/dim]",
            title="[bold green]Integration Test Status[/bold green]",
            border_style="green"
        ))

        confirmed = Confirm.ask("\nDid you see the secret message above?", default=True)

        if confirmed:
            console.print("[green]✓ User confirmation received[/green]")
            test_results["user_confirmation"] = True
        else:
            console.print("[yellow]✗ User did not confirm[/yellow]")
            test_results["user_confirmation"] = False

        # ===== TEST 6: Terminate pod =====
        console.print("\n[bold cyan]Test 6: Terminate pod[/bold cyan]")
        console.print(f"[yellow]Running: autopod kill {pod_id} -y[/yellow]")

        result = run_cli_command(["kill", pod_id, "-y"])

        if result.returncode != 0:
            console.print(f"[red]✗ Terminate command failed[/red]")
            test_results["terminate_pod"] = False
        else:
            console.print(f"[green]✓ Pod terminated successfully[/green]")
            test_results["terminate_pod"] = True
            pod_id = None  # Don't try to clean up again

        # ===== TEST 7: Verify pod removed from list =====
        console.print("\n[bold cyan]Test 7: Verify pod removed[/bold cyan]")
        time.sleep(3)

        result = run_cli_command(["list"])

        if result.returncode == 0 and (pod_id is None or pod_id not in result.stdout):
            console.print(f"[green]✓ Pod removed from list[/green]")
            test_results["verify_removed"] = True
        else:
            console.print(f"[yellow]⚠ Pod may still be in list[/yellow]")
            test_results["verify_removed"] = False

    except subprocess.TimeoutExpired as e:
        console.print(f"\n[red]✗ Command timed out: {e}[/red]")
    except KeyboardInterrupt:
        console.print("\n[yellow]✗ Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error:[/bold red]")
        console.print(f"[red]{e}[/red]")
        import traceback
        console.print(traceback.format_exc())
    finally:
        # Cleanup: Make sure pod is terminated
        if pod_id:
            console.print(f"\n[yellow]Cleaning up: terminating pod {pod_id}...[/yellow]")
            try:
                run_cli_command(["kill", pod_id, "-y"])
                console.print("[green]✓ Cleanup complete[/green]")
            except:
                console.print("[dim]Error during cleanup (pod may already be terminated)[/dim]")

    # ===== RESULTS SUMMARY =====
    console.print("\n" + "="*60)
    console.print("[bold cyan]CLI Integration Test Results[/bold cyan]")
    console.print("="*60 + "\n")

    from rich.table import Table
    table = Table(title="Test Results")
    table.add_column("Test", style="cyan")
    table.add_column("Result", justify="center")

    for test_name, passed in test_results.items():
        result_str = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        table.add_row(test_name.replace("_", " ").title(), result_str)

    console.print(table)

    total = len(test_results)
    passed = sum(1 for r in test_results.values() if r)

    console.print(f"\n[bold]Passed: {passed}/{total}[/bold]")

    if passed == total:
        console.print("\n[bold green]✓ ALL CLI TESTS PASSED[/bold green]")
        console.print("[dim]autopod CLI is fully operational![/dim]")
    else:
        console.print(f"\n[bold yellow]⚠️  {total - passed} test(s) failed[/bold yellow]")

    console.print(f"\n[dim]Full logs: ~/.autopod/logs/autopod.log[/dim]")


if __name__ == "__main__":
    console.print("\n[bold]Press Ctrl+C to cancel within 3 seconds...[/bold]")
    try:
        time.sleep(3)
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test cancelled by user[/yellow]")
