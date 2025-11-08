# PRD: RunPod Pod Lifecycle Management

**Feature Name:** RunPod Pod Lifecycle Management
**Version:** 1.0
**Status:** Draft
**Created:** 2025-11-08

---

## Introduction/Overview

This feature enables autopod to programmatically manage the lifecycle of RunPod GPU instances. Users need a reliable way to create pods with ComfyUI, establish secure SSH tunnels for API access, and cleanly stop/terminate pods to minimize costs. This is the foundation upon which all other autopod features will be built.

**Problem it solves:** Manually creating pods, configuring SSH, and remembering to shut them down is error-prone and leads to wasted compute costs. This feature automates the entire pod lifecycle.

**Goal:** Provide a simple, reliable CLI interface for creating, connecting to, and destroying RunPod pods running ComfyUI.

---

## Goals

1. Enable users to create RunPod pods running ComfyUI with a single command
2. Automatically establish SSH tunnel for accessing ComfyUI API and GUI
3. Provide terminal SSH access for debugging and manual operations
4. Handle failures gracefully with automatic retries and cost-safe fallback
5. Allow users to stop (pause) or terminate (destroy) pods to control costs
6. Store configuration and pod state persistently for V2 compatibility
7. Minimize time between "run command" and "ComfyUI is accessible"
8. Provide excellent logging for debugging

---

## User Stories

**As a user, I want to:**

1. **Configure autopod once** so I don't have to provide credentials every time
   - Store RunPod API key in `~/.autopod/config.json`
   - Automated SSH key detection (keychain first, then interactive setup)
   - First-time setup wizard that holds my hand through SSH configuration
   - Config file should include all preferences and defaults

2. **Create a pod with filtered GPU selection** so I see only relevant options
   - Filter by network speed (high/extreme for my use case)
   - Filter by CUDA version (e.g., require CUDA 12.8 for specific workflows)
   - Show only 4-5 GPUs I use regularly (primarily secure cloud)
   - See available GPU types with pricing
   - Select GPU type, count, and optional network volume interactively
   - See estimated cost per hour before confirming

3. **Choose which RunPod template to use** for flexibility
   - Default to official RunPod ComfyUI template (`runpod/comfyui:latest`)
   - Option to specify custom template via flag or interactive selection
   - Template selection should be saved as default for future use

4. **Automatically connect to the pod** so I can immediately access ComfyUI
   - SSH tunnel is created automatically after pod is ready
   - ComfyUI GUI is accessible at http://localhost:8188
   - Clear status messages show connection progress with Rich progress bars

5. **Access ComfyUI GUI in my browser** to verify the connection works
   - Ability to open browser automatically or manually
   - Confirmation that tunnel is working correctly

6. **SSH directly into the pod** for debugging and manual operations
   - Drop into terminal session of running pod
   - Install models manually if needed
   - Debug stuck workflows
   - Simple command like `autopod pod shell <pod-id>`

7. **Have the system handle transient failures intelligently** prioritizing cost savings
   - Automatic retries with exponential backoff
   - If pod continually fails, pause or terminate automatically
   - Terminate only if all outputs are backed up, otherwise stop
   - Clear indication of failure mode and recovery action taken

8. **Track all my pods with meaningful names** so I can identify them easily
   - Auto-generated names like `autopod-2025-11-08-001`
   - Increment counter for multiple pods per day
   - Pod info persisted across sessions (V2-compatible storage)

9. **Stop a running pod** to reduce costs when not actively rendering
   - Simple command to pause pod (maintains state, cheaper rate)
   - Confirmation that pod was stopped successfully

10. **Terminate a pod** when I'm completely done with it
    - Simple command to destroy pod
    - Warning if pod has been running for significant time/cost
    - Confirmation before permanent deletion

11. **Have excellent logging** so I can debug issues easily
    - Full tracebacks in log files
    - Easy access to logs via command
    - Logs don't expose credentials
    - Logs show all RunPod API interactions

---

## Functional Requirements

### FR1: Configuration Management

**FR1.1:** The system must store RunPod API key in `~/.autopod/config.json`

**FR1.2:** The config file must be created with secure permissions (chmod 600)

**FR1.3:** On first run, if config file doesn't exist, the system must:
- Prompt for RunPod API key (interactive, secure input)
- Attempt to detect SSH key from keychain/ssh-agent
- If SSH key not found, guide user through SSH key setup step-by-step
- Prompt for default region (default: detect from locale, user prefers North America)
- Prompt for default cloud type (secure vs community, default: secure)
- Save all settings to config file

**FR1.4:** The system must validate the API key by making a test API call before saving

**FR1.5:** The system must provide commands to manage configuration:
- `autopod config init` - Run first-time setup wizard
- `autopod config show` - Display current config (redact sensitive values)
- `autopod config set <key> <value>` - Update specific setting

**FR1.6:** SSH key management must:
- First try to use SSH agent/keychain
- Fall back to prompting for SSH key path
- Validate SSH key exists and has correct permissions
- Offer to generate new SSH key pair if needed
- Provide clear instructions for adding public key to RunPod account

### FR2: Pod Creation

**FR2.1:** The system must query RunPod API for available GPU types with filtering:
- Filter by cloud type (secure/community, default: secure)
- Filter by region (default: North America or user's locale)
- Filter by network speed (high/extreme preferred)
- Filter by CUDA version (optional, e.g., >= 12.8)
- Show only relevant GPUs (4-5 options max)

**FR2.2:** The system must present GPU options interactively with:
- GPU name (e.g., "RTX A40", "RTX 4090")
- VRAM amount
- Cost per hour
- Availability status
- Network speed rating
- CUDA version

**FR2.3:** The system must allow user to select:
- GPU type
- GPU count (1-N based on availability)
- ComfyUI template (default: `runpod/comfyui:latest`)
- Network volume ID (optional, default: none)
- Region (if not using default)

**FR2.4:** The system must show estimated cost per hour before creating pod

**FR2.5:** The system must generate pod name using format: `autopod-YYYY-MM-DD-NNN` where NNN is incrementing counter

**FR2.6:** The system must create pod using specified template and configuration

**FR2.7:** The system must display Rich progress indicator during pod creation with stages:
- "Requesting pod..."
- "Waiting for pod to start..."
- "Pod running, waiting for SSH..."
- "SSH ready, establishing tunnel..."
- "Connected!"

**FR2.8:** The system must implement intelligent retry logic:
- Exponential backoff (2s, 4s, 8s, 16s, 32s, max 5 retries)
- If pod fails repeatedly, automatically pause or terminate
- Terminate only if outputs are backed up, otherwise stop
- Log all retry attempts with timestamps

**FR2.9:** The system must timeout after 10 minutes if pod never becomes ready

**FR2.10:** The system must persist pod information to `~/.autopod/pods.json` including:
- Pod ID and name
- Creation timestamp
- GPU configuration
- Connection details (SSH host, port)
- Current status
- Accumulated cost

### FR3: SSH Tunnel Management

**FR3.1:** The system must establish SSH tunnel mapping localhost:8188 → pod:8188

**FR3.2:** The system must handle SSH authentication using detected/configured SSH key

**FR3.3:** The system must verify tunnel is working by attempting connection to http://localhost:8188

**FR3.4:** The system must keep SSH tunnel alive as background process

**FR3.5:** The system must provide direct SSH terminal access via command:
- `autopod pod shell <pod-id>` - Drop into pod terminal
- Interactive terminal session for debugging
- Ability to manually install models, edit files, etc.

**FR3.6:** The system must handle "Host key verification" gracefully:
- Add to known_hosts automatically (with user consent)
- Or use StrictHostKeyChecking=no with warning

**FR3.7:** The system must cleanup tunnel process when pod is stopped/terminated

**FR3.8:** The system must provide SSH connection details in output for manual access

### FR4: Pod Control

**FR4.1:** The system must provide command to list all pods:
- `autopod pods list` - Show all tracked pods
- Display: name, ID, status, GPU type, runtime, cost

**FR4.2:** The system must provide command to stop (pause) a running pod:
- `autopod pod stop <pod-id>`
- Show confirmation with cost savings

**FR4.3:** The system must provide command to terminate (destroy) a pod:
- `autopod pod kill <pod-id>`
- Show confirmation prompt with total cost and runtime
- Warning if pod was running for significant time

**FR4.4:** The system must provide command to get pod details:
- `autopod pod info <pod-id>`
- Show full details: status, GPU, runtime, cost, connection info

**FR4.5:** The system must track pod runtime and cost accurately

**FR4.6:** The system must sync pod status with RunPod API periodically

### FR5: Logging and Error Handling

**FR5.1:** The system must maintain comprehensive logs at `~/.autopod/logs/autopod.log`

**FR5.2:** Logs must include:
- All RunPod API requests and responses
- SSH connection attempts and results
- Pod creation/deletion events
- Error tracebacks (full Python traceback)
- Timestamps for all events
- Cost calculations

**FR5.3:** Logs must NOT include:
- API keys
- SSH private keys
- Any sensitive credentials

**FR5.4:** The system must provide command to view logs:
- `autopod logs` - Tail recent logs
- `autopod logs --full` - Show all logs

**FR5.5:** The system must provide clear error messages for common failures:
- Invalid API key
- Insufficient RunPod credits
- No GPUs available matching filters
- SSH connection failures
- Network timeouts
- SSH key not found or invalid

**FR5.6:** The system must cleanup partially created resources on failure

**FR5.7:** The system must implement log rotation (max 10MB, keep 5 files)

---

## Non-Goals (Out of Scope)

**NOT included in this feature:**

1. Job processing and workflow execution (covered in PRD #2)
2. File transfer capabilities (covered in PRD #2)
3. WebSocket monitoring of jobs (covered in PRD #3)
4. Cost limit enforcement (covered in PRD #4)
5. Multiple concurrent pod management in single command (V2 feature)
6. Pod editing after creation (template changes, port forwarding, encrypted disk) - nice-to-have for V2
7. Automatic pod termination on job completion (covered in PRD #3/4)
8. GUI for pod management (CLI only for V1)

---

## Design Considerations

### CLI Commands

```bash
# First-time setup (interactive wizard)
autopod config init

# Show current config (redacted)
autopod config show

# Update specific config value
autopod config set api-key <key>

# Create and connect to pod (interactive GPU selection)
autopod connect

# Create pod with specific config
autopod connect --gpu A40 --gpu-count 2 --volume <vol-id>

# Create pod with custom template
autopod connect --template my-custom-comfyui:latest

# List all pods
autopod pods list

# Get pod details
autopod pod info <pod-id>

# SSH into pod terminal
autopod pod shell <pod-id>

# Stop pod (pause, cheaper)
autopod pod stop <pod-id>

# Terminate pod (destroy)
autopod pod kill <pod-id>

# View logs
autopod logs
autopod logs --full
```

### Interactive GPU Selection (Example)

```
Select Cloud Type:
  1. Secure Cloud (recommended, more reliable)
  2. Community Cloud (cheaper, variable availability)
[1-2]: 1

Select Region:
  1. North America (default)
  2. Europe
  3. Asia Pacific
[1-3]: 1

Filtering: Secure Cloud | North America | Network: High+ | CUDA: Any

Available GPUs:
┌─────────────┬──────┬──────────┬──────────────┬─────────┬──────┐
│ GPU Type    │ VRAM │ Cost/hr  │ Available    │ Network │ CUDA │
├─────────────┼──────┼──────────┼──────────────┼─────────┼──────┤
│ RTX A5000   │ 24GB │ $0.27    │ ✓ High       │ High    │ 12.4 │
│ RTX A40     │ 48GB │ $0.40    │ ✓ Medium     │ Extreme │ 12.4 │
│ RTX 3090    │ 24GB │ $0.46    │ ✓ Low        │ High    │ 12.1 │
│ RTX A6000   │ 48GB │ $0.49    │ ✓ High       │ Extreme │ 12.4 │
└─────────────┴──────┴──────────┴──────────────┴─────────┴──────┘

Select GPU: [↑↓ arrows, Enter to confirm]
GPU Count: 2
Network Volume (optional, press Enter to skip):

Estimated cost: $0.80/hr (2x RTX A40)
Confirm? [y/N]: y

Creating pod: autopod-2025-11-08-001
→ Requesting pod... ⟳
```

### Config File Format

```json
{
  "runpod": {
    "api_key": "YOUR_API_KEY_HERE",
    "ssh_key_path": "~/.ssh/id_rsa",
    "default_region": "NA",
    "default_cloud_type": "secure",
    "default_template": "runpod/comfyui:latest"
  },
  "ssh": {
    "tunnel_port": 8188,
    "connect_timeout": 30,
    "max_retries": 5
  },
  "filters": {
    "network_speed": ["high", "extreme"],
    "cuda_version": null,
    "favorite_gpus": ["RTX A40", "RTX A6000", "RTX A5000", "RTX 3090"]
  },
  "defaults": {
    "gpu_type": "RTX A40",
    "gpu_count": 2,
    "network_volume": null
  },
  "logging": {
    "level": "INFO",
    "max_size_mb": 10,
    "backup_count": 5
  }
}
```

### Pod State File (`~/.autopod/pods.json`)

```json
{
  "autopod-2025-11-08-001": {
    "pod_id": "abc123xyz",
    "name": "autopod-2025-11-08-001",
    "status": "running",
    "created_at": "2025-11-08T16:45:00Z",
    "gpu_type": "RTX A40",
    "gpu_count": 2,
    "cost_per_hour": 0.80,
    "ssh_host": "abc123xyz.pod.runpod.io",
    "ssh_port": 22,
    "tunnel_port": 8188,
    "template": "runpod/comfyui:latest",
    "network_volume": null,
    "total_runtime_seconds": 3600,
    "estimated_cost_usd": 0.80
  }
}
```

---

## Technical Considerations

### Dependencies

- `runpod` - Official RunPod Python SDK (if available, otherwise GraphQL)
- `rich` - Terminal UI, progress bars, and tables
- `paramiko` or `subprocess` - SSH tunnel and terminal session management
- `requests` - HTTP requests for tunnel verification
- `json` - Config and state file handling
- `logging` - Python standard logging with rotation
- `locale` - Detect user's region for defaults

### RunPod API

- Uses GraphQL API for pod management
- Template: `runpod/comfyui:latest` (official RunPod ComfyUI image)
- API key authentication via headers
- Pod creation is asynchronous (requires polling)
- Need to query available GPUs with filters
- Region codes: Map to RunPod's region identifiers

### SSH Setup - User-Friendly Flow

**Priority order:**
1. Try SSH agent/keychain (most seamless)
2. Check for ~/.ssh/id_rsa (common default)
3. Prompt for SSH key path
4. Offer to generate new SSH key pair
5. Show clear instructions for adding public key to RunPod

**Example first-run flow:**
```
Welcome to autopod! Let's set up your configuration.

RunPod API Key: [secure input]
✓ API key validated

Checking for SSH keys...
✗ No SSH key found in agent/keychain

Do you have an existing SSH key? [y/N]: n

Let's create an SSH key for RunPod:
→ Generating SSH key pair...
✓ Created: ~/.ssh/autopod_rsa

Next steps:
1. Copy your public key:
   cat ~/.ssh/autopod_rsa.pub | pbcopy
2. Go to: https://runpod.io/console/user/settings
3. Click "SSH Keys" → "Add SSH Key"
4. Paste and save

Press Enter when done...
```

### Tunnel Management

- SSH tunnel runs in background (subprocess or paramiko)
- Track process ID for cleanup
- Verify tunnel by HTTP GET to localhost:8188/system_stats (ComfyUI API endpoint)
- Terminal access via separate SSH session (interactive)

### Retries and Intelligent Failure Handling

**Retry Strategy:**
- Exponential backoff: 2s, 4s, 8s, 16s, 32s (max 5 retries)
- Pod creation timeout: 10 minutes total
- SSH connection timeout: 30 seconds per attempt

**Failure Handling (Cost-First Approach):**
```python
if retry_count > max_retries:
    if outputs_are_backed_up():
        log.warning("Repeated failures, terminating pod")
        terminate_pod()
    else:
        log.warning("Repeated failures, stopping pod to save costs")
        stop_pod()
```

### Logging Implementation

```python
import logging
from logging.handlers import RotatingFileHandler

# Setup in ~/.autopod/logs/autopod.log
handler = RotatingFileHandler(
    '~/.autopod/logs/autopod.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)

# Format with full context
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Include tracebacks
logger.exception("Pod creation failed", exc_info=True)
```

---

## Success Metrics

**This feature is successful when:**

1. User can complete first-time setup (including SSH) in < 5 minutes with clear guidance
2. User can create pod and access ComfyUI GUI in < 5 minutes (95th percentile)
3. SSH tunnel establishment succeeds on first try 90% of the time
4. Automatic retries handle transient failures 95% of the time
5. On repeated failures, pod is stopped/terminated automatically (100% of cases)
6. No credentials are leaked in logs or error messages (100% compliance)
7. User can drop into pod terminal for debugging within 10 seconds
8. All pods are tracked persistently across sessions (zero data loss)
9. Logs contain sufficient information to diagnose 95% of issues

**Acceptance criteria:**

- [ ] Run `autopod config init`, complete SSH setup, config file created successfully
- [ ] Run `autopod connect`, select GPU with filters, pod created within 5 minutes
- [ ] Open browser to http://localhost:8188, see ComfyUI GUI
- [ ] Run `autopod pod shell <pod-id>`, get interactive terminal in pod
- [ ] Run `autopod pod stop <pod-id>`, pod status changes to "stopped" in RunPod
- [ ] Run `autopod pod kill <pod-id>`, pod is terminated and removed from tracking
- [ ] Run `autopod pods list`, see all pods with status and costs
- [ ] Invalid API key produces clear error message (not crash)
- [ ] Network failure triggers automatic retry, then stops pod if continues failing
- [ ] Run `autopod logs`, see detailed logs with tracebacks (no credentials exposed)
- [ ] Restart autopod, previously created pods still appear in `pods list`

---

## Open Questions

**ANSWERED:**

1. ✓ **RunPod ComfyUI Template:** `runpod/comfyui:latest`

2. ✓ **SSH Key Setup:** Use keychain/agent first, then interactive hand-holding setup

3. ✓ **Pod Naming:** `autopod-2025-11-08-001` format with incrementing counter

4. ✓ **State Persistence:** `~/.autopod/pods.json` for V2 compatibility

5. ✓ **Region Selection:** Required, default to North America (or user locale), interactive selection

6. ✓ **Network Volume:** Allow specification during creation, default to none

**REMAINING:**

1. **Port Conflicts (Multi-Pod V2):** If multiple pods running, how to handle localhost:8188 conflicts? (Likely: 8188, 8189, 8190... but defer to V2)

2. **Encrypted Disk:** Does RunPod API support encrypted disk option? If so, should we expose it? (Defer to V2 unless easy to add)

3. **Custom Port Forwarding:** RunPod allows custom port mapping - should we support in V1? (Defer to V2)

---

## Notes

- This is a foundational feature - all other features depend on this working reliably
- **Cost savings is the top priority** - when in doubt, stop the pod
- Focus on user experience: clear feedback, helpful errors, hand-holding for SSH setup
- Comprehensive logging is essential for debugging expensive cloud operations
- Keep interaction flow similar to RunPod web interface for familiarity
- V2 compatibility for state storage is important - use JSON files for now
- Document RunPod API quirks as we discover them

---

**Next Steps:**
1. Generate task list for implementation
2. Begin with config management and SSH setup (most critical for UX)
3. Test against real RunPod API frequently
4. Update README.md with setup instructions as features are implemented
