# Task List: RunPod Pod Lifecycle Management

## Relevant Files

- `src/autopod/__init__.py` - Main package initialization
- `src/autopod/providers/__init__.py` - Provider package initialization
- `src/autopod/providers/base.py` - Abstract CloudProvider base class
- `src/autopod/providers/runpod.py` - RunPod provider implementation
- `src/autopod/config.py` - Configuration management (load, validate, init wizard)
- `src/autopod/logging.py` - Logging setup with rotating file handler
- `src/autopod/ssh.py` - SSH tunnel and shell access management
- `src/autopod/pod_manager.py` - Pod control and state management
- `src/autopod/cli.py` - Rich-based CLI interface
- `requirements.txt` - Python dependencies
- `setup.py` or `pyproject.toml` - Package configuration
- `tests/test_config.py` - Unit tests for configuration
- `tests/test_providers/test_base.py` - Tests for provider abstraction
- `tests/test_providers/test_runpod.py` - Tests for RunPod provider
- `tests/manual/test_pod_creation.py` - Manual test script for real API calls
- `README.md` - User documentation with examples

### Notes

- Unit tests should be placed in the `tests/` directory mirroring the source structure
- Use `pytest` to run tests
- Manual test scripts go in `tests/manual/` and require real API keys

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

Example:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

## Tasks

- [x] 0.0 Create feature branch
  - [x] 0.1 Create and checkout a new branch `feature/runpod-pod-lifecycle`

- [x] 1.0 Set up project structure and dependencies
  - [x] 1.1 Create `requirements.txt` with V1 dependencies (rich, requests, websocket-client, paramiko, runpod SDK) and `setup.py`/`pyproject.toml`
  - [x] 1.2 Install dependencies in conda environment and verify imports work
  - [x] 1.3 Create test directory structure (`tests/`, `tests/manual/`, `tests/test_providers/`)

- [x] 2.0 Implement provider abstraction layer
  - [x] 2.1 Create `src/autopod/providers/base.py` with `CloudProvider` abstract base class
  - [x] 2.2 Define all abstract methods (authenticate, get_gpu_availability, create_pod, get_pod_status, stop_pod, terminate_pod, get_ssh_connection_string) with comprehensive docstrings
  - [x] 2.3 Create `tests/test_providers/test_base.py` with basic interface tests

- [x] 3.0 Implement configuration management
  - [x] 3.1 Create `src/autopod/config.py` with functions for loading, saving, and validating config (`~/.autopod/config.json` with chmod 600)
  - [x] 3.2 Implement SSH key detection (`detect_ssh_keys()`) and interactive setup wizard (`config_init_wizard()`)
  - [x] 3.3 Add default config template with sensible defaults (RTX A40 preference, regions, etc.)
  - [x] 3.4 Create `tests/test_config.py` with tests for config loading, validation, and SSH key detection

- [x] 4.0 Implement logging system
  - [x] 4.1 Create `src/autopod/logging.py` with `setup_logging()` function using RotatingFileHandler (10MB max, 5 backups at `~/.autopod/logs/autopod.log`)
  - [x] 4.2 Configure log format, levels (DEBUG for file, INFO for console), and add filter to redact sensitive data (API keys, credentials)
  - [x] 4.3 Create `tests/test_logging.py` with tests for log directory creation and sensitive data redaction

- [x] 5.0 Implement RunPod provider
  - [x] 5.1 Create `src/autopod/providers/runpod.py` with `RunPodProvider` class, implement authentication and GPU availability checking with type mapping
  - [x] 5.2 Implement pod lifecycle methods (create_pod with GPU fallback A40→A6000→A5000, get_pod_status with cost calculation, stop_pod, terminate_pod, get_ssh_connection_string)
  - [x] 5.3 Add pod naming (`autopod-YYYY-MM-DD-NNN`), error handling, retry logic with exponential backoff, and logging to all methods
  - [x] 5.4 Create `tests/test_providers/test_runpod.py` with mocked API tests and `tests/manual/test_pod_creation.py` manual test script with Rich output

- [x] 6.0 Implement SSH tunnel management
  - [x] 6.1 Create `src/autopod/ssh.py` with `SSHTunnel` class implementing tunnel lifecycle (create_tunnel, is_alive, close, wait_for_connection)
  - [x] 6.2 Implement `open_shell()` for direct SSH exec into pod with host key verification handling and timeout logic
  - [x] 6.3 Add comprehensive logging and error handling for connection failures
  - [x] 6.4 Create `tests/test_ssh.py` with tests using mocked subprocess calls

- [ ] 7.0 Implement pod control commands
  - [ ] 7.1 Create `src/autopod/pod_manager.py` with `PodManager` class implementing list_pods, get_pod_info, stop_pod, terminate_pod, shell_into_pod methods
  - [ ] 7.2 Add Rich formatting (Table for list, Panel for info) with runtime and cost display
  - [ ] 7.3 Implement state persistence to `~/.autopod/pods.json` (save_pod_state, load_pod_state functions)
  - [ ] 7.4 Create `tests/test_pod_manager.py` with tests for pod listing and state persistence

- [ ] 8.0 Implement CLI interface
  - [ ] 8.1 Create `src/autopod/cli.py` with main entry point and implement `config init` command with Rich wizard flow
  - [ ] 8.2 Implement `connect` command with flags (--gpu, --gpu-count, --volume, --dry-run, --interactive) and Rich table for GPU selection
  - [ ] 8.3 Implement pod management commands (list, info, stop, kill, shell) and `logs` command
  - [ ] 8.4 Add Rich progress bars, Ctrl+C signal handler, error handling, help text, and create `tests/test_cli.py`

- [ ] 9.0 Testing and documentation
  - [ ] 9.1 Run all unit tests with pytest, fix any failures, and run manual test script with real RunPod API
  - [ ] 9.2 Test end-to-end workflows (config init, pod creation with defaults and --interactive, SSH tunnel, pod shell, pod stop/kill, --dry-run)
  - [ ] 9.3 Update README.md with installation instructions and working examples for all commands and flags
  - [ ] 9.4 Verify all README examples work, commit final changes, and merge feature branch to main
