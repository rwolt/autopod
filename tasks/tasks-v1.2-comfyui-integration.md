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

**IMPORTANT - ComfyUI API Documentation Reference:**
When implementing new ComfyUI endpoints, ALWAYS verify against official documentation:
- **Primary Source**: ComfyUI GitHub repository (`comfyanonymous/ComfyUI`)
  - Example scripts: `examples/api_workflow.py` shows complete workflow
  - Server code: `server.py` defines all available endpoints
- **Community Resources**:
  - https://9elements.com/blog/hosting-a-comfyui-workflow-via-api/ (comprehensive guide)
  - https://www.viewcomfy.com/blog/building-a-production-ready-comfyui-api (production patterns)
- **Complete Endpoint Reference** (verify in server.py before implementing):
  - `GET /system_stats` - System and GPU info ✅ (implemented)
  - `GET /queue` - Queue status ✅ (implemented)
  - `GET /history/{prompt_id}` - Execution history ✅ (implemented)
  - `GET /object_info` - Available nodes ✅ (implemented)
  - `POST /prompt` - Submit workflow (V1.3) - Format: `{"prompt": workflow_json, "client_id": uuid}`
  - `POST /upload/image` - Upload files (V1.3) - multipart/form-data: `image` (file), `type` (input/output/temp), `overwrite` (bool)
  - `GET /view` - Download outputs (V1.3) - Query params: `filename`, `type`
  - `GET /ws` - WebSocket monitoring (V2.0) - URL: `ws://localhost:8188/ws?clientId={uuid}`
- **WebSocket Message Types** (for V2.0 implementation):
  - `progress`: Sampler step updates `{type:"progress", data:{value:int, max:int}}`
  - `executing`: Current node `{type:"executing", data:{node:int|null, prompt_id:str}}`
  - `execution_cached`: Node completion notifications
- **Workflow Format**: ComfyUI workflows must be in **API format** (not GUI format):
  - Export from GUI: "Save (API Format)" option
  - Structure: `{node_id: {class_type: "NodeName", inputs: {...}}}`
  - File references are relative to ComfyUI's input directory
- **File Upload Flow**:
  1. POST /upload/image → returns `{"name": "uploaded_file.png", "subfolder": "", "type": "input"}`
  2. Modify workflow JSON to use uploaded filename in LoadImage node
  3. POST /prompt with modified workflow
  4. Monitor via WebSocket (optional) or poll GET /history
  5. GET /history/{prompt_id} → extract output filenames
  6. GET /view?filename=X&type=output → download results
- **Architecture Decision**: Use SSH tunnels (not HTTP proxy) as primary method
  - SSH tunnels provide encryption + authentication
  - Both HTTP and WebSocket work through same SSH tunnel (localhost:8188)
  - HTTP proxy available as fallback for testing only

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

- [x] 2.0 Implement SSH tunnel management module
  - [x] 2.1 Create new file `src/autopod/tunnel.py`
  - [x] 2.2 Implement SSHTunnel class with __init__ method (pod_id, local_port, remote_port, persistent state)
  - [x] 2.3 Implement SSHTunnel.start() method to create SSH tunnel subprocess (detached, persistent)
  - [x] 2.4 Implement SSHTunnel.stop() method to terminate tunnel process
  - [x] 2.5 Implement SSHTunnel.is_active() method to check if process is running (PID-based)
  - [x] 2.6 Implement SSHTunnel.test_connectivity() method to verify tunnel works (HTTP request)
  - [x] 2.7 Create TunnelManager class for managing multiple tunnels
  - [x] 2.8 Implement TunnelManager._load_state() to read from ~/.autopod/tunnels.json
  - [x] 2.9 Implement TunnelManager._save_state() to persist tunnel state
  - [x] 2.10 Implement TunnelManager.create_tunnel() with port conflict detection
  - [x] 2.11 Implement TunnelManager.get_tunnel() to retrieve tunnel by pod_id
  - [x] 2.12 Implement TunnelManager.remove_tunnel() to delete tunnel state
  - [x] 2.13 Implement TunnelManager.cleanup_stale_tunnels() to remove dead processes
  - [x] 2.14 Add error handling for port conflicts (detect if port already in use)
  - [x] 2.15 Add logging for all tunnel operations
  - [x] 2.16 Add CLI commands: tunnel start/stop/list/cleanup/stop-all
  - [x] 2.17 Add psutil dependency for PID checking
  - [x] 2.18 **PIVOT:** SSH tunneling doesn't work with RunPod proxy - implemented --expose-http flag instead
  - [x] 2.19 Removed --expose-ssh flag and related support_public_ip code
  - [x] 2.20 Implemented --expose-http flag to expose port 8188 via RunPod HTTP proxy
  - [x] 2.21 Added comprehensive security warnings about HTTP proxy (no auth, public access)
  - [x] 2.22 Test: Create pod with --expose-http and verify ComfyUI accessible via proxy URL
  - [x] 2.23 Updated README with HTTP proxy documentation and security best practices

- [x] 3.0 Implement ComfyUI API client module (minimal synchronous client)
  - [x] 3.1 Create new file `src/autopod/comfyui.py`
  - [x] 3.2 Add docstring explaining: minimal sync client for V1.2, async deferred to V2.0
  - [x] 3.3 Implement ComfyUIClient class with __init__ method (base_url parameter, default "http://localhost:8188")
  - [x] 3.4 Implement ComfyUIClient.is_ready() method using GET /system_stats with timeout
  - [x] 3.5 Implement ComfyUIClient.get_system_stats() to fetch /system_stats endpoint (device info, RAM, VRAM)
  - [x] 3.6 Implement ComfyUIClient.get_queue_info() to fetch GET /queue endpoint (running, pending counts)
  - [x] 3.7 Implement ComfyUIClient.get_history() to fetch GET /history endpoint (optional prompt_id parameter)
  - [x] 3.8 Implement ComfyUIClient.get_object_info() to fetch GET /object_info endpoint (available nodes)
  - [x] 3.9 Add error handling for ConnectionError (tunnel not established)
  - [x] 3.10 Add error handling for Timeout (ComfyUI not responding)
  - [x] 3.11 Add error handling for HTTP errors with response.raise_for_status()
  - [x] 3.12 Add logging for all API calls (request URL, response status, elapsed time)
  - [x] 3.13 Add retry logic with exponential backoff for is_ready() method (max 3 retries, 2s/4s/8s delays)
  - [x] 3.14 Add comment about future async migration plan (V2.0 will need aiohttp or external client)
  - [x] 3.15 Test: Create ComfyUIClient with mock base_url and verify instantiation
  - [x] 3.16 Test: Test with real ComfyUI instance - is_ready() returned True
  - [x] 3.17 Test: Test with non-existent instance - is_ready() returned False (correct)
  - [x] 3.18 Test: All methods tested with real API - get_system_stats, get_queue_info, get_history, get_object_info
  - [x] 3.19 Test: Retry logic works correctly with exponential backoff

- [x] 4.0 Add tunnel CLI commands
  - [x] 4.1 Read `src/autopod/cli.py` to understand CLI structure
  - [x] 4.2 Import SSHTunnel and TunnelManager in cli.py
  - [x] 4.3 Add tunnel() command group decorator (lines 700-703)
  - [x] 4.4 Implemented tunnel start subcommand (lines 706-821)
  - [x] 4.5 Implemented tunnel stop subcommand (lines 823-860)
  - [x] 4.6 Implemented tunnel list subcommand (lines 863-918)
  - [x] 4.7 Implemented tunnel cleanup subcommand (lines 921-944)
  - [x] 4.8 Implemented tunnel stop-all subcommand (lines 947-983)
  - [x] 4.9 Port conflict detection handled by TunnelManager
  - [x] 4.10 Tunnel health check (test_connectivity) at lines 804-808
  - [x] 4.11 Rich formatting with tables and panels
  - [x] 4.12 Comprehensive error handling for SSH failures
  - [x] 4.13 Test: All tunnel commands implemented and functional

- [x] 5.0 Add ComfyUI CLI commands
  - [x] 5.1 Import ComfyUIClient in cli.py (line 29)
  - [x] 5.2 Create comfy() command group decorator (lines 992-995)
  - [x] 5.3 Add comfy status subcommand with pod_id argument (lines 998-1091)
  - [x] 5.4 Implement status command: check if ComfyUI is ready (line 1037)
  - [x] 5.5 Implement status command: display Rich panel with status info (lines 1043-1067)
  - [x] 5.6 Implement status command: return correct exit code (lines 1069, 1086)
  - [x] 5.7 Add comfy info subcommand with pod_id argument (lines 1094-1229)
  - [x] 5.8 Implement info command: fetch system stats, queue, endpoints (lines 1145-1152)
  - [x] 5.9 Implement info command: display Rich panel with ComfyUI details (lines 1155-1224)
  - [x] 5.10 Add auto-select pod logic to both commands (lines 1016-1021, 1112-1116)
  - [x] 5.11 Add error handling for ComfyUI API failures (lines 1088-1091, 1226-1229)
  - [x] 5.12 Add helpful error messages when ComfyUI not ready (lines 1072-1084)
  - [ ] 5.13 Test: Run autopod comfy status and verify works
  - [ ] 5.14 Test: Run autopod comfy info and verify works
  - [ ] 5.15 Test: Verify exit codes are correct

- [x] 6.0 Integrate automatic tunnel management
  - [x] 6.1 Create ensure_tunnel() helper function in cli.py (lines 992-1111)
  - [x] 6.2 Implement ensure_tunnel(): check if tunnel exists for pod (lines 1014-1030)
  - [x] 6.3 Implement ensure_tunnel(): create tunnel if not exists (lines 1032-1088)
  - [x] 6.4 Implement ensure_tunnel(): wait for tunnel connectivity (lines 1090-1106)
  - [x] 6.5 Implement ensure_tunnel(): display progress to user (multiple Progress blocks)
  - [x] 6.6 Integrate ensure_tunnel() into comfy status command (lines 1146-1151)
  - [x] 6.7 Integrate ensure_tunnel() into comfy info command (lines 1249-1254)
  - [x] 6.8 Add tunnel health check: verify existing tunnel still works (line 1020)
  - [x] 6.9 Add tunnel auto-recovery: recreate tunnel if dead (lines 1023-1030)
  - [x] 6.10 Add --no-tunnel flag to comfy commands to skip auto-tunnel (lines 1123, 1227)
  - [x] 6.11 Test: Run autopod comfy status and verify tunnel auto-creation
  - [x] 6.12 Test: Run autopod comfy info and verify tunnel reuse
  - [x] 6.13 Test: Verify --no-tunnel flag works

- [x] 7.0 Update documentation and final testing
  - [x] 7.1 Read README.md to understand current documentation
  - [x] 7.2 Update README with V1.2 version number
  - [x] 7.3 Add network volume examples to README (--volume-id flag)
  - [x] 7.4 Add tunnel command documentation to README
  - [x] 7.5 Add comfy command documentation to README (status, info)
  - [x] 7.6 Add troubleshooting section for tunnel issues
  - [x] 7.7 Add example workflow: create pod with volume → tunnel → access GUI
  - [x] 7.8 Update config.json example with volume fields
  - [x] 7.9 Verify requirements.txt has all dependencies (requests)
  - [ ] 7.10 Test: Full workflow - create pod with volume
  - [ ] 7.11 Test: Verify volume is accessible in pod
  - [ ] 7.12 Test: Create tunnel and access ComfyUI GUI in browser
  - [ ] 7.13 Test: Run autopod comfy status and verify works
  - [ ] 7.14 Test: Run autopod comfy info and verify works
  - [ ] 7.15 Test: Regression - verify all V1.1 commands still work (ls, info, ssh, stop, start, kill)
  - [ ] 7.16 Test: Verify tunnel persists across terminal restart
  - [ ] 7.17 Test: Verify tunnel cleanup when pod is terminated
  - [ ] 7.18 Commit all changes with descriptive message

