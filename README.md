# autopod

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight CLI controller for managing RunPod GPU instances with ease.

## Overview

autopod automates the process of creating, managing, and accessing RunPod GPU pods through an intuitive command-line interface. It provides smart GPU selection with automatic fallback, SSH access, and comprehensive pod lifecycle management - all designed to help you save money on compute costs.

**Status:** Version 1.2 - Production Ready

## Features

### V1.2 (Current) - ComfyUI Integration
- **SSH Tunnel Management** - Automatic SSH tunnels for secure ComfyUI access
- **ComfyUI API Client** - Query ComfyUI status, system info, and queue via API
- **Network Volume Support** - Attach RunPod network volumes for persistent model storage
- **Tunnel Auto-Recovery** - Automatic tunnel health checks and recreation
- **ComfyUI Commands** - `autopod comfy status` and `autopod comfy info`
- **Localhost Access** - Access ComfyUI GUI at http://localhost:8188 via SSH tunnel
- **All V1.1 Features** - Full backward compatibility with pod lifecycle management

### V1.1 Features
- **Smart Pod Creation** - Automatic GPU selection with fallback preferences
- **Datacenter Selection** - Specify datacenter via `--datacenter` flag (e.g., CA-MTL-1)
- **Optimized Defaults** - 50GB container disk by default (perfect for ComfyUI)
- **Auto-Cleanup** - Stale pods automatically removed from cache
- **SSH Access** - Seamless shell access and command execution (with PTY-free mode)
- **Pod Management** - List, info, start, stop, and terminate operations
- **Cost Management** - Stop pods to reduce costs (~$0.02/hr), restart when needed
- **Rich Terminal UI** - Beautiful tables, progress bars, and formatted output
- **Auto-Select** - Commands work without pod ID when only one pod exists
- **Configuration Management** - Simple setup wizard with SSH key detection
- **Cost Visibility** - Real-time cost tracking and runtime display
- **Improved Error Messages** - Helpful hints guide you to solutions
- **Robust Metadata Handling** - Gracefully handles missing pod information

## Installation

### Prerequisites

- Python 3.10 or higher
- RunPod account with API key
- SSH key pair (can be generated during setup)

### Install from source

```bash
git clone https://github.com/rwolt/autopod.git
cd autopod
pip install -e .
```

### Verify installation

```bash
autopod --version
```

## Quick Start

### 1. Initial Setup

Run the configuration wizard:

```bash
autopod config init
```

The wizard will guide you through:
- Entering your RunPod API key (get it from [RunPod settings](https://www.runpod.io/console/user/settings))
- Setting up SSH key (auto-detects existing keys or guides you to create one)
- Configuring GPU preferences

### 2. Create Your First Pod

Create a pod with default settings (uses your GPU preferences):

```bash
autopod connect
```

Or specify a GPU type:

```bash
autopod connect --gpu "RTX A40"
```

### 3. Access Your Pod

SSH into the pod:

```bash
autopod ssh
```

Or execute a command:

```bash
autopod ssh -c "nvidia-smi"
```

**Note:** If your SSH key has a passphrase, add it to ssh-agent to avoid authentication issues:

```bash
ssh-add ~/.ssh/id_ed25519_runpod
```

autopod will automatically detect passphrase-protected keys and provide guidance if needed.

### 4. Manage Your Pods

List all pods:

```bash
autopod list
```

Get detailed info:

```bash
autopod info
```

### 5. Cost Management

Stop pod to save money (keeps state, reduces cost to ~$0.02/hr):

```bash
autopod stop
```

Restart when needed:

```bash
autopod start
```

### 6. Clean Up

Terminate the pod when completely done:

```bash
autopod kill
```

## CLI Reference

### Global Commands

#### `autopod --help`
Show help for all commands

#### `autopod --version`
Show version information

---

### Configuration

#### `autopod config init`
Run interactive configuration wizard

**Example:**
```bash
autopod config init
```

Sets up RunPod API key, SSH key, and GPU preferences.

---

### Pod Creation

#### `autopod connect`
Create and connect to a new pod

**Options:**
- `--gpu <TYPE>` - GPU type (e.g., 'RTX A40', 'RTX A5000')
- `--gpu-count <N>` - Number of GPUs (default: 1)
- `--disk-size <GB>` - Disk size in GB (default: 50)
- `--datacenter <ID>` - Datacenter region (e.g., 'CA-MTL-1', 'US-GA-1')
- `--template <NAME>` - Docker template (overrides config default)
- `--cloud-type <TYPE>` - SECURE, COMMUNITY, or ALL (default: SECURE)
- `--volume-id <ID>` - Network volume ID to attach (for persistent storage)
- `--volume-mount <PATH>` - Mount path for network volume (default: /workspace)
- `--dry-run` - Show what would be created without creating
- `--interactive` - Interactive mode with prompts (future)

**Examples:**

Create pod with default GPU preferences:
```bash
autopod connect
```

Create pod with specific GPU:
```bash
autopod connect --gpu "RTX A5000"
```

Create pod with multiple GPUs and larger disk:
```bash
autopod connect --gpu "RTX A40" --gpu-count 2 --disk-size 100
```

Create pod in specific datacenter:
```bash
autopod connect --datacenter CA-MTL-1
```

Create pod with network volume (for persistent model storage):
```bash
autopod connect --volume-id abc123xyz --volume-mount /workspace
```

Preview without creating:
```bash
autopod connect --dry-run
```

**Smart GPU Selection:**
- If no `--gpu` specified, uses first preference from config
- Automatically falls back to second and third preferences if unavailable
- Example preferences: RTX A40 → RTX A6000 → RTX A5000

---

### HTTP Port Exposure

#### `autopod connect --expose-http`
Expose ComfyUI HTTP port (8188) via RunPod's HTTP proxy

By default, pods are not accessible from the internet. The `--expose-http` flag exposes port 8188 through RunPod's HTTPS proxy, making ComfyUI's web interface accessible from your browser.

**Examples:**

Create pod with HTTP proxy enabled:
```bash
autopod connect --expose-http
```

**Access URL format:**
```
https://[pod-id]-8188.proxy.runpod.net
```

Example:
```bash
autopod connect --expose-http --gpu "RTX A40"
# After pod creation:
# → Visit: https://abc123xyz-8188.proxy.runpod.net
```

**Security Considerations:**

⚠️ **Important:** When using `--expose-http`, be aware of these security implications:

- **No Authentication:** Anyone with the URL can access your ComfyUI instance
- **Public Access:** The proxy URL is publicly accessible on the internet
- **Traffic Inspection:** RunPod can technically inspect HTTPS traffic (though it's encrypted in transit)
- **Exposed Workflows:** Your ComfyUI workflows and generated content are accessible to anyone with the URL

**Recommended Security Practices:**

1. **Terminate When Not in Use:**
   ```bash
   autopod kill [pod-id] -y    # Stop charges and remove access
   ```

2. **Use Stop for Breaks:**
   ```bash
   autopod stop [pod-id]       # Pauses pod, removes HTTP access
   ```

3. **Keep URLs Private:** Don't share the proxy URL in public places

4. **Monitor Costs:** HTTP-exposed pods should be terminated promptly to avoid unnecessary charges

**When to Use HTTP Proxy:**

- ✅ Quick testing and development
- ✅ Short-lived workflows (terminate immediately after)
- ✅ Non-sensitive projects
- ✅ When you need browser GUI access

**When NOT to Use:**

- ❌ Production workloads with sensitive data
- ❌ Long-running pods left unattended
- ❌ Processing confidential/private content
- ❌ When security is a primary concern

**Read More:**
- [RunPod Port Exposure Documentation](https://docs.runpod.io/pods/configuration/expose-ports)

---

### Pod Listing & Information

#### `autopod list` (aliases: `ls`, `ps`)
List all pods with status, GPU, runtime, and cost

**Options:**
- `--all` - Show all pods including non-autopod (future)

**Example:**
```bash
autopod list
```

**Output:**
```
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Pod ID       ┃ Status    ┃ GPU        ┃ Runtime   ┃ Cost      ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━┩
│ abc-123      │ RUNNING   │ 1x RTX A40 │ 12.3 min  │ $0.0821   │
│ def-456      │ STOPPED   │ 1x RTX A40 │ 45.2 min  │ $0.3014   │
└──────────────┴───────────┴────────────┴───────────┴───────────┘
```

Aliases work identically:
```bash
autopod ls    # Short alias
autopod ps    # Docker-like alias
```

#### `autopod info [POD_ID]`
Show detailed information about a specific pod

**Arguments:**
- `[POD_ID]` - Optional pod ID (auto-selects if only one pod exists)

**Examples:**

Get info for specific pod:
```bash
autopod info abc-123
```

Auto-select when only one pod:
```bash
autopod info
```

**Output:**
```
╭─── Pod: abc-123 ────────────────────────────────╮
│ Status:       RUNNING                           │
│ GPU:          1x RTX A40                        │
│ Cost/hour:    $0.40                             │
│ Runtime:      12.3 minutes                      │
│ Total cost:   $0.0821                           │
│ SSH:          Ready (ssh.runpod.io)             │
╰─────────────────────────────────────────────────╯
```

---

### SSH Access

#### `autopod ssh [POD_ID]` (alias: `shell`)
Open SSH shell or execute commands on a pod

**Arguments:**
- `[POD_ID]` - Optional pod ID (auto-selects if only one pod exists)

**Options:**
- `-c, --command <CMD>` - Execute command instead of interactive shell

**Examples:**

Interactive shell (auto-select):
```bash
autopod ssh
```

Interactive shell (specific pod):
```bash
autopod ssh abc-123
```

Execute single command:
```bash
autopod ssh abc-123 -c "nvidia-smi"
```

Execute command with auto-select:
```bash
autopod ssh -c "ls -la"
```

**Alias:**
```bash
autopod shell abc-123    # Same as 'ssh'
```

---

### Pod Control

#### `autopod stop [POD_ID]`
Stop (pause) a pod

Stopped pods reduce compute charges from ~$0.40/hr to ~$0.02/hr while retaining disk state. You can restart them later with `autopod start`.

**Arguments:**
- `[POD_ID]` - Optional pod ID (auto-selects if only one pod exists)

**Examples:**

Stop specific pod:
```bash
autopod stop abc-123
```

Stop the only running pod:
```bash
autopod stop
```

#### `autopod start [POD_ID]` (alias: `resume`)
Start (resume) a stopped pod

Resumes a previously stopped pod. **Note:** GPU availability is not guaranteed - the pod may restart with a different GPU type or as CPU-only if the original GPU is unavailable.

**Arguments:**
- `[POD_ID]` - Optional pod ID (auto-selects if only one pod exists)

**Examples:**

Start specific pod:
```bash
autopod start abc-123
```

Start with auto-select:
```bash
autopod start
```

**Alias:**
```bash
autopod resume abc-123    # Same as 'start'
```

**Output:**
```bash
✓ Pod abc-123 started successfully
⚠ GPU availability not guaranteed - check pod info to verify GPU type

Checking pod status...
╭─── Pod: abc-123 ────────────────────────────────╮
│ Status:       RUNNING                           │
│ GPU:          1x RTX A40                        │  ← Verify GPU type
│ Cost/hour:    $0.40                             │
│ Runtime:      0.1 minutes                       │
│ Total cost:   $0.0007                           │
│ SSH:          Ready (ssh.runpod.io)             │
╰─────────────────────────────────────────────────╯
```

#### `autopod kill [POD_ID]` (aliases: `terminate`, `rm`)
Terminate (destroy) a pod permanently

**WARNING:** This is destructive and cannot be undone. All data on the pod will be lost unless saved to a network volume.

**Arguments:**
- `[POD_ID]` - Optional pod ID (auto-selects if only one pod exists)

**Options:**
- `-y, --yes` - Skip confirmation prompt

**Examples:**

Terminate with confirmation:
```bash
autopod kill abc-123
```

Skip confirmation:
```bash
autopod kill abc-123 -y
```

Auto-select:
```bash
autopod kill
```

**Aliases:**
```bash
autopod terminate abc-123    # Explicit name
autopod rm abc-123           # Docker-like alias
```

---

### SSH Tunnels

#### `autopod tunnel start [POD_ID]`
Create an SSH tunnel to access services running on a pod

**Arguments:**
- `[POD_ID]` - Optional pod ID (auto-selects if only one pod exists)

**Options:**
- `--local-port <PORT>` - Local port (default: 8188)
- `--remote-port <PORT>` - Remote port on pod (default: 8188)

**Examples:**

Create tunnel to ComfyUI (auto-select pod):
```bash
autopod tunnel start
```

Create tunnel with specific ports:
```bash
autopod tunnel start abc-123 --local-port 8188 --remote-port 8188
```

Access ComfyUI in browser after tunnel created:
```bash
open http://localhost:8188
```

#### `autopod tunnel stop [POD_ID]`
Stop an SSH tunnel for a pod

**Examples:**
```bash
autopod tunnel stop abc-123
autopod tunnel stop    # Auto-select
```

#### `autopod tunnel list`
List all active SSH tunnels

**Example:**
```bash
autopod tunnel list
```

**Output:**
```
┏━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Pod ID     ┃ Status    ┃ Port      ┃ PID       ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━┩
│ abc-123    │ Active    │ 8188      │ 12345     │
└────────────┴───────────┴───────────┴───────────┘
```

#### `autopod tunnel cleanup`
Remove dead/stale tunnels from tracking

**Example:**
```bash
autopod tunnel cleanup
```

#### `autopod tunnel stop-all`
Stop all active SSH tunnels

**Example:**
```bash
autopod tunnel stop-all
```

---

### ComfyUI Commands

#### `autopod comfy status [POD_ID]`
Check if ComfyUI is ready and responding

**Arguments:**
- `[POD_ID]` - Optional pod ID (auto-selects if only one pod exists)

**Options:**
- `--port <PORT>` - Local tunnel port (default: 8188)
- `--no-tunnel` - Skip automatic tunnel creation

**Examples:**

Check ComfyUI status (auto-creates tunnel):
```bash
autopod comfy status
```

Check specific pod:
```bash
autopod comfy status abc-123
```

**Output (ready):**
```
╭─────────── ComfyUI Status: READY ───────────╮
│ Pod ID:       abc-123                       │
│ Tunnel:       localhost:8188 (Active)      │
│ ComfyUI:      Ready ✓                       │
│ Access:       http://localhost:8188         │
╰─────────────────────────────────────────────╯
```

**Output (not ready):**
```
╭────────── ComfyUI Status: NOT READY ────────╮
│ Pod ID:       abc-123                       │
│ Tunnel:       localhost:8188 (Active)      │
│ ComfyUI:      Not responding ✗              │
│ Wait Time:    ~60 seconds after pod start   │
╰─────────────────────────────────────────────╯
```

#### `autopod comfy info [POD_ID]`
Show detailed ComfyUI system information

**Arguments:**
- `[POD_ID]` - Optional pod ID (auto-selects if only one pod exists)

**Options:**
- `--port <PORT>` - Local tunnel port (default: 8188)
- `--no-tunnel` - Skip automatic tunnel creation

**Examples:**

Get ComfyUI info (auto-creates tunnel):
```bash
autopod comfy info
```

Get info for specific pod:
```bash
autopod comfy info abc-123
```

**Output:**
```
╭──────────── ComfyUI Information ────────────╮
│ Pod ID:       abc-123                       │
│ Status:       Ready ✓                       │
│                                             │
│ System:                                     │
│   Python:     3.10.12                       │
│   RAM:        62.8 GB                       │
│                                             │
│ GPU 0:                                      │
│   Name:       NVIDIA RTX A40                │
│   VRAM:       45.6 GB                       │
│                                             │
│ Queue:                                      │
│   Running:    0 jobs                        │
│   Pending:    0 jobs                        │
│                                             │
│ Access:       http://localhost:8188         │
╰─────────────────────────────────────────────╯
```

---

## Common Workflows

### Quick GPU Session

```bash
# Create pod with defaults
autopod connect

# Wait for it to finish creating, then SSH in
autopod ssh

# Do your work...

# Terminate when done
autopod kill -y
```

### Cost-Conscious Development

Use stop/start for development sessions to minimize costs:

```bash
# Create pod for ComfyUI development
autopod connect --gpu "RTX 4090"

# Work on your project, use the GUI, etc.
autopod ssh

# Take a break? Stop the pod to reduce costs
autopod stop    # Goes from $0.59/hr → $0.02/hr

# Come back later, resume your work
autopod start   # Restarts with your data intact

# Check GPU type after restart (may have changed!)
autopod info

# Done for the day? Terminate to stop all charges
autopod kill -y
```

**Cost Savings Example:**
- Running 8 hours: $4.72
- Stop/start workflow (2hr work, 6hr stopped): $1.30
- **Savings: $3.42 (72%!)**

### Managing Multiple Pods

```bash
# List all pods
autopod list

# Get info for specific pod
autopod info abc-123

# SSH into specific pod
autopod ssh abc-123

# Stop pods you're not using
autopod stop abc-123
autopod stop def-456

# Kill terminated work
autopod kill ghi-789 -y
```

### Troubleshooting Pod Issues

Sometimes pods need a restart to fix issues:

```bash
# Pod acting weird? Stop and restart
autopod stop abc-123
autopod start abc-123

# Check if GPU changed after restart
autopod info abc-123

# If GPU wrong, just kill and recreate
autopod kill abc-123 -y
autopod connect --gpu "RTX 4090"
```

### Using ComfyUI Web Interface

Use HTTP proxy for browser-based ComfyUI access:

```bash
# Create pod with HTTP proxy enabled
autopod connect --expose-http --gpu "RTX A40"

# Note the proxy URL from the output:
# → ComfyUI accessible at: https://abc123xyz-8188.proxy.runpod.net

# Open the URL in your browser and use ComfyUI GUI
# (Wait ~60 seconds for ComfyUI to fully start)

# When done, terminate immediately to save costs
autopod kill abc-123 -y
```

**Security Reminder:** HTTP proxy has no authentication. Anyone with the URL can access your ComfyUI instance. Terminate pods immediately when done to prevent unauthorized access and unnecessary charges.

### Accessing ComfyUI Securely via SSH Tunnel (Recommended)

For better security, use SSH tunnels instead of HTTP proxy:

```bash
# Create pod WITHOUT --expose-http (more secure)
autopod connect --gpu "RTX A40"

# Create SSH tunnel (or let comfy commands auto-create it)
autopod tunnel start

# Wait for ComfyUI to start (~60 seconds)
autopod comfy status

# Open ComfyUI in browser at localhost:8188
open http://localhost:8188

# Work with ComfyUI GUI securely (no public URL!)

# Check system info via API
autopod comfy info

# When done, stop tunnel and terminate pod
autopod tunnel stop
autopod kill -y
```

**Why SSH tunnel is better than HTTP proxy:**
- ✅ Encrypted and authenticated (SSH keys)
- ✅ Not publicly accessible on internet
- ✅ No 100-second timeout limit
- ✅ Works for both HTTP API and WebSocket connections
- ✅ Same tunnel serves both browser GUI and API calls

---

## Configuration

Configuration is stored in `~/.autopod/config.json` with chmod 600 (secure).

### Configuration File Structure

```json
{
  "providers": {
    "runpod": {
      "api_key": "your-api-key-here",
      "ssh_key_path": "/Users/you/.ssh/id_ed25519",
      "default_template": "runpod/comfyui:latest",
      "default_region": "NA-US",
      "cloud_type": "SECURE",
      "default_volume_id": "",
      "default_volume_mount": "/workspace"
    }
  },
  "defaults": {
    "gpu_preferences": ["RTX A40", "RTX A6000", "RTX A5000"],
    "gpu_count": 1
  }
}
```

### Editing Configuration

You can manually edit the config file:

```bash
# macOS
open ~/.autopod/config.json

# Linux
nano ~/.autopod/config.json
```

Or re-run the wizard:

```bash
autopod config init
```

### GPU Preferences Explained

The `gpu_preferences` list defines fallback order:
1. **First choice** - Tried first when you run `autopod connect`
2. **Second choice** - Used if first is unavailable
3. **Third choice** - Used if both above are unavailable

Example: `["RTX A40", "RTX A6000", "RTX A5000"]`
- Prefers RTX A40 (best value for large models)
- Falls back to RTX A6000 if A40 unavailable
- Falls back to RTX A5000 if both above unavailable

You can override this with `--gpu` flag:
```bash
autopod connect --gpu "RTX 4090"    # Force specific GPU
```

---

## Important Notes

### GPU Availability After Restart

When you `stop` a pod and later `start` it, **RunPod does NOT guarantee the same GPU will be available**. The pod may restart with:
- ✅ Same GPU type (if available)
- ⚠️ Different GPU type (fallback)
- ⚠️ CPU-only (no GPUs available)

**Always check after restart:**
```bash
autopod start abc-123
autopod info abc-123    # Verify GPU type
```

If wrong GPU type, just create a new pod:
```bash
autopod kill abc-123 -y
autopod connect --gpu "RTX 4090"
```

### Stop vs Kill

- **`autopod stop`** - Pauses pod, keeps disk/data, ~$0.02/hr storage cost
  - Use for: Development sessions, breaks, overnight
  - Restart with: `autopod start`

- **`autopod kill`** - Destroys pod completely, $0 cost
  - Use for: Done with work, cleaning up, wrong GPU type
  - Cannot restart (must create new pod)

---

## State Management

autopod tracks pods in `~/.autopod/pods.json` for quick access.

**Note:** This state file is for convenience only. The source of truth is always the RunPod API. If pods are created/deleted outside autopod, the state will sync on next `list` command.

---

## Logs

All operations are logged to `~/.autopod/logs/autopod.log` with automatic rotation (10MB max, 5 backups).

View logs:
```bash
tail -f ~/.autopod/logs/autopod.log
```

---

## Troubleshooting

### SSH Connection Fails

**Symptom:** `autopod ssh` fails with connection error

**Solutions:**
1. Check if pod is ready: `autopod info <pod-id>` (look for "SSH: Ready")
2. Wait 30-60 seconds after pod creation for SSH to initialize
3. Verify SSH key permissions: `chmod 600 ~/.ssh/id_ed25519`
4. Check if SSH key has passphrase (may need to add to ssh-agent)

### Config Not Found

**Symptom:** `Configuration file not found`

**Solution:**
```bash
autopod config init
```

### Pod Starts with Wrong GPU

**Symptom:** After `autopod start`, pod has different GPU than expected

**Solution:**
This is expected behavior - GPU availability is not guaranteed. Options:
1. Use the different GPU if acceptable
2. Kill and recreate with desired GPU:
   ```bash
   autopod kill abc-123 -y
   autopod connect --gpu "RTX 4090"
   ```

### GPU Not Available

**Symptom:** `No GPUs available from preferences`

**Solution:**
1. Try specific GPU: `autopod connect --gpu "RTX A5000"`
2. Check RunPod console for available GPUs
3. Try `--cloud-type ALL` to include community cloud
4. Update GPU preferences in config

### SSH Tunnel Issues

**Symptom:** `autopod tunnel start` fails or `autopod comfy status` reports connection error

**Solutions:**
1. Check if pod SSH is ready: `autopod info` (wait ~30-60s after creation)
2. Verify port 8188 isn't already in use:
   ```bash
   lsof -i :8188
   ```
3. Kill stale tunnel processes:
   ```bash
   autopod tunnel cleanup
   ```
4. Manually stop and recreate tunnel:
   ```bash
   autopod tunnel stop
   autopod tunnel start
   ```

**Symptom:** ComfyUI not responding through tunnel

**Solutions:**
1. ComfyUI takes ~60 seconds to start after pod creation
2. Check ComfyUI status: `autopod comfy status`
3. Verify tunnel is active: `autopod tunnel list`
4. Test connectivity via browser: `open http://localhost:8188`

---

## Examples from Tests

Our integration tests demonstrate the full workflow. See `tests/manual/test_cli_integration.py` for a complete example that:

1. Creates a pod
2. Waits for SSH
3. Executes a test command
4. Terminates the pod
5. Verifies cleanup

Run the test:
```bash
cd tests/manual
python test_cli_integration.py
```

---

## Roadmap

### V1.0 - Pod Lifecycle Management ✅
- Pod creation with smart GPU selection
- SSH access (interactive and command execution)
- Pod listing and info display
- Pod start, stop, and termination
- Configuration management
- Rich terminal UI

### V1.2 - ComfyUI Integration ✅
- SSH tunnel management with auto-recovery
- ComfyUI HTTP API client (status, info, system stats)
- Network volume support for persistent storage
- Secure localhost access (no public URLs)
- Tunnel commands (start, stop, list, cleanup)
- ComfyUI commands (status, info)

### V1.3 - Workflow Execution (Next)
- Job-based workflow execution (`autopod comfy run`)
- File upload/download via ComfyUI API
- Workflow template system
- Job JSON format for workflow definitions
- Workflow submission and monitoring
- Output retrieval and download
- End-to-end automation

### V1.4 - True SSH Tunnels (Planned)
- Public IP pod creation (`--enable-ssh-tunnel`)
- True SSH with port forwarding support
- SSH daemon detection and setup
- Hybrid access (SSH tunnel + HTTP proxy fallback)
- Enhanced security for production workflows

### V2.0 - Job Management & Safety (Planned)
- Sequential job queue (multiple jobs, single pod)
- Cost safety (budget limits, timeout warnings)
- Enhanced UI with live progress
- Interactive controls (keyboard shortcuts)
- WebSocket monitoring for real-time progress

### V3.0 - Multi-Pod Parallelization (Planned)
- Multiple SSH tunnels (unique ports per pod)
- Parallel job execution (one pod per job)
- Multi-pod monitoring and aggregation
- Textualize TUI for visual management

---

## Project Structure

```
autopod/
├── CLAUDE.md                      # Development workflow guide
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── setup.py                       # Package configuration
├── tasks/                         # PRDs and task lists
│   ├── prd-*.md                  # Product requirement documents
│   └── tasks-*.md                # Implementation task lists
├── src/autopod/                   # Main package
│   ├── __init__.py               # Package initialization
│   ├── cli.py                    # CLI interface (Click-based)
│   ├── config.py                 # Configuration management
│   ├── logging.py                # Logging setup
│   ├── pod_manager.py            # High-level pod management
│   ├── ssh.py                    # SSH shell access
│   ├── tunnel.py                 # SSH tunnel management (V1.2)
│   ├── comfyui.py                # ComfyUI API client (V1.2)
│   └── providers/                # Provider abstraction
│       ├── __init__.py
│       ├── base.py               # Abstract CloudProvider
│       └── runpod.py             # RunPod implementation
└── tests/                         # Test files
    ├── test_*.py                 # Unit tests
    └── manual/                   # Manual integration tests
        ├── test_cli_integration.py
        ├── test_pod_creation.py
        ├── test_ssh_simple.py
        ├── test_v1.2_integration_comfyui.py
        └── test_v1.2_tunnel_integration.py
```

---

## Development

See [CLAUDE.md](./CLAUDE.md) for detailed development workflow, architecture documentation, and contribution guidelines.

### Running Tests

Unit tests:
```bash
pytest
```

Integration tests (requires RunPod API key):
```bash
cd tests/manual
python test_cli_integration.py
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Raymond Wolt

---

## Support

- **Issues:** [GitHub Issues](https://github.com/rwolt/autopod/issues)
- **Documentation:** [CLAUDE.md](./CLAUDE.md)
- **Logs:** `~/.autopod/logs/autopod.log`

---

**Made with ❤️ for efficient GPU compute**
