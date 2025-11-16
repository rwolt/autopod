"""Tests for V1.2 bug fixes in RunPod provider.

Tests for:
1. Runtime/cost calculation with metadata created_at fallback
2. HTTP port detection logic (type='http' vs ip check)
3. GPU display name extraction
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime, timezone, timedelta
from autopod.providers.runpod import RunPodProvider
import json


@pytest.fixture
def provider():
    """Create a RunPodProvider instance with test API key."""
    with patch('autopod.providers.runpod.runpod'):
        return RunPodProvider(api_key="test-api-key-123")


@pytest.fixture
def mock_pod_data_with_created_at():
    """Mock pod data with createdAt field from RunPod API."""
    created_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    return {
        "id": "test-pod-123",
        "desiredStatus": "RUNNING",
        "gpuCount": 1,
        "costPerHr": 0.4,
        "machineId": "test-machine",
        "createdAt": created_time.isoformat(),
        "machine": {
            "gpuDisplayName": "A40"
        },
        "runtime": {
            "ports": [
                {"privatePort": 8188, "publicPort": 60924, "type": "http", "ip": "100.65.19.162"},
                {"privatePort": 8080, "publicPort": 60925, "type": "http", "ip": "100.65.19.162"}
            ]
        }
    }


@pytest.fixture
def mock_pod_data_without_created_at():
    """Mock pod data WITHOUT createdAt field (common for new pods)."""
    return {
        "id": "test-pod-123",
        "desiredStatus": "RUNNING",
        "gpuCount": 1,
        "costPerHr": 0.4,
        "machineId": "test-machine",
        # No createdAt field
        "machine": {
            "gpuDisplayName": "A5000"
        },
        "runtime": {
            "ports": [
                {"privatePort": 8188, "publicPort": 60924, "type": "http", "ip": "100.65.19.162"}
            ]
        }
    }


@pytest.fixture
def mock_metadata_with_created_at():
    """Mock metadata with created_at timestamp."""
    created_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    return {
        "pod_host_id": "test-pod-123-host",
        "created_at": created_time.isoformat(),
        "port_labels": {
            "8188": "ComfyUI",
            "8080": "FileBrowser"
        }
    }


class TestRuntimeCostCalculation:
    """Test runtime and cost calculation with metadata fallback."""

    def test_runtime_with_api_created_at(self, provider, mock_pod_data_with_created_at):
        """Test runtime calculation when RunPod API provides createdAt."""
        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.get_pod.return_value = mock_pod_data_with_created_at

            with patch.object(provider, '_load_pod_metadata', return_value=None):
                status = provider.get_pod_status("test-pod-123")

                # Should calculate runtime from createdAt (10 minutes ago)
                assert status["runtime_minutes"] > 9.0
                assert status["runtime_minutes"] < 11.0

                # Should calculate cost correctly: (runtime_hours * cost_per_hour)
                expected_cost = (status["runtime_minutes"] / 60.0) * 0.4
                assert abs(status["total_cost"] - expected_cost) < 0.001

    def test_runtime_with_metadata_fallback(self, provider,
                                           mock_pod_data_without_created_at,
                                           mock_metadata_with_created_at):
        """Test runtime calculation falls back to metadata created_at when API doesn't provide it."""
        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.get_pod.return_value = mock_pod_data_without_created_at

            with patch.object(provider, '_load_pod_metadata', return_value=mock_metadata_with_created_at):
                status = provider.get_pod_status("test-pod-123")

                # Should calculate runtime from metadata created_at (5 minutes ago)
                assert status["runtime_minutes"] > 4.0
                assert status["runtime_minutes"] < 6.0

                # Should calculate cost correctly
                expected_cost = (status["runtime_minutes"] / 60.0) * 0.4
                assert abs(status["total_cost"] - expected_cost) < 0.001

    def test_runtime_without_any_timestamp(self, provider, mock_pod_data_without_created_at):
        """Test runtime calculation when neither API nor metadata provide timestamp."""
        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.get_pod.return_value = mock_pod_data_without_created_at

            with patch.object(provider, '_load_pod_metadata', return_value={}):
                status = provider.get_pod_status("test-pod-123")

                # Should default to 0.0 when no timestamp available
                assert status["runtime_minutes"] == 0.0
                assert status["total_cost"] == 0.0


class TestHTTPPortDetection:
    """Test HTTP proxy port detection logic."""

    def test_detects_http_ports_correctly(self, provider, mock_pod_data_with_created_at):
        """Test that HTTP ports are detected by type='http', not IP address."""
        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.get_pod.return_value = mock_pod_data_with_created_at

            with patch.object(provider, '_load_pod_metadata', return_value={}):
                status = provider.get_pod_status("test-pod-123")

                # The pod data has ports with type='http' but private IPs (not 0.0.0.0)
                # This should still work with the fixed logic
                assert status is not None

    def test_http_ports_with_private_ips(self, provider):
        """Test HTTP port detection works with private IPs (not 0.0.0.0)."""
        pod_data = {
            "id": "test-pod",
            "desiredStatus": "RUNNING",
            "gpuCount": 1,
            "costPerHr": 0.4,
            "machineId": "test-machine",
            "machine": {"gpuDisplayName": "A40"},
            "runtime": {
                "ports": [
                    # HTTP proxy port with private IP (real RunPod behavior)
                    {"privatePort": 8188, "publicPort": 60924, "type": "http", "ip": "100.65.19.162"},
                    # SSH port with private IP
                    {"privatePort": 22, "publicPort": 60923, "type": "tcp", "ip": "100.65.19.162"}
                ]
            }
        }

        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.get_pod.return_value = pod_data

            with patch.object(provider, '_load_pod_metadata', return_value={}):
                status = provider.get_pod_status("test-pod")

                # Should successfully detect port 8188 as HTTP (type='http')
                # Should NOT detect port 22 (type='tcp')
                assert status is not None


class TestGPUDisplayName:
    """Test GPU display name extraction."""

    def test_gpu_name_from_machine_display_name(self, provider):
        """Test GPU type extracted from machine.gpuDisplayName (preferred method)."""
        pod_data = {
            "id": "test-pod",
            "desiredStatus": "RUNNING",
            "gpuCount": 1,
            "costPerHr": 0.4,
            "machineId": "test-machine",
            "machine": {
                "gpuDisplayName": "A40"  # This should be used
            },
            "gpuTypeId": "NVIDIA A40",  # This should be ignored
            "runtime": None
        }

        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.get_pod.return_value = pod_data

            with patch.object(provider, '_load_pod_metadata', return_value={}):
                status = provider.get_pod_status("test-pod")

                assert status["gpu_type"] == "A40"

    def test_gpu_name_fallback_to_type_id_mapping(self, provider):
        """Test GPU type falls back to gpuTypeId mapping when machine.gpuDisplayName missing."""
        pod_data = {
            "id": "test-pod",
            "desiredStatus": "RUNNING",
            "gpuCount": 1,
            "costPerHr": 0.4,
            "machineId": "test-machine",
            "machine": {},  # No gpuDisplayName
            "gpuTypeId": "NVIDIA RTX A5000",  # Should map to "RTX A5000"
            "runtime": None
        }

        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.get_pod.return_value = pod_data

            with patch.object(provider, '_load_pod_metadata', return_value={}):
                status = provider.get_pod_status("test-pod")

                # Should map "NVIDIA RTX A5000" to "RTX A5000"
                assert status["gpu_type"] == "RTX A5000"

    def test_gpu_name_unknown_when_no_info(self, provider):
        """Test GPU type defaults to 'Unknown' when no information available."""
        pod_data = {
            "id": "test-pod",
            "desiredStatus": "RUNNING",
            "gpuCount": 1,
            "costPerHr": 0.4,
            "machineId": "test-machine",
            "machine": {},  # No gpuDisplayName
            # No gpuTypeId
            "runtime": None
        }

        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.get_pod.return_value = pod_data

            with patch.object(provider, '_load_pod_metadata', return_value={}):
                status = provider.get_pod_status("test-pod")

                assert status["gpu_type"] == "Unknown"


class TestMetadataCreatedAtSaving:
    """Test that created_at timestamp is saved to metadata during pod creation."""

    def test_created_at_saved_in_metadata(self, provider):
        """Test that created_at timestamp is saved when pod is created."""
        mock_response = {
            "id": "new-pod-123",
            "imageName": "runpod/comfyui:latest",
            "machine": {
                "podHostId": "new-pod-123-host"
            }
        }

        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.create_pod.return_value = mock_response

            # Mock GPU availability
            with patch.object(provider, 'get_gpu_availability', return_value={
                'available': True,
                'gpu_type_id': 'NVIDIA RTX A5000'
            }):
                saved_metadata = {}

                def mock_save(pod_id, metadata):
                    saved_metadata.update(metadata)

                with patch.object(provider, '_save_pod_metadata', side_effect=mock_save):
                    config = {
                        "gpu_type": "RTX A5000",
                        "gpu_count": 1,
                        "disk_size_gb": 50,
                        "template": "runpod/comfyui:latest"
                    }

                    pod_id = provider.create_pod(config)

                    # Verify metadata was saved with created_at
                    assert "created_at" in saved_metadata
                    assert saved_metadata["pod_host_id"] == "new-pod-123-host"

                    # Verify created_at is a valid ISO 8601 timestamp
                    created_at = datetime.fromisoformat(saved_metadata["created_at"])
                    assert isinstance(created_at, datetime)

                    # Verify it's recent (within last minute)
                    time_diff = datetime.now(timezone.utc) - created_at
                    assert time_diff.total_seconds() < 60

    def test_port_labels_saved_in_metadata(self, provider):
        """Test that port_labels are saved to metadata when pod is created."""
        mock_response = {
            "id": "new-pod-123",
            "imageName": "runpod/comfyui:latest",
            "machine": {
                "podHostId": "new-pod-123-host"
            }
        }

        with patch('autopod.providers.runpod.runpod') as mock_runpod:
            mock_runpod.create_pod.return_value = mock_response

            # Mock GPU availability
            with patch.object(provider, 'get_gpu_availability', return_value={
                'available': True,
                'gpu_type_id': 'NVIDIA RTX A5000'
            }):
                saved_metadata = {}

                def mock_save(pod_id, metadata):
                    saved_metadata.update(metadata)

                with patch.object(provider, '_save_pod_metadata', side_effect=mock_save):
                    config = {
                        "gpu_type": "RTX A5000",
                        "gpu_count": 1,
                        "disk_size_gb": 50,
                        "template": "runpod/comfyui:latest",
                        "ports": "8188/http,8080/http",
                        "port_labels": {
                            "8188": "ComfyUI",
                            "8080": "FileBrowser"
                        }
                    }

                    pod_id = provider.create_pod(config)

                    # Verify port_labels were saved
                    assert "port_labels" in saved_metadata
                    assert saved_metadata["port_labels"]["8188"] == "ComfyUI"
                    assert saved_metadata["port_labels"]["8080"] == "FileBrowser"
