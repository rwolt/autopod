# PRD: V1.2 - ComfyUI Integration & Network Volumes

## Introduction/Overview

V1.2 adds ComfyUI integration to autopod, enabling users to interact with ComfyUI instances running on RunPod pods. This release focuses on establishing reliable connectivity through SSH tunnels and enabling basic API interactions.

**Problem Statement:**
V1.1 provides pod lifecycle management but doesn't integrate with ComfyUI, the primary workload for autopod. Users need to:
1. Attach network volumes (for models/checkpoints) during pod creation
2. Access ComfyUI GUI and API through SSH tunnels
3. Verify ComfyUI is running and ready
4. Perform basic API operations (check status, list workflows)

**Goal:**
Enable users to create pods with network volumes attached, establish SSH tunnels to ComfyUI, and interact with the ComfyUI API programmatically.

---

## Goals

1. **Network Volume Integration**: Attach RunPod network volumes during pod creation
2. **SSH Tunnel Management**: Create and maintain tunnels to ComfyUI (localhost:8188 → pod:8188)
3. **ComfyUI Connectivity**: Verify ComfyUI is accessible and responding
4. **Basic API Operations**: Check ComfyUI status, list available endpoints
5. **Foundation for V1.3+**: Establish patterns for workflow submission (deferred to later versions)

---

## User Stories

### US-1: Network Volume Attachment
**As a** user with existing models stored in a RunPod network volume
**I want** to attach my volume when creating a pod
**So that** ComfyUI has access to my models without re-downloading them

**Acceptance Criteria:**
- `autopod connect --volume-id <id>` attaches network volume during creation
- Volume mount path configurable (default: `/workspace`)
- `autopod info` shows attached volume ID and mount path
- Config file supports `default_volume_id` setting
- Clear error if volume doesn't exist or is in wrong datacenter

### US-2: SSH Tunnel to ComfyUI
**As a** user who wants to access ComfyUI on my pod
**I want** autopod to create an SSH tunnel automatically
**So that** I can access ComfyUI at http://localhost:8188

**Acceptance Criteria:**
- New command: `autopod tunnel <pod-id>` creates SSH tunnel
- Tunnel runs in background (non-blocking)
- Shows message: `"ComfyUI available at http://localhost:8188"`
- Tunnel stays open until explicitly closed or pod terminated
- `autopod tunnel --stop` closes tunnel
- `autopod tunnel --status` shows if tunnel is active

### US-3: ComfyUI Status Check
**As a** user who just created a pod
**I want** to verify ComfyUI is running and ready
**So that** I don't waste time trying to connect before it's ready

**Acceptance Criteria:**
- New command: `autopod comfy status` checks if ComfyUI is responding
- Shows: `"ComfyUI: Ready"` or `"ComfyUI: Starting (container still initializing)"`
- Automatically establishes tunnel if not already active
- Returns exit code 0 if ready, 1 if not ready
- Works with auto-selected pod (single pod scenario)

### US-4: ComfyUI API Info
**As a** user exploring ComfyUI capabilities
**I want** to see basic API information
**So that** I understand what operations are available

**Acceptance Criteria:**
- New command: `autopod comfy info` shows ComfyUI details
- Displays: version, available endpoints, queue status
- Shows number of pending/running jobs (if any)
- Formatted with Rich panels for readability

---

## Functional Requirements

### FR-1: Network Volume Attachment

**Implementation:**
1. Add `--volume-id` flag to `autopod connect`:
   ```bash
   autopod connect --volume-id <volume-id> --volume-mount /workspace
   ```

2. Config file support (`~/.autopod/config.json`):
   ```json
   {
     "providers": {
       "runpod": {
         "default_volume_id": "abc123xyz",
         "default_volume_mount": "/workspace"
       }
     }
   }
   ```

3. Pass to RunPod API during pod creation:
   ```python
   pod_params = {
       "name": pod_name,
       "image_name": template,
       "gpu_type_id": gpu_type,
       "gpu_count": gpu_count,
       "cloud_type": cloud_type,
       "container_disk_in_gb": disk_size,
       "volume_in_gb": 0,  # Not using pod volume
       "network_volume_id": volume_id,  # Network volume
       "volume_mount_path": mount_path
   }
   ```

4. Validate volume exists and is accessible:
   - Query RunPod API for volume details
   - Check volume is in same datacenter as pod (if datacenter specified)
   - Show warning if volume is in different datacenter

5. Display in `autopod info`:
   ```
   Pod Information
   ├─ Volume:     abc123xyz → /workspace
   ```

**Location**: `src/autopod/cli.py:connect()`, `src/autopod/providers/runpod.py:create_pod()`

### FR-2: SSH Tunnel Management

**Implementation:**
1. Create new module `src/autopod/tunnel.py`:
   ```python
   class SSHTunnel:
       def __init__(self, pod_id, local_port=8188, remote_port=8188):
           self.pod_id = pod_id
           self.local_port = local_port
           self.remote_port = remote_port
           self.process = None

       def start(self, ssh_connection_string, ssh_key_path):
           """Start SSH tunnel in background"""
           cmd = [
               "ssh", "-N", "-L",
               f"{self.local_port}:localhost:{self.remote_port}",
               "-i", ssh_key_path,
               "-o", "StrictHostKeyChecking=accept-new",
               ssh_connection_string
           ]
           self.process = subprocess.Popen(cmd)
           return self.process.pid

       def stop(self):
           """Stop SSH tunnel"""
           if self.process:
               self.process.terminate()
               self.process.wait(timeout=5)

       def is_active(self):
           """Check if tunnel is still running"""
           return self.process and self.process.poll() is None

       def test_connectivity(self, timeout=5):
           """Test if ComfyUI is accessible through tunnel"""
           import requests
           try:
               response = requests.get(
                   f"http://localhost:{self.local_port}/",
                   timeout=timeout
               )
               return response.status_code == 200
           except requests.RequestException:
               return False
   ```

2. Add CLI commands:
   ```python
   @cli.command()
   @click.argument("pod_id", required=False)
   @click.option("--stop", is_flag=True, help="Stop tunnel")
   @click.option("--status", is_flag=True, help="Check tunnel status")
   def tunnel(pod_id, stop, status):
       """Manage SSH tunnel to ComfyUI"""
       pass
   ```

3. Store tunnel state in `~/.autopod/tunnels.json`:
   ```json
   {
     "pod-abc123": {
       "pid": 12345,
       "local_port": 8188,
       "remote_port": 8188,
       "started_at": "2025-11-10T23:50:00Z"
     }
   }
   ```

4. Automatic cleanup:
   - Check tunnel health on each operation
   - Remove stale tunnel entries (process not running)
   - Close tunnels when pod is terminated

**Location**: `src/autopod/tunnel.py`, `src/autopod/cli.py:tunnel()`

### FR-3: ComfyUI Status Check

**Implementation:**
1. Create new module `src/autopod/comfyui.py`:
   ```python
   class ComfyUIClient:
       def __init__(self, base_url="http://localhost:8188"):
           self.base_url = base_url

       def is_ready(self, timeout=5):
           """Check if ComfyUI is responding"""
           try:
               response = requests.get(
                   f"{self.base_url}/system_stats",
                   timeout=timeout
               )
               return response.status_code == 200
           except requests.RequestException:
               return False

       def get_system_stats(self):
           """Get ComfyUI system information"""
           response = requests.get(f"{self.base_url}/system_stats")
           response.raise_for_status()
           return response.json()

       def get_queue_info(self):
           """Get current queue status"""
           response = requests.get(f"{self.base_url}/queue")
           response.raise_for_status()
           return response.json()

       def get_history(self, prompt_id=None):
           """Get execution history"""
           url = f"{self.base_url}/history"
           if prompt_id:
               url += f"/{prompt_id}"
           response = requests.get(url)
           response.raise_for_status()
           return response.json()
   ```

2. Add CLI command group:
   ```python
   @cli.group()
   def comfy():
       """ComfyUI operations"""
       pass

   @comfy.command()
   @click.argument("pod_id", required=False)
   def status(pod_id):
       """Check ComfyUI status"""
       # Auto-select pod if not specified
       # Ensure tunnel is active
       # Check ComfyUI connectivity
       # Display status with Rich
       pass
   ```

3. Status display:
   ```
   ┌─ ComfyUI Status ─────────────────────────────┐
   │ Status:      Ready ✓                         │
   │ Tunnel:      localhost:8188 → pod-abc:8188   │
   │ Queue:       0 pending, 0 running            │
   │ System:      GPU 45GB/48GB, CPU 12%          │
   └──────────────────────────────────────────────┘
   ```

**Location**: `src/autopod/comfyui.py`, `src/autopod/cli.py:comfy()`

### FR-4: ComfyUI Info Display

**Implementation:**
1. Extend `ComfyUIClient`:
   ```python
   def get_embeddings(self):
       """List available embeddings"""
       response = requests.get(f"{self.base_url}/embeddings")
       response.raise_for_status()
       return response.json()

   def get_extensions(self):
       """List installed extensions"""
       response = requests.get(f"{self.base_url}/extensions")
       response.raise_for_status()
       return response.json()
   ```

2. Add CLI command:
   ```python
   @comfy.command()
   @click.argument("pod_id", required=False)
   def info(pod_id):
       """Show ComfyUI information"""
       # Display system stats, extensions, queue info
       pass
   ```

3. Info display:
   ```
   ┌─ ComfyUI Information ────────────────────────┐
   │ Version:     Latest                          │
   │ Endpoints:   /prompt, /queue, /history       │
   │              /system_stats, /embeddings      │
   │ Extensions:  5 installed                     │
   │ Models:      /workspace/models/              │
   └──────────────────────────────────────────────┘

   Queue Status:
   • Pending: 0 jobs
   • Running: 0 jobs
   ```

**Location**: `src/autopod/comfyui.py`, `src/autopod/cli.py:comfy()`

### FR-5: Automatic Tunnel on ComfyUI Commands

**Implementation:**
When any `autopod comfy` command is run:
1. Check if tunnel exists for pod
2. If not, automatically create tunnel
3. Wait for tunnel to be ready (test connectivity)
4. Proceed with command

This provides seamless UX - users don't need to manually run `autopod tunnel` first.

```python
def ensure_tunnel(pod_id, provider, console):
    """Ensure SSH tunnel is active, create if needed"""
    tunnel_manager = TunnelManager()
    tunnel = tunnel_manager.get_tunnel(pod_id)

    if not tunnel or not tunnel.is_active():
        console.print("[cyan]Creating SSH tunnel...[/cyan]")
        ssh_info = provider.get_ssh_connection_string(pod_id)
        tunnel = SSHTunnel(pod_id)
        tunnel.start(ssh_info, ssh_key_path)

        # Wait for tunnel to be ready
        for i in range(10):
            if tunnel.test_connectivity():
                console.print("[green]✓ Tunnel established[/green]")
                tunnel_manager.save_tunnel(pod_id, tunnel)
                return tunnel
            time.sleep(1)

        raise RuntimeError("Tunnel failed to establish")

    return tunnel
```

**Location**: `src/autopod/tunnel.py`, `src/autopod/cli.py`

---

## Non-Goals (Out of Scope for V1.2)

### Explicitly NOT in V1.2:
1. **Workflow Submission**: Deferred to V1.3+ (focus is connectivity, not execution)
2. **File Upload/Download**: Deferred to V1.3+ (will use ComfyUI API)
3. **WebSocket Monitoring**: Deferred to V2.0 (real-time progress tracking)
4. **Multi-Pod Tunnels**: Deferred to V3.0 (single pod only in V1.2)
5. **Custom Port Configuration**: Fixed to 8188 (ComfyUI default)
6. **Cloudflare R2 Integration**: Deferred to V2.0+
7. **Job Queue Management**: Deferred to V2.0
8. **Cost Tracking During Jobs**: Deferred to V2.0
9. **Integration Tests**: Manual testing only (like V1.1)
10. **Custom ComfyUI Templates**: Use RunPod's default template

---

## Technical Considerations

### Network Volume Datacenter Locality
- Network volumes are datacenter-specific
- Pod must be in same datacenter as volume to attach
- If user specifies `--datacenter` AND `--volume-id`, validate compatibility
- Provide clear error: `"Volume abc123 is in US-GA-1, but you requested CA-MTL-1"`
- Suggest: Query volume datacenter and auto-select matching datacenter

### SSH Tunnel Reliability
- Tunnels can die silently (network issues, pod restart, etc.)
- Check tunnel health before each ComfyUI operation
- Automatically recreate tunnel if detected as dead
- Store tunnel PID for cleanup on exit

### ComfyUI Startup Time
- ComfyUI container takes 30-60s to start after pod creation
- `autopod comfy status` should retry with backoff
- Show progress: `"Waiting for ComfyUI to start... (30s elapsed)"`
- Max wait time: 2 minutes (then suggest checking pod logs)

### Port Conflicts
- localhost:8188 might already be in use
- Detect port conflicts before creating tunnel
- For V1.2: Just error with helpful message
- For V3.0: Auto-select different port (8189, 8190, etc.)

### Backward Compatibility
- All V1.0/V1.1 commands continue to work unchanged
- New commands are additive only
- Config file format is backward compatible (new fields are optional)

---

## Success Metrics

### V1.2 is successful when:
1. ✅ Can create pod with network volume attached
2. ✅ Can establish SSH tunnel to ComfyUI (localhost:8188)
3. ✅ Can verify ComfyUI is ready via `autopod comfy status`
4. ✅ Can view ComfyUI info via `autopod comfy info`
5. ✅ Can open ComfyUI GUI at http://localhost:8188 in browser
6. ✅ Tunnels are automatically managed (created on demand, cleaned up on exit)
7. ✅ All V1.1 functionality still works

### Validation:
- Manual test: Create pod with volume → tunnel → access GUI
- Manual test: `autopod comfy status` works immediately after creation
- Manual test: `autopod comfy info` shows correct information
- Manual test: Tunnel survives pod stop/start cycle
- Manual test: Multiple tunnel operations don't create duplicate tunnels

---

## Open Questions

1. **Volume Discovery**:
   - Q: Should autopod list available volumes?
   - A: Nice to have, but not blocking. User can check RunPod UI for volume IDs.
   - Impact: Defer `autopod volume list` to V1.3+ if time permits

2. **Tunnel Auto-Start**:
   - Q: Should `autopod connect` automatically start tunnel after creation?
   - A: Yes, if ComfyUI is detected as ready. Provide `--no-tunnel` flag to skip.
   - Impact: Better UX, but need reliable ComfyUI readiness check

3. **Tunnel Cleanup**:
   - Q: Should tunnels close when terminal exits?
   - A: No - tunnels should persist across terminal sessions (use `autopod tunnel --stop`)
   - Impact: Need proper process management and state tracking

4. **ComfyUI Template**:
   - Q: Which RunPod template should be default?
   - A: Use `runpod/comfyui:latest` (already default in V1.0)
   - Impact: None - already implemented

---

## Implementation Phases

### Phase 1: Network Volume Integration (Priority 1)
- FR-1: Add volume attachment to pod creation
- Config file support for default volume
- Validation and error handling

### Phase 2: SSH Tunnel Management (Priority 1)
- FR-2: Create tunnel.py module
- CLI commands for tunnel management
- State persistence in tunnels.json

### Phase 3: ComfyUI API Client (Priority 2)
- FR-3: Create comfyui.py module
- Status check implementation
- FR-4: Info display

### Phase 4: Integration & UX Polish (Priority 2)
- FR-5: Automatic tunnel on comfy commands
- Tunnel health checks and auto-recovery
- Rich formatting for all displays

### Phase 5: Manual Testing (Priority 3)
- Test all scenarios end-to-end
- Verify volume attachment works
- Verify tunnel reliability
- Update README with V1.2 features

---

## Dependencies

### External:
- `requests` - HTTP client for ComfyUI API (already a dependency)
- `subprocess` - SSH tunnel process management (stdlib)

### Internal:
- V1.1 Pod Lifecycle: All functionality preserved
- SSH connection string logic: Reuse existing implementation

### Documentation:
- Update README with network volume examples
- Document tunnel commands
- Document comfy commands
- Add troubleshooting section for tunnel issues

---

## Appendix: Testing Checklist

### Manual Test Plan for V1.2:

```bash
# Test 1: Network volume attachment
1. Create pod with volume: autopod connect --volume-id <id>
2. SSH into pod: autopod ssh
3. Verify volume mounted: ls /workspace
4. ✓ Verify: Files from network volume are accessible

# Test 2: SSH tunnel creation
1. Create tunnel: autopod tunnel <pod-id>
2. ✓ Verify: Shows "ComfyUI available at http://localhost:8188"
3. Open browser: http://localhost:8188
4. ✓ Verify: ComfyUI GUI loads

# Test 3: Tunnel persistence
1. Create tunnel: autopod tunnel
2. Close terminal
3. Open new terminal
4. Check status: autopod tunnel --status
5. ✓ Verify: Tunnel still active

# Test 4: ComfyUI status check
1. Immediately after pod creation: autopod comfy status
2. ✓ Verify: Shows "Starting..." initially
3. Wait 30-60s, check again
4. ✓ Verify: Shows "Ready" when available

# Test 5: ComfyUI info
1. Run: autopod comfy info
2. ✓ Verify: Shows version, endpoints, queue status
3. ✓ Verify: Tunnel auto-created if not already active

# Test 6: Automatic tunnel management
1. Create pod (no tunnel)
2. Run: autopod comfy status (should auto-create tunnel)
3. ✓ Verify: Tunnel created automatically
4. Run: autopod comfy info
5. ✓ Verify: Uses existing tunnel (no duplicate)

# Test 7: Volume datacenter validation
1. Get volume datacenter from RunPod UI
2. Try: autopod connect --volume-id <id> --datacenter <different-dc>
3. ✓ Verify: Shows helpful error about datacenter mismatch

# Test 8: Regression check
1. Run all V1.1 commands: connect, ls, info, ssh, stop, start, kill
2. ✓ Verify: All work exactly as before
```

---

## Version History

- **v1.0** - 2025-11-10 - Initial PRD for V1.2 ComfyUI integration

