"""Tests for RunPod provider implementation."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from autopod.providers.runpod import RunPodProvider


@pytest.fixture
def mock_runpod():
    """Mock the runpod module."""
    with patch('autopod.providers.runpod.runpod') as mock:
        yield mock


@pytest.fixture
def provider():
    """Create a RunPodProvider instance with test API key."""
    with patch('autopod.providers.runpod.runpod'):
        return RunPodProvider(api_key="test-api-key-123")


def test_init_with_valid_api_key():
    """Test initialization with valid API key."""
    with patch('autopod.providers.runpod.runpod') as mock_runpod:
        provider = RunPodProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert mock_runpod.api_key == "test-key"


def test_init_with_empty_api_key():
    """Test initialization with empty API key raises ValueError."""
    with pytest.raises(ValueError, match="API key cannot be empty"):
        RunPodProvider(api_key="")


def test_authenticate_success(provider, mock_runpod):
    """Test successful authentication."""
    mock_runpod.get_gpus.return_value = [{"id": "gpu1"}]

    result = provider.authenticate("test-key")

    assert result is True
    assert provider.api_key == "test-key"
    mock_runpod.get_gpus.assert_called_once()


def test_authenticate_failure(provider, mock_runpod):
    """Test failed authentication."""
    mock_runpod.get_gpus.return_value = None

    result = provider.authenticate("invalid-key")

    assert result is False


def test_authenticate_exception(provider, mock_runpod):
    """Test authentication with exception."""
    mock_runpod.get_gpus.side_effect = Exception("Network error")

    result = provider.authenticate("test-key")

    assert result is False


def test_get_gpu_availability_found(provider, mock_runpod):
    """Test GPU availability check for available GPU."""
    # Mock get_gpus (for finding GPU ID)
    mock_runpod.get_gpus.return_value = [
        {
            "id": "NVIDIA A40",
            "displayName": "A40",
            "memoryInGb": 48
        }
    ]

    # Mock get_gpu (for detailed pricing)
    mock_runpod.get_gpu.return_value = {
        "id": "NVIDIA A40",
        "displayName": "A40",
        "memoryInGb": 48,
        "maxGpuCount": 10,
        "securePrice": 0.40,
        "communityPrice": 0.35,
        "secureSpotPrice": 0.20,
        "communitySpotPrice": 0.24,
        "secureCloud": True,
        "communityCloud": False
    }

    result = provider.get_gpu_availability("RTX A40")

    assert result["available"] is True
    assert result["cost_per_hour"] == 0.20  # Lowest price (spot)
    assert result["secure_price"] == 0.40
    assert result["community_price"] == 0.35
    assert result["spot_price"] == 0.20
    assert result["memory_gb"] == 48
    assert result["gpu_type_id"] == "NVIDIA A40"
    assert result["max_gpu_count"] == 10
    assert result["secure_cloud"] is True
    assert result["community_cloud"] is False


def test_get_gpu_availability_not_found(provider, mock_runpod):
    """Test GPU availability check for unavailable GPU."""
    mock_runpod.get_gpus.return_value = [
        {
            "id": "OTHER_GPU",
            "displayName": "Other GPU"
        }
    ]

    result = provider.get_gpu_availability("RTX A40")

    assert result["available"] is False
    assert result["max_gpu_count"] == 0
    assert result["cost_per_hour"] == 0.0


def test_get_gpu_availability_no_gpus(provider, mock_runpod):
    """Test GPU availability check when no GPUs returned."""
    mock_runpod.get_gpus.return_value = []

    result = provider.get_gpu_availability("RTX A40")

    assert result["available"] is False
    assert result["cost_per_hour"] == 0.0


def test_get_gpu_availability_exception(provider, mock_runpod):
    """Test GPU availability check with exception."""
    mock_runpod.get_gpus.side_effect = Exception("API error")

    result = provider.get_gpu_availability("RTX A40")

    assert result["available"] is False
    assert result["cost_per_hour"] == 0.0


def test_create_pod_success(provider, mock_runpod):
    """Test successful pod creation."""
    # Mock GPU availability
    with patch.object(provider, 'get_gpu_availability') as mock_avail:
        mock_avail.return_value = {
            "available": True,
            "gpu_type_id": "NVIDIA_RTX_A40"
        }

        # Mock pod creation
        mock_runpod.create_pod.return_value = {"id": "pod-abc123"}

        # Mock pod name generation
        with patch.object(provider, '_generate_pod_name') as mock_name:
            mock_name.return_value = "autopod-2025-11-08-001"

            config = {
                "gpu_type": "RTX A40",
                "gpu_count": 1,
                "template": "runpod/comfyui:latest"
            }

            pod_id = provider.create_pod(config)

            assert pod_id == "pod-abc123"
            mock_runpod.create_pod.assert_called_once()


def test_create_pod_gpu_not_available(provider, mock_runpod):
    """Test pod creation when GPU is not available."""
    with patch.object(provider, 'get_gpu_availability') as mock_avail:
        mock_avail.return_value = {"available": False}

        config = {"gpu_type": "RTX A40"}

        with pytest.raises(RuntimeError, match="not available"):
            provider.create_pod(config)


def test_create_pod_creation_fails(provider, mock_runpod):
    """Test pod creation when RunPod API fails."""
    with patch.object(provider, 'get_gpu_availability') as mock_avail:
        mock_avail.return_value = {
            "available": True,
            "gpu_type_id": "NVIDIA_RTX_A40"
        }

        # Mock failed pod creation
        mock_runpod.create_pod.return_value = None

        with patch.object(provider, '_generate_pod_name'):
            config = {"gpu_type": "RTX A40"}

            with pytest.raises(RuntimeError, match="Pod creation failed"):
                provider.create_pod(config)


def test_get_pod_status_success(provider, mock_runpod):
    """Test successful pod status retrieval."""
    import time
    creation_time_millis = int((time.time() - 600) * 1000)  # 10 minutes ago

    mock_runpod.get_pod.return_value = {
        "id": "pod-abc123",
        "desiredStatus": "RUNNING",
        "gpuCount": 1,
        "costPerHr": 0.40,
        "creationTimeMillis": creation_time_millis,
        "gpuTypeId": "NVIDIA RTX A40",
        "runtime": {
            "host": "ssh.runpod.io",
            "ports": [
                {"privatePort": 22, "publicPort": 12345}
            ]
        }
    }

    status = provider.get_pod_status("pod-abc123")

    assert status["pod_id"] == "pod-abc123"
    assert status["status"] == "RUNNING"
    assert status["gpu_count"] == 1
    assert status["cost_per_hour"] == 0.40
    assert 9.9 < status["runtime_minutes"] < 10.1
    assert abs(status["total_cost"] - (10.0 / 60.0 * 0.40)) < 0.01
    assert status["ssh_host"] == "ssh.runpod.io"
    assert status["ssh_ready"] is True


def test_get_pod_status_not_found(provider, mock_runpod):
    """Test pod status when pod not found."""
    mock_runpod.get_pod.return_value = None

    with pytest.raises(RuntimeError, match="not found"):
        provider.get_pod_status("pod-nonexistent")


def test_stop_pod_success(provider, mock_runpod):
    """Test successful pod stop."""
    # RunPod SDK returns None on success
    mock_runpod.stop_pod.return_value = None

    result = provider.stop_pod("pod-abc123")

    assert result is True
    mock_runpod.stop_pod.assert_called_once_with("pod-abc123")


def test_stop_pod_exception(provider, mock_runpod):
    """Test pod stop with exception."""
    mock_runpod.stop_pod.side_effect = Exception("API error")

    result = provider.stop_pod("pod-abc123")

    assert result is False


def test_terminate_pod_success(provider, mock_runpod):
    """Test successful pod termination."""
    # RunPod SDK returns None on success
    mock_runpod.terminate_pod.return_value = None

    result = provider.terminate_pod("pod-abc123")

    assert result is True
    mock_runpod.terminate_pod.assert_called_once_with("pod-abc123")


def test_terminate_pod_exception(provider, mock_runpod):
    """Test pod termination with exception."""
    mock_runpod.terminate_pod.side_effect = Exception("API error")

    result = provider.terminate_pod("pod-abc123")

    assert result is False


def test_get_ssh_connection_string_success(provider, mock_runpod):
    """Test successful SSH connection string retrieval."""
    # Mock the two external dependencies of get_ssh_connection_string
    with patch.object(provider, 'get_pod_status') as mock_get_status, \
         patch.object(provider, '_load_pod_metadata') as mock_load_metadata:

        # Setup the mock return values
        mock_get_status.return_value = {
            "ssh_ready": True,
            "ssh_host": "ssh.runpod.io"
        }
        mock_load_metadata.return_value = {
            "pod_host_id": "xyz-123"
        }

        # Call the function
        conn_str = provider.get_ssh_connection_string("pod-abc123")

        # Assert the correct behavior
        mock_get_status.assert_called_once_with("pod-abc123")
        mock_load_metadata.assert_called_once_with("pod-abc123")
        assert conn_str == "xyz-123@ssh.runpod.io"


def test_get_ssh_connection_string_no_ssh(provider, mock_runpod):
    """Test SSH connection string when SSH not available."""
    with patch.object(provider, 'get_pod_status') as mock_status:
        mock_status.return_value = {
            "ssh_host": "",
            "ssh_port": 0
        }

        with pytest.raises(RuntimeError, match="SSH connection not available"):
            provider.get_ssh_connection_string("pod-abc123")


def test_generate_pod_name_format(provider, mock_runpod):
    """Test pod name generation format."""
    mock_runpod.get_pods.return_value = []

    name = provider._generate_pod_name()

    # Check format: autopod-YYYY-MM-DD-NNN
    parts = name.split("-")
    assert len(parts) == 5
    assert parts[0] == "autopod"
    assert len(parts[1]) == 4  # Year
    assert len(parts[2]) == 2  # Month
    assert len(parts[3]) == 2  # Day
    assert len(parts[4]) == 3  # Number


def test_generate_pod_name_increments(provider, mock_runpod):
    """Test pod name generation increments correctly."""
    today = datetime.now().strftime("%Y-%m-%d")

    mock_runpod.get_pods.return_value = [
        {"name": f"autopod-{today}-001"},
        {"name": f"autopod-{today}-002"},
        {"name": f"autopod-{today}-005"},  # Gap in sequence
    ]

    name = provider._generate_pod_name()

    # Should be 006 (max + 1)
    assert name.endswith("-006")


def test_generate_pod_name_no_existing_pods(provider, mock_runpod):
    """Test pod name generation with no existing pods."""
    mock_runpod.get_pods.return_value = []

    name = provider._generate_pod_name()

    # Should be 001
    assert name.endswith("-001")


def test_retry_with_backoff_success_first_try(provider):
    """Test retry succeeds on first attempt."""
    mock_func = Mock(return_value="success")

    result = provider._retry_with_backoff(mock_func, arg1="test")

    assert result == "success"
    assert mock_func.call_count == 1


def test_retry_with_backoff_success_after_retries(provider):
    """Test retry succeeds after some failures."""
    mock_func = Mock(side_effect=[
        Exception("Fail 1"),
        Exception("Fail 2"),
        "success"
    ])

    result = provider._retry_with_backoff(
        mock_func,
        max_retries=3,
        initial_delay=0.01  # Small delay for testing
    )

    assert result == "success"
    assert mock_func.call_count == 3


def test_retry_with_backoff_all_fail(provider):
    """Test retry exhausts all attempts."""
    mock_func = Mock(side_effect=Exception("Always fails"))

    with pytest.raises(Exception, match="Always fails"):
        provider._retry_with_backoff(
            mock_func,
            max_retries=2,
            initial_delay=0.01
        )

    # Should try: initial + 2 retries = 3 times
    assert mock_func.call_count == 3


def test_get_pod_status_runtime_with_creationTimeMillis(provider, mock_runpod):
    """Test that runtime is calculated from creationTimeMillis if uptimeInSeconds is not present."""
    import time
    # Set creation time to 60 minutes ago in milliseconds
    creation_time_millis = int((time.time() - 3600) * 1000)

    mock_runpod.get_pod.return_value = {
        "id": "pod-abc123",
        "desiredStatus": "STOPPED",
        "gpuCount": 1,
        "costPerHr": 0.50,
        "creationTimeMillis": creation_time_millis,
        "gpuTypeId": "NVIDIA RTX A6000",
        "runtime": None  # No runtime data for stopped pod
    }

    status = provider.get_pod_status("pod-abc123")

    assert status["pod_id"] == "pod-abc123"
    assert status["status"] == "STOPPED"
    assert status["cost_per_hour"] == 0.50
    # Check if runtime is approximately 60 minutes
    assert 59.9 < status["runtime_minutes"] < 60.1
    # Check if total cost is approximately cost_per_hour
    assert 0.49 < status["total_cost"] < 0.51
