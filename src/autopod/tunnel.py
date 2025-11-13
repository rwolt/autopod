"""SSH tunnel management for autopod.

This module provides persistent SSH tunnel management to access pod services
(like ComfyUI) running on remote GPU providers via local port forwarding.

Design Philosophy:
- Tunnels persist across autopod sessions (survive terminal closure)
- State saved to ~/.autopod/tunnels.json for reconnection
- SSH processes run independently of autopod process
- Auto-cleanup when pods terminate (smart automation)
- Explicit control via CLI commands (list, stop, cleanup)
- Security features: idle timeouts, warnings, audit trail

Example:
    >>> manager = TunnelManager()
    >>> tunnel = manager.create_tunnel(
    ...     pod_id="abc123",
    ...     ssh_connection_string="abc123-xyz@ssh.runpod.io",
    ...     local_port=8188,
    ...     remote_port=8188
    ... )
    >>> tunnel.start()
    >>> # Close terminal, reopen later
    >>> manager = TunnelManager()  # Reconnects to existing tunnels
    >>> tunnel = manager.get_tunnel("abc123")
    >>> tunnel.is_active()  # True
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, List
import requests
import psutil

logger = logging.getLogger(__name__)


class SSHTunnel:
    """Manages a single SSH tunnel to a pod.

    An SSH tunnel forwards a local port to a remote port on the pod,
    allowing access to pod services (like ComfyUI on port 8188) via
    localhost.

    Tunnels are persistent - they continue running even after the
    autopod process exits. Use TunnelManager to reconnect to existing
    tunnels.

    Attributes:
        pod_id: Unique pod identifier
        ssh_connection_string: Full SSH connection string (e.g., "pod-id-machine@ssh.runpod.io")
        local_port: Local port to bind (e.g., 8188)
        remote_port: Remote port to forward (e.g., 8188 for ComfyUI)
        ssh_key_path: Path to SSH private key (optional, uses ssh-agent if not specified)
        process: subprocess.Popen object for the SSH tunnel
        pid: Process ID of the SSH tunnel (for reconnection)
    """

    def __init__(
        self,
        pod_id: str,
        ssh_connection_string: str,
        local_port: int,
        remote_port: int,
        ssh_key_path: Optional[str] = None,
        pid: Optional[int] = None
    ):
        """Initialize SSH tunnel configuration.

        Args:
            pod_id: Unique pod identifier
            ssh_connection_string: SSH connection string (e.g., "user@host")
            local_port: Local port to bind
            remote_port: Remote port to forward
            ssh_key_path: Path to SSH private key (optional)
            pid: Existing process ID (for reconnection)
        """
        self.pod_id = pod_id
        self.ssh_connection_string = ssh_connection_string
        self.local_port = local_port
        self.remote_port = remote_port
        self.ssh_key_path = ssh_key_path
        self.process: Optional[subprocess.Popen] = None
        self.pid = pid

        # If PID provided, try to reconnect to existing process
        if pid and psutil.pid_exists(pid):
            try:
                self.process = psutil.Process(pid)
                logger.debug(f"Reconnected to existing tunnel: pod={pod_id}, pid={pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.warning(f"Could not reconnect to tunnel PID {pid}")
                self.pid = None

        logger.debug(
            f"SSHTunnel initialized: pod={pod_id}, "
            f"local={local_port}, remote={remote_port}"
        )

    def start(self) -> bool:
        """Start the SSH tunnel.

        Creates an SSH tunnel using subprocess with port forwarding:
        localhost:{local_port} -> pod:{remote_port}

        The tunnel runs as an independent background process that persists
        even after autopod exits.

        Returns:
            True if tunnel started successfully, False otherwise

        Raises:
            RuntimeError: If tunnel is already running
        """
        if self.is_active():
            raise RuntimeError(
                f"Tunnel for pod {self.pod_id} is already running (PID: {self.pid})"
            )

        logger.info(
            f"Starting SSH tunnel for pod {self.pod_id}: "
            f"localhost:{self.local_port} -> {self.remote_port}"
        )

        # Build SSH command
        # -N: No remote command (just forwarding)
        # -L: Local port forwarding
        # -o ServerAliveInterval=60: Keep connection alive
        # -o ServerAliveCountMax=3: Max failed keepalives before disconnect
        # -o ExitOnForwardFailure=yes: Exit if port forwarding fails
        # -o StrictHostKeyChecking=no: Accept new host keys automatically
        #
        # NOTE: We intentionally do NOT use -i flag here, even if ssh_key_path is provided.
        # This allows SSH to use ssh-agent, which handles passphrase-protected keys seamlessly.
        # The user must run `ssh-add <key>` before starting tunnels.
        cmd = [
            "ssh",
            "-N",
            "-L", f"{self.local_port}:localhost:{self.remote_port}",
            "-o", "ServerAliveInterval=60",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "StrictHostKeyChecking=no",
        ]

        # Add connection string
        cmd.append(self.ssh_connection_string)

        logger.debug(f"SSH command: {' '.join(cmd)}")

        try:
            # Start SSH tunnel as background process
            # Process runs independently of autopod
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent process
            )

            self.pid = self.process.pid

            # Give tunnel time to establish
            time.sleep(2)

            # Check if process is still running
            if self.process.poll() is not None:
                # Process died immediately
                _, stderr = self.process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"SSH tunnel failed to start: {error_msg}")
                self.pid = None
                return False

            logger.info(
                f"SSH tunnel started successfully: "
                f"localhost:{self.local_port} -> pod {self.pod_id}:{self.remote_port} "
                f"(PID: {self.pid})"
            )
            return True

        except Exception as e:
            logger.exception(f"Failed to start SSH tunnel: {e}")
            self.pid = None
            return False

    def is_active(self) -> bool:
        """Check if the SSH tunnel process is running.

        Works even if autopod was restarted - checks if PID exists in system.

        Returns:
            True if tunnel process is active, False otherwise
        """
        if self.pid is None:
            return False

        # Check if PID exists in system
        if not psutil.pid_exists(self.pid):
            return False

        # Verify it's actually an SSH process (not a recycled PID)
        try:
            proc = psutil.Process(self.pid)
            cmdline = " ".join(proc.cmdline())

            # Check if it's our SSH tunnel
            if "ssh" in cmdline.lower() and str(self.local_port) in cmdline:
                return True
            else:
                logger.warning(f"PID {self.pid} exists but is not our SSH tunnel")
                return False

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def test_connectivity(self, timeout: int = 5) -> bool:
        """Test if the tunnel is working by making an HTTP request.

        Attempts to connect to localhost:{local_port} to verify the tunnel
        is forwarding traffic correctly.

        Args:
            timeout: Request timeout in seconds (default: 5)

        Returns:
            True if tunnel is responding, False otherwise
        """
        if not self.is_active():
            logger.warning(
                f"Cannot test connectivity: tunnel for pod {self.pod_id} is not active"
            )
            return False

        try:
            # Try to connect to localhost on the tunnel port
            # Just checking if *something* responds (don't care about HTTP errors)
            url = f"http://localhost:{self.local_port}"
            logger.debug(f"Testing tunnel connectivity: {url}")

            response = requests.get(url, timeout=timeout)

            # Any HTTP response (even 404) means tunnel is working
            logger.info(
                f"Tunnel connectivity test passed: {url} returned {response.status_code}"
            )
            return True

        except requests.exceptions.ConnectionError:
            logger.warning(
                f"Tunnel connectivity test failed: connection refused on port {self.local_port}"
            )
            return False
        except requests.exceptions.Timeout:
            logger.warning(f"Tunnel connectivity test failed: timeout after {timeout}s")
            return False
        except Exception as e:
            logger.warning(f"Tunnel connectivity test failed: {e}")
            return False

    def stop(self) -> bool:
        """Stop the SSH tunnel.

        Terminates the SSH tunnel process gracefully.

        Returns:
            True if tunnel stopped successfully, False otherwise
        """
        if not self.is_active():
            logger.warning(f"Tunnel for pod {self.pod_id} is not running")
            return False

        logger.info(f"Stopping SSH tunnel for pod {self.pod_id} (PID: {self.pid})")

        try:
            proc = psutil.Process(self.pid)

            # Try graceful termination first
            proc.terminate()

            # Wait up to 5 seconds for process to exit
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Force kill if graceful termination failed
                logger.warning(f"Force killing SSH tunnel for pod {self.pod_id}")
                proc.kill()
                proc.wait()

            logger.info(f"SSH tunnel stopped: pod {self.pod_id}")
            self.pid = None
            return True

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Could not stop tunnel: {e}")
            return False

    def get_status(self) -> Dict:
        """Get tunnel status information.

        Returns:
            Dictionary with tunnel status:
            {
                "pod_id": str,
                "local_port": int,
                "remote_port": int,
                "active": bool,
                "pid": int or None,
                "ssh_connection": str
            }
        """
        return {
            "pod_id": self.pod_id,
            "local_port": self.local_port,
            "remote_port": self.remote_port,
            "active": self.is_active(),
            "pid": self.pid,
            "ssh_connection": self.ssh_connection_string
        }

    def to_dict(self) -> Dict:
        """Serialize tunnel state for persistence.

        Returns:
            Dictionary suitable for JSON serialization
        """
        return {
            "pod_id": self.pod_id,
            "ssh_connection_string": self.ssh_connection_string,
            "local_port": self.local_port,
            "remote_port": self.remote_port,
            "ssh_key_path": self.ssh_key_path,
            "pid": self.pid
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SSHTunnel":
        """Deserialize tunnel state from persistence.

        Args:
            data: Dictionary from JSON

        Returns:
            SSHTunnel instance
        """
        return cls(
            pod_id=data["pod_id"],
            ssh_connection_string=data["ssh_connection_string"],
            local_port=data["local_port"],
            remote_port=data["remote_port"],
            ssh_key_path=data.get("ssh_key_path"),
            pid=data.get("pid")
        )


class TunnelManager:
    """Manages multiple SSH tunnels with persistence.

    TunnelManager handles:
    - Creating and tracking tunnels
    - Persisting tunnel state to ~/.autopod/tunnels.json
    - Reconnecting to existing tunnels after autopod restarts
    - Cleaning up stale/dead tunnels
    - Port conflict detection

    Example:
        >>> manager = TunnelManager()
        >>> tunnel = manager.create_tunnel("pod-abc", "user@host", 8188, 8188)
        >>> tunnel.start()
        >>> # ... later, in new session ...
        >>> manager = TunnelManager()  # Auto-loads existing tunnels
        >>> tunnel = manager.get_tunnel("pod-abc")
        >>> tunnel.is_active()  # True!
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize TunnelManager.

        Args:
            config_dir: Configuration directory (default: ~/.autopod)
        """
        if config_dir is None:
            config_dir = Path.home() / ".autopod"

        self.config_dir = config_dir
        self.state_file = config_dir / "tunnels.json"

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Load existing tunnels from disk
        self.tunnels: Dict[str, SSHTunnel] = self._load_state()

        logger.debug(f"TunnelManager initialized with {len(self.tunnels)} tunnels")

    def _load_state(self) -> Dict[str, SSHTunnel]:
        """Load tunnel state from disk.

        Reconnects to existing SSH processes if they're still alive.

        Returns:
            Dictionary of pod_id -> SSHTunnel
        """
        if not self.state_file.exists():
            logger.debug("No existing tunnel state found")
            return {}

        try:
            data = json.loads(self.state_file.read_text())
            tunnels = {}

            for pod_id, info in data.items():
                try:
                    tunnel = SSHTunnel.from_dict(info)

                    # Only keep tunnel if SSH process is still alive
                    if tunnel.is_active():
                        tunnels[pod_id] = tunnel
                        logger.info(f"Reconnected to tunnel: {pod_id} (PID: {tunnel.pid})")
                    else:
                        logger.info(f"Removing stale tunnel: {pod_id}")

                except Exception as e:
                    logger.warning(f"Could not restore tunnel {pod_id}: {e}")

            return tunnels

        except Exception as e:
            logger.error(f"Failed to load tunnel state: {e}")
            return {}

    def _save_state(self) -> None:
        """Save tunnel state to disk.

        Only saves tunnels that are currently active.
        """
        try:
            # Only persist active tunnels
            data = {}
            for pod_id, tunnel in self.tunnels.items():
                if tunnel.is_active():
                    data[pod_id] = tunnel.to_dict()

            self.state_file.write_text(json.dumps(data, indent=2))
            logger.debug(f"Saved {len(data)} tunnel(s) to {self.state_file}")

        except Exception as e:
            logger.error(f"Failed to save tunnel state: {e}")

    def create_tunnel(
        self,
        pod_id: str,
        ssh_connection_string: str,
        local_port: int,
        remote_port: int,
        ssh_key_path: Optional[str] = None
    ) -> SSHTunnel:
        """Create a new SSH tunnel.

        Args:
            pod_id: Unique pod identifier
            ssh_connection_string: SSH connection string (e.g., "user@host")
            local_port: Local port to bind
            remote_port: Remote port to forward
            ssh_key_path: Path to SSH private key (optional)

        Returns:
            SSHTunnel instance

        Raises:
            RuntimeError: If tunnel already exists for pod or port conflict
        """
        # Check if tunnel already exists for this pod
        if pod_id in self.tunnels and self.tunnels[pod_id].is_active():
            raise RuntimeError(
                f"Tunnel already exists for pod {pod_id} "
                f"on port {self.tunnels[pod_id].local_port}"
            )

        # Check for port conflicts
        if self._is_port_in_use(local_port):
            raise RuntimeError(
                f"Port {local_port} is already in use. "
                f"Choose a different port or stop the existing tunnel."
            )

        tunnel = SSHTunnel(
            pod_id=pod_id,
            ssh_connection_string=ssh_connection_string,
            local_port=local_port,
            remote_port=remote_port,
            ssh_key_path=ssh_key_path
        )

        self.tunnels[pod_id] = tunnel
        return tunnel

    def get_tunnel(self, pod_id: str) -> Optional[SSHTunnel]:
        """Get tunnel by pod ID.

        Args:
            pod_id: Pod identifier

        Returns:
            SSHTunnel if exists, None otherwise
        """
        return self.tunnels.get(pod_id)

    def list_tunnels(self) -> List[SSHTunnel]:
        """Get list of all tunnels.

        Returns:
            List of SSHTunnel instances
        """
        return list(self.tunnels.values())

    def remove_tunnel(self, pod_id: str) -> bool:
        """Remove tunnel from tracking.

        Does NOT stop the tunnel - use tunnel.stop() first.

        Args:
            pod_id: Pod identifier

        Returns:
            True if tunnel was removed, False if not found
        """
        if pod_id in self.tunnels:
            del self.tunnels[pod_id]
            self._save_state()
            logger.info(f"Removed tunnel: {pod_id}")
            return True
        return False

    def cleanup_stale_tunnels(self) -> int:
        """Remove tunnels for dead SSH processes.

        Returns:
            Number of stale tunnels removed
        """
        stale_pods = []

        for pod_id, tunnel in self.tunnels.items():
            if not tunnel.is_active():
                stale_pods.append(pod_id)

        for pod_id in stale_pods:
            self.remove_tunnel(pod_id)
            logger.info(f"Cleaned up stale tunnel: {pod_id}")

        if stale_pods:
            self._save_state()

        return len(stale_pods)

    def stop_all_tunnels(self) -> int:
        """Stop all active tunnels.

        Returns:
            Number of tunnels stopped
        """
        stopped = 0

        for tunnel in self.tunnels.values():
            if tunnel.is_active():
                if tunnel.stop():
                    stopped += 1

        # Clean up state
        self.tunnels.clear()
        self._save_state()

        return stopped

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a local port is already in use by any tunnel.

        Args:
            port: Port number to check

        Returns:
            True if port is in use, False otherwise
        """
        for tunnel in self.tunnels.values():
            if tunnel.local_port == port and tunnel.is_active():
                return True
        return False
