import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from autopod.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

@patch('autopod.cli.load_provider')
@patch('autopod.cli.get_single_pod_id')
@patch('runpod.get_pod')
@patch('autopod.cli.ComfyUIClient')
def test_comfy_info_success(MockComfyUIClient, mock_get_pod, mock_get_single_pod_id, mock_load_provider, runner):
    """Test the 'autopod comfy info' command for a successful case."""
    # Arrange
    mock_provider = MagicMock()
    mock_load_provider.return_value = mock_provider
    mock_get_single_pod_id.return_value = "pod-123"
    mock_get_pod.return_value = {
        "runtime": {
            "ports": [
                {"privatePort": 8188, "ip": "0.0.0.0"}
            ]
        }
    }

    mock_comfy_client_instance = MockComfyUIClient.return_value
    mock_comfy_client_instance.is_ready.return_value = True
    mock_comfy_client_instance.get_system_stats.return_value = {"system": {"os": "Linux"}}
    mock_comfy_client_instance.get_queue_info.return_value = {}
    mock_comfy_client_instance.get_object_info.return_value = {}

    # Act
    result = runner.invoke(cli, ['comfy', 'info'])

    # Assert
    assert result.exit_code == 0
    assert "URL: https://pod-123-8188.proxy.runpod.net" in result.output
    assert "System Information" in result.output
    mock_load_provider.assert_called_once()
    mock_get_single_pod_id.assert_called_once()
    mock_get_pod.assert_called_once_with("pod-123")
    MockComfyUIClient.assert_called_with(base_url="https://pod-123-8188.proxy.runpod.net")
    mock_comfy_client_instance.is_ready.assert_called_once()
    mock_comfy_client_instance.get_system_stats.assert_called_once()

@patch('autopod.cli.load_provider')
@patch('autopod.cli.get_single_pod_id')
@patch('runpod.get_pod')
@patch('autopod.cli.ComfyUIClient')
def test_comfy_info_not_ready(MockComfyUIClient, mock_get_pod, mock_get_single_pod_id, mock_load_provider, runner):
    """Test the 'autopod comfy info' command when the service is not ready."""
    # Arrange
    mock_provider = MagicMock()
    mock_load_provider.return_value = mock_provider
    mock_get_single_pod_id.return_value = "pod-123"
    mock_get_pod.return_value = {
        "runtime": {
            "ports": [
                {"privatePort": 8188, "ip": "0.0.0.0"}
            ]
        }
    }

    mock_comfy_client_instance = MockComfyUIClient.return_value
    mock_comfy_client_instance.is_ready.return_value = False

    # Act
    result = runner.invoke(cli, ['comfy', 'info'])

    # Assert
    assert result.exit_code == 1
    assert "URL: https://pod-123-8188.proxy.runpod.net" in result.output
    assert "The service may still be starting up" in result.output
    mock_comfy_client_instance.is_ready.assert_called_once()
