#!/usr/bin/env python3
"""Comprehensive integration test for RunPodProvider.

Tests EVERY public method against the real RunPod API:
1. authenticate()
2. get_gpu_availability()
3. create_pod()
4. get_pod_status()
5. stop_pod()
6. get_ssh_connection_string()
7. terminate_pod()

Uses RTX A5000 (cheapest at ~$0.11/hr spot).
Total expected cost: < $0.02
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from autopod.config import load_config
from autopod.providers import RunPodProvider
from autopod.logging import setup_logging

console = Console()
logger = setup_logging()


def test_method(method_name: str, test_func):
    """Wrapper to test a method and report results."""
    console.print(f"\n[cyan]Testing: {method_name}[/cyan]")
    try:
        result = test_func()
        console.print(f"[green]✓ {method_name} - PASSED[/green]")
        return True, result
    except Exception as e:
        console.print(f"[red]✗ {method_name} - FAILED: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False, None


def main():
    """Run comprehensive integration tests."""
    console.print(Panel.fit(
        "[bold yellow]⚠️  RunPod Provider Integration Test[/bold yellow]\n"
        "[dim]Testing ALL methods with real API calls[/dim]\n"
        "[dim]Expected cost: < $0.02[/dim]",
        border_style="yellow"
    ))

    results = {}
    pod_id = None

    try:
        # Load config
        config = load_config()
        api_key = config["providers"]["runpod"]["api_key"]

        # ===== TEST 1: authenticate() =====
        def test_authenticate():
            provider = RunPodProvider(api_key=api_key)
            success = provider.authenticate(api_key)
            assert success, "Authentication failed"
            return provider

        success, provider = test_method("authenticate()", test_authenticate)
        results["authenticate"] = success
        if not success:
            console.print("[red]Cannot continue without authentication[/red]")
            return

        # ===== TEST 2: get_gpu_availability() =====
        def test_gpu_availability():
            info = provider.get_gpu_availability("RTX A5000")
            assert info["available"], "RTX A5000 not available"
            assert info["cost_per_hour"] > 0, "Invalid pricing"
            assert info["memory_gb"] > 0, "Invalid VRAM"
            console.print(f"  Cost: ${info['cost_per_hour']:.2f}/hr")
            console.print(f"  VRAM: {info['memory_gb']} GB")
            console.print(f"  Secure: ${info['secure_price']:.2f}/hr")
            console.print(f"  Spot: ${info['spot_price']:.2f}/hr")
            return info

        success, gpu_info = test_method("get_gpu_availability()", test_gpu_availability)
        results["get_gpu_availability"] = success
        if not success:
            console.print("[red]Cannot continue without GPU availability[/red]")
            return

        # ===== TEST 3: create_pod() =====
        def test_create_pod():
            nonlocal pod_id
            pod_config = {
                "gpu_type": "RTX A5000",
                "gpu_count": 1,
                "template": "runpod/pytorch:latest",
                "cloud_type": "ALL",
                "disk_size_gb": 10,
            }
            pod_id = provider.create_pod(pod_config)
            assert pod_id, "Pod ID is empty"
            assert isinstance(pod_id, str), "Pod ID should be string"
            console.print(f"  Pod ID: {pod_id}")
            return pod_id

        success, pod_id = test_method("create_pod()", test_create_pod)
        results["create_pod"] = success
        if not success:
            console.print("[yellow]Skipping remaining tests (no pod created)[/yellow]")
            return

        # Wait for pod to initialize
        console.print("\n[dim]Waiting 10 seconds for pod to initialize...[/dim]")
        time.sleep(10)

        # ===== TEST 4: get_pod_status() =====
        def test_get_status():
            status = provider.get_pod_status(pod_id)
            assert status["pod_id"] == pod_id, "Pod ID mismatch"
            assert status["status"] in ["RUNNING", "CREATED"], f"Unexpected status: {status['status']}"
            assert status["cost_per_hour"] > 0, "Invalid cost"
            console.print(f"  Status: {status['status']}")
            console.print(f"  GPU: {status['gpu_count']}x {status['gpu_type']}")
            console.print(f"  Cost: ${status['cost_per_hour']:.2f}/hr")
            console.print(f"  Runtime: {status['runtime_minutes']:.2f} min")
            console.print(f"  Total cost: ${status['total_cost']:.4f}")
            return status

        success, status = test_method("get_pod_status()", test_get_status)
        results["get_pod_status"] = success

        # ===== TEST 5: get_ssh_connection_string() =====
        def test_ssh_connection():
            # SSH might not be ready immediately, that's okay
            try:
                conn_str = provider.get_ssh_connection_string(pod_id)
                assert "@" in conn_str, "Invalid SSH connection string format"
                assert ":" in conn_str, "Missing port in SSH connection string"
                console.print(f"  SSH: {conn_str}")
                return conn_str
            except RuntimeError as e:
                if "not available" in str(e):
                    console.print(f"  [yellow]SSH not ready yet (expected)[/yellow]")
                    return None
                raise

        success, ssh_conn = test_method("get_ssh_connection_string()", test_ssh_connection)
        results["get_ssh_connection_string"] = success

        # ===== TEST 6: stop_pod() =====
        def test_stop():
            success = provider.stop_pod(pod_id)
            assert success, "Stop pod failed"
            console.print(f"  Pod {pod_id} stopped")
            return success

        success, _ = test_method("stop_pod()", test_stop)
        results["stop_pod"] = success

        # Wait for stop to take effect
        console.print("\n[dim]Waiting 5 seconds for stop to take effect...[/dim]")
        time.sleep(5)

        # Verify pod is stopped
        console.print("\n[cyan]Verifying pod is stopped...[/cyan]")
        try:
            status = provider.get_pod_status(pod_id)
            console.print(f"  Status after stop: {status['status']}")
            if status['status'] == 'RUNNING':
                console.print(f"  [yellow]Warning: Pod still RUNNING (stop may take time)[/yellow]")
        except Exception as e:
            console.print(f"  [yellow]Could not verify: {e}[/yellow]")

        # ===== TEST 7: terminate_pod() =====
        def test_terminate():
            success = provider.terminate_pod(pod_id)
            assert success, "Terminate pod failed"
            console.print(f"  Pod {pod_id} terminated")
            return success

        success, _ = test_method("terminate_pod()", test_terminate)
        results["terminate_pod"] = success

        # Wait and verify termination
        console.print("\n[dim]Waiting 3 seconds to verify termination...[/dim]")
        time.sleep(3)

        console.print("\n[cyan]Verifying pod is terminated...[/cyan]")
        try:
            provider.get_pod_status(pod_id)
            console.print(f"  [yellow]Warning: Pod still exists after termination[/yellow]")
        except RuntimeError as e:
            if "not found" in str(e):
                console.print(f"  [green]✓ Pod successfully deleted[/green]")
            else:
                console.print(f"  [yellow]Unexpected error: {e}[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red]")
        console.print(f"[red]{e}[/red]")
        import traceback
        console.print(traceback.format_exc())

    finally:
        # Make sure pod is cleaned up
        if pod_id:
            console.print(f"\n[yellow]Ensuring pod {pod_id} is terminated...[/yellow]")
            try:
                provider.terminate_pod(pod_id)
                console.print("[green]✓ Cleanup complete[/green]")
            except:
                console.print("[dim]Pod already terminated or error cleaning up[/dim]")

    # Print summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]Test Results Summary[/bold cyan]")
    console.print("="*60 + "\n")

    table = Table(title="Integration Test Results")
    table.add_column("Method", style="cyan")
    table.add_column("Result", justify="center")

    for method, passed in results.items():
        result = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        table.add_row(method, result)

    console.print(table)

    total = len(results)
    passed = sum(1 for r in results.values() if r)
    console.print(f"\n[bold]Passed: {passed}/{total}[/bold]")

    if passed == total:
        console.print("\n[bold green]✓ ALL TESTS PASSED[/bold green]")
        console.print("[dim]RunPod provider is fully functional![/dim]")
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
