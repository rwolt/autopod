"""Tests for configuration management."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from autopod.config import (
    get_config_dir,
    get_config_path,
    ensure_config_dir,
    get_default_config,
    load_config,
    save_config,
    validate_config,
    detect_ssh_keys,
)


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory for testing."""
    config_dir = tmp_path / ".autopod"
    monkeypatch.setattr("autopod.config.get_config_dir", lambda: config_dir)
    return config_dir


def test_get_config_dir_returns_path():
    """Test that get_config_dir returns a Path object."""
    config_dir = get_config_dir()
    assert isinstance(config_dir, Path)
    assert config_dir.name == ".autopod"


def test_get_config_path_returns_json_file():
    """Test that get_config_path returns config.json path."""
    config_path = get_config_path()
    assert isinstance(config_path, Path)
    assert config_path.name == "config.json"


def test_ensure_config_dir_creates_directory(temp_config_dir):
    """Test that ensure_config_dir creates the directory."""
    assert not temp_config_dir.exists()
    ensure_config_dir()
    assert temp_config_dir.exists()


def test_ensure_config_dir_idempotent(temp_config_dir):
    """Test that ensure_config_dir can be called multiple times."""
    ensure_config_dir()
    ensure_config_dir()
    assert temp_config_dir.exists()


def test_get_default_config_structure():
    """Test that default config has correct structure."""
    config = get_default_config()

    assert "providers" in config
    assert "runpod" in config["providers"]
    assert "defaults" in config

    runpod = config["providers"]["runpod"]
    assert "api_key" in runpod
    assert "ssh_key_path" in runpod
    assert "default_template" in runpod
    assert "default_region" in runpod
    assert "cloud_type" in runpod

    defaults = config["defaults"]
    assert "gpu_preferences" in defaults
    assert "gpu_count" in defaults


def test_get_default_config_values():
    """Test that default config has expected values."""
    config = get_default_config()

    # Check GPU preferences
    gpu_prefs = config["defaults"]["gpu_preferences"]
    assert "RTX A40" in gpu_prefs
    assert "RTX A6000" in gpu_prefs
    assert "RTX A5000" in gpu_prefs

    # Check defaults
    assert config["defaults"]["gpu_count"] == 1
    assert config["providers"]["runpod"]["default_template"] == "runpod/comfyui:latest"


def test_save_and_load_config(temp_config_dir):
    """Test saving and loading configuration."""
    config = get_default_config()
    config["providers"]["runpod"]["api_key"] = "test-api-key-123"

    save_config(config)

    # Check file exists
    config_path = temp_config_dir / "config.json"
    assert config_path.exists()

    # Check file permissions (600 = owner read/write only)
    stat_info = os.stat(config_path)
    permissions = oct(stat_info.st_mode)[-3:]
    assert permissions == "600"

    # Load and verify
    loaded_config = load_config()
    assert loaded_config == config
    assert loaded_config["providers"]["runpod"]["api_key"] == "test-api-key-123"


def test_load_config_file_not_found(temp_config_dir):
    """Test that load_config raises FileNotFoundError if config doesn't exist."""
    with pytest.raises(FileNotFoundError):
        load_config()


def test_load_config_malformed_json(temp_config_dir):
    """Test that load_config raises JSONDecodeError for malformed JSON."""
    ensure_config_dir()
    config_path = temp_config_dir / "config.json"

    # Write malformed JSON
    with open(config_path, 'w') as f:
        f.write("{invalid json")

    with pytest.raises(json.JSONDecodeError):
        load_config()


def test_validate_config_valid():
    """Test that validate_config returns True for valid config."""
    config = get_default_config()
    config["providers"]["runpod"]["api_key"] = "test-key"
    config["providers"]["runpod"]["ssh_key_path"] = "/path/to/key"

    assert validate_config(config) is True


def test_validate_config_missing_providers():
    """Test that validate_config returns False if providers is missing."""
    config = {"defaults": {}}
    assert validate_config(config) is False


def test_validate_config_missing_defaults():
    """Test that validate_config returns False if defaults is missing."""
    config = {"providers": {}}
    assert validate_config(config) is False


def test_validate_config_missing_runpod_provider():
    """Test that validate_config returns False if runpod provider is missing."""
    config = {
        "providers": {"other_provider": {}},
        "defaults": {}
    }
    assert validate_config(config) is False


def test_validate_config_missing_required_fields():
    """Test that validate_config returns False if required fields are missing."""
    config = {
        "providers": {
            "runpod": {
                "api_key": "test"
                # Missing ssh_key_path and default_template
            }
        },
        "defaults": {}
    }
    assert validate_config(config) is False


def test_validate_config_empty_api_key():
    """Test that validate_config returns False if API key is empty."""
    config = get_default_config()
    config["providers"]["runpod"]["api_key"] = ""

    assert validate_config(config) is False


def test_detect_ssh_keys_no_ssh_dir(tmp_path, monkeypatch):
    """Test detect_ssh_keys when .ssh directory doesn't exist."""
    # Mock home directory to point to temp path (which has no .ssh)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    keys = detect_ssh_keys()
    assert keys == []


def test_detect_ssh_keys_finds_keys(tmp_path, monkeypatch):
    """Test detect_ssh_keys finds existing SSH keys."""
    # Create fake .ssh directory with keys
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    # Create some fake key files
    (ssh_dir / "id_rsa").touch()
    (ssh_dir / "id_ed25519").touch()
    (ssh_dir / "other_file.txt").touch()  # Should be ignored

    # Mock home directory
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    keys = detect_ssh_keys()

    # Should find id_rsa and id_ed25519
    assert len(keys) == 2
    key_names = [k.name for k in keys]
    assert "id_rsa" in key_names
    assert "id_ed25519" in key_names
    assert "other_file.txt" not in key_names
