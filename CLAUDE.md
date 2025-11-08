# CLAUDE.md - autopod Development Guide

## Project Overview

**autopod** is a lightweight CLI controller for automating ComfyUI workflows on RunPod instances. The primary goal is to save money on compute costs when running image-to-video workflows by enabling automated pod lifecycle management.

### Core Purpose
- Automate RunPod pod creation and termination
- Control headless ComfyUI instances via API
- Monitor job completion to minimize idle compute time
- Serve as the backbone for a future video rendering pipeline

### Key Features

**Version 1 (MVP - Single Pod, Sequential Jobs):**
- Create RunPod pods programmatically via API
- Establish SSH tunnel to remote ComfyUI instance (localhost:8188 → pod:8188)
- Read jobs from local filesystem (JSON format)
- Transfer input files via SCP
- Submit jobs to ComfyUI API using parameterized workflow templates
- WebSocket-based real-time job status monitoring
- Rich terminal UI with live progress, cost tracking, and keyboard controls
- Interactive controls: Open ComfyUI GUI in browser, kill/stop pod, view logs
- Safe shutdown handling (Ctrl+C triggers graceful pod stop)
- Stuck job detection and cost safety warnings

**Version 2 (Multi-Pod, Parallel Jobs):**
- Multiple SSH tunnels (one per pod on unique ports: 8188, 8189, 8190...)
- One pod per job for parallel execution
- Textualize TUI for managing multiple pods (table view, interactive selection)
- Aggregate cost monitoring across all running pods
- Cloudflare R2 for job queue and file storage

**Version 3 (Cloud-Native Pipeline):**
- Long-running worker pods that poll R2 for jobs
- RunPod Network Volumes for model storage and output buffering
- Multi-tier storage: Network Volume (30-day cache) + R2 (permanent)
- Fully autonomous operation (no Mac connection required)

### Technology Stack

**Core:**
- **Language:** Python 3.10+
- **Terminal UI:** Rich library for progress bars, live status, and formatted output
- **Infrastructure:** RunPod API, SSH/SCP for file transfer
- **APIs:** ComfyUI API (REST + WebSocket), RunPod API (GraphQL)
- **Storage:** Local filesystem (V1), Cloudflare R2 (V2+), RunPod Network Volumes (V2+)

**Key Dependencies (V1):**
- `rich` - Terminal output and progress bars
- `requests` - HTTP API calls
- `websocket-client` - ComfyUI WebSocket monitoring
- `runpod` - Official RunPod Python SDK (if available, otherwise direct API calls)
- `paramiko` or `scp` - SSH tunnel and file transfer
- Standard library: `subprocess`, `json`, `webbrowser`, `signal`

**Additional Dependencies (V2+):**
- `textual` (Textualize) - Full TUI for multi-pod management
- `boto3` - Cloudflare R2 (S3-compatible) client

**Dependencies Philosophy:**
- Use proven, stable libraries that solve real problems
- Rich (~1.5MB, pure Python) provides professional terminal output with minimal overhead
- Future GUI/web interface can consume JSON output from the same core
- Keep V1 dependencies minimal - only add when value is clear

### Architecture Philosophy
- **Lightweight proof-of-concept controller** - focused, pragmatic, and proven
- No unnecessary features, but existing features should work really well
- Build lower-level primitives first, interfaces later
- Design as a pipeline backbone, not a feature-rich application
- Prioritize cost visibility and safe cancellation (monitoring expensive compute is critical)

### UI/Monitoring Strategy

**Hybrid CLI + Rich Console Output** (chosen approach)

Instead of a pure CLI or full TUI (Textualize), we use a middle-ground approach:

**Phase 1: CLI with Rich Progress/Status**
```bash
autopod run --job-file ./jobs/render.json

→ Pod Creation    [████████████████] 100% (pod-xyz created)
→ SSH Connection  [████████████████] 100% (connected)
→ Job Queue       [████░░░░░░░░░░░░]  25% (1/4 jobs complete)
   ├─ job-001.mp4 ✓ completed (2m 34s)
   ├─ job-002.mp4 ⟳ rendering... (1m 12s elapsed)
   ├─ job-003.mp4 ⋯ queued
   └─ job-004.mp4 ⋯ queued

Cost: $0.42 elapsed | Ctrl+C to safely stop pod
```

**Phase 2: Status/Control Commands**
```bash
autopod status          # Show current running jobs
autopod cancel <job-id> # Cancel specific job
autopod stop            # Gracefully stop pod
autopod logs <job-id>   # Stream logs
```

**Why this approach:**
- ✅ Good enough for manual monitoring (clear visibility of expensive compute)
- ✅ Still scriptable and pipeline-friendly
- ✅ Cost-safe with clear feedback and Ctrl+C handling
- ✅ Future-proof: `--json` flag enables programmatic use and future GUIs
- ✅ Minimal complexity: Rich is enhanced `print()`, not a UI framework

**When to upgrade to full TUI (Textualize):**
Only if manual usage exceeds 80% and you need:
- Scrollable job history
- Interactive job selection/management
- Real-time log viewing with filtering
- Multi-pod management in one view

**Decision:** Start with Rich, add `--json` mode for programmatic use, evaluate Textualize later based on actual usage patterns.

---

## Technical Architecture

### Version 1: Single Pod Controller (Mac-based)

**Architecture Overview:**
```
┌─────────────────────────────────────────────────────────────┐
│  Mac (autopod controller)                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  1. Read job JSON (local file)                       │   │
│  │  2. Create RunPod pod via API                        │   │
│  │  3. SSH tunnel: localhost:8188 → pod:8188           │   │
│  │  4. SCP input files → pod                           │   │
│  │  5. POST workflow to ComfyUI API (via tunnel)       │   │
│  │  6. WebSocket monitor (via tunnel)                   │   │
│  │  7. Download outputs (SCP or API)                    │   │
│  │  8. Stop/terminate pod                               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                    SSH Tunnel (port 8188)
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  RunPod Pod                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ComfyUI (headless) on port 8188                     │   │
│  │  - Receives files via SCP                            │   │
│  │  - Processes workflow locally                        │   │
│  │  - Exposes API + WebSocket + GUI                     │   │
│  │  - Network volume mounted (for models)               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Key Principles:**
- Controller runs entirely on Mac - Mac must stay connected during job
- No custom pod software required - vanilla ComfyUI image
- SSH tunnel provides full API + GUI access
- Files transferred via SCP (simple, reliable for V1)

### Job Format

Jobs are defined as JSON files with input/output specifications:

```json
{
  "job_id": "job-001",
  "workflow_template": "img2vid-basic",
  "inputs": {
    "image": "./inputs/frame001.png",
    "audio": "./inputs/voice.wav",
    "mask": "./inputs/mask.png"
  },
  "outputs": {
    "video": "./outputs/result-{job_id}.mp4"
  },
  "pod_config": {
    "gpu_type": "A40",
    "gpu_count": 2,
    "max_cost_usd": 5.00
  }
}
```

**V1 Implementation:**
- Input paths are **local** to Mac
- Controller uploads files to pod via SCP before starting workflow
- Output paths are **local** to Mac
- Controller downloads outputs from pod via SCP after completion

**V2+ with R2:**
```json
{
  "inputs": {
    "image": "r2://autopod-bucket/inputs/abc123.png",
    "audio": "r2://autopod-bucket/inputs/xyz789.wav"
  },
  "outputs": {
    "video": "r2://autopod-bucket/outputs/result-{job_id}.mp4"
  }
}
```

### Workflow Templates

ComfyUI workflows must be saved in **API format** (different from GUI format).

**Creating a template:**
1. Design workflow in ComfyUI GUI
2. Save → "Save (API Format)" → get JSON
3. Parameterize inputs (replace hardcoded paths with placeholders)
4. Save as template file (e.g., `templates/img2vid-basic.json`)

**Template placeholders:**
```json
{
  "3": {
    "inputs": {
      "image": "{input.image}",
      "audio": "{input.audio}"
    }
  }
}
```

Controller replaces `{input.image}` with actual pod path before submission.

### Interactive Controls (V1)

When running a job, the Rich UI provides keyboard controls:

```bash
autopod run --job ./jobs/render.json

→ Pod Created      pod-abc123 (2x A40, $1.20/hr)
→ SSH Tunnel       localhost:8188 → pod:8188
→ Files Uploaded   [████████] 3/3 files (234MB)
→ Job Submitted    prompt_id: xyz-789
→ Rendering        [████░░░░] 45% (frame 120/240)

Cost: $0.15 | Runtime: 7m 32s | Est. Complete: 9m

Keyboard Commands:
  [o] Open ComfyUI GUI in browser (http://localhost:8188)
  [k] Kill pod immediately (terminate)
  [s] Stop pod (pause, $0.12/hr stopped)
  [l] Show logs (SSH tail -f)
  [q] Quit controller (leave pod running)
  [Ctrl+C] Safe shutdown (stop pod after current job)
```

**Implementation details:**
- `o` → `webbrowser.open("http://localhost:8188")` - full ComfyUI GUI access
- `k` → RunPod API terminate (immediate, no data loss if outputs already saved)
- `s` → RunPod API stop (pauses pod, 10x cheaper than running)
- `l` → SSH exec `docker logs -f <container>` or `tail -f /var/log/comfyui.log`
- `Ctrl+C` → Signal handler that waits for current frame, downloads outputs, stops pod

**Why GUI access matters:**
- API workflows can be finicky to debug
- Quick mask fixes, parameter tweaks
- Visual confirmation that workflow is correct
- Fallback when automation fails

### Cost Safety Features

**1. Stuck Job Detection:**
- Monitor WebSocket for progress updates
- If no update for N minutes (configurable, default 5) → prompt user:
  ```
  ⚠️  WARNING: No progress for 5 minutes
  Cost: $0.85 | Estimated waste: $12.00/hr

  [k] Kill pod now  [w] Wait 5 more minutes  [o] Open GUI to debug
  ```

**2. Cost Limits:**
- `pod_config.max_cost_usd` in job JSON
- Controller tracks elapsed cost
- When approaching limit (90%) → warning
- When exceeded → automatic stop

**3. Runtime Estimates:**
- Track frame/second for video renders
- Estimate completion time
- Show projected total cost

**4. Confirmation Prompts:**
- Before starting expensive pods (>$1/hr) → confirm
- Before killing pod with unsaved outputs → confirm

---

## Version 2: Multi-Pod Architecture

When scaling to parallel jobs (one pod per job), architecture changes significantly.

### Multi-Pod SSH Tunneling

**Port mapping strategy:**
```python
pods = [
  {"id": "pod-abc", "local_port": 8188, "remote_port": 8188},
  {"id": "pod-def", "local_port": 8189, "remote_port": 8188},
  {"id": "pod-ghi", "local_port": 8190, "remote_port": 8188},
]
```

Each pod's ComfyUI runs on port 8188 internally, but tunnels to unique local port.

**Python implementation:**
```python
import subprocess

def create_tunnel(pod_ssh_host, local_port, remote_port=8188):
    cmd = [
        "ssh", "-N", "-L",
        f"{local_port}:localhost:{remote_port}",
        pod_ssh_host
    ]
    proc = subprocess.Popen(cmd)
    return proc  # Keep process alive
```

Controller manages multiple `Popen` processes - one per pod.

### Multi-Pod UI (Textualize TUI)

At this scale, Rich is insufficient - need Textualize:

```
┌─ autopod - 3 pods running ──────────────────────────────────┐
│ Total Cost: $3.60/hr | Runtime: 14m 22s | Est: $0.86        │
├──────────────────────────────────────────────────────────────┤
│ Pod ID      │ Job       │ Status   │ GPU      │ Port │ Cost │
├─────────────┼───────────┼──────────┼──────────┼──────┼──────┤
│ pod-abc ✓   │ job-001   │ 67% ⟳    │ 38GB/48G │ 8188 │ $0.34│
│ pod-def ✓   │ job-002   │ 23% ⟳    │ 41GB/48G │ 8189 │ $0.21│
│ pod-ghi ✗   │ job-003   │ Failed   │ --       │ 8190 │ $0.12│
└─────────────┴───────────┴──────────┴──────────┴──────┴──────┘

Selected: pod-abc
  Rendering frame 182/240 (1.2 fps)
  Started: 14m 22s ago | Est. complete: 6m 18s
  Output: result-job-001.mp4(estimated 125MB)

[↑↓] Select  [o] Open GUI  [k] Kill  [l] Logs  [Enter] Details
```

**Features:**
- Table view of all pods
- Arrow keys to select pod
- Per-pod detail view
- Aggregate cost tracking
- Interactive controls for selected pod

### Monitoring & Logging Strategy

**Data sources for monitoring:**

**1. RunPod API (Pod-level metrics):**
- Pod status (running, stopped, terminated)
- GPU type, count
- Cost per hour
- Uptime
- Basic health

**2. SSH Exec Commands (GPU/System metrics):**
```bash
# GPU usage via SSH
ssh pod-abc "nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader"
# Output: 98%, 89%, 38912MB, 49140MB

# Container logs
ssh pod-abc "docker logs --tail 50 <container_id>"

# System resources
ssh pod-abc "top -bn1 | head -20"
```

**3. ComfyUI API (Job-level metrics):**
```python
# Via tunnel
response = requests.get(f"http://localhost:{port}/history")
# Returns: job progress, current node, outputs

# WebSocket for real-time updates
ws = websocket.WebSocketApp(f"ws://localhost:{port}/ws")
# Streams: progress updates, errors, completion
```

**4. Log aggregation:**
- Each pod streams logs via SSH
- Controller aggregates and displays
- Option to tail specific pod's logs
- Error detection (pattern matching for common failures)

**Monitoring implementation:**
```python
class PodMonitor:
    def __init__(self, pod_id, ssh_host, local_port):
        self.pod_id = pod_id
        self.ssh_host = ssh_host
        self.local_port = local_port

    def get_gpu_stats(self):
        """SSH exec nvidia-smi"""
        cmd = f"ssh {self.ssh_host} nvidia-smi ..."
        return parse_output(cmd)

    def get_job_progress(self):
        """Query ComfyUI API via tunnel"""
        return requests.get(f"http://localhost:{self.local_port}/history")

    def tail_logs(self, lines=50):
        """Stream logs via SSH"""
        cmd = f"ssh {self.ssh_host} docker logs -f ..."
        return subprocess.Popen(cmd, stdout=subprocess.PIPE)
```

### File Handling (V2+ with Cloudflare R2)

**Multi-tier storage architecture:**

```
Mac                  Cloudflare R2              RunPod Pods
───                  ─────────────              ───────────

Upload files ─────>  inputs/
                     jobs/job-001.json
                           │
                           │
                           ├──────────────────> Pod downloads inputs
                           │                    Processes locally
                           │                    Writes to network volume
                           │
                     <────────────────────────  Uploads to R2
                     outputs/result-001.mp4

                                                RunPod Network Volume
                                                ────────────────────
                                                30-day backup buffer
                                                Syncs to R2
                                                Auto-deletes after R2 confirm
```

**Storage strategy:**
1. **Inputs:** Always in R2 before job starts
2. **Processing:** Local pod storage (fast)
3. **Outputs (critical path):**
   - Write to pod local storage (fast)
   - Upload to Network Volume (fast, local network)
   - Upload to R2 (slower, but permanent)
   - Only terminate pod after both succeed
4. **Cleanup:** Network Volume deletes files >30 days old if confirmed in R2

**Why multi-tier:**
- Network Volume = speed + first-line backup (pod crash protection)
- R2 = permanent + accessible anywhere
- 30-day buffer handles temporary R2 upload failures

### When to Use Each Version

**Use V1 when:**
- Testing/prototyping workflows
- Running 1-5 jobs sequentially
- Mac connection is reliable
- Manual oversight is acceptable

**Upgrade to V2 when:**
- Running >3 jobs in parallel regularly
- Time is more valuable than manual monitoring
- Need unattended operation

**Upgrade to V3 when:**
- Running 24/7 production pipeline
- Mac disconnect is unacceptable
- Scaling to 10+ concurrent pods
- Need API integration with other services

---

## Development Workflow

This project follows a structured 3-step development process for implementing features:

1. **PRD Creation** - Define what to build and why
2. **Task List Generation** - Break down implementation into actionable steps
3. **Implementation** - Execute tasks systematically with progress tracking

---

## Step 1: Product Requirements Document (PRD)

### Goal
Create a detailed PRD in Markdown format based on feature requests. The PRD should be clear, actionable, and suitable for a junior developer to understand and implement.

### Process

1. **Receive Initial Prompt:** User provides a brief description of a new feature or functionality
2. **Ask Clarifying Questions:** AI asks only 3-5 critical questions needed for a clear PRD
3. **Generate PRD:** Create comprehensive PRD using the structure below
4. **Save PRD:** Save as `prd-[feature-name].md` in `/tasks/` directory

### Clarifying Questions Guidelines

Ask only the most critical questions needed to write a clear PRD. Focus on areas where the initial prompt is ambiguous or missing essential context.

**Common areas needing clarification:**
- **Problem/Goal:** "What problem does this feature solve for the user?"
- **Core Functionality:** "What are the key actions a user should be able to perform?"
- **Scope/Boundaries:** "Are there any specific things this feature should NOT do?"
- **Success Criteria:** "How will we know when this feature is successfully implemented?"

**Important:** Only ask questions when the answer isn't reasonably inferable from the initial prompt. Prioritize questions that would significantly impact the PRD's clarity.

### Formatting Requirements for Questions

- Number all questions (1, 2, 3, etc.)
- List options for each question as A, B, C, D, etc. for easy reference
- Make it simple for the user to respond with selections like "1A, 2C, 3B"

**Example Format:**
```
1. What is the primary goal of this feature?
   A. Improve user onboarding experience
   B. Increase user retention
   C. Reduce support burden
   D. Generate additional revenue

2. Who is the target user for this feature?
   A. New users only
   B. Existing users only
   C. All users
   D. Admin users only

3. What is the expected timeline for this feature?
   A. Urgent (1-2 weeks)
   B. High priority (3-4 weeks)
   C. Standard (1-2 months)
   D. Future consideration (3+ months)
```

### PRD Structure

The generated PRD must include these sections:

1. **Introduction/Overview**
   - Briefly describe the feature and the problem it solves
   - State the goal

2. **Goals**
   - List specific, measurable objectives for this feature

3. **User Stories**
   - Detail user narratives describing feature usage and benefits

4. **Functional Requirements**
   - List specific functionalities the feature must have
   - Use clear, concise language (e.g., "The system must allow users to upload a profile picture")
   - Number all requirements

5. **Non-Goals (Out of Scope)**
   - Clearly state what this feature will NOT include to manage scope

6. **Design Considerations (Optional)**
   - Link to mockups, describe UI/UX requirements
   - Mention relevant components/styles if applicable

7. **Technical Considerations (Optional)**
   - Mention known technical constraints, dependencies, or suggestions
   - Example: "Should integrate with the existing Auth module"

8. **Success Metrics**
   - How will the success of this feature be measured?
   - Example: "Increase user engagement by 10%", "Reduce support tickets related to X"

9. **Open Questions**
   - List any remaining questions or areas needing further clarification

### Target Audience
Assume the primary reader is a **junior developer**. Requirements should be explicit, unambiguous, and avoid jargon where possible. Provide enough detail for them to understand the feature's purpose and core logic.

### Output Specifications
- **Format:** Markdown (.md)
- **Location:** `/tasks/`
- **Filename:** `prd-[feature-name].md`

### Final Instructions for Step 1
- **DO NOT** start implementing the PRD
- Make sure to ask the user clarifying questions
- Take the user's answers to the clarifying questions and improve the PRD

---

## Step 2: Task List Generation

### Goal
Create a detailed, step-by-step task list in Markdown format based on the PRD. The task list should guide a developer through implementation systematically.

### Process

1. **Receive Requirements:** Reference the PRD or feature request
2. **Analyze Requirements:** Analyze functional requirements, user needs, and implementation scope
3. **Phase 1 - Generate Parent Tasks:**
   - Create the file and generate main, high-level tasks
   - **IMPORTANT:** Always include task `0.0 "Create feature branch"` as the first task (unless user specifically requests otherwise)
   - Use judgment on how many additional high-level tasks (likely ~5)
   - Present tasks to user WITHOUT sub-tasks yet
   - Inform user: "I have generated the high-level tasks based on your requirements. Ready to generate the sub-tasks? Respond with 'Go' to proceed."
4. **Wait for Confirmation:** Pause and wait for user to respond with "Go"
5. **Phase 2 - Generate Sub-Tasks:**
   - Break down each parent task into smaller, actionable sub-tasks
   - Ensure sub-tasks logically follow from parent task
   - Cover implementation details implied by requirements
6. **Identify Relevant Files:**
   - List potential files to be created or modified
   - Include corresponding test files
7. **Generate Final Output:** Combine into final Markdown structure
8. **Save Task List:** Save in `/tasks/` directory as `tasks-[feature-name].md`

### Output Format

```markdown
## Relevant Files

- `path/to/potential/file1.ts` - Brief description of why this file is relevant (e.g., Contains the main component for this feature).
- `path/to/file1.test.ts` - Unit tests for `file1.ts`.
- `path/to/another/file.tsx` - Brief description (e.g., API route handler for data submission).
- `path/to/another/file.test.tsx` - Unit tests for `another/file.tsx`.
- `lib/utils/helpers.ts` - Brief description (e.g., Utility functions needed for calculations).
- `lib/utils/helpers.test.ts` - Unit tests for `helpers.ts`.

### Notes

- Unit tests should typically be placed alongside the code files they are testing (e.g., `MyComponent.tsx` and `MyComponent.test.tsx` in the same directory).
- Use `npx jest [optional/path/to/test/file]` to run tests. Running without a path executes all tests found by the Jest configuration.

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

Example:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

## Tasks

- [ ] 0.0 Create feature branch
  - [ ] 0.1 Create and checkout a new branch for this feature (e.g., `git checkout -b feature/[feature-name]`)
- [ ] 1.0 Parent Task Title
  - [ ] 1.1 [Sub-task description 1.1]
  - [ ] 1.2 [Sub-task description 1.2]
- [ ] 2.0 Parent Task Title
  - [ ] 2.1 [Sub-task description 2.1]
- [ ] 3.0 Parent Task Title (may not require sub-tasks if purely structural or configuration)
```

### Interaction Model
The process explicitly requires a pause after generating parent tasks to get user confirmation ("Go") before proceeding to generate detailed sub-tasks. This ensures the high-level plan aligns with user expectations before diving into details.

### Target Audience
Assume the primary reader is a **junior developer** who will implement the feature.

### Output Specifications
- **Format:** Markdown (.md)
- **Location:** `/tasks/`
- **Filename:** `tasks-[feature-name].md`

---

## Step 3: Implementation

### Process

1. **Work through tasks sequentially** - Follow the task list from top to bottom
2. **Check off completed tasks** - Update the markdown file after each sub-task:
   - Change `- [ ]` to `- [x]`
   - Update after each sub-task, not just parent tasks
3. **Review and iterate** - User reviews generated code and suggests improvements
4. **Break down complex tasks** - Use sub-tasks to make implementation digestible

### Guidelines

- Focus on one task at a time
- Maintain progress tracking in the task list file
- Ask questions if requirements are unclear
- Test as you go (when applicable)
- Keep commits atomic and well-described

---

## Project Structure

```
autopod/
├── CLAUDE.md              # This file - development workflow guide
├── README.md              # Project README
├── tasks/                 # PRDs and task lists for features
│   ├── prd-*.md          # Product requirement documents
│   └── tasks-*.md        # Task lists for implementation
├── src/                   # Source code (TBD)
│   ├── autopod/          # Main package
│   │   ├── cli.py        # CLI interface (Rich-based)
│   │   ├── providers/    # Provider abstraction layer
│   │   │   ├── base.py   # Abstract Provider interface
│   │   │   ├── runpod.py # RunPod implementation
│   │   │   └── vastai.py # Vast.ai implementation (future)
│   │   ├── comfyui.py    # ComfyUI API client
│   │   ├── ssh.py        # SSH tunnel management
│   │   ├── monitor.py    # Job monitoring (WebSocket)
│   │   ├── templates.py  # Workflow template handling
│   │   ├── config.py     # Config management
│   │   └── logging.py    # Logging setup
│   └── tests/            # Test files
├── templates/             # ComfyUI workflow templates (API format)
│   ├── img2vid-basic.json
│   └── img2vid-lipsync.json
├── jobs/                  # Local job queue (V1)
│   └── *.json            # Job specifications
├── inputs/                # Local input files (V1)
└── outputs/               # Local output files (V1)
```

---

## Provider Abstraction Architecture

### Design Principle

autopod is designed to support multiple GPU cloud providers (RunPod, Vast.ai, etc.) without requiring significant refactoring. The provider abstraction layer ensures clean separation of concerns.

### Provider Interface

All providers must implement a common interface defined in `src/autopod/providers/base.py`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional

class CloudProvider(ABC):
    """Abstract base class for GPU cloud providers"""

    @abstractmethod
    def authenticate(self, api_key: str) -> bool:
        """Validate API credentials"""
        pass

    @abstractmethod
    def get_gpu_availability(self, gpu_type: str) -> Dict:
        """Check if specific GPU type is available, return details"""
        pass

    @abstractmethod
    def create_pod(self, config: Dict) -> str:
        """Create pod, return pod_id"""
        pass

    @abstractmethod
    def get_pod_status(self, pod_id: str) -> Dict:
        """Get pod status and connection details"""
        pass

    @abstractmethod
    def stop_pod(self, pod_id: str) -> bool:
        """Stop (pause) pod"""
        pass

    @abstractmethod
    def terminate_pod(self, pod_id: str) -> bool:
        """Terminate (destroy) pod"""
        pass

    @abstractmethod
    def get_ssh_connection_string(self, pod_id: str) -> str:
        """Get SSH connection string for pod"""
        pass
```

### V1 GPU Selection: Sane Defaults

**Keep it simple for V1:**

**Default behavior:**
```bash
autopod connect
→ Using default: RTX A40 (1 GPU, Secure Cloud, North America)
→ Checking availability...
→ ✓ RTX A40 available, creating pod...
```

**Fallback logic:**
```python
preferred_gpus = ["RTX A40", "RTX A6000", "RTX A5000"]  # Try in order

for gpu_type in preferred_gpus:
    if provider.get_gpu_availability(gpu_type)['available']:
        create_pod(gpu_type)
        break
```

**Override with flags:**
```bash
autopod connect --gpu "RTX 4090" --gpu-count 2
```

**No complex UI for V1** - just smart defaults that work 95% of the time.

### V2: Expand Selection Options

Later, add:
- Interactive GPU browser (all options)
- Filters (region, network, CUDA)
- Save custom defaults

### Provider-Specific Configuration

```json
{
  "providers": {
    "runpod": {
      "api_key": "...",
      "ssh_key_path": "~/.ssh/id_rsa",
      "default_template": "runpod/comfyui:latest",
      "default_region": "NA-US",
      "cloud_type": "secure"
    }
  },
  "defaults": {
    "gpu_preferences": ["RTX A40", "RTX A6000", "RTX A5000"],
    "gpu_count": 1
  }
}
```

### Adding a New Provider

To add a new provider (e.g., Vast.ai):

1. Create `src/autopod/providers/vastai.py`
2. Implement `CloudProvider` interface
3. Add provider to config
4. No changes needed to CLI or core logic

---

## Testing Philosophy

### V1 Testing Strategy

**Goals:**
- Get feedback quickly during development
- Avoid over-engineering test infrastructure
- Test real APIs sparingly (costs money)
- Validate cost-critical operations

**Approach:**

**1. Manual Testing Scripts**
```python
# tests/manual/test_pod_creation.py
"""Manual test for pod creation - Run when ready to test with real API"""
from autopod.providers.runpod import RunPodProvider
from rich.console import Console

console = Console()

def test_pod_creation():
    console.print("[yellow]Testing pod creation...[/yellow]")

    provider = RunPodProvider(api_key="...")

    console.print("Checking A40 availability...")
    gpu_info = provider.get_gpu_availability("RTX A40")
    console.print(f"Available: {gpu_info['available']}")

    if input("Create pod? [y/N]: ").lower() == 'y':
        pod_id = provider.create_pod({"gpu_type": "RTX A40", "gpu_count": 1})
        console.print(f"[green]✓ Pod created: {pod_id}[/green]")
```

**2. Rich Console Output for Immediate Feedback**

Every function shows what it's doing:
```python
from rich.console import Console
console = Console()

def check_gpu_availability(gpu_type):
    console.print(f"[cyan]Checking {gpu_type} availability...[/cyan]")

    result = api.get_gpu(gpu_type)

    if result['available']:
        console.print(f"[green]✓ {gpu_type} available ({result['count']} units)[/green]")
    else:
        console.print(f"[yellow]✗ {gpu_type} not available[/yellow]")

    return result
```

**3. Dry-Run Mode for Safety**
```bash
autopod connect --dry-run  # Shows plan, doesn't create pod
```

```python
def create_pod(config, dry_run=False):
    if dry_run:
        console.print("[yellow]DRY RUN - Would create:[/yellow]")
        console.print(f"  GPU: {config['gpu_type']}")
        console.print(f"  Count: {config['gpu_count']}")
        console.print(f"  Cost: ${config['cost_per_hour']}/hr")
        return "dry-run-pod-id"

    # Actually create pod
    return api.create_pod(config)
```

**4. Unit Tests for Pure Logic**

Use pytest for non-API code:
```python
# tests/test_config.py
def test_load_config():
    config = load_config("test_config.json")
    assert config['defaults']['gpu_preferences'][0] == "RTX A40"

# tests/test_pod_naming.py
def test_pod_name_generation():
    name = generate_pod_name()
    assert name.startswith("autopod-2025-")
```

**5. Mock APIs for Integration Tests**
```python
from unittest.mock import Mock, patch

def test_pod_creation_with_fallback():
    provider = RunPodProvider(api_key="test")

    # Mock API responses
    with patch.object(provider, 'get_gpu_availability') as mock_gpu:
        mock_gpu.side_effect = [
            {'available': False},  # A40 not available
            {'available': True}     # A6000 available
        ]

        result = provider.create_pod_with_fallback()
        assert result['gpu_type'] == "RTX A6000"
```

### Feedback During Development

**As features are implemented:**

1. **Verbose output shows everything:**
```python
console.print("[dim]DEBUG: API response:[/dim]")
console.print(response)  # Temporary, remove before commit
```

2. **Test each function immediately:**
```bash
# After implementing get_gpu_availability()
python -c "from autopod.providers.runpod import RunPodProvider; \
           p = RunPodProvider('key'); \
           print(p.get_gpu_availability('RTX A40'))"
```

3. **User reviews output and gives feedback:**
   - "Cost calculation is wrong" → AI fixes
   - "SSH connection fails" → AI debugs with logs

4. **Incremental commits:**
   - Implement one function → test → commit
   - Don't wait for whole feature to commit

### Logging for Production

**All operations log to `~/.autopod/logs/autopod.log`:**

```python
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)

def create_pod(config):
    logger.info(f"Creating pod: gpu={config['gpu_type']}, count={config['gpu_count']}")

    try:
        response = api.create_pod(config)
        logger.info(f"Pod created successfully: {response['pod_id']}")
        logger.debug(f"Full API response: {response}")
        return response

    except Exception as e:
        logger.exception("Pod creation failed", exc_info=True)
        raise
```

**Log levels:**
- `DEBUG`: API requests/responses, internal state
- `INFO`: User actions, pod lifecycle events
- `WARNING`: Retries, using fallback GPU
- `ERROR`: Failures (with full traceback)
- `CRITICAL`: Unrecoverable errors

**Testing checklist:**
- [ ] Function has Rich console output showing progress
- [ ] Function logs at appropriate level
- [ ] Errors include full traceback in logs
- [ ] `--dry-run` mode works (if applicable)
- [ ] Manual test script exists for API interactions

---

## Development Guidelines

### Code Quality
- Write clear, maintainable code suitable for junior developers to understand
- Add comments for complex logic
- Follow Python best practices (PEP 8)

### Testing
- Write tests alongside implementation
- Test files should live alongside source files
- Run tests frequently during development

### Documentation
- **README.md must be updated frequently** when new features are added
- Include **working examples** for every CLI flag and feature
- Show real command examples with expected output
- Document all keyboard controls and interactive features
- Keep usage examples up-to-date as features evolve
- Make it easy for users to copy-paste and run commands

### Version Control
- Always create feature branches (unless specifically instructed otherwise)
- Use descriptive commit messages
- Keep commits focused and atomic

### Cost Consciousness
Remember: The primary goal of autopod is to **save money on compute costs**. Any feature should be evaluated against this principle.

---

## Working with AI Assistants

### Effective Prompting
- Be specific about what phase you're in (PRD, Task List, or Implementation)
- Reference task numbers when discussing implementation
- Provide context about decisions made in earlier phases

### Workflow Commands
- **"Let's create a PRD for [feature]"** - Initiates Step 1
- **"Go"** - Confirms parent tasks and triggers sub-task generation in Step 2
- **"Let's implement task X.X"** - Focuses on specific task implementation

### Asking for Help
- Reference specific requirements from PRD
- Point to task numbers in task list
- Ask about tradeoffs and alternatives
- Request code reviews and improvements

---

## Notes

- This workflow is designed to break complex projects into manageable pieces
- Each step builds on the previous one, ensuring clarity before implementation
- The process is iterative - it's okay to revise PRDs and task lists as understanding evolves
- Keep the focus on lightweight, essential features that serve the core mission

---

## Quick Reference

### V1 Command Examples

```bash
# Run a single job
autopod run --job ./jobs/render-001.json

# Run multiple jobs sequentially
autopod run --jobs ./jobs/*.json

# Run with cost limit
autopod run --job ./jobs/render.json --max-cost 2.50

# Dry run (show what would happen without executing)
autopod run --job ./jobs/render.json --dry-run

# JSON output mode (for scripting)
autopod run --job ./jobs/render.json --json > result.json
```

### Keyboard Controls (V1)

| Key | Action |
|-----|--------|
| `o` | Open ComfyUI GUI in browser |
| `k` | Kill pod immediately (terminate) |
| `s` | Stop pod (pause, cheaper) |
| `l` | Show logs (tail -f) |
| `q` | Quit controller (leave pod running) |
| `Ctrl+C` | Safe shutdown (stop pod gracefully) |

### Job JSON Schema

```json
{
  "job_id": "unique-id",
  "workflow_template": "template-name",
  "inputs": {
    "param_name": "local/path/or/r2://uri"
  },
  "outputs": {
    "output_name": "destination/path"
  },
  "pod_config": {
    "gpu_type": "A40|A6000|A5000|RTX4090|RTX3090",
    "gpu_count": 1,
    "max_cost_usd": 5.00,
    "timeout_minutes": 60
  }
}
```

### Common RunPod GPU Types (for reference)

| GPU Type | VRAM | Cost/hr | Best For |
|----------|------|---------|----------|
| RTX A5000 | 24GB | $0.27 | Budget-friendly, small-medium models |
| RTX A40 | 48GB | $0.40 | Best value for large models |
| RTX 3090 | 24GB | $0.46 | Good performance, medium models |
| RTX A6000 | 48GB | $0.49 | High-end production |
| RTX 4090 | 24GB | $0.59 | Fastest for medium models |

**Note:** Costs are approximate and vary by availability. Always check RunPod pricing.

### Development Workflow Cheat Sheet

1. **Create PRD:** `"Let's create a PRD for [feature]"`
2. **Generate tasks:** AI creates high-level tasks → User reviews
3. **Expand tasks:** User says `"Go"` → AI generates sub-tasks
4. **Implement:** Work through tasks, checking off as you go
5. **Test & iterate:** Review, improve, repeat

### Key File Locations

- **Job specs:** `./jobs/*.json`
- **Workflow templates:** `./templates/*.json` (API format)
- **Input files (V1):** `./inputs/`
- **Output files (V1):** `./outputs/`
- **PRDs:** `./tasks/prd-*.md`
- **Task lists:** `./tasks/tasks-*.md`

---

**Last Updated:** 2025-11-08
