# PRD: v1.2 Bug Fixes & UX Improvements

## 1. Introduction

As we conclude the V1.2 feature set and prepare for V1.3 (API-driven job processing), it's crucial to address bugs, usability gaps, and documentation issues identified during manual testing. This document outlines the requirements for a maintenance release to stabilize the user experience, improve clarity, and fix incorrect behaviors before building more complex functionality.

The goal is to create a more reliable and intuitive experience for users managing pods and interacting with the ComfyUI service, with a specific focus on correcting faulty SSH tunnel logic.

## 2. Goals

*   **Improve Data Accuracy:** Ensure that information presented to the user (e.g., cost, runtime) is correct and reliable.
*   **Enhance User Experience:** Provide clearer, dynamic feedback about service availability and reduce user confusion.
*   **Resolve Logic Conflicts:** Fix underlying bugs related to network and tunnel management, and provide tools to manage tunnels.
*   **Improve Documentation:** Make it easier for new users to understand configuration and default behaviors.

## 3. User Stories

*   **As a user,** I want to see the accurate, up-to-date runtime and total cost when I run `autopod info`, so I can track my spending.
*   **As a user,** I want `autopod comfy info` to show me the direct URL to the ComfyUI GUI, so I can access it quickly without having to construct the URL myself.
*   **As a user,** I want a clear, visual indicator that tells me when the ComfyUI service is ready, so I don't have to guess or repeatedly try to access a URL that isn't live yet.
*   **As a user who uses the `--expose-http` option,** I want the CLI to work without network conflicts or faulty tunnels, so I don't encounter errors about ports already being in use.
*   **As a developer or power user,** I want a command to kill any lingering `autopod` SSH tunnels, so I can easily clean up my local environment if needed.
*   **As a new user,** I want to understand how to configure `autopod` and what happens by default *before* I try running commands, so I can set up the tool correctly from the start.

## 4. Functional Requirements

### 4.1. CLI & Data Display

1.  **FR1.1 - Accurate Cost and Runtime:** The `autopod info` command **must** correctly calculate and display the pod's current runtime and total accumulated cost. It should no longer display zero for these values for active pods.
2.  **FR1.2 - Display ComfyUI URL:** The `autopod comfy info` command **must** display the full, clickable URL to the ComfyUI web interface.
3.  **FR1.3 - Dynamic Service Health Check:**
    *   When a pod is being created or started, the UI for `autopod comfy info` (or the main status view) **must** display a "pending" or "initializing" status (e.g., with a yellow indicator) for the ComfyUI service.
    *   The tool **must** periodically poll the ComfyUI GUI endpoint in the background to check for availability.
    *   Once the endpoint returns a successful response (e.g., HTTP 200), the status **must** update to "online" or "available" (e.g., with a green indicator).

### 4.2. Networking & Tunneling

1.  **FR2.1 - Disable Automatic Tunneling:** The application logic **must be modified to completely disable automatic SSH tunnel creation** for this version. Commands like `autopod comfy status` or `autopod comfy info` must not be blocked by or attempt to initiate a tunnel.
2.  **FR2.2 - Clear Stale Tunnel Cache:** The application **must** ensure that no stale or cached tunnel information from previous runs interferes with current commands. Any in-memory or cached tunnel state should be cleared on startup.
3.  **FR2.3 - Add Tunnel Kill-Switch:** A new command or flag, such as `autopod tunnel kill --all`, **must** be implemented. This command will find and terminate all active SSH tunnel processes that were created by `autopod`.

### 4.3. Documentation

1.  **FR3.1 - Reorganize README:** The `README.md` file **must** be updated to move the "Configuration" section to a more prominent position, directly above the "Common Workflows" section.
2.  **FR3.2 - Clarify GPU Selection Logic:** The "Configuration" section **must** be expanded to clearly explain the GPU selection process, including:
    *   The hierarchy of selection: command-line flags override the config file, which overrides the system defaults.
    *   The explicit list of default GPU types and the order in which they are tried if no user configuration is present.

## 5. Non-Goals (Out of Scope)

*   **API-driven Job Processing:** This PRD does not cover any part of the V1.3 feature set.
*   **Full SSH Tunnel Implementation:** Implementing "true" SSH tunneling for pods with public IPs is a V1.4 feature and is explicitly out of scope for this release.
*   **Advanced Port Management:** Automatically finding and using an alternative open port is not required.
*   **Full TUI Implementation:** We will continue using `rich` for UI components.

## 6. Design & Technical Considerations

*   **Polling Strategy:** The health check for the ComfyUI service should be lightweight. A suggested approach is to poll every 2-3 seconds for the first 30 seconds after pod creation, and if the service is still not available, slow the polling interval to every 10-15 seconds thereafter to reduce overhead.
*   **Tunneling Logic:** The removal of auto-tunneling is required because the current implementation does not work correctly with RunPod's proxy-based SSH access (used for pods without a dedicated public IP). The existing tunnel infrastructure should be disabled to prevent conflicts until it is properly re-implemented in V1.4.

## 7. Success Metrics

*   The `autopod info` command correctly reports non-zero runtime and cost for a pod that has been running for several minutes.
*   The `autopod comfy info` and `status` commands execute without error and do not create any new SSH processes.
*   The ComfyUI service status indicator correctly transitions from a "pending" state to an "available" state after the service starts.
*   The `autopod tunnel kill --all` command successfully terminates any lingering `autopod` SSH processes.
*   The `README.md` file reflects the updated structure and contains clear documentation on GPU selection defaults.

## 8. Open Questions

*   None at this time. The requirements are well-defined.
