# autopod

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight CLI controller for managing RunPod GPU instances with ease.

## Overview

autopod automates the process of creating, managing, and accessing RunPod GPU pods through an intuitive command-line interface. It provides smart GPU selection with automatic fallback, SSH access, and comprehensive pod lifecycle management - all designed to help you save money on compute costs.

**Status:** Version 1.2 - Production Ready

## Features

### V1.2 (Current) - HTTP Proxy & Template-Agnostic Design
- **Flexible Port Exposure** - Expose any HTTP ports with custom labels (`--expose PORT:LABEL`)
- **Template-Based Defaults** - Config-driven port templates for common Docker images
- **HTTP Proxy Access** - Access web services via RunPod's HTTP proxy URLs (no SSH tunnel needed)
- **Health Checks** - `autopod info` shows service URLs with live health status
- **Network Volume Support** - Attach RunPod network volumes for persistent storage
- **Template-Agnostic** - Works with any Docker template (ComfyUI, PyTorch, custom images)
- **Ready-to-Use SSH Commands** - Copy-paste SSH commands from `autopod info`
- **Tunnel Infrastructure** - Manual SSH tunnel management for advanced use cases
- **All V1.1 Features** - Full backward compatibility with pod lifecycle management

### V1.1 Features
- **Smart Pod Creation** - Automatic GPU selection with fallback preferences
- **Datacenter Selection** - Specify datacenter via `--datacenter` flag (e.g., CA-MTL-1)
- **Optimized Defaults** - 50GB container disk by default (perfect for ComfyUI)
- **Auto-Cleanup** - Stale pods automatically removed from cache
- **SSH Access** - Interactive shell access to pods
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

### GPU Selection Hierarchy

`autopod` selects a GPU in the following order of priority:

1.  **Command-Line Flag:** A GPU specified with `autopod connect --gpu "TYPE"` will always be used.
2.  **Configuration File:** If no flag is provided, `autopod` uses the first GPU from the `gpu_preferences` list in your `~/.autopod/config.json` file.
3.  **Hardcoded Default:** If no configuration file is found, `autopod` falls back to a default list: `["RTX A40", "RTX A6000", "RTX A5000"]`.

If the first choice GPU is not available, `autopod` will automatically try the next GPU in the preference list.

### Editing Configuration

You can manually edit the config file:

```bash
# macOS
open ~/.autopod/config.json

# Linux
nano ~/.autopod/config.json
```

Or re-run the wizard at any time:

```bash
autopod config init
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

### Using Web Services (ComfyUI, JupyterLab, etc.)

Use HTTP proxy for browser-based access to any web service:

```bash
# Create pod with all template ports exposed via HTTP proxy
autopod connect --expose-all --gpu "RTX A40"

# Get service URLs with health checks
autopod info

# Output shows:
# 🌐 HTTP Proxy Services:
#   ✓ ComfyUI: https://abc123xyz-8188.proxy.runpod.net (online)
#   ⏳ FileBrowser: https://abc123xyz-8080.proxy.runpod.net (timeout - may be starting)
#   ✓ JupyterLab: https://abc123xyz-8888.proxy.runpod.net (online)
#
# 🔑 SSH Access:
#   ssh abc123xyz-64411540@ssh.runpod.io -i ~/.ssh/id_ed25519

# Open any URL in your browser
# (Wait ~60-120 seconds for services to fully start)

# When done, terminate immediately to save costs
autopod kill abc-123 -y
```

**Flexible Port Exposure:**
```bash
# Expose specific ports with custom labels
autopod connect --expose 8188:myapp --expose 8080:admin

# Expose single port (auto-labeled from config if available)
autopod connect --expose 8188

# Expose all ports for a template (reads from config)
autopod connect --expose-all
```

**Security Reminder:** HTTP proxy has no authentication. Anyone with the URL can access your services. Terminate pods immediately when done to prevent unauthorized access and unnecessary charges.

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
- `--expose <PORT[:LABEL]>` - Expose port via HTTP proxy with optional label (repeatable)
- `--expose-all` - Expose all ports defined in config for this template
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

Create pod with all template ports exposed:
```bash
autopod connect --expose-all
```

Create pod with specific ports and custom labels:
```bash
autopod connect --expose 8188:ComfyUI --expose 8080:FileBrowser
```

Create pod with single port (auto-labeled from config if available):
```bash
autopod connect --expose 8188
```

---

### HTTP Port Exposure

#### Port Exposure Overview

By default, pods are not accessible from the internet. Use the `--expose` or `--expose-all` flags to expose ports through RunPod's HTTPS proxy, making web services accessible from your browser.

**Supported Flags:**
- `--expose <PORT[:LABEL]>` - Expose specific port with optional label (repeatable)
- `--expose-all` - Expose all ports defined in config for the template

**Common Ports (RunPod ComfyUI Template):**
- `8188` - ComfyUI web interface
- `8080` - FileBrowser (admin / adminadmin12)
- `8888` - JupyterLab (token via JUPYTER_PASSWORD env var)

**Port Templates in Config:**

Add templates to `~/.autopod/config.json` for `--expose-all` support:

```json
{
  "port_templates": {
    "runpod/comfyui:latest": {
      "8188": "ComfyUI",
      "8080": "FileBrowser",
      "8888": "JupyterLab"
    },
    "your/custom:template": {
      "3000": "WebApp",
      "8000": "API"
    }
  }
}
```

**Security Notes:**
- HTTP proxy has **no authentication by default**
- Anyone with the URL can access your services
- URLs format: `https://[pod-id]-[port].proxy.runpod.net`
- Traffic is HTTPS encrypted but RunPod can inspect it
- **Best Practice:** Only expose ports you need, terminate pods when done

**Examples:**

Expose all template ports:
```bash
autopod connect --expose-all
```

Expose specific ports with custom labels:
```bash
autopod connect --expose 8188:MyApp --expose 3000:WebUI
```

Expose single port (auto-labeled from config):
```bash
autopod connect --expose 8188
```

---

### Pod Listing & Information

#### `autopod list` (aliases: `ls`, `ps`)
List all pods with status, GPU, runtime, and cost

#### `autopod info [POD_ID]`
Show detailed information about a specific pod

---

### SSH Access

#### `autopod ssh [POD_ID]` (alias: `shell`)
Open interactive SSH shell on a pod

---

### Pod Control

#### `autopod stop [POD_ID]`
Stop (pause) a pod

#### `autopod start [POD_ID]` (alias: `resume`)
Start (resume) a stopped pod

#### `autopod kill [POD_ID]` (aliases: `terminate`, `rm`)
Terminate (destroy) a pod permanently

---

### SSH Tunnels

**Note on V1.2 Changes:**
- **Automatic tunneling has been disabled.** Web services are now accessed via RunPod HTTP proxy by default.
- Tunnels must be managed manually using the commands below.
- Full SSH tunnel support for pods with public IPs is planned for V1.4.

**For V1.2, use the HTTP proxy instead of manual tunnels for GUI access:**
```bash
# 1. Create a pod with HTTP proxy enabled
autopod connect --expose-all

# 2. Get service URLs with health checks
autopod info

# URLs are displayed in format: https://[pod-id]-[port].proxy.runpod.net
```

#### `autopod tunnel start [POD_ID]`
Manually create an SSH tunnel to access a service on a pod.

**This command will likely fail with RunPod's default SSH proxy.** It is intended for use with pods that have a dedicated public IP (a V1.4 feature).

#### `autopod tunnel stop [POD_ID]`
Stop an SSH tunnel for a specific pod.

#### `autopod tunnel list`
List all active and stale SSH tunnels managed by `autopod`.

#### `autopod tunnel cleanup`
Remove dead/stale tunnels from tracking.

#### `autopod tunnel stop-all`
Stop all active SSH tunnels managed by `autopod`. This is a useful kill-switch if you have multiple tunnels running.

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

### Verbose Logging / Debugging

**Enable verbose output for troubleshooting:**

```bash
# Using command-line flag (recommended)
autopod --verbose info
autopod -v connect

# Using environment variable
AUTOPOD_DEBUG=1 autopod info
```

**Default behavior:**
- Console: Only shows warnings and errors (quiet)
- Log file: Captures everything (`~/.autopod/logs/autopod.log`)

**When to use verbose mode:**
- Debugging connection issues
- Troubleshooting API errors
- Understanding what autopod is doing
- Reporting bugs

### GPU Not Available

**Symptom:** `No GPUs available from preferences`

**Solution:**
1. Try specific GPU: `autopod connect --gpu "RTX A5000"`
2. Check RunPod console for available GPUs
3. Try `--cloud-type ALL` to include community cloud
4. Update GPU preferences in config

### SSH Tunnel Issues (V1.2)

**Note:** SSH tunnels do not work in V1.2 due to RunPod's proxied SSH limitations. Use `--expose-http` instead.

**Symptom:** `autopod tunnel start` fails

**Explanation:** RunPod's `ssh.runpod.io` proxy does not support SSH port forwarding (`-L` flag). This is a known limitation.

**Solution:** Use HTTP proxy instead:
```bash
autopod connect --expose-all     # Create pod with HTTP proxy
autopod info                     # View service URLs with health checks
```

SSH tunnels will be available in V1.4 when public IP pod support is added.

**Symptom:** Web service not responding via HTTP proxy

**Solutions:**
1. Services take ~60-120 seconds to start after pod creation
2. Check service health: `autopod info` (shows live health checks)
3. Verify pod was created with `--expose-all` or `--expose PORT` flag
4. Check the proxy URLs in the pod creation output or `autopod info`

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

### V1.2 - HTTP Proxy & Template-Agnostic Design ✅
- Flexible port exposure with custom labels (`--expose PORT:LABEL`)
- Template-based port defaults (`--expose-all` reads from config)
- HTTP proxy access for web services (no SSH tunnel needed)
- Live health checks in `autopod info` command
- Ready-to-use SSH commands displayed in output
- Network volume support for persistent storage
- Tunnel infrastructure (groundwork for V1.4, not functional in V1.2)

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