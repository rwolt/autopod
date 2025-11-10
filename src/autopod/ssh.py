"""SSH tunnel and shell access management for autopod.

This module provides SSH tunnel creation and management for connecting to
remote RunPod instances. Supports port forwarding (for ComfyUI API access)
and direct shell access.
"""

import subprocess
from subprocess import TimeoutExpired
import time
import socket
import logging
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class SSHTunnel:
    """Manages SSH tunnel to a remote pod for port forwarding.

    Creates an SSH tunnel that forwards a local port to a remote service
    (typically ComfyUI on port 8188).

    Example:
        >>> tunnel = SSHTunnel(
        ...     ssh_host="ssh.runpod.io",
        ...     ssh_port=12345,
        ...     local_port=8188,
        ...     remote_port=8188,
        ...     ssh_key_path="~/.ssh/id_ed25519_runpod"
        ... )
        >>> tunnel.create_tunnel()
        >>> tunnel.wait_for_connection(timeout=30)
        >>> # Now you can access http://localhost:8188
        >>> tunnel.close()
    """

    def __init__(
        self,
        ssh_host: str,
        ssh_port: Optional[int] = None,
        local_port: int = 8188,
        remote_port: int = 8188,
        ssh_key_path: Optional[str] = None,
        ssh_user: str = "root"
    ):
        """Initialize SSH tunnel configuration.

        Args:
            ssh_host: SSH host address (e.g., "ssh.runpod.io")
            ssh_port: SSH port number (optional, for legacy format)
            local_port: Local port to forward to (default: 8188)
            remote_port: Remote service port (default: 8188 for ComfyUI)
            ssh_key_path: Path to SSH private key (optional)
            ssh_user: SSH username (default: "root")
        """
        self.ssh_host = ssh_host
        self.ssh_port = ssh_port
        self.local_port = local_port
        self.remote_port = remote_port
        self.ssh_key_path = ssh_key_path
        self.ssh_user = ssh_user
        self.process: Optional[subprocess.Popen] = None

        port_info = f":{ssh_port}" if ssh_port else ""
        logger.debug(
            f"SSHTunnel initialized: {ssh_user}@{ssh_host}{port_info} "
            f"(local:{local_port} -> remote:{remote_port})"
        )

    def create_tunnel(self, timeout: int = 10) -> bool:
        """Create the SSH tunnel using subprocess.

        Starts an SSH process with port forwarding (-L flag) in the background.
        The tunnel runs in a separate process and forwards traffic from
        localhost:local_port to remote_host:remote_port.

        Args:
            timeout: Maximum time to wait for tunnel creation (seconds)

        Returns:
            True if tunnel was created successfully, False otherwise

        Raises:
            RuntimeError: If tunnel creation fails
        """
        if self.process and self.is_alive():
            logger.warning("SSH tunnel already exists and is running")
            return True

        # Build SSH command
        # -N: No remote command (just port forwarding)
        # -L: Local port forwarding
        # -o StrictHostKeyChecking=accept-new: Accept new host keys automatically
        # -o ServerAliveInterval=60: Keep connection alive
        # -o ServerAliveCountMax=3: Max missed keepalives before disconnect
        cmd = [
            "ssh",
            "-N",  # No remote command
            "-L", f"{self.local_port}:localhost:{self.remote_port}",
        ]

        # Add port if specified (legacy format)
        if self.ssh_port is not None:
            cmd.extend(["-p", str(self.ssh_port)])

        # Add connection options
        cmd.extend([
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ServerAliveInterval=60",
            "-o", "ServerAliveCountMax=3",
        ])

        # Add SSH key if provided
        if self.ssh_key_path:
            expanded_path = str(Path(self.ssh_key_path).expanduser())
            cmd.extend(["-i", expanded_path])

        # Add user@host
        cmd.append(f"{self.ssh_user}@{self.ssh_host}")

        logger.info(f"Creating SSH tunnel: localhost:{self.local_port} -> {self.ssh_host}:{self.remote_port}")
        logger.debug(f"SSH command: {' '.join(cmd)}")

        try:
            # Start SSH process in background
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )

            logger.info(f"SSH tunnel process started (PID: {self.process.pid})")

            # Wait for tunnel to be ready
            if not self.wait_for_connection(timeout=timeout):
                self.close()
                raise RuntimeError(f"SSH tunnel failed to establish within {timeout}s")

            logger.info("SSH tunnel established successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create SSH tunnel: {e}", exc_info=True)
            if self.process:
                self.close()
            raise RuntimeError(f"SSH tunnel creation failed: {e}")

    def is_alive(self) -> bool:
        """Check if the SSH tunnel process is still running.

        Returns:
            True if tunnel is running, False otherwise
        """
        if not self.process:
            return False

        # Check if process is still running
        return self.process.poll() is None

    def wait_for_connection(self, timeout: int = 30, interval: float = 0.5) -> bool:
        """Wait for the SSH tunnel to become ready for connections.

        Polls the local port to check if it's accepting connections.
        This ensures the tunnel is fully established before returning.

        Args:
            timeout: Maximum time to wait (seconds)
            interval: Time between connection attempts (seconds)

        Returns:
            True if tunnel is ready, False if timeout reached
        """
        logger.debug(f"Waiting for SSH tunnel on localhost:{self.local_port}...")

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if process is still alive
            if not self.is_alive():
                logger.error("SSH tunnel process died while waiting for connection")
                return False

            # Try to connect to local port
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', self.local_port))
                sock.close()

                if result == 0:
                    logger.debug(f"SSH tunnel ready on localhost:{self.local_port}")
                    return True

            except Exception as e:
                logger.debug(f"Connection attempt failed: {e}")

            time.sleep(interval)

        logger.warning(f"SSH tunnel not ready after {timeout}s")
        return False

    def close(self) -> None:
        """Close the SSH tunnel and cleanup resources.

        Terminates the SSH process gracefully (SIGTERM), waits briefly,
        then forces termination (SIGKILL) if needed.
        """
        if not self.process:
            logger.debug("No SSH tunnel process to close")
            return

        logger.info(f"Closing SSH tunnel (PID: {self.process.pid})")

        try:
            # Try graceful termination first
            self.process.terminate()

            # Wait up to 3 seconds for process to exit
            try:
                self.process.wait(timeout=3)
                logger.info("SSH tunnel closed gracefully")
            except TimeoutExpired:
                # Force kill if still running
                logger.warning("SSH tunnel didn't exit gracefully, forcing kill")
                self.process.kill()
                self.process.wait()
                logger.info("SSH tunnel force killed")

        except Exception as e:
            logger.error(f"Error closing SSH tunnel: {e}", exc_info=True)
        finally:
            self.process = None

    def __enter__(self):
        """Context manager entry - create tunnel."""
        self.create_tunnel()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close tunnel."""
        self.close()
        return False


def open_shell(
    ssh_host: str,
    ssh_port: Optional[int] = None,
    ssh_key_path: Optional[str] = None,
    ssh_user: str = "root",
    timeout: int = 30
) -> int:
    """Open an interactive SSH shell to a remote pod.

    This creates a direct SSH connection (not a tunnel) and gives the user
    an interactive terminal session. Useful for debugging, manual commands,
    and log inspection.

    Args:
        ssh_host: SSH host address (e.g., "ssh.runpod.io")
        ssh_port: SSH port number (optional, for legacy format)
        ssh_key_path: Path to SSH private key (optional)
        ssh_user: SSH username (default: "root")
        timeout: Connection timeout in seconds

    Returns:
        Exit code from SSH session (0 = success, non-zero = error)

    Example:
        >>> # Opens interactive shell to RunPod pod
        >>> exit_code = open_shell(
        ...     ssh_host="ssh.runpod.io",
        ...     ssh_user="abc123-def456",
        ...     ssh_key_path="~/.ssh/id_ed25519_runpod"
        ... )
        >>> # User can now run commands interactively
    """
    port_info = f":{ssh_port}" if ssh_port else ""
    logger.info(f"Opening SSH shell to {ssh_user}@{ssh_host}{port_info}")

    # Build SSH command for interactive shell
    cmd = ["ssh"]

    # Add port if specified (legacy format)
    if ssh_port is not None:
        cmd.extend(["-p", str(ssh_port)])

    # Add connection options
    cmd.extend([
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"ConnectTimeout={timeout}",
    ])

    # Add SSH key if provided
    if ssh_key_path:
        expanded_path = str(Path(ssh_key_path).expanduser())
        cmd.extend(["-i", expanded_path])

    # Add user@host
    cmd.append(f"{ssh_user}@{ssh_host}")

    logger.debug(f"SSH shell command: {' '.join(cmd)}")

    try:
        # Run SSH in foreground (interactive)
        # This replaces the current process with SSH
        result = subprocess.run(cmd)

        logger.info(f"SSH shell exited with code {result.returncode}")
        return result.returncode

    except KeyboardInterrupt:
        logger.info("SSH shell interrupted by user")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        logger.error(f"SSH shell failed: {e}", exc_info=True)
        return 1


def parse_ssh_connection_string(conn_str: str) -> Dict[str, any]:
    """Parse SSH connection string into components.

    Supports two formats:
    1. RunPod format: "{pod_id}-{machine_id}@ssh.runpod.io" (no port)
    2. Legacy format: "user@host:port" (with port)

    Args:
        conn_str: SSH connection string

    Returns:
        Dictionary with keys: user, host, port (port=None if not specified)

    Examples:
        >>> parse_ssh_connection_string("abc-def@ssh.runpod.io")
        {'user': 'abc-def', 'host': 'ssh.runpod.io', 'port': None}

        >>> parse_ssh_connection_string("root@ssh.runpod.io:12345")
        {'user': 'root', 'host': 'ssh.runpod.io', 'port': 12345}
    """
    if "@" not in conn_str:
        raise ValueError(f"Invalid SSH connection string format: {conn_str}")

    # Check if port is included
    if ":" in conn_str:
        # Format: user@host:port
        user_host, port_str = conn_str.rsplit(":", 1)
        user, host = user_host.split("@", 1)
        port = int(port_str)
    else:
        # Format: user@host (RunPod proxy format)
        user, host = conn_str.split("@", 1)
        port = None

    return {
        "user": user,
        "host": host,
        "port": port
    }
