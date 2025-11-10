"""Tests for SSH tunnel and shell access management."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
from autopod.ssh import SSHTunnel, open_shell, parse_ssh_connection_string


@pytest.fixture
def mock_subprocess():
    """Mock subprocess module."""
    with patch('autopod.ssh.subprocess') as mock:
        yield mock


@pytest.fixture
def mock_socket():
    """Mock socket module for connection testing."""
    with patch('autopod.ssh.socket') as mock:
        yield mock


@pytest.fixture
def mock_time():
    """Mock time module for fast tests."""
    with patch('autopod.ssh.time') as mock:
        yield mock


def test_ssh_tunnel_init():
    """Test SSHTunnel initialization with all parameters."""
    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188,
        remote_port=8188,
        ssh_key_path="~/.ssh/id_ed25519",
        ssh_user="root"
    )

    assert tunnel.ssh_host == "ssh.runpod.io"
    assert tunnel.ssh_port == 12345
    assert tunnel.local_port == 8188
    assert tunnel.remote_port == 8188
    assert tunnel.ssh_key_path == "~/.ssh/id_ed25519"
    assert tunnel.ssh_user == "root"
    assert tunnel.process is None


def test_ssh_tunnel_init_defaults():
    """Test SSHTunnel initialization with default values."""
    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )

    assert tunnel.remote_port == 8188  # Default
    assert tunnel.ssh_user == "root"   # Default
    assert tunnel.ssh_key_path is None  # Default


def test_create_tunnel_success(mock_subprocess, mock_socket):
    """Test successful SSH tunnel creation."""
    # Mock process
    mock_process = Mock()
    mock_process.pid = 12345
    mock_process.poll.return_value = None  # Still running
    mock_subprocess.Popen.return_value = mock_process

    # Mock socket connection (tunnel ready)
    mock_sock = Mock()
    mock_sock.connect_ex.return_value = 0  # Success
    mock_socket.socket.return_value = mock_sock

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )

    result = tunnel.create_tunnel(timeout=10)

    assert result is True
    assert tunnel.process == mock_process

    # Verify SSH command structure
    call_args = mock_subprocess.Popen.call_args[0][0]
    assert call_args[0] == "ssh"
    assert "-N" in call_args  # No remote command
    assert "-L" in call_args
    assert "8188:localhost:8188" in call_args
    assert "-p" in call_args
    assert "12345" in call_args
    assert "root@ssh.runpod.io" in call_args


def test_create_tunnel_with_ssh_key(mock_subprocess, mock_socket):
    """Test SSH tunnel creation with SSH key path."""
    mock_process = Mock()
    mock_process.poll.return_value = None
    mock_subprocess.Popen.return_value = mock_process

    # Mock socket for connection check
    mock_sock = Mock()
    mock_sock.connect_ex.return_value = 0
    mock_socket.socket.return_value = mock_sock

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188,
        ssh_key_path="~/.ssh/id_ed25519_runpod"
    )

    tunnel.create_tunnel(timeout=10)

    # Verify SSH key is in command
    call_args = mock_subprocess.Popen.call_args[0][0]
    assert "-i" in call_args
    # Should expand ~ to home directory
    key_index = call_args.index("-i")
    assert call_args[key_index + 1].endswith(".ssh/id_ed25519_runpod")


def test_create_tunnel_already_running(mock_subprocess, mock_socket):
    """Test creating tunnel when one already exists."""
    mock_process = Mock()
    mock_process.poll.return_value = None  # Still running
    mock_subprocess.Popen.return_value = mock_process

    mock_sock = Mock()
    mock_sock.connect_ex.return_value = 0
    mock_socket.socket.return_value = mock_sock

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )

    # Create first tunnel
    tunnel.create_tunnel(timeout=10)

    # Try to create again
    result = tunnel.create_tunnel(timeout=10)

    assert result is True
    # Should only create once
    assert mock_subprocess.Popen.call_count == 1


def test_create_tunnel_connection_timeout(mock_subprocess, mock_socket):
    """Test SSH tunnel creation with connection timeout."""
    mock_process = Mock()
    mock_process.poll.return_value = None
    mock_subprocess.Popen.return_value = mock_process

    # Mock socket connection failure
    mock_sock = Mock()
    mock_sock.connect_ex.return_value = 1  # Connection refused
    mock_socket.socket.return_value = mock_sock

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )

    # Should raise RuntimeError on timeout
    with pytest.raises(RuntimeError, match="failed to establish"):
        tunnel.create_tunnel(timeout=1)

    # Should have called terminate
    mock_process.terminate.assert_called_once()


def test_is_alive_running(mock_subprocess):
    """Test is_alive() when tunnel is running."""
    mock_process = Mock()
    mock_process.poll.return_value = None  # Still running

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )
    tunnel.process = mock_process

    assert tunnel.is_alive() is True


def test_is_alive_stopped(mock_subprocess):
    """Test is_alive() when tunnel has stopped."""
    mock_process = Mock()
    mock_process.poll.return_value = 0  # Exited

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )
    tunnel.process = mock_process

    assert tunnel.is_alive() is False


def test_is_alive_no_process():
    """Test is_alive() when no process exists."""
    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )

    assert tunnel.is_alive() is False


def test_wait_for_connection_success(mock_socket):
    """Test wait_for_connection() succeeds."""
    # Mock successful connection
    mock_sock = Mock()
    mock_sock.connect_ex.return_value = 0  # Success
    mock_socket.socket.return_value = mock_sock

    # Mock running process
    mock_process = Mock()
    mock_process.poll.return_value = None

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )
    tunnel.process = mock_process

    result = tunnel.wait_for_connection(timeout=5, interval=0.1)

    assert result is True
    mock_sock.connect_ex.assert_called_with(('localhost', 8188))


def test_wait_for_connection_timeout(mock_socket, mock_time):
    """Test wait_for_connection() times out."""
    # Mock failed connection
    mock_sock = Mock()
    mock_sock.connect_ex.return_value = 1  # Connection refused
    mock_socket.socket.return_value = mock_sock

    # Mock running process
    mock_process = Mock()
    mock_process.poll.return_value = None

    # Mock time to simulate timeout
    mock_time.time.side_effect = [0, 0.5, 1.0, 5.1]  # Exceed timeout
    mock_time.sleep = Mock()  # Don't actually sleep

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )
    tunnel.process = mock_process

    result = tunnel.wait_for_connection(timeout=5, interval=0.1)

    assert result is False


def test_wait_for_connection_process_dies(mock_socket):
    """Test wait_for_connection() when process dies."""
    mock_sock = Mock()
    mock_sock.connect_ex.return_value = 1  # Not ready yet
    mock_socket.socket.return_value = mock_sock

    # Mock process that dies
    mock_process = Mock()
    mock_process.poll.return_value = 1  # Process exited with error

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )
    tunnel.process = mock_process

    result = tunnel.wait_for_connection(timeout=5)

    assert result is False


def test_close_graceful(mock_subprocess):
    """Test graceful tunnel close."""
    mock_process = Mock()
    mock_process.wait = Mock()  # Exits cleanly
    mock_process.pid = 12345

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )
    tunnel.process = mock_process

    tunnel.close()

    # Should call terminate then wait
    mock_process.terminate.assert_called_once()
    mock_process.wait.assert_called_once_with(timeout=3)
    assert tunnel.process is None


def test_close_force_kill(mock_subprocess):
    """Test force kill when graceful close fails."""
    mock_process = Mock()
    mock_process.pid = 12345

    # Simulate timeout on wait
    import subprocess
    mock_process.wait.side_effect = [subprocess.TimeoutExpired("ssh", 3), None]

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )
    tunnel.process = mock_process

    tunnel.close()

    # Should call terminate, then kill
    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_called_once()
    assert tunnel.process is None


def test_close_no_process():
    """Test close when no process exists."""
    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )

    # Should not raise error
    tunnel.close()


def test_context_manager(mock_subprocess, mock_socket):
    """Test SSHTunnel as context manager."""
    mock_process = Mock()
    mock_process.poll.return_value = None
    mock_subprocess.Popen.return_value = mock_process

    mock_sock = Mock()
    mock_sock.connect_ex.return_value = 0
    mock_socket.socket.return_value = mock_sock

    tunnel = SSHTunnel(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        local_port=8188
    )

    with tunnel as t:
        assert t == tunnel
        assert t.process is not None

    # Should close on exit
    mock_process.terminate.assert_called_once()


def test_open_shell_success(mock_subprocess):
    """Test successful interactive shell opening."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_subprocess.run.return_value = mock_result

    exit_code = open_shell(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        ssh_key_path="~/.ssh/id_ed25519"
    )

    assert exit_code == 0

    # Verify SSH command
    call_args = mock_subprocess.run.call_args[0][0]
    assert call_args[0] == "ssh"
    assert "-p" in call_args
    assert "12345" in call_args
    assert "root@ssh.runpod.io" in call_args


def test_open_shell_with_custom_user(mock_subprocess):
    """Test shell opening with custom user."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_subprocess.run.return_value = mock_result

    open_shell(
        ssh_host="ssh.runpod.io",
        ssh_port=12345,
        ssh_user="ubuntu"
    )

    call_args = mock_subprocess.run.call_args[0][0]
    assert "ubuntu@ssh.runpod.io" in call_args


def test_open_shell_keyboard_interrupt(mock_subprocess):
    """Test shell handling KeyboardInterrupt."""
    mock_subprocess.run.side_effect = KeyboardInterrupt()

    exit_code = open_shell(
        ssh_host="ssh.runpod.io",
        ssh_port=12345
    )

    assert exit_code == 130  # Standard SIGINT exit code


def test_open_shell_error(mock_subprocess):
    """Test shell handling errors."""
    mock_subprocess.run.side_effect = Exception("Connection failed")

    exit_code = open_shell(
        ssh_host="ssh.runpod.io",
        ssh_port=12345
    )

    assert exit_code == 1


def test_parse_ssh_connection_string_valid():
    """Test parsing valid SSH connection string."""
    result = parse_ssh_connection_string("root@ssh.runpod.io:12345")

    assert result["user"] == "root"
    assert result["host"] == "ssh.runpod.io"
    assert result["port"] == 12345


def test_parse_ssh_connection_string_custom_user():
    """Test parsing with custom username."""
    result = parse_ssh_connection_string("ubuntu@10.0.0.5:2222")

    assert result["user"] == "ubuntu"
    assert result["host"] == "10.0.0.5"
    assert result["port"] == 2222


def test_parse_ssh_connection_string_invalid_no_at():
    """Test parsing invalid string (missing @)."""
    with pytest.raises(ValueError, match="Invalid SSH connection string"):
        parse_ssh_connection_string("ssh.runpod.io:12345")


def test_parse_ssh_connection_string_invalid_no_port():
    """Test parsing invalid string (missing port)."""
    with pytest.raises(ValueError, match="Invalid SSH connection string"):
        parse_ssh_connection_string("root@ssh.runpod.io")
