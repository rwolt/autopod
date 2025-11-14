#!/usr/bin/env python3
"""
Comprehensive test suite for V1.2 Tasks 2.0, 3.0, and 4.0

Tests:
- Task 2.0: SSH tunnel management module (tunnel.py)
- Task 3.0: ComfyUI API client module (comfyui.py)
- Task 4.0: Tunnel CLI commands

Run from project root:
    python tests/manual/test_v1.2_tasks_2_3_4.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from autopod.tunnel import SSHTunnel, TunnelManager
from autopod.comfyui import ComfyUIClient
import json
import tempfile
from unittest.mock import Mock, patch
from rich.console import Console

console = Console()


def print_test_header(test_name):
    """Print a formatted test header."""
    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold cyan]{test_name}[/bold cyan]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")


def print_result(passed, message):
    """Print test result."""
    if passed:
        console.print(f"[green]✓ PASS:[/green] {message}")
    else:
        console.print(f"[red]✗ FAIL:[/red] {message}")
    return passed


# =============================================================================
# Task 2.0: SSH Tunnel Module Tests
# =============================================================================

def test_task_2_0_tunnel_module():
    """Test Task 2.0: SSH tunnel management module."""
    print_test_header("Task 2.0: SSH Tunnel Module Tests")

    all_passed = True

    # Test 2.2: SSHTunnel class initialization
    console.print("[bold]Test 2.2: SSHTunnel initialization[/bold]")
    try:
        tunnel = SSHTunnel(
            pod_id="test-pod-123",
            ssh_connection_string="test-user@test-host",
            local_port=8188,
            remote_port=8188,
            ssh_key_path="/path/to/key"
        )

        all_passed &= print_result(
            tunnel.pod_id == "test-pod-123",
            "Pod ID set correctly"
        )
        all_passed &= print_result(
            tunnel.local_port == 8188,
            "Local port set correctly"
        )
        all_passed &= print_result(
            tunnel.remote_port == 8188,
            "Remote port set correctly"
        )
        all_passed &= print_result(
            tunnel.ssh_connection_string == "test-user@test-host",
            "SSH connection string set correctly"
        )
    except Exception as e:
        all_passed &= print_result(False, f"SSHTunnel initialization failed: {e}")

    # Test 2.7-2.9: TunnelManager state management
    console.print("\n[bold]Test 2.7-2.9: TunnelManager state management[/bold]")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "tunnels.json"

            # Create TunnelManager with custom state file
            with patch('autopod.tunnel.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)
                manager = TunnelManager()

                # Verify state file location
                all_passed &= print_result(
                    hasattr(manager, 'state_file'),
                    "TunnelManager has state_file attribute"
                )

                # Test empty state load
                all_passed &= print_result(
                    len(manager.tunnels) == 0,
                    "Empty state loads correctly"
                )
    except Exception as e:
        all_passed &= print_result(False, f"TunnelManager state management failed: {e}")

    # Test 2.10: Port conflict detection
    console.print("\n[bold]Test 2.14: Port conflict detection[/bold]")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('autopod.tunnel.Path.home') as mock_home:
                mock_home.return_value = Path(tmpdir)
                manager = TunnelManager()

                # Create a tunnel on port 8188
                tunnel1 = SSHTunnel(
                    pod_id="pod1",
                    local_port=8188,
                    remote_port=8188,
                    ssh_connection_string="test@host"
                )
                manager.tunnels["pod1"] = tunnel1

                # Mock _is_port_in_use to return True for port 8188
                with patch.object(manager, '_is_port_in_use', return_value=True):
                    # Try to create another tunnel on same port
                    conflict_detected = False
                    try:
                        manager.create_tunnel(
                            pod_id="pod2",
                            ssh_connection_string="test2@host",
                            local_port=8188,
                            remote_port=8188
                        )
                    except RuntimeError as e:
                        if "already in use" in str(e):
                            conflict_detected = True

                    all_passed &= print_result(
                        conflict_detected,
                        "Port conflict detection works"
                    )
    except Exception as e:
        all_passed &= print_result(False, f"Port conflict detection failed: {e}")

    return all_passed


# =============================================================================
# Task 3.0: ComfyUI Client Module Tests
# =============================================================================

def test_task_3_0_comfyui_client():
    """Test Task 3.0: ComfyUI API client module."""
    print_test_header("Task 3.0: ComfyUI Client Module Tests")

    all_passed = True

    # Test 3.3: ComfyUIClient initialization
    console.print("[bold]Test 3.3: ComfyUIClient initialization[/bold]")
    try:
        client = ComfyUIClient(base_url="http://localhost:8188")

        all_passed &= print_result(
            client.base_url == "http://localhost:8188",
            "Base URL set correctly"
        )
        all_passed &= print_result(
            hasattr(client, 'is_ready'),
            "Client has is_ready() method"
        )
        all_passed &= print_result(
            hasattr(client, 'get_system_stats'),
            "Client has get_system_stats() method"
        )
        all_passed &= print_result(
            hasattr(client, 'get_queue_info'),
            "Client has get_queue_info() method"
        )
        all_passed &= print_result(
            hasattr(client, 'get_history'),
            "Client has get_history() method"
        )
    except Exception as e:
        all_passed &= print_result(False, f"ComfyUIClient initialization failed: {e}")

    # Test 3.4-3.9: API methods (with mocked responses)
    console.print("\n[bold]Test 3.4-3.9: API methods (mocked)[/bold]")
    try:
        client = ComfyUIClient(base_url="http://localhost:8188")

        # Mock requests.get
        with patch('requests.get') as mock_get:
            # Test is_ready()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"devices": []}
            mock_get.return_value = mock_response

            result = client.is_ready()
            all_passed &= print_result(
                result == True,
                "is_ready() returns True on success"
            )

            # Test get_system_stats()
            mock_response.json.return_value = {
                "system": {"ram_total": 32000000000},
                "devices": [{"name": "NVIDIA RTX A40"}]
            }
            stats = client.get_system_stats()
            all_passed &= print_result(
                stats is not None and "system" in stats,
                "get_system_stats() returns valid data"
            )

            # Test get_queue_info()
            mock_response.json.return_value = {
                "queue_running": [],
                "queue_pending": []
            }
            queue = client.get_queue_info()
            all_passed &= print_result(
                queue is not None and "queue_running" in queue,
                "get_queue_info() returns valid data"
            )

            # Test get_history()
            mock_response.json.return_value = {}
            history = client.get_history()
            all_passed &= print_result(
                history is not None,
                "get_history() returns valid data"
            )
    except Exception as e:
        all_passed &= print_result(False, f"API methods test failed: {e}")

    # Test 3.9-3.11: Error handling
    console.print("\n[bold]Test 3.9-3.11: Error handling[/bold]")
    try:
        client = ComfyUIClient(base_url="http://localhost:9999")  # Non-existent

        # Test ConnectionError handling
        with patch('requests.get') as mock_get:
            from requests.exceptions import ConnectionError
            mock_get.side_effect = ConnectionError("Connection refused")

            result = client.is_ready()
            all_passed &= print_result(
                result == False,
                "is_ready() returns False on ConnectionError"
            )

            # Test Timeout handling
            from requests.exceptions import Timeout
            mock_get.side_effect = Timeout("Request timed out")

            result = client.is_ready()
            all_passed &= print_result(
                result == False,
                "is_ready() returns False on Timeout"
            )
    except Exception as e:
        all_passed &= print_result(False, f"Error handling test failed: {e}")

    return all_passed


# =============================================================================
# Task 4.0: Tunnel CLI Commands Tests
# =============================================================================

def test_task_4_0_tunnel_cli():
    """Test Task 4.0: Tunnel CLI commands."""
    print_test_header("Task 4.0: Tunnel CLI Commands Tests")

    all_passed = True

    console.print("[bold]Test 4.1-4.2: CLI imports and structure[/bold]")
    try:
        # Check if CLI imports tunnel modules
        from autopod.cli import tunnel, tunnel_start, tunnel_stop, tunnel_list

        all_passed &= print_result(
            tunnel is not None,
            "tunnel() command group exists"
        )
        all_passed &= print_result(
            tunnel_start is not None,
            "tunnel start subcommand exists"
        )
        all_passed &= print_result(
            tunnel_stop is not None,
            "tunnel stop subcommand exists"
        )
        all_passed &= print_result(
            tunnel_list is not None,
            "tunnel list subcommand exists"
        )
    except ImportError as e:
        all_passed &= print_result(False, f"CLI imports failed: {e}")

    console.print("\n[bold]Note:[/bold] Full CLI integration tests require a live pod.")
    console.print("Manual testing recommended for:")
    console.print("  - autopod tunnel start <pod-id>")
    console.print("  - autopod tunnel list")
    console.print("  - autopod tunnel stop <pod-id>")
    console.print("  - autopod tunnel cleanup")

    return all_passed


# =============================================================================
# Main Test Runner
# =============================================================================

def main():
    """Run all tests."""
    console.print("\n[bold magenta]V1.2 Tasks 2.0, 3.0, 4.0 Test Suite[/bold magenta]")
    console.print("[dim]Testing tunnel module, ComfyUI client, and CLI commands[/dim]\n")

    results = {}

    # Run tests
    results["Task 2.0 (Tunnel Module)"] = test_task_2_0_tunnel_module()
    results["Task 3.0 (ComfyUI Client)"] = test_task_3_0_comfyui_client()
    results["Task 4.0 (Tunnel CLI)"] = test_task_4_0_tunnel_cli()

    # Print summary
    print_test_header("Test Summary")

    all_passed = True
    for task_name, passed in results.items():
        status = "[green]✓ PASSED[/green]" if passed else "[red]✗ FAILED[/red]"
        console.print(f"{task_name}: {status}")
        all_passed &= passed

    console.print()
    if all_passed:
        console.print("[bold green]All tests passed! ✓[/bold green]")
        sys.exit(0)
    else:
        console.print("[bold red]Some tests failed! ✗[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
