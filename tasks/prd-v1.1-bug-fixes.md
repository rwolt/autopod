# PRD: V1.1 - Critical Bug Fixes & Production Readiness

## Introduction/Overview

V1.1 is a focused bug fix release to address critical issues discovered during V1 testing. This release makes no architectural changes and adds no new features - it simply makes the existing V1 commands work reliably and correctly.

**Problem Statement:**
V1 testing revealed several bugs that prevent production use:
1. `autopod ls` shows stale/terminated pods from local cache
2. Default pod configuration insufficient for real use (20GB disk too small, no datacenter option)
3. `autopod info` fails when auto-selecting from stale pods
4. Missing pod metadata shows as "Unknown" in table output

**Goal:**
Ship a stable, bug-free V1 that works exactly as documented in the V1 PRD.

---

## Goals

1. **Fix pod listing accuracy**: `autopod ls` only shows pods that exist in RunPod
2. **Fix default pod configuration**: Increase disk size and add datacenter control
3. **Improve error messages**: Clear, actionable errors when things go wrong
4. **No regressions**: All V1 features continue to work exactly as before

---

## User Stories

### US-1: Accurate Pod Listing
**As a** user who has terminated pods in the RunPod UI
**I want** `autopod ls` to show only pods that currently exist
**So that** I don't get confused by stale entries

**Acceptance Criteria:**
- Running `autopod ls` shows only pods that exist in RunPod API
- Terminated pods are automatically removed from `~/.autopod/pods.json`
- User sees message when stale pods are cleaned: `"Removed N stale pod(s) from cache"`
- Empty pod list shows: `"No pods found"` (not error or broken table)

### US-2: Sufficient Disk Space
**As a** user creating pods for ComfyUI or other workloads
**I want** pods to have enough disk space by default
**So that** I don't run out of space during installation

**Acceptance Criteria:**
- `autopod connect` creates pods with 50GB container disk (was 20GB)
- User can override with `--disk-size` flag
- Disk size shown in `autopod info` output

### US-3: Datacenter Control
**As a** user with a network volume in a specific datacenter
**I want** to specify which datacenter to use
**So that** my pods can access my network volumes

**Acceptance Criteria:**
- New flag: `autopod connect --datacenter CA-MTL-1`
- Config file supports `default_datacenter` setting
- Datacenter shown in `autopod info` output (if available from API)

### US-4: Better Error Messages
**As a** user when something goes wrong
**I want** clear error messages that tell me what to do
**So that** I can fix problems without reading source code

**Acceptance Criteria:**
- Pod not found: `"Pod abc-123 not found. It may have been terminated. Run 'autopod ls' to see available pods."`
- No pods for auto-select: `"No pods found. Create one with 'autopod connect'."`
- SSH not ready: `"SSH not yet available for pod abc-123. Container may still be starting. Wait 30s and try again."`
- API key invalid: `"RunPod API key is invalid. Check your config at ~/.autopod/config.json"`

---

## Functional Requirements

### FR-1: Pod Listing Auto-Cleanup

**Implementation:**
1. When `list_pods()` is called, iterate through cached pod IDs
2. For each pod ID, call `provider.get_pod_status(pod_id)`
3. If API raises `RuntimeError` with "not found":
   - Remove pod ID from cache
   - Add to `removed_pods` counter
4. After iteration, if `removed_pods > 0`:
   - Print: `[yellow]Removed {removed_pods} stale pod(s) from cache[/yellow]`
5. Display only successfully fetched pods in table

**Location**: `src/autopod/pod_manager.py:list_pods()`

### FR-2: Increase Default Disk Size

**Implementation:**
1. Change default in `cli.py:connect()`:
   - `--disk-size` default: `20` → `50`
2. Update help text: `"Disk size in GB (default: 50)"`

**Location**: `src/autopod/cli.py:166`

### FR-3: Add Datacenter Configuration

**Implementation:**
1. Add CLI flag to `autopod connect`:
   - `--datacenter` (type: str, help: "Datacenter region (e.g., CA-MTL-1, US-GA-1)")
2. Add to config schema:
   ```json
   {
     "providers": {
       "runpod": {
         "default_datacenter": "CA-MTL-1"
       }
     }
   }
   ```
3. Pass to `create_pod()` as `pod_config["datacenter"]` (if RunPod API supports it)
4. If API doesn't support datacenter selection, document as future enhancement

**Location**: `src/autopod/cli.py:connect()`, `src/autopod/config.py`

### FR-4: Enhanced Error Messages

**Implementation:**
Update error handling in:

1. **Pod not found** (`pod_manager.py:get_pod_info()`):
   ```python
   except RuntimeError as e:
       if "not found" in str(e):
           console.print(f"[red]✗ Pod {pod_id} not found[/red]")
           console.print("[dim]It may have been terminated. Run 'autopod ls' to see available pods.[/dim]")
   ```

2. **No pods for auto-select** (`cli.py:get_single_pod_id()`):
   ```python
   if len(pods) == 0:
       console.print("[yellow]No pods found[/yellow]")
       console.print("[dim]Create one with 'autopod connect'[/dim]")
   ```

3. **SSH not ready** (`providers/runpod.py:get_ssh_connection_string()`):
   ```python
   if not status.get("ssh_ready"):
       raise RuntimeError(
           f"SSH not yet available for pod {pod_id}. "
           "Container may still be starting. Wait 30s and try again."
       )
   ```

4. **Invalid API key** (`providers/runpod.py:authenticate()`):
   ```python
   if not valid:
       logger.warning("Authentication failed - invalid API key")
       console.print("[red]✗ RunPod API key is invalid[/red]")
       console.print(f"[dim]Check your config at {get_config_path()}[/dim]")
   ```

**Locations**: Multiple files as noted above

### FR-5: Display Missing Pod Metadata

**Implementation:**
When `get_pod_status()` returns incomplete data, show sensible defaults:
- GPU type unknown → "Unknown GPU"
- Cost unknown → "$0.00/hr"
- Runtime unknown → "0.0 min"

Ensure table formatting doesn't break with missing data.

**Location**: `src/autopod/pod_manager.py:_print_pods_table()`

---

## Non-Goals (Out of Scope for V1.1)

### Explicitly NOT in V1.1:
1. **Network volume attachment**: Deferred to V1.5
2. **Port exposure configuration**: Deferred to V1.5
3. **SSH tunneling**: Deferred to V1.5
4. **Integration tests**: Deferred to V1.5
5. **ComfyUI-specific features**: Deferred to V1.5
6. **New commands**: Only fixing existing commands
7. **Configuration wizard enhancements**: Config structure stays the same
8. **Manual cleanup command**: Auto-cleanup during `ls` is sufficient

---

## Technical Considerations

### Backward Compatibility
- All existing commands work exactly as before
- Config file format unchanged (only additions)
- `~/.autopod/pods.json` format unchanged
- CLI flags are additive only (no breaking changes)

### Edge Cases
1. **All cached pods are stale**: Show "No pods found" + cleanup message
2. **Network error during list**: Show cached data with warning
3. **Pod terminated mid-operation**: Graceful error, suggest `autopod ls`
4. **Datacenter not supported by API**: Document limitation, fail gracefully

### Testing Strategy
1. **Manual testing**: Create pod, terminate in UI, run `autopod ls`
2. **Config testing**: Test with/without datacenter setting
3. **Error testing**: Test all error message paths
4. **Regression testing**: Ensure all V1 commands still work

---

## Success Metrics

### V1.1 is successful when:
1. ✅ `autopod ls` never shows terminated pods
2. ✅ Default disk size (50GB) works for typical ComfyUI installations
3. ✅ Error messages are helpful and actionable
4. ✅ All V1 commands continue to work
5. ✅ No new bugs introduced

### Validation:
- Manual test: Terminate all pods in UI → `autopod ls` → should show "No pods found"
- Manual test: `autopod connect` → pod has 50GB disk
- Manual test: `autopod info <nonexistent-pod>` → helpful error message
- Manual test: All V1 commands from original PRD still work

---

## Open Questions

1. **Datacenter API Support**:
   - Q: Does RunPod API accept datacenter parameter in `create_pod()`?
   - A: Test during implementation. If not supported, document as limitation.
   - Impact: May need to document workaround or defer to V1.5

2. **Cleanup Timing**:
   - Q: Should cleanup happen on every `ls` or only periodically?
   - A: Every `ls` is fine - it's fast and keeps cache accurate
   - Impact: None

3. **Disk Size Limits**:
   - Q: What's the maximum disk size RunPod allows?
   - A: Test during implementation, document limits
   - Impact: May need validation/warning for large sizes

---

## Implementation Phases

### Phase 1: Core Bug Fixes (Priority 1)
- FR-1: Pod listing auto-cleanup
- FR-5: Handle missing metadata gracefully

### Phase 2: Configuration Improvements (Priority 2)
- FR-2: Increase default disk size
- FR-3: Add datacenter option

### Phase 3: UX Polish (Priority 3)
- FR-4: Enhanced error messages
- Documentation updates

### Phase 4: Validation
- Manual testing of all fixes
- README updates with new defaults

---

## Dependencies

### External:
- None (all dependencies already in V1)

### Internal:
- V1 Pod Lifecycle: All V1 functionality preserved

### Documentation:
- Update README with new disk size default
- Document datacenter option
- Update error message examples

---

## Appendix: Testing Checklist

### Manual Test Plan for V1.1:

```bash
# Test 1: Stale pod cleanup
1. Create pod with `autopod connect`
2. Note pod ID
3. Terminate pod in RunPod UI
4. Run `autopod ls`
5. ✓ Verify: Shows "Removed 1 stale pod(s)" message
6. ✓ Verify: Pod not in list

# Test 2: Default disk size
1. Run `autopod connect`
2. Check pod in RunPod UI
3. ✓ Verify: Container disk is 50GB

# Test 3: Datacenter option
1. Run `autopod connect --datacenter CA-MTL-1`
2. ✓ Verify: Pod created (or helpful error if not supported)

# Test 4: Error messages
1. Run `autopod info nonexistent-pod-id`
2. ✓ Verify: Helpful error message with suggestion

# Test 5: No pods case
1. Terminate all pods
2. Run `autopod ls`
3. ✓ Verify: Shows "No pods found" cleanly

# Test 6: Regression check
1. Run all V1 commands: connect, ls, info, ssh, stop, start, kill
2. ✓ Verify: All work as in V1
```

---

## Version History

- **v1.0** - 2025-11-10 - Initial PRD for V1.1 bug fixes
