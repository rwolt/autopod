"""Pod control and state management for autopod.

This module provides high-level pod management functionality including
listing pods, getting detailed info, stopping, terminating, and SSH access.
"""

import logging
from typing import List, Dict, Optional
from pathlib import Path
import json

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from autopod.providers.base import CloudProvider
from autopod.ssh import open_shell, parse_ssh_connection_string

logger = logging.getLogger(__name__)


class PodManager:
    """High-level pod management interface.

    Provides user-friendly methods for managing pods with Rich formatting
    and state persistence.

    Example:
        >>> from autopod.providers import RunPodProvider
        >>> from autopod.pod_manager import PodManager
        >>>
        >>> provider = RunPodProvider(api_key="...")
        >>> manager = PodManager(provider)
        >>>
        >>> # List all pods
        >>> manager.list_pods()
        >>>
        >>> # Get detailed info
        >>> manager.get_pod_info("pod-123")
        >>>
        >>> # SSH into pod
        >>> manager.shell_into_pod("pod-123")
    """

    def __init__(self, provider: CloudProvider, console: Optional[Console] = None):
        """Initialize pod manager.

        Args:
            provider: Cloud provider instance (e.g., RunPodProvider)
            console: Rich console for output (creates new one if not provided)
        """
        self.provider = provider
        self.console = console if console else Console()
        self.state_file = Path.home() / ".autopod" / "pods.json"
        logger.debug(f"PodManager initialized with provider: {provider.__class__.__name__}")

    def list_pods(self, show_table: bool = True) -> List[Dict]:
        """List all pods with formatted table output.

        Args:
            show_table: Whether to print Rich table (default: True)

        Returns:
            List of pod status dictionaries

        Example:
            >>> manager.list_pods()
            ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
            ┃ Pod ID       ┃ Status     ┃ GPU        ┃ Runtime    ┃ Cost       ┃
            ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
            │ abc-123      │ RUNNING    │ 1x RTX A40 │ 12.3 min   │ $0.0821    │
            │ def-456      │ STOPPED    │ 2x RTX A40 │ 45.2 min   │ $0.6027    │
            └──────────────┴────────────┴────────────┴────────────┴────────────┘
        """
        logger.info("Listing all pods")

        try:
            # Load pod state to get all known pod IDs
            pod_state = self.load_pod_state()

            if not pod_state:
                if show_table:
                    self.console.print("[yellow]No pods found[/yellow]")
                return []

            # Get status for each pod and track stale pods
            pods_info = []
            stale_pods = []

            for pod_id in pod_state.keys():
                try:
                    status = self.provider.get_pod_status(pod_id)
                    pods_info.append(status)
                except RuntimeError as e:
                    # Check if this is a "pod not found" error (stale pod)
                    if "not found" in str(e).lower():
                        logger.info(f"Removing stale pod from cache: {pod_id}")
                        self._remove_pod_from_state(pod_id)
                        stale_pods.append(pod_id)
                    else:
                        # Other runtime errors - log and skip
                        logger.warning(f"Could not get status for pod {pod_id}: {e}")
                except Exception as e:
                    # Network errors or other issues - log but don't remove from cache
                    logger.warning(f"Could not get status for pod {pod_id}: {e}")

            # Notify user if stale pods were cleaned up
            if stale_pods and show_table:
                self.console.print(
                    f"[yellow]Removed {len(stale_pods)} stale pod(s) from cache[/yellow]"
                )
                logger.info(f"Cleaned up stale pods: {', '.join(stale_pods)}")

            # Check if we have any pods left after cleanup
            if not pods_info:
                if show_table:
                    self.console.print("[yellow]No pods found[/yellow]")
                return []

            if show_table:
                self._print_pods_table(pods_info)

            return pods_info

        except Exception as e:
            logger.error(f"Error listing pods: {e}", exc_info=True)
            if show_table:
                self.console.print(f"[red]Error listing pods: {e}[/red]")
            return []

    def get_pod_info(self, pod_id: str, show_panel: bool = True) -> Optional[Dict]:
        """Get detailed information about a specific pod.

        Args:
            pod_id: Pod identifier
            show_panel: Whether to print Rich panel (default: True)

        Returns:
            Pod status dictionary or None if not found

        Example:
            >>> manager.get_pod_info("abc-123")
            ╭─── Pod: abc-123 ───────────────────────────────╮
            │ Status:       RUNNING                          │
            │ GPU:          1x RTX A40                       │
            │ Cost/hour:    $0.40                            │
            │ Runtime:      12.3 minutes                     │
            │ Total cost:   $0.0821                          │
            │ SSH:          Ready (ssh.runpod.io)            │
            ╰────────────────────────────────────────────────╯
        """
        logger.info(f"Getting info for pod: {pod_id}")

        try:
            status = self.provider.get_pod_status(pod_id)

            if show_panel:
                self._print_pod_panel(status)

            return status

        except RuntimeError as e:
            # Check if this is a "pod not found" error
            if "not found" in str(e).lower():
                logger.info(f"Pod {pod_id} not found")
                if show_panel:
                    self.console.print(f"[red]✗ Pod {pod_id} not found[/red]")
                    self.console.print("[dim]It may have been terminated. Run 'autopod ls' to see available pods.[/dim]")
            else:
                logger.error(f"Error getting pod info: {e}", exc_info=True)
                if show_panel:
                    self.console.print(f"[red]Error getting pod info: {e}[/red]")
            return None
        except Exception as e:
            logger.error(f"Error getting pod info: {e}", exc_info=True)
            if show_panel:
                self.console.print(f"[red]Error getting pod info: {e}[/red]")
            return None

    def stop_pod(self, pod_id: str) -> bool:
        """Stop (pause) a running pod.

        Stopped pods do not incur compute charges but retain their disk state.
        They can be restarted later.

        Args:
            pod_id: Pod identifier

        Returns:
            True if successful, False otherwise

        Example:
            >>> manager.stop_pod("abc-123")
            ✓ Pod abc-123 stopped successfully
        """
        logger.info(f"Stopping pod: {pod_id}")

        try:
            success = self.provider.stop_pod(pod_id)

            if success:
                self.console.print(f"[green]✓ Pod {pod_id} stopped successfully[/green]")
            else:
                self.console.print(f"[yellow]⚠ Failed to stop pod {pod_id}[/yellow]")

            return success

        except Exception as e:
            logger.error(f"Error stopping pod: {e}", exc_info=True)
            self.console.print(f"[red]✗ Error stopping pod: {e}[/red]")
            return False

    def start_pod(self, pod_id: str) -> bool:
        """Start (resume) a stopped pod.

        Resumes a previously stopped pod. Note that GPU availability is not
        guaranteed - the pod may restart with a different GPU or as CPU-only.

        Args:
            pod_id: Pod identifier

        Returns:
            True if successful, False otherwise

        Example:
            >>> manager.start_pod("abc-123")
            ✓ Pod abc-123 started successfully
            ⚠ GPU availability not guaranteed - check pod info to verify GPU type
        """
        logger.info(f"Starting pod: {pod_id}")

        try:
            success = self.provider.start_pod(pod_id)

            if success:
                self.console.print(f"[green]✓ Pod {pod_id} started successfully[/green]")
                self.console.print(
                    "[yellow]⚠ GPU availability not guaranteed - "
                    "check pod info to verify GPU type[/yellow]"
                )
            else:
                self.console.print(f"[yellow]⚠ Failed to start pod {pod_id}[/yellow]")

            return success

        except Exception as e:
            logger.error(f"Error starting pod: {e}", exc_info=True)
            self.console.print(f"[red]✗ Error starting pod: {e}[/red]")
            return False

    def terminate_pod(self, pod_id: str, confirm: bool = False) -> bool:
        """Terminate (destroy) a pod permanently.

        WARNING: This is destructive and cannot be undone. All data on the pod
        will be lost unless saved to a network volume.

        Args:
            pod_id: Pod identifier
            confirm: Whether to skip confirmation prompt

        Returns:
            True if successful, False otherwise

        Example:
            >>> manager.terminate_pod("abc-123")
            ⚠️  WARNING: This will permanently delete pod abc-123
            Continue? [y/N]: y
            ✓ Pod abc-123 terminated successfully
        """
        logger.info(f"Terminating pod: {pod_id}")

        if not confirm:
            self.console.print(
                f"[bold yellow]⚠️  WARNING: This will permanently delete pod {pod_id}[/bold yellow]"
            )
            response = input("Continue? [y/N]: ")
            if response.lower() != "y":
                self.console.print("[dim]Cancelled[/dim]")
                return False

        try:
            success = self.provider.terminate_pod(pod_id)

            if success:
                self.console.print(f"[green]✓ Pod {pod_id} terminated successfully[/green]")
                # Remove from state
                self._remove_pod_from_state(pod_id)
            else:
                self.console.print(f"[yellow]⚠ Failed to terminate pod {pod_id}[/yellow]")

            return success

        except Exception as e:
            logger.error(f"Error terminating pod: {e}", exc_info=True)
            self.console.print(f"[red]✗ Error terminating pod: {e}[/red]")
            return False

    def shell_into_pod(self, pod_id: str, ssh_key_path: Optional[str] = None) -> int:
        """Open an interactive SSH shell to a pod.

        Args:
            pod_id: Pod identifier
            ssh_key_path: Path to SSH private key (optional)

        Returns:
            Exit code from SSH session (0 = success)

        Example:
            >>> manager.shell_into_pod("abc-123")
            Opening SSH shell to abc-123...
            root@abc-123:~#
        """
        logger.info(f"Opening SSH shell to pod: {pod_id}")

        try:
            # Get SSH connection details
            conn_str = self.provider.get_ssh_connection_string(pod_id)

            ssh_info = parse_ssh_connection_string(conn_str)

            self.console.print(f"[cyan]Opening SSH shell to {pod_id}...[/cyan]")

            # Open interactive shell
            exit_code = open_shell(
                ssh_host=ssh_info["host"],
                ssh_port=ssh_info["port"],
                ssh_key_path=ssh_key_path,
                ssh_user=ssh_info["user"],
            )

            logger.info(f"SSH shell exited with code: {exit_code}")
            return exit_code

        except Exception as e:
            logger.error(f"Error opening SSH shell: {e}", exc_info=True)
            self.console.print(f"[red]✗ Error opening SSH shell: {e}[/red]")
            return 1

    def load_pod_state(self) -> Dict:
        """Load pod state from persistent storage.

        Returns:
            Dictionary mapping pod_id to metadata

        Example:
            >>> state = manager.load_pod_state()
            >>> print(state)
            {
                'abc-123': {'pod_host_id': 'abc-123-xyz', 'created_at': '2025-...'},
                'def-456': {'pod_host_id': 'def-456-abc', 'created_at': '2025-...'}
            }
        """
        if not self.state_file.exists():
            logger.debug("No pod state file found")
            return {}

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
            logger.debug(f"Loaded state for {len(state)} pods")
            return state
        except Exception as e:
            logger.error(f"Error loading pod state: {e}", exc_info=True)
            return {}

    def save_pod_state(self, pod_id: str, metadata: Dict) -> None:
        """Save pod state to persistent storage.

        Args:
            pod_id: Pod identifier
            metadata: Metadata to store (e.g., pod_host_id, created_at)

        Example:
            >>> manager.save_pod_state("abc-123", {
            ...     "pod_host_id": "abc-123-xyz",
            ...     "created_at": "2025-11-09T12:00:00"
            ... })
        """
        # Ensure directory exists
        self.state_file.parent.mkdir(exist_ok=True, mode=0o700)

        # Load existing state
        state = self.load_pod_state()

        # Update with new metadata
        state[pod_id] = metadata

        # Save back to file
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            self.state_file.chmod(0o600)
            logger.debug(f"Saved state for pod {pod_id}")
        except Exception as e:
            logger.error(f"Error saving pod state: {e}", exc_info=True)

    def _remove_pod_from_state(self, pod_id: str) -> None:
        """Remove a pod from persistent state.

        Args:
            pod_id: Pod identifier to remove
        """
        state = self.load_pod_state()
        if pod_id in state:
            del state[pod_id]

            try:
                with open(self.state_file, "w") as f:
                    json.dump(state, f, indent=2)
                self.state_file.chmod(0o600)
                logger.debug(f"Removed pod {pod_id} from state")
            except Exception as e:
                logger.error(f"Error removing pod from state: {e}", exc_info=True)

    def _print_pods_table(self, pods: List[Dict]) -> None:
        """Print formatted table of pods.

        Args:
            pods: List of pod status dictionaries
        """
        table = Table(title="Pods")

        table.add_column("Pod ID", style="cyan", no_wrap=True)
        table.add_column("Status", style="magenta")
        table.add_column("GPU", style="green")
        table.add_column("Runtime", justify="right", style="yellow")
        table.add_column("Cost", justify="right", style="red")

        for pod in pods:
            pod_id = pod.get("pod_id", "unknown")
            status = pod.get("status", "UNKNOWN")

            # Handle missing GPU metadata gracefully
            gpu_count = pod.get("gpu_count", 0)
            gpu_type = pod.get("gpu_type", "Unknown GPU")
            if gpu_count > 0:
                gpu = f"{gpu_count}x {gpu_type}"
            else:
                gpu = "N/A"

            # Handle missing runtime/cost metadata gracefully
            runtime_minutes = pod.get("runtime_minutes", 0.0)
            total_cost = pod.get("total_cost", 0.0)
            runtime = f"{runtime_minutes:.1f} min"
            cost = f"${total_cost:.4f}"

            # Color code status
            if status == "RUNNING":
                status_str = f"[green]{status}[/green]"
            elif status == "STOPPED":
                status_str = f"[yellow]{status}[/yellow]"
            elif status == "TERMINATED":
                status_str = f"[red]{status}[/red]"
            else:
                status_str = f"[dim]{status}[/dim]"

            table.add_row(pod_id, status_str, gpu, runtime, cost)

        self.console.print(table)

    def _print_pod_panel(self, pod: Dict) -> None:
        """Print formatted panel with pod details.

        Args:
            pod: Pod status dictionary
        """
        pod_id = pod.get("pod_id", "unknown")

        # Handle missing metadata gracefully
        status = pod.get("status", "UNKNOWN")
        gpu_count = pod.get("gpu_count", 0)
        gpu_type = pod.get("gpu_type", "Unknown GPU")
        cost_per_hour = pod.get("cost_per_hour", 0.0)
        runtime_minutes = pod.get("runtime_minutes", 0.0)
        total_cost = pod.get("total_cost", 0.0)

        # Format GPU display
        if gpu_count > 0:
            gpu_display = f"{gpu_count}x {gpu_type}"
        else:
            gpu_display = "N/A"

        # Build info text
        info_lines = [
            f"[bold]Status:[/bold]       {status}",
            f"[bold]GPU:[/bold]          {gpu_display}",
            f"[bold]Cost/hour:[/bold]    ${cost_per_hour:.2f}",
            f"[bold]Runtime:[/bold]      {runtime_minutes:.1f} minutes",
            f"[bold]Total cost:[/bold]   ${total_cost:.4f}",
        ]

        # Add SSH info if available
        if pod.get("ssh_ready"):
            ssh_host = pod.get("ssh_host", "N/A")
            info_lines.append(f"[bold]SSH:[/bold]          Ready ({ssh_host})")
        else:
            info_lines.append(f"[bold]SSH:[/bold]          Not ready")

        info_text = "\n".join(info_lines)

        # Color code panel based on status (already extracted above)
        if status == "RUNNING":
            border_style = "green"
        elif status == "STOPPED":
            border_style = "yellow"
        elif status == "TERMINATED":
            border_style = "red"
        else:
            border_style = "dim"

        panel = Panel(
            info_text,
            title=f"[bold]Pod: {pod_id}[/bold]",
            border_style=border_style,
        )

        self.console.print(panel)
