"""RunPod provider implementation.

This module implements the CloudProvider interface for RunPod,
providing pod creation, management, and monitoring capabilities.
"""

import os
import time
from typing import Dict, Optional, List
from datetime import datetime

import runpod
from autopod.providers.base import CloudProvider
from autopod.logging import get_logger

logger = get_logger(__name__)


class RunPodProvider(CloudProvider):
    """RunPod cloud provider implementation."""

    # GPU type mapping (RunPod internal names → display names)
    GPU_TYPE_MAP = {
        "NVIDIA RTX A40": "RTX A40",
        "NVIDIA RTX A6000": "RTX A6000",
        "NVIDIA RTX A5000": "RTX A5000",
        "NVIDIA RTX 4090": "RTX 4090",
        "NVIDIA RTX 3090": "RTX 3090",
        "NVIDIA A100 80GB": "A100 80GB",
        "NVIDIA A100 40GB": "A100 40GB",
    }

    # Reverse mapping for lookups
    DISPLAY_NAME_TO_GPU_ID = {v: k for k, v in GPU_TYPE_MAP.items()}

    def __init__(self, api_key: str):
        """Initialize RunPod provider.

        Args:
            api_key: RunPod API key

        Raises:
            ValueError: If API key is empty
        """
        if not api_key:
            raise ValueError("RunPod API key cannot be empty")

        self.api_key = api_key
        runpod.api_key = api_key

        logger.info("RunPod provider initialized")

    def authenticate(self, api_key: str) -> bool:
        """Validate API credentials with RunPod.

        Args:
            api_key: API key to validate

        Returns:
            True if valid, False otherwise

        Example:
            provider = RunPodProvider(api_key="test")
            if provider.authenticate(api_key):
                print("Valid credentials")
        """
        try:
            # Set API key
            runpod.api_key = api_key
            self.api_key = api_key

            # Try to fetch GPU list as authentication test
            gpus = runpod.get_gpus()

            if gpus is not None:
                logger.info("Authentication successful")
                return True
            else:
                logger.warning("Authentication failed - invalid API key")
                return False

        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            return False

    def get_gpu_availability(self, gpu_type: str, gpu_count: int = 1) -> Dict:
        """Check if a specific GPU type is available.

        Args:
            gpu_type: GPU display name (e.g., "RTX A40", "RTX A6000") or GPU ID (e.g., "NVIDIA A40")
            gpu_count: Number of GPUs to check availability for (default: 1)

        Returns:
            Dictionary with availability information:
            {
                "available": True/False,
                "gpu_type_id": str,  # RunPod internal GPU type ID
                "display_name": str,  # Display name
                "memory_gb": int,  # VRAM in GB
                "max_gpu_count": int,  # Maximum GPUs you can request
                "cost_per_hour": float,  # Lowest cost per GPU per hour
                "secure_price": float,  # Secure cloud on-demand price
                "community_price": float,  # Community cloud on-demand price
                "spot_price": float,  # Lowest spot price
                "secure_cloud": bool,  # Available in secure cloud
                "community_cloud": bool,  # Available in community cloud
            }

        Example:
            info = provider.get_gpu_availability("RTX A40")
            if info["available"]:
                print(f"RTX A40 available: ${info['cost_per_hour']}/hr")
                print(f"  Secure: ${info['secure_price']}/hr")
                print(f"  Spot: ${info['spot_price']}/hr")
        """
        try:
            logger.debug(f"Checking availability for GPU: {gpu_type} (count: {gpu_count})")

            # First get basic GPU list to find the correct GPU ID
            gpus = runpod.get_gpus()
            gpu_id = None

            # Try to find matching GPU by display name or ID
            for gpu in gpus:
                gpu_display = gpu.get("displayName", "")
                gpu_full_id = gpu.get("id", "")

                # Match by display name or full ID
                if (gpu_type.lower() in gpu_display.lower() or
                    gpu_type.lower() in gpu_full_id.lower() or
                    gpu_display.lower() in gpu_type.lower()):
                    gpu_id = gpu_full_id
                    break

            if not gpu_id:
                logger.info(f"GPU type '{gpu_type}' not found in catalog")
                return {
                    "available": False,
                    "gpu_type_id": None,
                    "display_name": gpu_type,
                    "memory_gb": 0,
                    "max_gpu_count": 0,
                    "cost_per_hour": 0.0,
                    "secure_price": 0.0,
                    "community_price": 0.0,
                    "spot_price": 0.0,
                    "secure_cloud": False,
                    "community_cloud": False,
                }

            # Get detailed GPU information with pricing
            gpu_details = runpod.get_gpu(gpu_id, gpu_quantity=gpu_count)

            # Extract all pricing information
            secure_price = gpu_details.get("securePrice", 0.0) or 0.0
            community_price = gpu_details.get("communityPrice", 0.0) or 0.0
            secure_spot = gpu_details.get("secureSpotPrice", 0.0) or 0.0
            community_spot = gpu_details.get("communitySpotPrice", 0.0) or 0.0

            # Determine lowest available price
            available_prices = [p for p in [secure_price, community_price, secure_spot, community_spot] if p > 0]
            cost_per_hour = min(available_prices) if available_prices else 0.0

            # Lowest spot price
            spot_prices = [p for p in [secure_spot, community_spot] if p > 0]
            spot_price = min(spot_prices) if spot_prices else 0.0

            # Cloud availability
            secure_cloud = gpu_details.get("secureCloud", False)
            community_cloud = gpu_details.get("communityCloud", False)

            result = {
                "available": secure_cloud or community_cloud,
                "gpu_type_id": gpu_details.get("id"),
                "display_name": gpu_details.get("displayName"),
                "memory_gb": gpu_details.get("memoryInGb", 0),
                "max_gpu_count": gpu_details.get("maxGpuCount", 1),
                "cost_per_hour": cost_per_hour,
                "secure_price": secure_price,
                "community_price": community_price,
                "spot_price": spot_price,
                "secure_cloud": secure_cloud,
                "community_cloud": community_cloud,
            }

            logger.info(
                f"GPU '{gpu_type}' available: ${cost_per_hour}/hr "
                f"(secure: ${secure_price}, community: ${community_price}, spot: ${spot_price}) "
                f"{result['memory_gb']}GB VRAM"
            )

            return result

        except ValueError as e:
            # GPU not found
            logger.warning(f"GPU '{gpu_type}' not found: {e}")
            return {
                "available": False,
                "gpu_type_id": None,
                "display_name": gpu_type,
                "memory_gb": 0,
                "max_gpu_count": 0,
                "cost_per_hour": 0.0,
                "secure_price": 0.0,
                "community_price": 0.0,
                "spot_price": 0.0,
                "secure_cloud": False,
                "community_cloud": False,
            }
        except Exception as e:
            logger.error(f"Error checking GPU availability: {e}", exc_info=True)
            return {
                "available": False,
                "gpu_type_id": None,
                "display_name": gpu_type,
                "memory_gb": 0,
                "max_gpu_count": 0,
                "cost_per_hour": 0.0,
                "secure_price": 0.0,
                "community_price": 0.0,
                "spot_price": 0.0,
                "secure_cloud": False,
                "community_cloud": False,
            }

    def create_pod(self, config: Dict) -> str:
        """Create a new pod with specified configuration.

        Args:
            config: Pod configuration dictionary with keys:
                - gpu_type (str): GPU display name (e.g., "RTX A40")
                - gpu_count (int): Number of GPUs (default: 1)
                - template (str): Docker template name (default: from config)
                - data_center_id (str, optional): Datacenter ID (e.g., "CA-MTL-1")
                - volume_id (str, optional): Network volume ID
                - cloud_type (str): "SECURE" or "ALL" (default: "SECURE")
                - disk_size_gb (int): Container disk size (default: 50)
                - env_vars (Dict, optional): Environment variables

        Returns:
            Pod ID as string

        Raises:
            RuntimeError: If pod creation fails

        Example:
            pod_id = provider.create_pod({
                "gpu_type": "RTX A40",
                "gpu_count": 1,
                "template": "runpod/comfyui:latest"
            })
        """
        try:
            gpu_type = config.get("gpu_type")
            gpu_count = config.get("gpu_count", 1)
            template = config.get("template", "runpod/pytorch:latest")
            cloud_type = config.get("cloud_type", "SECURE")  # SECURE or ALL

            logger.info(f"Creating pod: gpu={gpu_type}, count={gpu_count}, template={template}")

            # Get GPU type ID
            gpu_info = self.get_gpu_availability(gpu_type)
            if not gpu_info["available"]:
                raise RuntimeError(f"GPU type '{gpu_type}' not available")

            gpu_type_id = gpu_info["gpu_type_id"]

            # Build pod creation parameters
            pod_params = {
                "name": self._generate_pod_name(),
                "image_name": template,
                "gpu_type_id": gpu_type_id,
                "gpu_count": gpu_count,
                "cloud_type": cloud_type,
                "container_disk_in_gb": config.get("disk_size_gb", 50),
            }

            # Add optional parameters
            if "volume_id" in config:
                pod_params["volume_in_gb"] = config["volume_id"]

            if "env_vars" in config:
                pod_params["env"] = config["env_vars"]

            if "data_center_id" in config:
                pod_params["data_center_id"] = config["data_center_id"]

            logger.debug(f"Pod creation params: {pod_params}")

            # Create pod using RunPod SDK
            pod = runpod.create_pod(**pod_params)

            if not pod or "id" not in pod:
                raise RuntimeError(f"Pod creation failed: {pod}")

            pod_id = pod["id"]

            # Extract podHostId from response (needed for SSH)
            pod_host_id = None
            if "machine" in pod and pod["machine"]:
                pod_host_id = pod["machine"].get("podHostId")

            logger.info(f"Pod created successfully: {pod_id}, podHostId: {pod_host_id}")

            # Store pod metadata for SSH access
            if pod_host_id:
                self._save_pod_metadata(pod_id, pod_host_id)

            return pod_id

        except Exception as e:
            logger.error(f"Error creating pod: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create pod: {e}") from e

    def get_pod_status(self, pod_id: str) -> Dict:
        """Get detailed status and metrics for a pod.

        Args:
            pod_id: Pod identifier

        Returns:
            Dictionary with pod status:
            {
                "pod_id": str,
                "status": str,  # "RUNNING", "STOPPED", "TERMINATED"
                "gpu_type": str,
                "gpu_count": int,
                "cost_per_hour": float,
                "runtime_minutes": float,
                "total_cost": float,
                "ssh_host": str,  # For RunPod: "ssh.runpod.io"
                "ssh_port": int,  # Not used for RunPod (uses proxy)
                "machine_id": str,  # Machine ID for SSH connection
            }
        """
        try:
            logger.debug(f"Getting status for pod: {pod_id}")

            # Get pod details from RunPod
            pod = runpod.get_pod(pod_id)

            if not pod:
                raise RuntimeError(f"Pod {pod_id} not found")

            # Extract status information
            status = pod.get("desiredStatus", "UNKNOWN")
            gpu_count = pod.get("gpuCount", 0)
            cost_per_hour = pod.get("costPerHr", 0.0)
            machine_id = pod.get("machineId", "")

            # Calculate runtime and cost
            runtime_minutes = 0.0
            total_cost = 0.0

            if "uptimeInSeconds" in pod:
                runtime_minutes = pod["uptimeInSeconds"] / 60.0
                total_cost = (runtime_minutes / 60.0) * cost_per_hour

            # RunPod SSH connection details
            # RunPod uses SSH proxy at ssh.runpod.io, NOT direct port mapping
            # Connection format: {pod_id}-{machine_id}@ssh.runpod.io
            ssh_host = ""
            ssh_ready = False

            # SSH is available when runtime data exists (container is running)
            if "runtime" in pod and pod["runtime"]:
                ssh_host = "ssh.runpod.io"
                ssh_ready = True
                logger.debug(f"SSH ready for pod {pod_id}: {pod_id}-{machine_id}@{ssh_host}")

            # Get GPU type display name
            gpu_type = "Unknown"
            if "gpuTypeId" in pod:
                # Try to map back to display name
                for display_name, gpu_id in self.DISPLAY_NAME_TO_GPU_ID.items():
                    if gpu_id == pod["gpuTypeId"]:
                        gpu_type = display_name
                        break

            result = {
                "pod_id": pod_id,
                "status": status,
                "gpu_type": gpu_type,
                "gpu_count": gpu_count,
                "cost_per_hour": cost_per_hour,
                "runtime_minutes": runtime_minutes,
                "total_cost": total_cost,
                "ssh_host": ssh_host,
                "ssh_port": 0,  # Not used for RunPod proxy
                "machine_id": machine_id,
                "ssh_ready": ssh_ready,
            }

            logger.info(
                f"Pod {pod_id} status: {status}, runtime: {runtime_minutes:.1f}min, "
                f"cost: ${total_cost:.4f}, ssh_ready: {ssh_ready}"
            )

            return result

        except Exception as e:
            logger.error(f"Error getting pod status: {e}", exc_info=True)
            raise RuntimeError(f"Failed to get pod status: {e}") from e

    def stop_pod(self, pod_id: str) -> bool:
        """Stop (pause) a running pod.

        Args:
            pod_id: Pod identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Stopping pod: {pod_id}")

            # RunPod SDK's stop_pod() returns None on success, raises on failure
            runpod.stop_pod(pod_id)

            logger.info(f"Pod {pod_id} stopped successfully")
            return True

        except Exception as e:
            logger.error(f"Error stopping pod: {e}", exc_info=True)
            return False

    def start_pod(self, pod_id: str) -> bool:
        """Start (resume) a stopped pod.

        Note: GPU availability is not guaranteed. The pod may start with a
        different GPU or as CPU-only if the original GPU type is unavailable.

        Args:
            pod_id: Pod identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Starting pod: {pod_id}")

            # Get pod info to retrieve GPU count (required by resume_pod)
            pod = runpod.get_pod(pod_id)
            if not pod:
                raise RuntimeError(f"Pod {pod_id} not found")

            gpu_count = pod.get("gpuCount", 1)
            logger.debug(f"Resuming pod {pod_id} with {gpu_count} GPU(s)")

            # RunPod SDK's resume_pod() requires pod_id and gpu_count
            runpod.resume_pod(pod_id, gpu_count)

            logger.info(f"Pod {pod_id} started successfully")
            logger.warning(
                f"Pod {pod_id} resumed - GPU availability not guaranteed. "
                "Check pod status to verify GPU type."
            )
            return True

        except Exception as e:
            logger.error(f"Error starting pod: {e}", exc_info=True)
            return False

    def terminate_pod(self, pod_id: str) -> bool:
        """Terminate (destroy) a pod permanently.

        Args:
            pod_id: Pod identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Terminating pod: {pod_id}")

            # RunPod SDK's terminate_pod() returns None on success, raises on failure
            runpod.terminate_pod(pod_id)

            logger.info(f"Pod {pod_id} terminated successfully")
            return True

        except Exception as e:
            logger.error(f"Error terminating pod: {e}", exc_info=True)
            return False

    def get_ssh_connection_string(self, pod_id: str) -> str:
        """Get SSH connection string for a pod.

        RunPod uses an SSH proxy system at ssh.runpod.io.
        Connection format: {podHostId}@ssh.runpod.io

        The podHostId is captured during pod creation and stored in
        ~/.autopod/pods.json since it's not available from get_pod().

        Args:
            pod_id: Pod identifier

        Returns:
            SSH connection string in format "{podHostId}@ssh.runpod.io"

        Raises:
            RuntimeError: If SSH is not yet available or podHostId not found

        Example:
            conn_str = provider.get_ssh_connection_string("abc123xyz")
            # Returns: "abc123xyz-64411540@ssh.runpod.io"
        """
        try:
            logger.debug(f"Getting SSH connection for pod: {pod_id}")

            # Get pod status to check if SSH is ready
            status = self.get_pod_status(pod_id)

            if not status.get("ssh_ready", False):
                raise RuntimeError(
                    f"SSH connection not available for pod {pod_id} "
                    "(container not started yet)"
                )

            # Load pod metadata to get podHostId
            pod_metadata = self._load_pod_metadata(pod_id)
            if not pod_metadata or "pod_host_id" not in pod_metadata:
                raise RuntimeError(
                    f"Pod host ID not found for pod {pod_id}. "
                    "Pod may have been created outside autopod."
                )

            pod_host_id = pod_metadata["pod_host_id"]
            ssh_host = status["ssh_host"]

            # RunPod SSH proxy format: {podHostId}@ssh.runpod.io
            conn_string = f"{pod_host_id}@{ssh_host}"

            logger.info(f"SSH connection string for pod {pod_id}: {conn_string}")

            return conn_string

        except Exception as e:
            logger.error(f"Error getting SSH connection string: {e}", exc_info=True)
            raise RuntimeError(f"Failed to get SSH connection string: {e}") from e

    def _generate_pod_name(self) -> str:
        """Generate a unique pod name with format: autopod-YYYY-MM-DD-NNN

        Returns:
            Generated pod name

        Example:
            "autopod-2025-11-08-001"
            "autopod-2025-11-08-042"
        """
        # Get current date
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")

        # Get list of existing pods to find next number
        try:
            pods = runpod.get_pods()

            # Filter pods created today with autopod prefix
            today_prefix = f"autopod-{date_str}-"
            today_pods = [p for p in pods if p.get("name", "").startswith(today_prefix)]

            # Extract numbers and find max
            max_num = 0
            for pod in today_pods:
                name = pod.get("name", "")
                # Extract number from end of name
                try:
                    num_str = name.split("-")[-1]
                    num = int(num_str)
                    max_num = max(max_num, num)
                except (ValueError, IndexError):
                    continue

            # Next number is max + 1
            next_num = max_num + 1

        except Exception as e:
            # If we can't get pods list, just use timestamp
            logger.warning(f"Could not get pods list for naming: {e}")
            next_num = int(now.strftime("%H%M%S")) % 1000  # Use time as number

        # Format: autopod-YYYY-MM-DD-NNN
        pod_name = f"autopod-{date_str}-{next_num:03d}"

        logger.debug(f"Generated pod name: {pod_name}")

        return pod_name

    def _retry_with_backoff(
        self,
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        *args,
        **kwargs
    ):
        """Retry a function with exponential backoff.

        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts (default: 3)
            initial_delay: Initial delay in seconds (default: 1.0)
            backoff_factor: Multiplier for each retry (default: 2.0)
            *args: Arguments to pass to function
            **kwargs: Keyword arguments to pass to function

        Returns:
            Result of successful function call

        Raises:
            Exception: Last exception if all retries fail

        Example:
            result = self._retry_with_backoff(
                runpod.get_pod,
                max_retries=3,
                pod_id="abc123"
            )
        """
        delay = initial_delay
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                if attempt == max_retries:
                    # Final attempt failed
                    logger.error(f"All {max_retries} retry attempts failed: {e}")
                    raise

                # Log retry attempt
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )

                # Wait before retrying
                time.sleep(delay)

                # Increase delay for next attempt
                delay *= backoff_factor

        # Should never reach here, but just in case
        raise last_exception if last_exception else RuntimeError("Retry failed")

    def _save_pod_metadata(self, pod_id: str, pod_host_id: str) -> None:
        """Save pod metadata to persistent storage.

        Stores pod metadata (including podHostId) to ~/.autopod/pods.json
        for SSH access. This is necessary because get_pod() doesn't return
        the podHostId.

        Args:
            pod_id: Pod identifier
            pod_host_id: Pod host ID for SSH (e.g., "abc-123")
        """
        import json
        from pathlib import Path

        # Ensure ~/.autopod directory exists
        autopod_dir = Path.home() / ".autopod"
        autopod_dir.mkdir(exist_ok=True, mode=0o700)

        pods_file = autopod_dir / "pods.json"

        # Load existing data
        pods_data = {}
        if pods_file.exists():
            try:
                with open(pods_file, "r") as f:
                    pods_data = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load pods metadata: {e}")

        # Update with new pod
        pods_data[pod_id] = {
            "pod_host_id": pod_host_id,
            "created_at": datetime.now().isoformat(),
        }

        # Save back to file
        try:
            with open(pods_file, "w") as f:
                json.dump(pods_data, f, indent=2)
            # Secure permissions
            pods_file.chmod(0o600)
            logger.debug(f"Saved metadata for pod {pod_id}")
        except Exception as e:
            logger.error(f"Failed to save pod metadata: {e}")

    def _load_pod_metadata(self, pod_id: str) -> Optional[Dict]:
        """Load pod metadata from persistent storage.

        Args:
            pod_id: Pod identifier

        Returns:
            Dictionary with pod metadata, or None if not found
        """
        import json
        from pathlib import Path

        pods_file = Path.home() / ".autopod" / "pods.json"

        if not pods_file.exists():
            return None

        try:
            with open(pods_file, "r") as f:
                pods_data = json.load(f)
            return pods_data.get(pod_id)
        except Exception as e:
            logger.warning(f"Could not load pod metadata: {e}")
            return None
