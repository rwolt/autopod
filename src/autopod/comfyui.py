"""
ComfyUI API Client Module

This module provides a minimal synchronous client for interacting with ComfyUI's HTTP API.

Design Decisions (V1.2):
- Synchronous requests library (not async) - V1.2 only manages single pod
- Read-only operations only - workflow submission deferred to V1.3+
- No external ComfyUI client libraries - keeping dependencies minimal
- Simple, maintainable code suitable for learning the API

Future Migration Path:
- V1.2: Minimal sync client (GET endpoints only)
- V1.3: Add workflow submission (POST /prompt)
- V2.0: Evaluate async (aiohttp) or adopt comfyui-workflow-client for parallel jobs

ComfyUI API Endpoints Used:
- GET /system_stats - Health check and system info (Python version, devices, VRAM)
- GET /queue - Current queue status (running, pending jobs)
- GET /history - Execution history
- GET /object_info - Available nodes (for info display)
"""

import logging
import time
from typing import Dict, List, Optional, Any
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """
    Minimal synchronous client for ComfyUI HTTP API.

    This client provides read-only access to ComfyUI's API endpoints
    for status checking, queue monitoring, and system information.

    Args:
        base_url: ComfyUI API base URL (default: http://localhost:8188)
        timeout: Request timeout in seconds (default: 10)

    Example:
        >>> client = ComfyUIClient("http://localhost:8188")
        >>> if client.is_ready():
        ...     stats = client.get_system_stats()
        ...     print(f"VRAM: {stats['devices'][0]['vram_total']} MB")
    """

    def __init__(self, base_url: str = "http://localhost:8188", timeout: int = 10):
        """
        Initialize ComfyUI API client.

        Args:
            base_url: ComfyUI API base URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        logger.debug(f"ComfyUIClient initialized: base_url={self.base_url}, timeout={timeout}s")

    def is_ready(self, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """
        Check if ComfyUI is ready to accept requests.

        Uses exponential backoff for retries (2s, 4s, 8s by default).

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Initial delay between retries in seconds (default: 2.0)

        Returns:
            True if ComfyUI is ready, False otherwise

        Example:
            >>> client = ComfyUIClient()
            >>> if client.is_ready():
            ...     print("ComfyUI is ready!")
        """
        for attempt in range(max_retries):
            try:
                logger.debug(f"Checking ComfyUI readiness (attempt {attempt + 1}/{max_retries})")
                start_time = time.time()

                response = requests.get(
                    f"{self.base_url}/system_stats",
                    timeout=self.timeout
                )

                elapsed = time.time() - start_time
                response.raise_for_status()

                logger.info(f"ComfyUI is ready (response: {response.status_code}, elapsed: {elapsed:.2f}s)")
                return True

            except ConnectionError as e:
                logger.debug(f"Connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.debug(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.warning("ComfyUI not reachable after retries")
                    return False

            except Timeout as e:
                logger.debug(f"Request timeout (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    logger.warning("ComfyUI not responding after retries")
                    return False

            except RequestException as e:
                logger.error(f"Request failed: {e}")
                return False

        return False

    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get ComfyUI system statistics.

        Returns system information including:
        - Python version
        - Device information (GPU, RAM, VRAM)
        - System resources

        Returns:
            Dictionary containing system stats

        Raises:
            ConnectionError: If ComfyUI is not reachable
            Timeout: If request times out
            RequestException: For other HTTP errors

        Example:
            >>> client = ComfyUIClient()
            >>> stats = client.get_system_stats()
            >>> print(f"Python: {stats['python_version']}")
            >>> print(f"Device: {stats['devices'][0]['name']}")
        """
        logger.debug("Fetching system stats from ComfyUI")
        start_time = time.time()

        try:
            response = requests.get(
                f"{self.base_url}/system_stats",
                timeout=self.timeout
            )
            response.raise_for_status()

            elapsed = time.time() - start_time
            data = response.json()

            logger.info(f"Fetched system stats (elapsed: {elapsed:.2f}s)")
            logger.debug(f"System stats: {data}")

            return data

        except ConnectionError as e:
            logger.error(f"Failed to connect to ComfyUI: {e}")
            raise
        except Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise
        except RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def get_queue_info(self) -> Dict[str, Any]:
        """
        Get current queue information.

        Returns information about running and pending jobs:
        - queue_running: List of currently executing jobs
        - queue_pending: List of jobs waiting to execute

        Returns:
            Dictionary containing queue information

        Raises:
            ConnectionError: If ComfyUI is not reachable
            Timeout: If request times out
            RequestException: For other HTTP errors

        Example:
            >>> client = ComfyUIClient()
            >>> queue = client.get_queue_info()
            >>> running_count = len(queue['queue_running'])
            >>> pending_count = len(queue['queue_pending'])
            >>> print(f"Running: {running_count}, Pending: {pending_count}")
        """
        logger.debug("Fetching queue info from ComfyUI")
        start_time = time.time()

        try:
            response = requests.get(
                f"{self.base_url}/queue",
                timeout=self.timeout
            )
            response.raise_for_status()

            elapsed = time.time() - start_time
            data = response.json()

            running_count = len(data.get('queue_running', []))
            pending_count = len(data.get('queue_pending', []))

            logger.info(f"Fetched queue info: running={running_count}, pending={pending_count} (elapsed: {elapsed:.2f}s)")
            logger.debug(f"Queue data: {data}")

            return data

        except ConnectionError as e:
            logger.error(f"Failed to connect to ComfyUI: {e}")
            raise
        except Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise
        except RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def get_history(self, prompt_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get execution history.

        Args:
            prompt_id: Optional specific prompt ID to fetch (default: fetch all)

        Returns:
            Dictionary containing execution history

        Raises:
            ConnectionError: If ComfyUI is not reachable
            Timeout: If request times out
            RequestException: For other HTTP errors

        Example:
            >>> client = ComfyUIClient()
            >>> history = client.get_history()
            >>> for prompt_id, data in history.items():
            ...     print(f"Prompt {prompt_id}: {data['status']['status_str']}")

            >>> # Get specific prompt
            >>> result = client.get_history("abc-123")
        """
        logger.debug(f"Fetching history from ComfyUI (prompt_id={prompt_id})")
        start_time = time.time()

        try:
            url = f"{self.base_url}/history"
            if prompt_id:
                url += f"/{prompt_id}"

            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            elapsed = time.time() - start_time
            data = response.json()

            history_count = len(data) if isinstance(data, dict) else 0
            logger.info(f"Fetched history: {history_count} entries (elapsed: {elapsed:.2f}s)")
            logger.debug(f"History data: {data}")

            return data

        except ConnectionError as e:
            logger.error(f"Failed to connect to ComfyUI: {e}")
            raise
        except Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise
        except RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def get_object_info(self, node_class: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about available ComfyUI nodes.

        Args:
            node_class: Optional specific node class to fetch info for

        Returns:
            Dictionary containing node information (inputs, outputs, categories)

        Raises:
            ConnectionError: If ComfyUI is not reachable
            Timeout: If request times out
            RequestException: For other HTTP errors

        Example:
            >>> client = ComfyUIClient()
            >>> nodes = client.get_object_info()
            >>> print(f"Available nodes: {len(nodes)}")

            >>> # Get specific node info
            >>> load_image = client.get_object_info("LoadImage")
        """
        logger.debug(f"Fetching object info from ComfyUI (node_class={node_class})")
        start_time = time.time()

        try:
            url = f"{self.base_url}/object_info"
            if node_class:
                url += f"/{node_class}"

            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            elapsed = time.time() - start_time
            data = response.json()

            node_count = len(data) if isinstance(data, dict) else 0
            logger.info(f"Fetched object info: {node_count} nodes (elapsed: {elapsed:.2f}s)")
            logger.debug(f"Object info: {list(data.keys())[:10]}..." if node_count > 10 else f"Object info: {data}")

            return data

        except ConnectionError as e:
            logger.error(f"Failed to connect to ComfyUI: {e}")
            raise
        except Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise
        except RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
