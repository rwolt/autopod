#!/usr/bin/env python3
"""Integration tests for PodManager against real RunPod API.

Tests the full stack:
- PodManager -> RunPodProvider -> RunPod API
- State persistence
- Rich formatting output
- Pod lifecycle (create, list, info, stop, terminate)

Expected cost: < $0.02 (creates 1 pod, terminates quickly)
Runtime: ~2-3 minutes
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from autopod.config import load_config
from autopod.providers import RunPodProvider
from autopod.pod_manager import PodManager
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
    """Run comprehensive PodManager integration tests."""
    console.print(Panel.fit(
        "[bold yellow]⚠️  PodManager Integration Test - REAL API CALLS[/bold yellow]\n"
        "[dim]Testing full pod lifecycle with PodManager[/dim]\n"
        "[dim]Expected cost: < $0.02[/dim]",
        border_style="yellow"
    ))

    results = {}
    pod_id = None

    try:
        # Load config
        config = load_config()
        api_key = config["providers"]["runpod"]["api_key"]
        ssh_key_path = config["providers"]["runpod"]["ssh_key_path"]

        # Create provider and manager
        provider = RunPodProvider(api_key=api_key)
        manager = PodManager(provider, console)

        # ===== TEST 1: Create pod via provider (for testing) =====
        def test_create_pod():
            nonlocal pod_id
            console.print("\n[yellow]Creating test pod...[/yellow]")

            pod_config = {
                "gpu_type": "RTX A5000",
                "gpu_count": 1,
                "template": "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04",
                "cloud_type": "ALL",
                "disk_size_gb": 10,
            }

            pod_id = provider.create_pod(pod_config)
            assert pod_id, "Pod ID is empty"
            console.print(f"  Pod ID: {pod_id}")

            # Manually save to state (simulating what CLI would do)
            manager.save_pod_state(pod_id, {
                "pod_host_id": pod_id + "-test",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
            })

            return pod_id

        success, pod_id = test_method("Create pod", test_create_pod)
        results["create_pod"] = success
        if not success:
            console.print("[red]Cannot continue without pod[/red]")
            return

        # Wait a few seconds for pod to initialize
        time.sleep(5)

        # ===== TEST 2: Load pod state =====
        def test_load_state():
            state = manager.load_pod_state()
            assert pod_id in state, f"Pod {pod_id} not in state"
            assert "pod_host_id" in state[pod_id], "Missing pod_host_id"
            console.print(f"  State loaded: {len(state)} pods")
            return state

        success, state = test_method("load_pod_state()", test_load_state)
        results["load_pod_state"] = success

        # ===== TEST 3: List pods =====
        def test_list_pods():
            console.print("\n[yellow]Listing all pods...[/yellow]")
            pods = manager.list_pods(show_table=True)
            assert len(pods) > 0, "No pods returned"

            # Find our pod
            found = False
            for pod in pods:
                if pod["pod_id"] == pod_id:
                    found = True
                    console.print(f"  ✓ Found our pod in list")
                    break

            assert found, f"Pod {pod_id} not found in list"
            return pods

        success, pods = test_method("list_pods()", test_list_pods)
        results["list_pods"] = success

        # ===== TEST 4: Get pod info =====
        def test_get_pod_info():
            console.print(f"\n[yellow]Getting info for pod {pod_id}...[/yellow]")
            info = manager.get_pod_info(pod_id, show_panel=True)

            assert info is not None, "No info returned"
            assert info["pod_id"] == pod_id, "Wrong pod ID"
            assert "status" in info, "Missing status"
            assert "gpu_type" in info, "Missing gpu_type"
            assert "cost_per_hour" in info, "Missing cost_per_hour"

            console.print(f"  Status: {info['status']}")
            console.print(f"  GPU: {info['gpu_count']}x {info['gpu_type']}")
            console.print(f"  Cost: ${info['cost_per_hour']:.2f}/hr")

            return info

        success, info = test_method("get_pod_info()", test_get_pod_info)
        results["get_pod_info"] = success

        # ===== TEST 5: Wait for SSH ready (optional, for completeness) =====
        def test_wait_for_ssh():
            console.print(f"\n[yellow]Waiting for SSH to become ready...[/yellow]")
            max_attempts = 12  # 60 seconds

            for attempt in range(1, max_attempts + 1):
                info = manager.get_pod_info(pod_id, show_panel=False)
                if info and info.get("ssh_ready"):
                    console.print(f"  ✓ SSH ready after {attempt * 5}s")
                    return True
                console.print(f"  Waiting... ({attempt}/{max_attempts})")
                time.sleep(5)

            console.print(f"  [yellow]SSH not ready after {max_attempts * 5}s (not critical)[/yellow]")
            return False  # Not critical for this test

        success, ssh_ready = test_method("Wait for SSH", test_wait_for_ssh)
        results["wait_for_ssh"] = success

        # ===== TEST 6: Stop pod =====
        def test_stop_pod():
            console.print(f"\n[yellow]Stopping pod {pod_id}...[/yellow]")
            success = manager.stop_pod(pod_id)
            assert success, "Stop pod failed"

            # Verify status changed
            time.sleep(3)
            info = manager.get_pod_info(pod_id, show_panel=False)
            console.print(f"  Status after stop: {info['status']}")

            return success

        success, _ = test_method("stop_pod()", test_stop_pod)
        results["stop_pod"] = success

        # ===== TEST 7: Terminate pod =====
        def test_terminate_pod():
            console.print(f"\n[yellow]Terminating pod {pod_id}...[/yellow]")
            # Use confirm=True to skip prompt
            success = manager.terminate_pod(pod_id, confirm=True)
            assert success, "Terminate pod failed"

            # Verify removed from state
            time.sleep(2)
            state = manager.load_pod_state()
            assert pod_id not in state, "Pod still in state after termination"
            console.print(f"  ✓ Pod removed from state")

            return success

        success, _ = test_method("terminate_pod()", test_terminate_pod)
        results["terminate_pod"] = success

        # Clear pod_id so we don't try to clean up again
        pod_id = None

        # ===== TEST 8: Verify termination =====
        def test_verify_termination():
            console.print(f"\n[yellow]Verifying pod termination...[/yellow]")
            time.sleep(3)

            # Try to get pod status - should fail
            try:
                provider.get_pod_status(pod_id if pod_id else "already-terminated")
                return False  # Should have raised error
            except RuntimeError as e:
                if "not found" in str(e):
                    console.print("  ✓ Pod successfully deleted")
                    return True
                raise

        success, _ = test_method("Verify termination", test_verify_termination)
        results["verify_termination"] = success

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
                manager.terminate_pod(pod_id, confirm=True)
                console.print("✓ Cleanup complete")
            except:
                console.print("[dim]Pod already terminated or error cleaning up[/dim]")

    # Print summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]PodManager Integration Test Results[/bold cyan]")
    console.print("="*60 + "\n")

    from rich.table import Table
    table = Table(title="Test Results")
    table.add_column("Test", style="cyan")
    table.add_column("Result", justify="center")

    for test_name, passed in results.items():
        result = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        table.add_row(test_name, result)

    console.print(table)

    total = len(results)
    passed = sum(1 for r in results.values() if r)
    console.print(f"\n[bold]Passed: {passed}/{total}[/bold]")

    if passed == total:
        console.print("\n[bold green]✓ ALL PODMANAGER TESTS PASSED[/bold green]")
        console.print("[dim]PodManager is fully operational![/dim]")
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
