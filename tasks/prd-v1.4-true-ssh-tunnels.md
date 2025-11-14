# PRD #4: V1.4 - True SSH Tunnels with Public IP

## Introduction / Overview

This PRD defines V1.4 of autopod, which adds support for **true SSH tunnels** using RunPod's public IP feature. This enables secure, encrypted SSH port forwarding to access ComfyUI and other pod services without relying on HTTP proxy URLs.

**Problem it solves**: V1.2 and V1.3 use RunPod's HTTP proxy for ComfyUI access, which has significant limitations:
- **Security**: No authentication (anyone with URL can access)
- **Timeout**: 100-second maximum connection time (Cloudflare limitation)
- **Public exposure**: Proxy URLs are publicly accessible
- **No SSH tunneling**: RunPod's proxied SSH (`ssh.runpod.io`) does not support port forwarding (`-L` flag)

**Goal**: Enable users to create pods with public IP addresses and full SSH daemon support, allowing true SSH port forwarding for secure, private access to ComfyUI and other services.

## Background: RunPod SSH Architecture

### Discovery from V1.2 Research

During V1.2 testing, we discovered that **RunPod's proxied SSH does NOT support port forwarding**:

```
Your Machine → ssh.runpod.io (proxy) → Pod
              ❌ Port forwarding blocked
              ❌ SCP/SFTP not supported
              ✅ Interactive shell only
```

**Why?** RunPod's basic SSH proxy is intentionally limited:
- Only supports interactive terminal sessions
- Does not forward SSH protocol channels (SCP, SFTP, `-L` forwarding)
- Community reports confirm: "channel 2: open failed: unknown channel type: unsupported channel type"

### Solution: Public IP with True SSH

RunPod offers a different mode - **SSH over TCP with public IP**:

```
Your Machine → Public IP:PORT (direct) → Pod SSH Daemon
              ✅ Full OpenSSH functionality
              ✅ Port forwarding works (-L flag)
              ✅ SCP/SFTP supported
```

**Requirements:**
1. Pod created with `support_public_ip: true`
2. TCP port 22 exposed (`ports: "22/tcp"`)
3. SSH daemon running in container
4. Community Cloud (Secure Cloud doesn't support public IP)

**Benefits:**
- Encrypted, authenticated access
- No timeout limits (direct connection)
- Private access (no public HTTP URLs)
- Full SSH capabilities

## Goals

1. **Public IP pod creation**: Add `--enable-ssh-tunnel` flag to create pods with public IP support
2. **SSH daemon detection**: Auto-detect if template has SSH daemon, install if needed
3. **Public IP SSH connection**: Detect and use public IP SSH instead of proxied SSH
4. **Hybrid mode**: Support both HTTP proxy (V1.2/V1.3) and true SSH (V1.4)
5. **Auto-selection**: Intelligently choose best access method based on pod capabilities
6. **Backward compatibility**: All existing V1.2/V1.3 functionality continues to work
7. **Cost transparency**: Show public IP cost to user before creation

## User Stories

### Story 1: Create pod with true SSH tunnel
**As a** security-conscious user
**I want to** create a pod with true SSH tunnel support
**So that** I can access ComfyUI securely without public HTTP URLs

**Acceptance criteria**:
- User runs `autopod connect --enable-ssh-tunnel`
- autopod requests public IP in pod creation (`support_public_ip: true`)
- autopod exposes TCP port 22 (`ports: "22/tcp"`)
- autopod detects public IP and port from pod info
- autopod creates SSH tunnel using public IP (not `ssh.runpod.io`)
- SSH tunnel port forwarding works (can access `localhost:8188`)
- User sees cost breakdown (GPU + public IP ~$0.02/hr)

### Story 2: Auto-detect and use public IP SSH
**As a** user
**I want** autopod to automatically use public IP SSH if available
**So that** I get the best access method without manual configuration

**Acceptance criteria**:
- User creates pod with `--enable-ssh-tunnel`
- autopod detects public IP in pod runtime info
- autopod automatically uses `root@<public-ip> -p <port>` instead of `ssh.runpod.io`
- Tunnel commands work seamlessly with public IP SSH
- ComfyUI API client works via SSH tunnel
- User can still use `--expose-http` for HTTP proxy fallback

### Story 3: Ensure SSH daemon is running
**As a** user
**I want** autopod to handle SSH daemon installation automatically
**So that** I don't have to manually configure containers

**Acceptance criteria**:
- autopod detects if template has SSH daemon
- If missing, autopod shows warning and offers to install
- User can provide custom Docker command to start SSH daemon
- Official RunPod templates work out-of-the-box
- SSH daemon starts automatically on pod creation
- SSH key authentication works correctly

### Story 4: Hybrid mode - use best available method
**As a** developer
**I want** autopod to use SSH tunnel when available, fall back to HTTP proxy
**So that** my code works on all pod types (with/without public IP)

**Acceptance criteria**:
- autopod detects pod capabilities (has public IP? has HTTP proxy?)
- Prefers SSH tunnel if public IP available
- Falls back to HTTP proxy if no public IP
- User can override with `--prefer-http-proxy` flag
- ComfyUI client works with both methods
- Error messages explain which method is being used

## Functional Requirements

### FR-1: Public IP Pod Creation
The system must support creating pods with public IP and TCP port 22 exposure.

**CLI Interface:**
```bash
autopod connect --enable-ssh-tunnel
autopod connect --enable-ssh-tunnel --expose-http  # Both methods
```

**Pod Configuration:**
```python
pod_config = {
    "support_public_ip": True,
    "ports": "22/tcp",  # Or "8188/http,22/tcp" for both
    ...
}
```

**RunPod API Parameters:**
```python
runpod.create_pod(
    support_public_ip=True,
    ports="22/tcp,8188/http",
    ...
)
```

### FR-2: Public IP Detection
The system must detect public IP address and port from pod runtime info.

**Detection Logic:**
```python
def get_public_ip_ssh(pod_id: str) -> Optional[Dict]:
    """
    Returns:
        {
            "ip": "213.173.109.39",
            "port": 13007,
            "connection_string": "root@213.173.109.39 -p 13007"
        }
        OR None if no public IP
    """
    pod_info = runpod.get_pod(pod_id)

    # Check runtime.ports for TCP port 22 mapping
    if pod_info.get("runtime") and pod_info["runtime"].get("ports"):
        for port in pod_info["runtime"]["ports"]:
            if port.get("privatePort") == 22 and port.get("type") == "tcp":
                return {
                    "ip": port.get("ip"),
                    "port": port.get("publicPort"),
                    "connection_string": f"root@{port['ip']} -p {port['publicPort']}"
                }

    return None
```

### FR-3: SSH Daemon Detection and Installation
The system must detect if SSH daemon is running, and help user install if needed.

**Detection:**
- Check if template is official RunPod template (has SSH daemon)
- Attempt SSH connection to verify daemon is responding
- Check for SSH process in container

**Installation Assistance:**
- Provide Docker command to install openssh-server
- Offer to create custom template with SSH daemon
- Document SSH daemon requirements in README

**Example Installation Command:**
```bash
apt update && \
DEBIAN_FRONTEND=noninteractive apt-get install openssh-server -y && \
mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
echo "$SSH_PUBLIC_KEY" >> ~/.ssh/authorized_keys && \
chmod 600 ~/.ssh/authorized_keys && \
service ssh start
```

### FR-4: Hybrid SSH Connection Method
The system must intelligently choose between public IP SSH and proxied SSH.

**Priority Order:**
1. **Public IP SSH** (if pod has TCP port 22 exposed)
   - Connection: `root@<public-ip> -p <port>`
   - Port forwarding: Works ✅
   - Use case: `--enable-ssh-tunnel` flag

2. **Proxied SSH** (fallback for all pods)
   - Connection: `pod-id-machine@ssh.runpod.io`
   - Port forwarding: Does NOT work ❌
   - Use case: Default, backward compatibility

**Updated `get_ssh_connection_string()`:**
```python
def get_ssh_connection_string(self, pod_id: str) -> str:
    """Get SSH connection string for pod.

    Prefers public IP SSH if available, falls back to proxied SSH.
    """
    # Try public IP SSH first
    public_ip_info = self.get_public_ip_ssh(pod_id)
    if public_ip_info:
        logger.info(f"Using public IP SSH: {public_ip_info['ip']}:{public_ip_info['port']}")
        return public_ip_info["connection_string"]

    # Fall back to proxied SSH
    pod_info = runpod.get_pod(pod_id)
    machine_id = pod_info.get("machine", {}).get("podHostId")
    if machine_id:
        logger.info("Using proxied SSH (port forwarding not supported)")
        return f"{pod_id}-{machine_id}@ssh.runpod.io"

    return f"{pod_id}@ssh.runpod.io"
```

### FR-5: SSH Tunnel with Public IP
The system must create SSH tunnels using public IP SSH when available.

**Tunnel Creation:**
```python
# Automatic detection
ssh_string = provider.get_ssh_connection_string(pod_id)
# Returns: "root@213.173.109.39 -p 13007" (public IP)
#      OR: "pod-id-machine@ssh.runpod.io" (proxied)

tunnel = tunnel_manager.create_tunnel(
    pod_id=pod_id,
    ssh_connection_string=ssh_string,
    local_port=8188,
    remote_port=8188
)

tunnel.start()
# If public IP → port forwarding works ✅
# If proxied → port forwarding fails ❌
```

**Warning on Proxied SSH:**
```python
if "@ssh.runpod.io" in ssh_connection_string:
    console.print(
        "[yellow]⚠️  WARNING: Using proxied SSH (ssh.runpod.io)[/yellow]\n"
        "[yellow]   Port forwarding may not work.[/yellow]\n"
        "[yellow]   Use --enable-ssh-tunnel for true SSH tunnel support.[/yellow]"
    )
```

### FR-6: ComfyUI Access Method Selection
The system must support multiple access methods for ComfyUI API.

**Access Methods:**
1. **SSH Tunnel** (preferred, if public IP available)
   - URL: `http://localhost:8188`
   - Via SSH tunnel to public IP
   - Secure, encrypted, no timeout

2. **HTTP Proxy** (fallback, always works)
   - URL: `https://pod-id-8188.proxy.runpod.net`
   - Via RunPod proxy
   - Public, 100s timeout

**Selection Logic:**
```python
def get_comfyui_access_method(pod_id: str) -> Dict:
    """Determine best access method for ComfyUI API."""

    # Check if tunnel exists and is active
    tunnel = tunnel_manager.get_tunnel(pod_id)
    if tunnel and tunnel.is_active():
        # Check if using public IP SSH
        if "@ssh.runpod.io" not in tunnel.ssh_connection_string:
            return {
                "method": "ssh_tunnel",
                "base_url": f"http://localhost:{tunnel.local_port}",
                "description": "SSH tunnel via public IP (secure, encrypted)"
            }

    # Check if HTTP proxy available
    pod_info = pod_manager.get_pod_info(pod_id)
    if pod_info.get("http_proxy_url"):
        return {
            "method": "http_proxy",
            "base_url": pod_info["http_proxy_url"],
            "description": "HTTP proxy (public URL, 100s timeout)"
        }

    # No access method available
    return {
        "method": "none",
        "base_url": None,
        "description": "No access method available"
    }
```

### FR-7: Cost Transparency
The system must show public IP cost to user before pod creation.

**Cost Display:**
```bash
autopod connect --enable-ssh-tunnel

Creating pod with true SSH tunnel support:
  GPU: RTX A40 (1x)              $0.40/hr
  Public IP                      $0.02/hr
  Container Disk: 50GB           included
                        ─────────────────
  Total:                         $0.42/hr

⚠️  Note: Public IP required for SSH tunnel support
⚠️  Works with Community Cloud only (not Secure Cloud)

Proceed? [y/N]:
```

### FR-8: Template Compatibility Check
The system must verify template compatibility with public IP SSH.

**Compatibility Matrix:**

| Template | SSH Daemon | Public IP | Compatible |
|----------|-----------|-----------|------------|
| `runpod/pytorch` | ✅ Yes | ✅ Yes | ✅ Works |
| `runpod/stable-diffusion` | ✅ Yes | ✅ Yes | ✅ Works |
| `runpod/comfyui` | ❓ Unknown | ✅ Yes | ⚠️ Test needed |
| Custom templates | ❌ No | ✅ Yes | ⚠️ Manual install |

**Detection Logic:**
```python
def check_template_ssh_support(template: str) -> Dict:
    """Check if template has SSH daemon."""

    # Known templates with SSH daemon
    ssh_supported = [
        "runpod/pytorch",
        "runpod/stable-diffusion",
        "runpod/tensorflow",
    ]

    if any(t in template for t in ssh_supported):
        return {"has_ssh": True, "verified": True}

    # Unknown template
    return {"has_ssh": False, "verified": False}
```

### FR-9: CLI Flags and Options
The system must provide clear CLI flags for SSH tunnel control.

**New Flags:**
```bash
# Enable true SSH tunnel (public IP + TCP port 22)
autopod connect --enable-ssh-tunnel

# Prefer HTTP proxy even if SSH tunnel available
autopod connect --prefer-http-proxy

# Both methods (HTTP proxy + SSH tunnel)
autopod connect --expose-http --enable-ssh-tunnel

# Show access methods for pod
autopod info <pod-id>
# Output shows:
#   Access Methods:
#     - SSH Tunnel: localhost:8188 (via 213.173.109.39:13007)
#     - HTTP Proxy: https://pod-id-8188.proxy.runpod.net
```

**Configuration Defaults:**
```json
{
  "defaults": {
    "prefer_ssh_tunnel": true,
    "auto_install_ssh_daemon": false,
    "ssh_tunnel_timeout": 300
  }
}
```

### FR-10: Error Handling and Warnings
The system must provide clear error messages and warnings for SSH tunnel issues.

**Error Scenarios:**

1. **Public IP not available:**
```
❌ ERROR: Public IP not available for this pod type
   Falling back to HTTP proxy access

   To enable SSH tunnels:
   - Use Community Cloud (not Secure Cloud)
   - Ensure GPU type supports public IP
```

2. **SSH daemon not running:**
```
❌ ERROR: SSH daemon not responding on port 22

   SSH tunnel will not work. Options:
   1. Use HTTP proxy: autopod connect --expose-http
   2. Install SSH daemon in template
   3. Use official RunPod template (has SSH daemon)
```

3. **Port forwarding failed:**
```
❌ ERROR: SSH port forwarding failed

   Possible causes:
   - Using proxied SSH (ssh.runpod.io) - not supported
   - SSH daemon not running on pod
   - Port already in use locally

   Solution: Use --enable-ssh-tunnel flag
```

## Non-Goals (Out of Scope)

### V1.4 will NOT include:

1. **Automatic SSH daemon installation**: User must use templates with SSH daemon or install manually
2. **Support for Secure Cloud**: Public IP only works on Community Cloud
3. **Custom port mapping**: Uses RunPod's automatic port assignment
4. **Multiple SSH tunnels per pod**: One tunnel per pod (can expose multiple ports in V2.0)
5. **SSH key management**: Uses existing SSH keys from user's system
6. **SOCKS proxy**: Only local port forwarding (`-L`), no SOCKS proxy (`-D`)
7. **Reverse tunnels**: No remote port forwarding (`-R`)
8. **IPv6 support**: IPv4 public IP only

## Design Considerations

### Public IP vs Proxied SSH: Trade-offs

| Feature | Public IP SSH | Proxied SSH |
|---------|---------------|-------------|
| **Port forwarding** | ✅ Works | ❌ Blocked |
| **SCP/SFTP** | ✅ Works | ❌ Blocked |
| **Cost** | +$0.02/hr | Free |
| **Security** | ✅ Encrypted | ✅ Encrypted |
| **Timeout** | ✅ None | N/A |
| **Availability** | Community Cloud | All clouds |
| **Setup** | Requires SSH daemon | No setup |

**Decision**: Support both, prefer public IP SSH when available.

### SSH Daemon Availability

**Known Working Templates:**
- `runpod/pytorch:*` - Has openssh-server pre-installed
- `runpod/stable-diffusion:*` - Has openssh-server pre-installed

**Unknown/Custom Templates:**
- `runpod/comfyui:*` - **Needs testing** (may not have SSH daemon)
- Custom templates - Likely need manual SSH daemon installation

**Installation Strategy:**
1. **V1.4**: Warn user if SSH daemon missing, provide installation command
2. **V1.5**: Auto-detect and offer to install SSH daemon
3. **V2.0**: Create custom autopod template with SSH daemon pre-installed

### Port Assignment

RunPod assigns ports automatically (not user-controlled):
- Internal port 22 → External port (e.g., 13007)
- Internal port 8188 → External port (e.g., 18188)

**Implication**: autopod must query pod runtime to get assigned ports.

### Connection String Format

**Public IP SSH:**
```bash
root@213.173.109.39 -p 13007
```

**Proxied SSH:**
```bash
pod-id-machine@ssh.runpod.io
```

**Detection**: Check if string contains `@ssh.runpod.io`.

## Technical Considerations

### Dependencies

No new dependencies required - all functionality uses existing libraries:
- `subprocess` - SSH tunnel creation
- `requests` - RunPod API queries
- `psutil` - Process management

### Code Changes Required

**1. `src/autopod/providers/runpod.py`:**
- Add `support_public_ip` parameter to `create_pod()`
- Add `get_public_ip_ssh()` method
- Update `get_ssh_connection_string()` to prefer public IP

**2. `src/autopod/cli.py`:**
- Add `--enable-ssh-tunnel` flag to `connect()` command
- Add `--prefer-http-proxy` flag to `comfy` commands
- Update `info` command to show access methods

**3. `src/autopod/tunnel.py`:**
- Add warning when using proxied SSH
- Add detection logic for public IP vs proxied SSH
- Update error messages to suggest `--enable-ssh-tunnel`

**4. `src/autopod/comfyui.py`:**
- Add access method selection logic
- Support both SSH tunnel and HTTP proxy URLs
- Add method detection to constructor

**5. `tests/manual/test_v1.4_true_ssh_tunnel.py`:**
- Test pod creation with `support_public_ip=True`
- Test public IP detection
- Test SSH tunnel creation with public IP
- Test ComfyUI API via SSH tunnel (not proxy)
- Verify port forwarding works

### Environment Variables

Pods with public IP expose:
```bash
RUNPOD_PUBLIC_IP="213.173.109.39"
RUNPOD_TCP_PORT_22="13007"
RUNPOD_TCP_PORT_8188="18188"
```

**Note**: These are available **inside** the pod, not in autopod client.

### Security Considerations

**Public IP Risks:**
- Pod is directly accessible from internet
- Requires SSH key authentication (no passwords)
- Firewall rules needed for production

**Mitigation:**
- Use SSH key authentication only (no password auth)
- Document security best practices in README
- Warn users about public IP exposure

## Success Metrics

### Must-Have for V1.4 Release:

1. **Pod creation with public IP**: User can run `autopod connect --enable-ssh-tunnel` and get public IP pod
2. **Public IP SSH detection**: autopod detects public IP and uses it for SSH (not proxy)
3. **SSH tunnel port forwarding**: SSH tunnel with `-L` flag works (can access `localhost:8188`)
4. **ComfyUI API via SSH tunnel**: All ComfyUI API methods work over SSH tunnel (not HTTP proxy)
5. **Hybrid support**: HTTP proxy still works for pods without public IP (backward compatibility)
6. **Cost transparency**: User sees public IP cost before pod creation
7. **Error handling**: Clear warnings when SSH daemon missing or port forwarding fails

### Test Coverage:

- **Integration test**: End-to-end pod creation with public IP + SSH tunnel + ComfyUI API access
- **Integration test**: Verify SSH tunnel works (NOT proxied SSH)
- **Integration test**: Verify HTTP proxy fallback still works
- **Unit test**: Public IP detection from pod runtime info
- **Unit test**: Connection string format for public IP vs proxied
- **Manual test**: SSH daemon availability on ComfyUI template

## Open Questions

### Q1: Does `runpod/comfyui:latest` template have SSH daemon?

**Investigation needed**:
- Spin up `runpod/comfyui` pod with TCP port 22
- Attempt SSH connection
- Check if openssh-server installed

**If YES**: Works out-of-the-box ✅
**If NO**: Need to provide SSH daemon installation instructions ⚠️

### Q2: What is the actual public IP cost?

**Research needed**:
- Verify public IP cost (~$0.02/hr estimated)
- Check if cost varies by region
- Document in cost calculation

### Q3: Does Secure Cloud support public IP?

**From research**: Secure Cloud does NOT support public IP (Community Cloud only)

**Implication**: Need to warn users and validate cloud type before enabling SSH tunnel.

## Example Usage

### Scenario 1: Create pod with true SSH tunnel

```bash
# Create pod with public IP and SSH tunnel
autopod connect --enable-ssh-tunnel

Creating pod with true SSH tunnel support:
  GPU: RTX A40 (1x)              $0.40/hr
  Public IP                      $0.02/hr
                        ─────────────────
  Total:                         $0.42/hr

✓ Pod created: abc123
✓ Public IP assigned: 213.173.109.39:13007
✓ SSH tunnel created: localhost:8188 → pod:8188
✓ ComfyUI accessible at: http://localhost:8188

Access Methods:
  SSH Tunnel:  http://localhost:8188 (secure, encrypted)
  Direct SSH:  ssh root@213.173.109.39 -p 13007
```

### Scenario 2: Hybrid mode (both HTTP proxy and SSH tunnel)

```bash
# Create pod with both access methods
autopod connect --expose-http --enable-ssh-tunnel

✓ Pod created: abc123
✓ Public IP assigned: 213.173.109.39:13007
✓ HTTP proxy URL: https://abc123-8188.proxy.runpod.net
✓ SSH tunnel created: localhost:8188 → pod:8188

Access Methods:
  SSH Tunnel:  http://localhost:8188 (preferred, secure)
  HTTP Proxy:  https://abc123-8188.proxy.runpod.net (fallback, public)
```

### Scenario 3: Auto-detect best access method

```bash
# Create pod, access via best method
autopod connect --enable-ssh-tunnel

# Later, ComfyUI commands auto-use SSH tunnel
autopod comfy status

Using SSH tunnel (localhost:8188) via public IP
✓ ComfyUI is ready
  Status: idle
  Queue: 0 running, 0 pending
```

### Scenario 4: Fallback to HTTP proxy when public IP unavailable

```bash
# Try to create pod on Secure Cloud (no public IP support)
autopod connect --enable-ssh-tunnel --cloud-type SECURE

⚠️  WARNING: Secure Cloud does not support public IP
   Falling back to HTTP proxy access

✓ Pod created: def456
✓ HTTP proxy URL: https://def456-8188.proxy.runpod.net
✗ SSH tunnel: Not available (no public IP)

Access Methods:
  HTTP Proxy:  https://def456-8188.proxy.runpod.net (only option)
```

## Implementation Roadmap

### Phase 1: Core Public IP Support (Week 1)
- [ ] Add `support_public_ip` parameter to `create_pod()`
- [ ] Add `--enable-ssh-tunnel` flag to CLI
- [ ] Implement public IP detection in `get_public_ip_ssh()`
- [ ] Update `get_ssh_connection_string()` to prefer public IP
- [ ] Test pod creation with public IP

### Phase 2: SSH Tunnel Integration (Week 2)
- [ ] Update tunnel creation to use public IP SSH
- [ ] Add warning for proxied SSH (port forwarding won't work)
- [ ] Test SSH tunnel with public IP (verify port forwarding works)
- [ ] Add error handling for missing SSH daemon

### Phase 3: ComfyUI Hybrid Access (Week 3)
- [ ] Implement access method selection in ComfyUI client
- [ ] Add `--prefer-http-proxy` flag
- [ ] Update `comfy` commands to use best access method
- [ ] Test ComfyUI API via both SSH tunnel and HTTP proxy

### Phase 4: Documentation and Testing (Week 4)
- [ ] Update README with `--enable-ssh-tunnel` documentation
- [ ] Document SSH daemon requirements
- [ ] Create `test_v1.4_true_ssh_tunnel.py`
- [ ] Test with `runpod/comfyui` template (verify SSH daemon)
- [ ] Update cost transparency display
- [ ] Mark V1.4 as complete

## Appendix: RunPod Public IP API Reference

### Pod Creation with Public IP

```python
import runpod

runpod.api_key = "your-api-key"

pod = runpod.create_pod(
    name="autopod-ssh-tunnel",
    image_name="runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04",
    gpu_type_id="NVIDIA A40",
    gpu_count=1,
    support_public_ip=True,  # ← Enable public IP
    ports="22/tcp,8188/http",  # ← Expose SSH and ComfyUI
    container_disk_in_gb=50,
    cloud_type="COMMUNITY"  # ← Public IP only works on Community Cloud
)

print(f"Pod ID: {pod['id']}")
```

### Retrieving Public IP from Pod Info

```python
pod_info = runpod.get_pod(pod_id)

# Public IP info in runtime.ports
for port in pod_info["runtime"]["ports"]:
    if port["privatePort"] == 22 and port["type"] == "tcp":
        public_ip = port["ip"]
        public_port = port["publicPort"]
        print(f"SSH: ssh root@{public_ip} -p {public_port}")
```

**Example Response:**
```json
{
  "runtime": {
    "ports": [
      {
        "ip": "213.173.109.39",
        "isIpPublic": true,
        "privatePort": 22,
        "publicPort": 13007,
        "type": "tcp"
      },
      {
        "ip": "213.173.109.39",
        "isIpPublic": true,
        "privatePort": 8188,
        "publicPort": 18188,
        "type": "http"
      }
    ]
  }
}
```

## Appendix: SSH Daemon Installation

### For Custom Templates

If your template doesn't have SSH daemon, add this to Docker command:

```bash
bash -c '
  # Update package list
  apt-get update && \

  # Install openssh-server (non-interactive)
  DEBIAN_FRONTEND=noninteractive apt-get install openssh-server -y && \

  # Create SSH directory
  mkdir -p ~/.ssh && chmod 700 ~/.ssh && \

  # Add SSH public key (from environment variable)
  echo "$SSH_PUBLIC_KEY" >> ~/.ssh/authorized_keys && \
  chmod 600 ~/.ssh/authorized_keys && \

  # Start SSH daemon
  service ssh start && \

  # Keep container running
  sleep infinity
'
```

### Verification

Test SSH daemon is running:
```bash
# Inside pod
ps aux | grep sshd

# Should show:
# root  123  0.0  0.0  12345  1234 ?  Ss  12:00  0:00 /usr/sbin/sshd -D
```

## Appendix: Cost Breakdown

### Public IP Pricing

| Item | Cost | Notes |
|------|------|-------|
| GPU (RTX A40) | $0.40/hr | Base GPU cost |
| Public IP | $0.02/hr | Estimated (verify with RunPod) |
| Container Disk (50GB) | Included | No extra cost |
| **Total** | **$0.42/hr** | ~5% increase for public IP |

### Cost Comparison: V1.2 vs V1.4

| Version | Access Method | Cost | Security | Timeout |
|---------|---------------|------|----------|---------|
| V1.2 | HTTP Proxy | $0.40/hr | ❌ No auth | ⚠️ 100s max |
| V1.4 | SSH Tunnel | $0.42/hr | ✅ Encrypted | ✅ None |

**Conclusion**: +$0.02/hr (~5%) for significantly better security and reliability.
