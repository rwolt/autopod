# PRD #3: V1.3 - ComfyUI Workflow Execution

## Introduction / Overview

This PRD defines V1.3 of autopod, which adds the ability to execute ComfyUI workflows on RunPod instances by processing job files from a local jobs folder. This completes the core automation loop: create pod → upload inputs → run workflow → download outputs → terminate pod.

**Problem it solves**: Users want to automate ComfyUI workflows (image generation, video processing, etc.) on RunPod without manual intervention. Currently, V1.2 only provides API client methods and SSH tunnel management, but no end-to-end job execution capability.

**Goal**: Enable users to define jobs in JSON files, place them in a `jobs/` folder, and execute them with a single command: `autopod comfy run --job-file jobs/my-job.json`. All communication happens over SSH tunnel (localhost:8188), NOT via public HTTP proxy.

## Goals

1. **Job-based workflow execution**: Define workflows as JSON job files with inputs, outputs, and workflow templates
2. **File upload/download**: Transfer input files to ComfyUI and retrieve generated outputs via HTTP API (over SSH tunnel)
3. **Workflow template system**: Parameterized ComfyUI workflow templates (API format) with placeholder substitution
4. **End-to-end automation**: Single command executes: upload → submit → monitor → download
5. **SSH-only communication**: All HTTP requests go through SSH tunnel (localhost:8188), NO public URLs
6. **Progress monitoring**: Real-time feedback during workflow execution with Rich console output
7. **Error handling**: Detect and report failures at each step (upload, submission, execution, download)

## User Stories

### Story 1: Run a simple text-to-image workflow
**As a** ComfyUI user
**I want to** run a text-to-image workflow on a RunPod pod
**So that** I can generate images without manually using the GUI

**Acceptance criteria**:
- User creates a job JSON file with workflow template and parameters
- User runs `autopod comfy run --job-file jobs/txt2img.json`
- autopod automatically creates SSH tunnel if needed
- autopod uploads any input files to ComfyUI
- autopod submits workflow and monitors execution
- autopod downloads generated images to local outputs/ directory
- User sees progress updates in terminal (Rich UI)

### Story 2: Process multiple jobs sequentially
**As a** power user
**I want to** queue multiple jobs in the jobs/ folder
**So that** I can batch process workflows overnight

**Acceptance criteria**:
- User creates multiple job JSON files in jobs/ directory
- User runs `autopod comfy run --jobs jobs/*.json`
- autopod processes each job sequentially on the same pod
- autopod reports progress for each job
- If one job fails, autopod continues with next job
- User can cancel with Ctrl+C and pod is safely stopped

### Story 3: Access ComfyUI GUI over SSH tunnel (not HTTP proxy)
**As a** developer
**I want to** access ComfyUI GUI via localhost:8188
**So that** I can debug workflows without exposing them publicly

**Acceptance criteria**:
- User creates pod WITHOUT --expose-http flag
- User runs `autopod comfy run` (which auto-creates SSH tunnel)
- User can open browser to http://localhost:8188 and see ComfyUI GUI
- All API requests go through SSH tunnel (verified in logs)
- NO HTTP proxy URLs are generated or used

### Story 4: Download workflow outputs automatically
**As a** user
**I want to** automatically download generated files after workflow completes
**So that** I don't have to manually fetch outputs

**Acceptance criteria**:
- Workflow generates output files (images, videos, etc.)
- autopod detects output files from workflow history
- autopod downloads files to local outputs/ directory (or custom --output-dir)
- autopod reports downloaded file names and sizes
- Output files are verified (size > 0, correct format)

## Functional Requirements

### FR-1: Job JSON Format
The system must support job specification files in JSON format with the following structure:

```json
{
  "job_id": "unique-job-identifier",
  "workflow_template": "template-name",
  "inputs": {
    "param_name": "local/path/to/file.png"
  },
  "outputs": {
    "output_name": "outputs/result.png"
  },
  "pod_config": {
    "gpu_type": "RTX A40",
    "gpu_count": 1,
    "max_cost_usd": 5.00,
    "timeout_minutes": 60
  }
}
```

### FR-2: Workflow Template System
- Templates stored in `templates/` directory as ComfyUI API-format JSON
- Templates use placeholder syntax: `{input.param_name}` for input file paths
- System must substitute placeholders with actual values before submission
- Templates must be validated (valid JSON, contains required fields)

### FR-3: File Upload to ComfyUI
- Upload files via `POST /upload/image` endpoint (multipart/form-data)
- Support image files (PNG, JPG, etc.) and other input types
- Show upload progress for large files
- Handle upload errors (network failures, disk full, etc.)
- Verify upload succeeded (check response status)

### FR-4: Workflow Submission
- Submit workflows via `POST /prompt` endpoint
- Request format: `{"prompt": workflow_json, "client_id": uuid}`
- Parse response to extract `prompt_id`
- Handle submission errors (invalid workflow, missing nodes, etc.)

### FR-5: Execution Monitoring
- Poll `GET /history/{prompt_id}` to check execution status
- Detect completion (prompt appears in history with outputs)
- Detect failures (exceptions in history)
- Show progress updates in terminal (Rich progress bar)
- Support timeout (fail if execution exceeds max time)

### FR-6: Output File Download
- Retrieve output file names from workflow history
- Download files via `GET /view?filename=X&type=output`
- Save files to local outputs/ directory (or custom path)
- Verify download integrity (file size matches)
- Report downloaded files to user

### FR-7: `autopod comfy run` Command
- CLI command to execute job files
- Flags:
  - `--job-file PATH`: Single job file to execute
  - `--jobs PATTERN`: Multiple job files (glob pattern)
  - `--output-dir PATH`: Custom output directory (default: ./outputs/)
  - `--dry-run`: Show execution plan without running
  - `--no-tunnel`: Skip SSH tunnel auto-creation (use existing)
- Auto-create SSH tunnel if not exists
- Display Rich console output with progress

### FR-8: SSH Tunnel Enforcement
- ALL HTTP requests MUST go through SSH tunnel (localhost:8188)
- NO HTTP proxy URLs should be generated or used
- System must verify tunnel exists before making API requests
- If tunnel fails, system must report error (not fall back to HTTP proxy)

### FR-9: Error Handling
- Detect and report errors at each step:
  - Job file not found or invalid JSON
  - Workflow template not found
  - SSH tunnel creation failed
  - File upload failed
  - Workflow submission failed
  - Workflow execution failed (exception in history)
  - Output download failed
- Provide actionable error messages
- Log errors to ~/.autopod/logs/autopod.log

### FR-10: Progress Reporting
- Show Rich-formatted progress for each step:
  - Creating SSH tunnel
  - Uploading input files (with progress bar)
  - Submitting workflow
  - Executing workflow (with polling updates)
  - Downloading outputs (with progress bar)
- Display estimated time remaining where applicable
- Show cost tracking (runtime, cost per hour, total cost)

## Non-Goals (Out of Scope)

### V1.3 will NOT include:
- **WebSocket monitoring**: Real-time progress via WebSocket (deferred to V2.0)
- **Multiple pods**: Only single pod execution (multi-pod in V3.0)
- **Job queue management**: No persistent queue system (deferred to V2.0)
- **Cost safety features**: No budget limits or stuck detection (deferred to V2.0)
- **Interactive controls**: No keyboard shortcuts during execution (deferred to V2.0)
- **Cloudflare R2 storage**: Only local file storage (deferred to V4.0+)
- **Custom workflow validation**: Only basic JSON validation (advanced validation in V2.0+)
- **Workflow retry logic**: No automatic retries on failure (manual re-run only)

## Design Considerations

### File Upload Method
**Decision**: Use ComfyUI HTTP API (`POST /upload/image`) over SSH tunnel

**Rationale**:
- SSH tunnel already established for API access
- Same tunnel works for both HTTP and file uploads
- No need for separate SCP connection
- Simpler error handling (single protocol)
- Multipart/form-data is standard HTTP

**Trade-offs**:
- Slightly slower than direct SCP for large files
- But acceptable for V1.3 scope (typical inputs: <100MB)

### Workflow Template Format
**Decision**: Use ComfyUI API format (not GUI format)

**Rationale**:
- API format is what ComfyUI expects for `POST /prompt`
- GUI format must be converted (adds complexity)
- Users can export API format directly from ComfyUI GUI

**How to create templates**:
1. Design workflow in ComfyUI GUI
2. Save → "Save (API Format)" → get JSON
3. Replace hardcoded paths with placeholders: `{input.image}`
4. Save as template file

### Progress Monitoring Strategy
**Decision**: Poll `GET /history` every 2 seconds (V1.3), upgrade to WebSocket in V2.0

**Rationale**:
- Simpler implementation (no WebSocket library needed yet)
- Good enough for single job execution
- WebSocket adds complexity (connection management, reconnection logic)
- Can upgrade to WebSocket later without breaking changes

**Trade-offs**:
- Polling is less efficient (2-second delay between updates)
- But acceptable for V1.3 (workflows typically take minutes)

## Technical Considerations

### Dependencies
- `requests` library (already required for ComfyUI API client)
- No new dependencies needed for V1.3

### File Locations
```
autopod/
├── jobs/                  # Job specification files
│   └── *.json
├── templates/             # ComfyUI workflow templates (API format)
│   └── *.json
├── inputs/                # Local input files (referenced by jobs)
│   └── *.png, *.jpg, etc.
└── outputs/               # Downloaded output files
    └── *.png, *.mp4, etc.
```

### ComfyUI API Endpoints Used
- `POST /upload/image` - Upload input files (multipart/form-data)
- `POST /prompt` - Submit workflow for execution
- `GET /history` - Check execution status and retrieve outputs
- `GET /history/{prompt_id}` - Get specific prompt details
- `GET /view?filename=X&type=output` - Download output files

### Code Organization
- `src/autopod/comfyui.py` - Extend with upload/download/submit methods
- `src/autopod/cli.py` - Add `autopod comfy run` command
- `src/autopod/workflow.py` - NEW module for template handling
- `tests/manual/test_v1.3_workflow_execution.py` - End-to-end test

## Success Metrics

### Must-Have for V1.3 Release:
1. **Core workflow**: User can run `autopod comfy run --job-file jobs/test.json` and get outputs
2. **SSH-only**: All API requests verified to go through localhost:8188 (no HTTP proxy)
3. **File handling**: Upload and download work for images (PNG/JPG)
4. **Error detection**: Failed workflows report clear error messages
5. **Progress visibility**: User sees Rich progress updates during execution

### Test Coverage:
- Integration test: End-to-end workflow execution (create pod → upload → submit → download → terminate)
- Integration test: Verify SSH tunnel used (NOT HTTP proxy)
- Integration test: Error handling for failed workflows
- Integration test: Multiple file upload/download

## Open Questions

*None at this time - PRD is complete and ready for task list generation.*

## Example Usage

```bash
# Create a job file
cat > jobs/txt2img.json <<EOF
{
  "job_id": "test-001",
  "workflow_template": "simple-txt2img",
  "inputs": {
    "prompt": "a beautiful sunset over mountains"
  },
  "outputs": {
    "image": "outputs/sunset-001.png"
  }
}
EOF

# Run the job
autopod comfy run --job-file jobs/txt2img.json

# Expected output:
# → Creating SSH tunnel... ✓
# → Uploading inputs... ✓ (0 files)
# → Submitting workflow... ✓ (prompt_id: abc-123)
# → Executing workflow... [████████████] 100%
# → Downloading outputs... ✓ (1 file, 2.4 MB)
#   - outputs/sunset-001.png
#
# Job completed successfully!
# Runtime: 45s | Cost: $0.08
```

## Appendix: Job JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["job_id", "workflow_template"],
  "properties": {
    "job_id": {
      "type": "string",
      "description": "Unique identifier for this job"
    },
    "workflow_template": {
      "type": "string",
      "description": "Name of workflow template file (without .json extension)"
    },
    "inputs": {
      "type": "object",
      "description": "Input parameters and file paths",
      "additionalProperties": {
        "type": "string"
      }
    },
    "outputs": {
      "type": "object",
      "description": "Output file mappings",
      "additionalProperties": {
        "type": "string"
      }
    },
    "pod_config": {
      "type": "object",
      "description": "Pod configuration (optional - uses defaults if not specified)",
      "properties": {
        "gpu_type": {"type": "string"},
        "gpu_count": {"type": "integer"},
        "max_cost_usd": {"type": "number"},
        "timeout_minutes": {"type": "integer"}
      }
    }
  }
}
```
