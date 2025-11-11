# Task List: V1.1 - Critical Bug Fixes & Production Readiness

## Relevant Files

- `src/autopod/pod_manager.py` - Pod listing logic that needs stale pod cleanup
- `src/autopod/cli.py` - CLI commands that need default updates and error message improvements
- `src/autopod/providers/runpod.py` - Provider error handling and SSH readiness checks
- `src/autopod/providers/base.py` - Abstract provider interface (may need updates)
- `src/autopod/config.py` - Configuration schema for datacenter defaults
- `README.md` - Documentation updates for new defaults
- `tests/manual/test_v1.1_fixes.py` - Manual integration test script for validating fixes against real RunPod API

### Notes

- Changes are backward compatible - no breaking changes to config or API
- Focus on bug fixes only - no new features
- Each task includes manual testing verification against real RunPod API
- Integration tests create real pods, validate behavior, then clean up

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

Example:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

## Tasks

- [x] 0.0 Create feature branch
  - [x] 0.1 Create and checkout a new branch `git checkout -b bugfix/v1.1-fixes`
  - [x] 0.2 Verify current V1 tests still pass (if any exist)

- [x] 1.0 Fix pod listing to auto-clean stale pods
  - [x] 1.1 Read `src/autopod/pod_manager.py:list_pods()` to understand current implementation
  - [x] 1.2 Add stale pod detection logic: wrap `get_pod_status()` in try-except to catch "not found" errors
  - [x] 1.3 Implement removal tracking: create `stale_pods = []` list to track removed pod IDs
  - [x] 1.4 Add cleanup logic: when `RuntimeError` with "not found" caught, call `self._remove_pod_from_state(pod_id)` and add to `stale_pods` list
  - [x] 1.5 Add user notification: after iteration, if `len(stale_pods) > 0`, print `[yellow]Removed {len(stale_pods)} stale pod(s) from cache[/yellow]`
  - [x] 1.6 Handle edge case: if all pods are stale and list is empty, ensure "No pods found" message displays correctly
  - [x] 1.7 Add logging: log at INFO level when stale pods are removed with pod IDs
  - [x] 1.8 Test manually: Create pod with `autopod connect`, note pod ID, terminate in RunPod UI, run `autopod ls`, verify cleanup message and pod removed from list
  - [x] 1.9 Test edge case: Terminate all pods in UI, run `autopod ls`, verify shows "No pods found" with cleanup message
  - [x] 1.10 Verify `~/.autopod/pods.json` is updated correctly (stale pods removed from file)

- [x] 2.0 Update default pod configuration
  - [x] 2.1 Read `src/autopod/cli.py:connect()` to understand current configuration flow
  - [x] 2.2 Update disk size default: Change `--disk-size` default from `20` to `50` in CLI decorator
  - [x] 2.3 Update help text: Change help text to `"Disk size in GB (default: 50)"`
  - [x] 2.4 Add datacenter CLI flag: Add `--datacenter` option with type=str, help="Datacenter region (e.g., CA-MTL-1, US-GA-1)"
  - [x] 2.5 Read `src/autopod/config.py` to understand config schema
  - [x] 2.6 Add datacenter to config schema: Add `default_datacenter` field to runpod provider config with default value
  - [x] 2.7 Update `connect()` logic: Read datacenter from CLI flag (priority) or config file (fallback)
  - [x] 2.8 Pass datacenter to provider: Add datacenter to `pod_config` dict if specified
  - [x] 2.9 Research RunPod API: Check if `create_pod()` accepts datacenter parameter (review SDK docs or test)
  - [x] 2.10 Implement datacenter handling: If API supports it, pass parameter; if not, document limitation in code comment
  - [x] 2.11 Test manually: Run `autopod connect`, verify pod created with 50GB disk (check in RunPod UI)
  - [x] 2.12 Test datacenter flag: Run `autopod connect --datacenter CA-MTL-1`, verify pod created (or graceful error if not supported)
  - [x] 2.13 Test config file: Set `default_datacenter` in config, run `autopod connect`, verify datacenter used

- [x] 3.0 Improve error messages across commands
  - [x] 3.1 Fix "pod not found" error in `src/autopod/pod_manager.py:get_pod_info()`
    - [x] 3.1.1 Wrap provider call in try-except for `RuntimeError`
    - [x] 3.1.2 Check if "not found" in error message
    - [x] 3.1.3 Print: `[red]✗ Pod {pod_id} not found[/red]` followed by `[dim]It may have been terminated. Run 'autopod ls' to see available pods.[/dim]`
    - [x] 3.1.4 Return None instead of raising exception
  - [x] 3.2 Fix "no pods" error in `src/autopod/cli.py:get_single_pod_id()`
    - [x] 3.2.1 When `len(pods) == 0`, print `[yellow]No pods found[/yellow]`
    - [x] 3.2.2 Add helpful hint: `[dim]Create one with 'autopod connect'[/dim]`
  - [x] 3.3 Fix "SSH not ready" error in `src/autopod/providers/runpod.py:get_ssh_connection_string()`
    - [x] 3.3.1 Update error message to: `"SSH not yet available for pod {pod_id}. Container may still be starting. Wait 30s and try again."`
    - [x] 3.3.2 Add logging at DEBUG level with pod status details
  - [x] 3.4 Fix "invalid API key" error in `src/autopod/providers/runpod.py:authenticate()`
    - [x] 3.4.1 Import console from cli (or create new Console instance)
    - [x] 3.4.2 On auth failure, print: `[red]✗ RunPod API key is invalid[/red]`
    - [x] 3.4.3 Add hint: `[dim]Check your config at {get_config_path()}[/dim]`
  - [x] 3.5 Test "pod not found" error: Run `autopod info fake-pod-id`, verify helpful error message
  - [x] 3.6 Test "no pods" error: Terminate all pods, run `autopod ssh` (auto-select), verify helpful message
  - [x] 3.7 Test "SSH not ready" error: Create pod, immediately run `autopod ssh <pod-id>`, verify helpful message (may need to catch pod in starting state)

- [x] 4.0 Handle missing pod metadata gracefully
  - [x] 4.1 Read `src/autopod/pod_manager.py:_print_pods_table()` to understand table rendering
  - [x] 4.2 Add fallback for missing GPU type: Use `pod.get('gpu_type', 'Unknown GPU')` instead of `pod['gpu_type']`
  - [x] 4.3 Add fallback for missing GPU count: Use `pod.get('gpu_count', 0)` with default 0
  - [x] 4.4 Add fallback for missing cost: Use `pod.get('cost_per_hour', 0.0)` with default 0.0
  - [x] 4.5 Add fallback for missing runtime: Use `pod.get('runtime_minutes', 0.0)` with default 0.0
  - [x] 4.6 Update GPU column formatting: Handle "0x Unknown GPU" case gracefully (show as "N/A" or similar)
  - [x] 4.7 Update cost column formatting: Handle $0.0000 case (show as "$0.00" or "N/A")
  - [x] 4.8 Read `src/autopod/pod_manager.py:_print_pod_panel()` to check panel rendering
  - [x] 4.9 Apply same fallback logic to panel info display
  - [x] 4.10 Test with mock data: Temporarily modify `get_pod_status()` to return incomplete data, verify table renders correctly
  - [x] 4.11 Test with real API: If RunPod returns incomplete data for any pod, verify graceful handling

- [x] 5.0 Update documentation and create manual tests
  - [x] 5.1 Create `tests/manual/test_v1.1_fixes.py` manual test script
  - [x] 5.2 Write test function: `test_stale_pod_cleanup()` - creates pod, terminates in API, runs `autopod ls`, verifies cleanup
  - [x] 5.3 Write test function: `test_default_disk_size()` - creates pod, checks disk size is 50GB via API
  - [x] 5.4 Write test function: `test_datacenter_option()` - creates pod with --datacenter flag, verifies (if supported)
  - [x] 5.5 Write test function: `test_error_messages()` - tests each error case (pod not found, no pods, SSH not ready)
  - [x] 5.6 Add cleanup function: Ensure all test pods are terminated after tests run
  - [x] 5.7 Add test instructions: Document how to run tests manually (not in CI due to cost)
  - [x] 5.8 Update `README.md`: Change disk size references from 20GB to 50GB
  - [x] 5.9 Update `README.md`: Add examples for `--datacenter` flag
  - [x] 5.10 Update `README.md`: Document error messages and what they mean
  - [x] 5.11 Update `README.md`: Add troubleshooting section for common errors
  - [x] 5.12 Run full manual test suite from `tests/manual/test_v1.1_fixes.py`
  - [x] 5.13 Verify all tests pass against real RunPod API
  - [x] 5.14 Document any limitations discovered (e.g., if datacenter not supported by API)

- [x] 6.0 Final validation and commit
  - [x] 6.1 Run through complete user workflow: `autopod config init` → `autopod connect` → `autopod ls` → `autopod info` → `autopod ssh` → `autopod kill`
  - [x] 6.2 Test stale pod scenario end-to-end: Create pod, terminate in UI, run all commands, verify graceful handling
  - [x] 6.3 Check all log files for errors: Review `~/.autopod/logs/autopod.log` for unexpected errors
  - [x] 6.4 Verify backward compatibility: Existing config files still work without modification
  - [x] 6.5 Review all code changes for code quality (consistent style, proper error handling, helpful comments)
  - [x] 6.6 Commit changes: `git add .` and `git commit -m "Fix V1.1 critical bugs: stale pod cleanup, 50GB disk default, datacenter option, improved error messages"`
  - [x] 6.7 Update task list: Mark all tasks as complete in this file
  - [x] 6.8 Ready for merge to main branch (or await review)

## Testing Approach

### Integration Testing Strategy

Each task includes manual testing against the **real RunPod API** to validate:
1. **Functionality**: Feature works as designed
2. **Error handling**: Graceful failures with helpful messages
3. **Performance**: No significant slowdowns
4. **Cleanup**: No orphaned resources

### Test Environment
- Real RunPod account with API key
- Real pods created and terminated during tests
- Costs: Minimal (~$0.10-0.20 total for all tests)

### Refactoring Approach

#### Pod Listing Cleanup (Task 1.0)
**Current state**: Loads all pod IDs from cache, attempts to fetch status, marks as "UNKNOWN" on error
**Refactored state**: Loads pod IDs, attempts fetch, **removes** from cache on "not found" error, tracks removals, notifies user

**Code changes**:
- Modify `list_pods()` exception handling
- Call existing `_remove_pod_from_state()` method
- Add user notification via Rich console
- Add INFO logging for audit trail

**Why this approach**: Minimal changes, reuses existing removal logic, maintains backward compatibility

#### Configuration Defaults (Task 2.0)
**Current state**: Hardcoded defaults in CLI decorator
**Refactored state**: CLI defaults + config file defaults with clear precedence (CLI > config > hardcoded)

**Code changes**:
- Update CLI decorator defaults
- Extend config schema with new fields
- Add precedence logic in `connect()` function
- Document precedence in code comments

**Why this approach**: Flexible for users (can override multiple ways), backward compatible (old configs still work)

#### Error Messages (Task 3.0)
**Current state**: Technical error messages leak implementation details
**Refactored state**: User-friendly messages with actionable next steps

**Code changes**:
- Add specific exception handling for common errors
- Use Rich console for formatted error display
- Include contextual help hints
- Maintain technical details in logs for debugging

**Why this approach**: Better UX without sacrificing debuggability (logs still have details)

#### Missing Metadata (Task 4.0)
**Current state**: Assumes all fields present, crashes or shows broken output when missing
**Refactored state**: Defensive programming with `.get()` and sensible defaults

**Code changes**:
- Replace `pod['field']` with `pod.get('field', default)`
- Add formatting logic for special cases (e.g., "N/A" for unknown GPU)
- Consistent fallback values across table and panel views

**Why this approach**: Robust against API changes, graceful degradation, no crashes
