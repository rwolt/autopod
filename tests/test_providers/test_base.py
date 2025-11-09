"""Tests for CloudProvider abstract base class."""

import pytest
from autopod.providers.base import CloudProvider


def test_cannot_instantiate_abstract_class():
    """Verify that CloudProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        CloudProvider()


def test_subclass_must_implement_all_methods():
    """Verify that subclasses must implement all abstract methods."""

    class IncompleteProvider(CloudProvider):
        """Incomplete provider implementation (missing methods)."""
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()


def test_complete_subclass_can_be_instantiated():
    """Verify that a complete implementation can be instantiated."""

    class CompleteProvider(CloudProvider):
        """Complete provider implementation."""

        def authenticate(self, api_key: str) -> bool:
            return True

        def get_gpu_availability(self, gpu_type: str) -> dict:
            return {"available": False, "count": 0}

        def create_pod(self, config: dict) -> str:
            return "test-pod-id"

        def get_pod_status(self, pod_id: str) -> dict:
            return {"status": "running"}

        def stop_pod(self, pod_id: str) -> bool:
            return True

        def terminate_pod(self, pod_id: str) -> bool:
            return True

        def get_ssh_connection_string(self, pod_id: str) -> str:
            return "root@test:22"

    # Should not raise
    provider = CompleteProvider()
    assert provider is not None
    assert isinstance(provider, CloudProvider)
