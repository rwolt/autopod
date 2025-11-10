"""Unit tests for PodManager class."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from autopod.pod_manager import PodManager


@pytest.fixture
def mock_provider():
    """Create a mock CloudProvider."""
    provider = Mock()
    provider.__class__.__name__ = "MockProvider"
    return provider


@pytest.fixture
def mock_console():
    """Create a mock Rich Console."""
    console = Mock()
    return console


@pytest.fixture
def pod_manager(mock_provider, mock_console, tmp_path):
    """Create PodManager instance with mocked dependencies."""
    manager = PodManager(mock_provider, mock_console)
    # Use temporary state file for testing
    manager.state_file = tmp_path / "pods.json"
    return manager


@pytest.fixture
def sample_pod_status():
    """Sample pod status dictionary."""
    return {
        "pod_id": "test-pod-123",
        "status": "RUNNING",
        "gpu_type": "RTX A40",
        "gpu_count": 1,
        "cost_per_hour": 0.40,
        "runtime_minutes": 12.5,
        "total_cost": 0.0833,
        "ssh_host": "ssh.runpod.io",
        "ssh_port": 0,
        "machine_id": "machine-abc",
        "ssh_ready": True,
    }


class TestPodManagerInit:
    """Tests for PodManager initialization."""

    def test_init_with_console(self, mock_provider, mock_console):
        """Test initialization with provided console."""
        manager = PodManager(mock_provider, mock_console)
        assert manager.provider == mock_provider
        assert manager.console == mock_console
        assert manager.state_file == Path.home() / ".autopod" / "pods.json"

    def test_init_without_console(self, mock_provider):
        """Test initialization without console creates one."""
        manager = PodManager(mock_provider)
        assert manager.provider == mock_provider
        assert manager.console is not None


class TestListPods:
    """Tests for list_pods method."""

    def test_list_pods_empty_state(self, pod_manager, mock_console):
        """Test listing pods when no pods exist."""
        # Empty state file
        pod_manager.save_pod_state("dummy", {})
        pod_manager._remove_pod_from_state("dummy")

        pods = pod_manager.list_pods(show_table=True)

        assert pods == []
        mock_console.print.assert_called_once()
        call_args = str(mock_console.print.call_args)
        assert "No pods found" in call_args

    def test_list_pods_with_data(self, pod_manager, mock_provider, sample_pod_status):
        """Test listing pods with existing pods."""
        # Setup state
        pod_manager.save_pod_state("test-pod-123", {"pod_host_id": "test-123-xyz"})

        # Mock provider response
        mock_provider.get_pod_status.return_value = sample_pod_status

        pods = pod_manager.list_pods(show_table=False)

        assert len(pods) == 1
        assert pods[0]["pod_id"] == "test-pod-123"
        mock_provider.get_pod_status.assert_called_once_with("test-pod-123")

    def test_list_pods_handles_errors(self, pod_manager, mock_provider):
        """Test listing pods handles errors gracefully."""
        # Setup state
        pod_manager.save_pod_state("test-pod-123", {"pod_host_id": "test-123-xyz"})

        # Mock provider to raise error
        mock_provider.get_pod_status.side_effect = RuntimeError("API error")

        pods = pod_manager.list_pods(show_table=False)

        # Should still return a list with unknown status
        assert len(pods) == 1
        assert pods[0]["pod_id"] == "test-pod-123"
        assert pods[0]["status"] == "UNKNOWN"


class TestGetPodInfo:
    """Tests for get_pod_info method."""

    def test_get_pod_info_success(self, pod_manager, mock_provider, sample_pod_status):
        """Test getting pod info successfully."""
        mock_provider.get_pod_status.return_value = sample_pod_status

        info = pod_manager.get_pod_info("test-pod-123", show_panel=False)

        assert info == sample_pod_status
        mock_provider.get_pod_status.assert_called_once_with("test-pod-123")

    def test_get_pod_info_error(self, pod_manager, mock_provider, mock_console):
        """Test getting pod info handles errors."""
        mock_provider.get_pod_status.side_effect = RuntimeError("Pod not found")

        info = pod_manager.get_pod_info("test-pod-123", show_panel=True)

        assert info is None
        mock_console.print.assert_called_once()


class TestStopPod:
    """Tests for stop_pod method."""

    def test_stop_pod_success(self, pod_manager, mock_provider, mock_console):
        """Test stopping pod successfully."""
        mock_provider.stop_pod.return_value = True

        result = pod_manager.stop_pod("test-pod-123")

        assert result is True
        mock_provider.stop_pod.assert_called_once_with("test-pod-123")
        mock_console.print.assert_called_once()
        call_args = str(mock_console.print.call_args)
        assert "stopped successfully" in call_args

    def test_stop_pod_failure(self, pod_manager, mock_provider, mock_console):
        """Test stopping pod failure."""
        mock_provider.stop_pod.return_value = False

        result = pod_manager.stop_pod("test-pod-123")

        assert result is False
        mock_console.print.assert_called_once()
        call_args = str(mock_console.print.call_args)
        assert "Failed to stop" in call_args

    def test_stop_pod_error(self, pod_manager, mock_provider, mock_console):
        """Test stopping pod handles errors."""
        mock_provider.stop_pod.side_effect = RuntimeError("API error")

        result = pod_manager.stop_pod("test-pod-123")

        assert result is False
        mock_console.print.assert_called_once()


class TestTerminatePod:
    """Tests for terminate_pod method."""

    def test_terminate_pod_with_confirm(self, pod_manager, mock_provider, mock_console):
        """Test terminating pod with confirmation."""
        # Setup state
        pod_manager.save_pod_state("test-pod-123", {"pod_host_id": "test-123-xyz"})

        mock_provider.terminate_pod.return_value = True

        result = pod_manager.terminate_pod("test-pod-123", confirm=True)

        assert result is True
        mock_provider.terminate_pod.assert_called_once_with("test-pod-123")

        # Verify pod removed from state
        state = pod_manager.load_pod_state()
        assert "test-pod-123" not in state

    @patch("builtins.input", return_value="y")
    def test_terminate_pod_user_confirms(self, mock_input, pod_manager, mock_provider):
        """Test terminating pod with user confirmation."""
        mock_provider.terminate_pod.return_value = True

        result = pod_manager.terminate_pod("test-pod-123", confirm=False)

        assert result is True
        mock_input.assert_called_once()

    @patch("builtins.input", return_value="n")
    def test_terminate_pod_user_cancels(self, mock_input, pod_manager, mock_provider):
        """Test terminating pod when user cancels."""
        result = pod_manager.terminate_pod("test-pod-123", confirm=False)

        assert result is False
        mock_provider.terminate_pod.assert_not_called()

    def test_terminate_pod_error(self, pod_manager, mock_provider, mock_console):
        """Test terminating pod handles errors."""
        mock_provider.terminate_pod.side_effect = RuntimeError("API error")

        result = pod_manager.terminate_pod("test-pod-123", confirm=True)

        assert result is False
        mock_console.print.assert_called_once()


class TestShellIntoPod:
    """Tests for shell_into_pod method."""

    @patch("autopod.pod_manager.open_shell")
    @patch("autopod.pod_manager.parse_ssh_connection_string")
    def test_shell_into_pod_success(
        self, mock_parse, mock_open_shell, pod_manager, mock_provider
    ):
        """Test opening SSH shell successfully."""
        mock_provider.get_ssh_connection_string.return_value = "user@host"
        mock_parse.return_value = {
            "user": "user",
            "host": "host",
            "port": None,
        }
        mock_open_shell.return_value = 0

        exit_code = pod_manager.shell_into_pod("test-pod-123")

        assert exit_code == 0
        mock_provider.get_ssh_connection_string.assert_called_once_with("test-pod-123")
        mock_open_shell.assert_called_once()

    def test_shell_into_pod_error(self, pod_manager, mock_provider, mock_console):
        """Test opening SSH shell handles errors."""
        mock_provider.get_ssh_connection_string.side_effect = RuntimeError("SSH not ready")

        exit_code = pod_manager.shell_into_pod("test-pod-123")

        assert exit_code == 1
        mock_console.print.assert_called()


class TestStatePersistence:
    """Tests for state persistence methods."""

    def test_save_and_load_pod_state(self, pod_manager):
        """Test saving and loading pod state."""
        metadata = {
            "pod_host_id": "test-123-xyz",
            "created_at": "2025-11-09T12:00:00",
        }

        pod_manager.save_pod_state("test-pod-123", metadata)

        state = pod_manager.load_pod_state()
        assert "test-pod-123" in state
        assert state["test-pod-123"] == metadata

    def test_load_empty_state(self, pod_manager):
        """Test loading state when file doesn't exist."""
        state = pod_manager.load_pod_state()
        assert state == {}

    def test_save_multiple_pods(self, pod_manager):
        """Test saving multiple pods."""
        pod_manager.save_pod_state("pod-1", {"pod_host_id": "pod-1-xyz"})
        pod_manager.save_pod_state("pod-2", {"pod_host_id": "pod-2-abc"})

        state = pod_manager.load_pod_state()
        assert len(state) == 2
        assert "pod-1" in state
        assert "pod-2" in state

    def test_remove_pod_from_state(self, pod_manager):
        """Test removing pod from state."""
        pod_manager.save_pod_state("pod-1", {"pod_host_id": "pod-1-xyz"})
        pod_manager.save_pod_state("pod-2", {"pod_host_id": "pod-2-abc"})

        pod_manager._remove_pod_from_state("pod-1")

        state = pod_manager.load_pod_state()
        assert "pod-1" not in state
        assert "pod-2" in state

    def test_state_file_permissions(self, pod_manager):
        """Test that state file has secure permissions."""
        pod_manager.save_pod_state("test-pod", {"data": "test"})

        # Check file permissions (should be 0o600)
        import stat
        mode = pod_manager.state_file.stat().st_mode
        perms = stat.S_IMODE(mode)
        assert perms == 0o600


class TestRichFormatting:
    """Tests for Rich formatting methods."""

    def test_print_pods_table(self, pod_manager, mock_console, sample_pod_status):
        """Test printing pods table."""
        pods = [sample_pod_status]

        pod_manager._print_pods_table(pods)

        # Verify console.print was called with a Table
        mock_console.print.assert_called_once()
        # The Table object should be passed to print

    def test_print_pod_panel(self, pod_manager, mock_console, sample_pod_status):
        """Test printing pod panel."""
        pod_manager._print_pod_panel(sample_pod_status)

        # Verify console.print was called with a Panel
        mock_console.print.assert_called_once()

    def test_print_pod_panel_ssh_not_ready(self, pod_manager, mock_console, sample_pod_status):
        """Test printing pod panel when SSH not ready."""
        sample_pod_status["ssh_ready"] = False

        pod_manager._print_pod_panel(sample_pod_status)

        mock_console.print.assert_called_once()
