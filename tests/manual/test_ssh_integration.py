#!/usr/bin/env python3
"""Comprehensive SSH integration test against real RunPod pod.

Tests SSH tunnel and shell functionality with a real pod:
1. Create pod with ComfyUI template (port 8188 exposed)
2. Parse SSH connection string
3. Create SSH tunnel (localhost:8188 -> pod:8188)
4. Verify tunnel is alive and ready
5. Test SSH command execution (non-interactive)
6. Close tunnel cleanly
7. Terminate pod

Uses RTX A5000 (cheapest at ~$0.11/hr spot).
Total expected cost: < $0.01
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from autopod.config import load_config
from autopod.providers import RunPodProvider
from autopod.ssh import SSHTunnel, open_shell, parse_ssh_connection_string
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
    """Run comprehensive SSH integration tests."""
    console.print(Panel.fit(
        "[bold yellow]⚠️  SSH Integration Test - REAL API CALLS[/bold yellow]\n"
        "[dim]Testing SSH tunnel and shell access with real pod[/dim]\n"
        "[dim]Expected cost: < $0.01[/dim]",
        border_style="yellow"
    ))

    results = {}
    pod_id = None
    tunnel = None

    try:
        # Load config
        config = load_config()
        api_key = config["providers"]["runpod"]["api_key"]
        ssh_key_path = config["providers"]["runpod"]["ssh_key_path"]

        # Create provider
        provider = RunPodProvider(api_key=api_key)

        # ===== TEST 1: Create pod with ComfyUI template =====
        def test_create_pod():
            nonlocal pod_id
            console.print("\n[yellow]Creating pod with ComfyUI template...[/yellow]")
            console.print("[dim]Template: runpod/comfyui:latest (port 8188 exposed)[/dim]")

            pod_config = {
                "gpu_type": "RTX A5000",
                "gpu_count": 1,
                "template": "runpod/comfyui:latest",  # ComfyUI with port 8188
                "cloud_type": "ALL",
                "disk_size_gb": 10,
            }
            pod_id = provider.create_pod(pod_config)
            assert pod_id, "Pod ID is empty"
            console.print(f"  Pod ID: {pod_id}")
            return pod_id

        success, pod_id = test_method("create_pod()", test_create_pod)
        results["create_pod"] = success
        if not success:
            console.print("[red]Cannot continue without pod[/red]")
            return

        # Wait for pod to initialize and SSH to become available
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

        console.print("\n[yellow]Waiting for container to start and SSH to become available...[/yellow]")
        console.print("[dim]ComfyUI containers can take 2-5 minutes for dependency installation[/dim]")
        console.print("[dim]Cold starts are slower than restarts[/dim]\n")

        # ===== TEST 2: Get SSH connection string (with retry) =====
        def test_get_ssh_connection():
            max_attempts = 36  # 36 attempts * 5 seconds = 180 seconds (3 minutes)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task(
                    "[cyan]Waiting for SSH...",
                    total=max_attempts
                )

                for attempt in range(1, max_attempts + 1):
                    try:
                        # Update progress
                        progress.update(
                            task,
                            completed=attempt,
                            description=f"[cyan]Attempt {attempt}/{max_attempts} - Checking SSH..."
                        )

                        conn_str = provider.get_ssh_connection_string(pod_id)
                        assert "@" in conn_str, "Invalid connection string format"
                        assert ":" in conn_str, "Missing port in connection string"

                        # Success!
                        progress.update(task, description="[green]✓ SSH Available!")
                        console.print(f"\n[green]✓ SSH ready after {attempt * 5} seconds ({attempt} attempts)[/green]")
                        console.print(f"  Connection: {conn_str}")
                        return conn_str

                    except RuntimeError as e:
                        if "not available" in str(e) and attempt < max_attempts:
                            # SSH not ready yet, wait and retry
                            progress.update(
                                task,
                                description=f"[yellow]Container initializing... (attempt {attempt}/{max_attempts})"
                            )
                            time.sleep(5)
                            continue
                        else:
                            # Either different error or last attempt
                            progress.update(task, description="[red]✗ SSH timeout")
                            raise

            raise RuntimeError(f"SSH not available after {max_attempts * 5} seconds (3 minutes)")

        success, conn_str = test_method("get_ssh_connection_string() [with retry]", test_get_ssh_connection)
        results["get_ssh_connection_string"] = success
        if not success:
            console.print("[red]Cannot continue without SSH connection info[/red]")
            return

        # ===== TEST 3: Parse SSH connection string =====
        def test_parse_connection():
            parsed = parse_ssh_connection_string(conn_str)
            assert "user" in parsed, "Missing user"
            assert "host" in parsed, "Missing host"
            assert "port" in parsed, "Missing port"
            assert isinstance(parsed["port"], int), "Port should be integer"
            console.print(f"  User: {parsed['user']}")
            console.print(f"  Host: {parsed['host']}")
            console.print(f"  Port: {parsed['port']}")
            return parsed

        success, ssh_info = test_method("parse_ssh_connection_string()", test_parse_connection)
        results["parse_ssh_connection_string"] = success
        if not success:
            return

        # ===== TEST 4: Create SSH tunnel =====
        def test_create_tunnel():
            nonlocal tunnel
            console.print("\n[yellow]Creating SSH tunnel to port 8188...[/yellow]")

            tunnel = SSHTunnel(
                ssh_host=ssh_info["host"],
                ssh_port=ssh_info["port"],  # None for RunPod proxy
                local_port=8188,
                remote_port=8188,
                ssh_key_path=ssh_key_path,
                ssh_user=ssh_info["user"]
            )

            result = tunnel.create_tunnel(timeout=30)
            assert result is True, "Tunnel creation failed"
            port_info = f":{ssh_info['port']}" if ssh_info['port'] else ""
            console.print(f"  Tunnel: localhost:8188 -> {ssh_info['user']}@{ssh_info['host']}{port_info} (remote:8188)")
            return tunnel

        success, tunnel = test_method("SSHTunnel.create_tunnel()", test_create_tunnel)
        results["create_tunnel"] = success
        if not success:
            console.print("[yellow]Skipping tunnel tests (tunnel creation failed)[/yellow]")
        else:
            # ===== TEST 5: Check tunnel is alive =====
            def test_tunnel_alive():
                alive = tunnel.is_alive()
                assert alive is True, "Tunnel process not running"
                console.print(f"  Tunnel process alive: PID {tunnel.process.pid}")
                return alive

            success, _ = test_method("SSHTunnel.is_alive()", test_tunnel_alive)
            results["is_alive"] = success

            # ===== TEST 6: Verify tunnel connection ready =====
            def test_tunnel_ready():
                # Tunnel should already be ready from create_tunnel()
                # But let's verify again
                ready = tunnel.wait_for_connection(timeout=5)
                assert ready is True, "Tunnel not ready for connections"
                console.print(f"  Port 8188 accepting connections")
                return ready

            success, _ = test_method("SSHTunnel.wait_for_connection()", test_tunnel_ready)
            results["wait_for_connection"] = success

            # ===== TEST 7: Test SSH command execution (non-interactive) =====
            def test_ssh_command():
                import subprocess

                console.print("\n[yellow]Testing SSH command execution...[/yellow]")

                # Build SSH command (handle RunPod proxy format without port)
                cmd = ["ssh"]

                # Add port if specified (legacy format)
                if ssh_info["port"] is not None:
                    cmd.extend(["-p", str(ssh_info["port"])])

                # Add SSH key and options
                cmd.extend([
                    "-i", ssh_key_path,
                    "-o", "StrictHostKeyChecking=accept-new",
                    "-o", "ConnectTimeout=10",
                    f"{ssh_info['user']}@{ssh_info['host']}",
                    "echo 'SSH connection successful' && hostname"
                ])

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=15
                )

                assert result.returncode == 0, f"SSH command failed: {result.stderr}"
                console.print(f"  Output: {result.stdout.strip()}")
                return result.stdout

            success, output = test_method("SSH command execution", test_ssh_command)
            results["ssh_command"] = success

            # ===== TEST 8: Close tunnel gracefully =====
            def test_close_tunnel():
                tunnel.close()
                # Verify process is gone
                alive = tunnel.is_alive()
                assert alive is False, "Tunnel still running after close"
                assert tunnel.process is None, "Process reference not cleared"
                console.print(f"  Tunnel closed successfully")
                return True

            success, _ = test_method("SSHTunnel.close()", test_close_tunnel)
            results["close_tunnel"] = success

        # ===== TEST 9: Terminate pod =====
        def test_terminate():
            success = provider.terminate_pod(pod_id)
            assert success, "Terminate pod failed"
            console.print(f"  Pod {pod_id} terminated")
            return success

        success, _ = test_method("terminate_pod()", test_terminate)
        results["terminate_pod"] = success

        # Verify termination
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
        # Make sure tunnel is closed
        if tunnel and tunnel.is_alive():
            console.print(f"\n[yellow]Ensuring tunnel is closed...[/yellow]")
            try:
                tunnel.close()
                console.print("✓ Tunnel closed")
            except:
                console.print("[dim]Error closing tunnel[/dim]")

        # Make sure pod is cleaned up
        if pod_id:
            console.print(f"\n[yellow]Ensuring pod {pod_id} is terminated...[/yellow]")
            try:
                provider.terminate_pod(pod_id)
                console.print("✓ Cleanup complete")
            except:
                console.print("[dim]Pod already terminated or error cleaning up[/dim]")

    # Print summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]SSH Integration Test Results[/bold cyan]")
    console.print("="*60 + "\n")

    from rich.table import Table
    table = Table(title="SSH Integration Test Results")
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
        console.print("\n[bold green]✓ ALL SSH TESTS PASSED[/bold green]")
        console.print("[dim]SSH tunnel functionality is fully operational![/dim]")
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
