# Task List: V1.2 - ComfyUI Integration & Network Volumes

## Relevant Files

- `src/autopod/cli.py` - Add volume flags, tunnel commands, comfy command group
- `src/autopod/providers/runpod.py` - Add network volume support in create_pod()
- `src/autopod/providers/base.py` - Update Provider interface if needed
- `src/autopod/tunnel.py` - **NEW** SSH tunnel management module
- `src/autopod/comfyui.py` - **NEW** ComfyUI API client module
- `src/autopod/config.py` - Add volume configuration fields
- `~/.autopod/tunnels.json` - **NEW** Tunnel state persistence
- `README.md` - Document V1.2 features
- `requirements.txt` - Verify requests dependency

### Notes

- V1.2 adds two new modules: `tunnel.py` and `comfyui.py`
- All V1.1 functionality must continue to work unchanged
- Each task includes testing sub-task to validate before moving forward
- Focus on clean, maintainable code that won't need refactoring

### Design Decisions

**ComfyUI Client Implementation:**
- **Decision**: Build minimal synchronous client (not using external libraries like `comfyui-workflow-client`)
- **Rationale**:
  - V1.2 only needs read-only operations (status, queue info, history)
  - No workflow submission yet (deferred to V1.3+)
  - Keep dependencies minimal (just `requests`, already required)
  - Learn the API deeply for future V2.0 work
  - External client is overkill for current needs
- **Future Migration Path**:
  - V1.2: Minimal sync client (GET endpoints only)
  - V1.3: Add workflow submission (POST /prompt)
  - V2.0: Evaluate async client (aiohttp) or adopt `comfyui-workflow-client` for parallel jobs

**Synchronous vs Async API:**
- **Decision**: Use synchronous `requests` library for V1.2
- **Rationale**:
  - Single pod only in V1.2 (no parallelism needed)
  - SSH tunnel is synchronous bottleneck anyway
  - Simpler code, easier to debug
  - Only checking status, not submitting jobs
- **When to switch to async**:
  - V2.0: Multiple jobs running simultaneously
  - V3.0: Multiple pods with concurrent monitoring
  - When WebSocket connections become necessary

**ComfyUI API Endpoints Used in V1.2:**
- `GET /system_stats` - Health check and system info (Python version, devices, VRAM)
- `GET /queue` - Current queue status (running, pending jobs)
- `GET /history` - Execution history
- `GET /object_info` - Available nodes (for info display)
- Note: `/prompt` (POST) deferred to V1.3 when we implement workflow submission

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

Example:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

## Tasks

- [x] 0.0 Create feature branch
  - [x] 0.1 Create and checkout a new branch for this feature (e.g., `git checkout -b feature/v1.2-comfyui-integration`)

- [x] 1.0 Add network volume support to pod creation
  - [x] 1.1 Read `src/autopod/providers/base.py` to understand Provider interface
  - [x] 1.2 Read `src/autopod/providers/runpod.py` to understand current create_pod() implementation
  - [x] 1.3 Read `src/autopod/config.py` to understand config structure
  - [x] 1.4 Update config.py to add volume fields (default_volume_id, default_volume_mount)
  - [x] 1.5 Add volume validation method to RunPodProvider (get_volume_info, check_volume_datacenter)
  - [x] 1.6 Update RunPodProvider.create_pod() to accept volume_id and volume_mount parameters
  - [x] 1.7 Add network_volume_id and volume_mount_path to pod creation API call
  - [x] 1.8 Update CLI connect() command to add --volume-id and --volume-mount flags
  - [x] 1.9 Add logic to read volume config from config file (CLI flag overrides config)
  - [x] 1.10 Add volume datacenter validation logic (warn if datacenter mismatch)
  - [x] 1.11 Update pod_manager to store volume info in pods.json state
  - [x] 1.12 Update pod_manager.get_pod_info() to display volume information
  - [x] 1.13 Test: Create pod with --volume-id flag and verify volume is attached
  - [x] 1.14 Test: SSH into pod and verify volume is mounted at correct path
  - [x] 1.15 Test: Run autopod info and verify volume information is displayed

- [ ] 2.0 Implement SSH tunnel management module
  - [ ] 2.1 Create new file `src/autopod/tunnel.py`
  - [ ] 2.2 Implement SSHTunnel class with __init__ method (pod_id, local_port, remote_port)
  - [ ] 2.3 Implement SSHTunnel.start() method to create SSH tunnel subprocess
  - [ ] 2.4 Implement SSHTunnel.stop() method to terminate tunnel process
  - [ ] 2.5 Implement SSHTunnel.is_active() method to check if process is running
  - [ ] 2.6 Implement SSHTunnel.test_connectivity() method to verify tunnel works (HTTP request)
  - [ ] 2.7 Create TunnelManager class for managing multiple tunnels
  - [ ] 2.8 Implement TunnelManager._get_state_file_path() to return ~/.autopod/tunnels.json
  - [ ] 2.9 Implement TunnelManager.load_tunnels() to read from tunnels.json
  - [ ] 2.10 Implement TunnelManager.save_tunnel() to persist tunnel state
  - [ ] 2.11 Implement TunnelManager.get_tunnel() to retrieve tunnel by pod_id
  - [ ] 2.12 Implement TunnelManager.remove_tunnel() to delete tunnel state
  - [ ] 2.13 Implement TunnelManager.cleanup_stale_tunnels() to remove dead processes
  - [ ] 2.14 Add error handling for port conflicts (detect if port already in use)
  - [ ] 2.15 Add logging for all tunnel operations
  - [ ] 2.16 Test: Create SSHTunnel instance and verify it can start/stop
  - [ ] 2.17 Test: Verify tunnel state is persisted to tunnels.json
  - [ ] 2.18 Test: Verify cleanup_stale_tunnels() removes dead processes

- [ ] 3.0 Implement ComfyUI API client module (minimal synchronous client)
  - [ ] 3.1 Create new file `src/autopod/comfyui.py`
  - [ ] 3.2 Add docstring explaining: minimal sync client for V1.2, async deferred to V2.0
  - [ ] 3.3 Implement ComfyUIClient class with __init__ method (base_url parameter, default "http://localhost:8188")
  - [ ] 3.4 Implement ComfyUIClient.is_ready() method using GET /system_stats with timeout
  - [ ] 3.5 Implement ComfyUIClient.get_system_stats() to fetch /system_stats endpoint (device info, RAM, VRAM)
  - [ ] 3.6 Implement ComfyUIClient.get_queue_info() to fetch GET /queue endpoint (running, pending counts)
  - [ ] 3.7 Implement ComfyUIClient.get_history() to fetch GET /history endpoint (optional prompt_id parameter)
  - [ ] 3.8 Implement ComfyUIClient.get_object_info() to fetch GET /object_info endpoint (available nodes)
  - [ ] 3.9 Add error handling for ConnectionError (tunnel not established)
  - [ ] 3.10 Add error handling for Timeout (ComfyUI not responding)
  - [ ] 3.11 Add error handling for HTTP errors with response.raise_for_status()
  - [ ] 3.12 Add logging for all API calls (request URL, response status, elapsed time)
  - [ ] 3.13 Add retry logic with exponential backoff for is_ready() method (max 3 retries, 2s/4s/8s delays)
  - [ ] 3.14 Add comment about future async migration plan (V2.0 will need aiohttp or external client)
  - [ ] 3.15 Test: Create ComfyUIClient with mock base_url and verify instantiation
  - [ ] 3.16 Test: Mock successful /system_stats response and verify is_ready() returns True
  - [ ] 3.17 Test: Mock connection error and verify is_ready() returns False
  - [ ] 3.18 Test: Mock timeout and verify proper error handling
  - [ ] 3.19 Test: Verify retry logic attempts correct number of times with delays

- [ ] 4.0 Add tunnel CLI commands
  - [ ] 4.1 Read `src/autopod/cli.py` to understand CLI structure
  - [ ] 4.2 Import SSHTunnel and TunnelManager in cli.py
  - [ ] 4.3 Add tunnel() command function with pod_id argument (optional)
  - [ ] 4.4 Add --stop flag to tunnel command
  - [ ] 4.5 Add --status flag to tunnel command
  - [ ] 4.6 Implement tunnel start logic (create tunnel, save state, display message)
  - [ ] 4.7 Implement tunnel stop logic (load tunnel, stop process, remove state)
  - [ ] 4.8 Implement tunnel status logic (check if active, display info)
  - [ ] 4.9 Add auto-select pod logic if pod_id not specified
  - [ ] 4.10 Add port conflict detection (check if 8188 already in use)
  - [ ] 4.11 Add tunnel health check (test connectivity before reporting success)
  - [ ] 4.12 Add Rich formatting for tunnel status display
  - [ ] 4.13 Add error handling for SSH connection failures
  - [ ] 4.14 Test: Run autopod tunnel and verify tunnel is created
  - [ ] 4.15 Test: Run autopod tunnel --status and verify correct status shown
  - [ ] 4.16 Test: Run autopod tunnel --stop and verify tunnel is closed
  - [ ] 4.17 Test: Verify tunnel persists across terminal sessions

- [ ] 5.0 Add ComfyUI CLI commands
  - [ ] 5.1 Import ComfyUIClient in cli.py
  - [ ] 5.2 Create comfy() command group decorator
  - [ ] 5.3 Add comfy status subcommand with pod_id argument (optional)
  - [ ] 5.4 Implement status command: check if ComfyUI is ready
  - [ ] 5.5 Implement status command: display Rich panel with status info
  - [ ] 5.6 Implement status command: return correct exit code (0=ready, 1=not ready)
  - [ ] 5.7 Add comfy info subcommand with pod_id argument (optional)
  - [ ] 5.8 Implement info command: fetch system stats, queue, endpoints
  - [ ] 5.9 Implement info command: display Rich panel with ComfyUI details
  - [ ] 5.10 Add auto-select pod logic to both commands
  - [ ] 5.11 Add error handling for ComfyUI API failures
  - [ ] 5.12 Add helpful error messages when ComfyUI not ready (suggest wait time)
  - [ ] 5.13 Test: Run autopod comfy status immediately after pod creation
  - [ ] 5.14 Test: Verify status shows "Starting..." initially
  - [ ] 5.15 Test: Wait 60s and verify status shows "Ready"
  - [ ] 5.16 Test: Run autopod comfy info and verify correct information displayed
  - [ ] 5.17 Test: Verify exit codes are correct

- [ ] 6.0 Integrate automatic tunnel management
  - [ ] 6.1 Create ensure_tunnel() helper function in cli.py
  - [ ] 6.2 Implement ensure_tunnel(): check if tunnel exists for pod
  - [ ] 6.3 Implement ensure_tunnel(): create tunnel if not exists
  - [ ] 6.4 Implement ensure_tunnel(): wait for tunnel connectivity (with timeout)
  - [ ] 6.5 Implement ensure_tunnel(): display progress to user
  - [ ] 6.6 Integrate ensure_tunnel() into comfy status command
  - [ ] 6.7 Integrate ensure_tunnel() into comfy info command
  - [ ] 6.8 Add tunnel health check: verify existing tunnel still works
  - [ ] 6.9 Add tunnel auto-recovery: recreate tunnel if dead
  - [ ] 6.10 Add --no-tunnel flag to comfy commands to skip auto-tunnel
  - [ ] 6.11 Test: Run autopod comfy status without existing tunnel
  - [ ] 6.12 Test: Verify tunnel is auto-created and command succeeds
  - [ ] 6.13 Test: Run autopod comfy info with existing tunnel
  - [ ] 6.14 Test: Verify existing tunnel is reused (no duplicate)
  - [ ] 6.15 Test: Kill tunnel process manually, run comfy command
  - [ ] 6.16 Test: Verify tunnel is auto-recreated

- [ ] 7.0 Update documentation and final testing
  - [ ] 7.1 Read README.md to understand current documentation
  - [ ] 7.2 Update README with V1.2 version number
  - [ ] 7.3 Add network volume examples to README (--volume-id flag)
  - [ ] 7.4 Add tunnel command documentation to README
  - [ ] 7.5 Add comfy command documentation to README (status, info)
  - [ ] 7.6 Add troubleshooting section for tunnel issues
  - [ ] 7.7 Add example workflow: create pod with volume → tunnel → access GUI
  - [ ] 7.8 Update config.json example with volume fields
  - [ ] 7.9 Verify requirements.txt has all dependencies (requests)
  - [ ] 7.10 Test: Full workflow - create pod with volume
  - [ ] 7.11 Test: Verify volume is accessible in pod
  - [ ] 7.12 Test: Create tunnel and access ComfyUI GUI in browser
  - [ ] 7.13 Test: Run autopod comfy status and verify works
  - [ ] 7.14 Test: Run autopod comfy info and verify works
  - [ ] 7.15 Test: Regression - verify all V1.1 commands still work (ls, info, ssh, stop, start, kill)
  - [ ] 7.16 Test: Verify tunnel persists across terminal restart
  - [ ] 7.17 Test: Verify tunnel cleanup when pod is terminated
  - [ ] 7.18 Commit all changes with descriptive message

