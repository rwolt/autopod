"""Abstract base class for cloud GPU providers.

This module defines the provider abstraction layer that allows autopod to support
multiple GPU cloud providers (RunPod, Vast.ai, etc.) without requiring changes to
core logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class CloudProvider(ABC):
    """Abstract base class for GPU cloud providers.

    All cloud provider implementations must inherit from this class and implement
    all abstract methods. This ensures a consistent interface across different
    providers.

    Example:
        class RunPodProvider(CloudProvider):
            def __init__(self, api_key: str):
                self.api_key = api_key

            def authenticate(self, api_key: str) -> bool:
                # Implementation for RunPod authentication
                pass
    """

    @abstractmethod
    def authenticate(self, api_key: str) -> bool:
        """Validate API credentials with the provider.

        Args:
            api_key: The API key to validate

        Returns:
            True if authentication successful, False otherwise

        Raises:
            ConnectionError: If unable to reach the provider's API
        """
        pass

    @abstractmethod
    def get_gpu_availability(self, gpu_type: str) -> Dict:
        """Check if a specific GPU type is available.

        Args:
            gpu_type: GPU type identifier (e.g., "RTX A40", "RTX A6000")

        Returns:
            Dictionary containing:
                - available (bool): Whether the GPU is available
                - count (int): Number of available units (0 if unavailable)
                - cost_per_hour (float): Cost per hour in USD
                - regions (list): Available regions/datacenters

        Example:
            {
                "available": True,
                "count": 12,
                "cost_per_hour": 0.40,
                "regions": ["NA-US", "EU-RO"]
            }

        Raises:
            ValueError: If gpu_type is not recognized
            ConnectionError: If unable to query availability
        """
        pass

    @abstractmethod
    def create_pod(self, config: Dict) -> str:
        """Create a new pod with specified configuration.

        Args:
            config: Pod configuration dictionary containing:
                - gpu_type (str): GPU type identifier
                - gpu_count (int): Number of GPUs
                - template (str): Container template/image name
                - region (str, optional): Preferred region
                - volume_id (str, optional): Network volume to attach
                - cloud_type (str, optional): Cloud type (e.g., "secure")

        Returns:
            Pod ID as a string

        Raises:
            ValueError: If configuration is invalid
            RuntimeError: If pod creation fails

        Example:
            config = {
                "gpu_type": "RTX A40",
                "gpu_count": 1,
                "template": "runpod/comfyui:latest",
                "region": "NA-US"
            }
            pod_id = provider.create_pod(config)
        """
        pass

    @abstractmethod
    def get_pod_status(self, pod_id: str) -> Dict:
        """Get detailed status and metrics for a pod.

        Args:
            pod_id: The unique identifier for the pod

        Returns:
            Dictionary containing:
                - status (str): Pod status ("running", "stopped", "terminated")
                - runtime_seconds (int): Total runtime in seconds
                - cost_usd (float): Total cost incurred so far
                - cost_per_hour (float): Current hourly rate
                - gpu_type (str): GPU type
                - gpu_count (int): Number of GPUs
                - created_at (str): ISO timestamp of creation

        Example:
            {
                "status": "running",
                "runtime_seconds": 3600,
                "cost_usd": 0.40,
                "cost_per_hour": 0.40,
                "gpu_type": "RTX A40",
                "gpu_count": 1,
                "created_at": "2025-11-08T10:00:00Z"
            }

        Raises:
            ValueError: If pod_id is invalid or pod not found
        """
        pass

    @abstractmethod
    def stop_pod(self, pod_id: str) -> bool:
        """Stop (pause) a running pod.

        Stopped pods retain their state and can be restarted. They typically
        incur reduced costs while stopped.

        Args:
            pod_id: The unique identifier for the pod

        Returns:
            True if stop successful, False otherwise

        Raises:
            ValueError: If pod_id is invalid or pod not found
            RuntimeError: If stop operation fails
        """
        pass

    @abstractmethod
    def terminate_pod(self, pod_id: str) -> bool:
        """Terminate (destroy) a pod permanently.

        Terminated pods cannot be restarted. All data not saved to network
        volumes will be lost.

        Args:
            pod_id: The unique identifier for the pod

        Returns:
            True if termination successful, False otherwise

        Raises:
            ValueError: If pod_id is invalid or pod not found
            RuntimeError: If termination operation fails
        """
        pass

    @abstractmethod
    def get_ssh_connection_string(self, pod_id: str) -> str:
        """Get SSH connection string for a pod.

        Args:
            pod_id: The unique identifier for the pod

        Returns:
            SSH connection string in format: user@host:port

        Example:
            "root@ssh.runpod.io:12345"

        Raises:
            ValueError: If pod_id is invalid or pod not found
            RuntimeError: If pod is not in a state that allows SSH
        """
        pass
