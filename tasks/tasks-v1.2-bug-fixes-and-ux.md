## Relevant Files

-   `src/autopod/providers/runpod.py` - **[High Impact]** Core logic for calculating pod runtime and cost needs to be fixed here.
-   `src/autopod/cli.py` - **[High Impact]** Will be modified to remove tunnel logic, add health checks, and update command outputs.
-   `src/autopod/comfyui.py` - Contains the existing `is_ready()` health check method to be integrated.
-   `src/autopod/tunnel.py` - Contains the `TunnelManager` and existing `stop-all`/`cleanup` logic that needs to be verified.
-   `README.md` - The main project documentation that needs to be updated.
-   `tests/test_providers/test_runpod.py` - **[New/High Impact]** Unit tests must be added to validate the corrected cost/runtime calculation.
-   `tests/test_cli.py` - Unit tests for the CLI changes will be added or updated.
-   `tests/manual/test_v1.2_fixes.py` - A new manual test script to validate all fixes against a live RunPod instance.

### Notes

-   This release focuses on surgical fixes and refactoring. The core architectural change is the removal of the automatic tunneling feature in favor of explicit user control and RunPod's HTTP proxy.
-   Testing must validate that the `comfy` commands work correctly *without* a local SSH tunnel when a pod is exposed via HTTP.

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

## Tasks

- [ ] 0.0 **Create Feature Branch**
    - [ ] 0.1 Create and checkout a new branch for this feature (`git checkout -b fix/v1.2-bugs-ux`)

- [ ] 1.0 **Fix Pod Runtime and Cost Calculation (FR1.1)**
    - [ ] 1.1 In `src/autopod/providers/runpod.py`, modify the `get_pod_status` method.
    - [ ] 1.2 The `runpod.get_pod(pod_id)` call returns a `creationTimeMillis` field. Use this field to calculate the total runtime. The logic should be `(current_time_millis - creationTimeMillis) / 1000 / 60` to get total minutes since creation, regardless of uptime.
    - [ ] 1.3 Use this new, correct `runtime_minutes` value to calculate `total_cost`. This will fix the bug where cost and runtime appear as zero for stopped pods.
    - [ ] 1.4 In `tests/test_providers/test_runpod.py`, add a new unit test `test_get_pod_status_runtime_calculation`.
    - [ ] 1.5 In this test, mock the `runpod.get_pod` call to return a sample pod dictionary containing `creationTimeMillis` (set to 1 hour ago) and `costPerHr`. Assert that the returned `runtime_minutes` is ~60 and `total_cost` is equal to `costPerHr`.

- [ ] 2.0 **Enhance `comfy` Command UX (FR1.2, FR1.3)**
    - [ ] 2.1 In `src/autopod/cli.py`, locate the `comfy_info` command function.
    - [ ] 2.2 Inside `comfy_info`, after getting the pod details, add logic to construct and display the ComfyUI proxy URL (`https://{pod_id}-8188.proxy.runpod.net`). This should only be displayed if the pod has port 8188 exposed.
    - [ ] 2.3 In `comfy_info`, integrate a `rich.status` spinner that calls the `ComfyUIClient.is_ready()` method from `src/autopod/comfyui.py`. The existing retry logic in `is_ready` is sufficient.
    - [ ] 2.4 The status message should be "Checking ComfyUI status..." (yellow) and change to "ComfyUI is available" (green) upon a successful check, or "ComfyUI is not responding" (red) on failure.
    - [ ] 2.5 In `tests/test_cli.py`, add a test for `comfy_info` that mocks the `ComfyUIClient.is_ready` method to first return `False` and then `True`, and verify the console output reflects the status change.

- [ ] 3.0 **Refactor and Control SSH Tunneling (FR2.1, FR2.2, FR2.3)**
    - [ ] 3.1 In `src/autopod/cli.py`, delete the `ensure_tunnel` function entirely.
    - [ ] 3.2 In `src/autopod/cli.py`, find the `comfy_status` and `comfy_info` commands and remove the calls to `ensure_tunnel`.
    - [ ] 3.3 Remove the `--no-tunnel` flag from both commands, as this behavior is now the default.
    - [ ] 3.4 Review the existing `autopod tunnel stop-all` command. Verify that its implementation in `src/autopod/tunnel.py` (the `stop_all_tunnels` method in `TunnelManager`) correctly uses `psutil` to find and terminate all managed SSH processes. This command serves as the required "kill switch".
    - [ ] 3.5 Review the `TunnelManager._load_state` method in `src/autopod/tunnel.py`. Verify that its logic for checking `tunnel.is_active()` correctly cleans up stale tunnel entries from the `tunnels.json` state file upon initialization. This serves as the "stale cache cleaner".
    - [ ] 3.6 Add a note to the `autopod tunnel --help` documentation clarifying that tunnels are no longer created automatically and must be managed explicitly with `tunnel start` and `tunnel stop`.

- [ ] 4.0 **Update Documentation (FR3.1, FR3.2)**
    - [ ] 4.1 Edit `README.md` to move the "Configuration" section above the "Common Workflows" section.
    - [ ] 4.2 In the "Configuration" section, add a clear explanation of the GPU selection order: 1) `--gpu` flag, 2) `gpu_preferences` in `config.json`, 3) The hardcoded default `["RTX A40", "RTX A6000", "RTX A5000"]`.
    - [ ] 4.3 Add a subsection explaining the change in tunnel behavior: tunnels are now manual, and users should use the RunPod HTTP proxy URL (from `comfy info`) for GUI access by default.
    - [ ] 4.4 Add the `autopod tunnel kill-all` (or `stop-all`) command to the examples in the README.

- [ ] 5.0 **Manual End-to-End Testing**
    - [ ] 5.1 Create a new manual test script `tests/manual/test_v1.2_fixes.py`.
    - [ ] 5.2 The script should guide the user to:
        - [ ] a. Create a pod using `autopod connect --expose-http`.
        - [ ] b. Wait 2 minutes, then run `autopod info {pod_id}` and visually confirm that "Runtime" is `~2.0 minutes` and "Total cost" is a non-zero value.
        - [ ] c. Run `autopod comfy info {pod_id}` and verify the proxy URL is displayed and the health status indicator works as expected.
        - [ ] d. Manually start a tunnel with `autopod tunnel start {pod_id}`.
        - [ ] e. Run `autopod tunnel stop-all -y` and verify the tunnel process is gone (e.g., using `ps aux | grep ssh`).
        - [ ] f. Terminate the pod with `autopod kill {pod_id} -y`.
    - [ ] 5.3 Execute the manual test script and confirm all steps pass.
