"""
Manual Test Plan for V1.2 Bug Fixes and UX Improvements

**Objective:**
Verify that all bug fixes and UX enhancements from the v1.2-bug-fixes-and-ux PRD
are working correctly in a live environment.

**Prerequisites:**
- `autopod` installed from the `fix/v1.2-bugs-ux` branch.
- RunPod API key configured (`autopod config init`).
- An available GPU on RunPod (e.g., RTX A40).

**Test Steps:**

Follow these steps in order. After each command, observe the output and
verify that it matches the expected behavior.
"""

import time
from rich.console import Console
from rich.panel import Panel

console = Console()

def print_step(step_num, title, instructions):
    """Prints a formatted step for the manual test."""
    console.print(Panel(
        f"[bold]Instructions:[/bold]\n{instructions}",
        title=f"[bold cyan]Step {step_num}: {title}[/bold cyan]",
        border_style="cyan",
        expand=False
    ))
    input("\nPress Enter to continue to the next step...")
    print("-" * 80)

def main():
    """Main function to guide the manual test."""
    console.print(Panel(
        "[bold green]V1.2 Manual Test Script[/bold green]\n\n"
        "This script will guide you through testing the latest fixes.\n"
        "You will be prompted to run commands and verify their output.",
        border_style="green"
    ))
    input("Press Enter to begin the test...")
    print("-" * 80)

    # --- Step 1: Create Pod ---
    print_step(
        1,
        "Create a Pod with HTTP Exposed",
        "Run the following command to create a new pod. This pod will be used for all subsequent tests.\n\n"
        "  [bold white]autopod connect --expose-http --gpu \"RTX A40\"[/bold white]\n\n"
        "After running, copy the [bold]pod ID[/bold] from the output. You will need it for the next steps."
    )

    # --- Step 2: Verify Runtime and Cost ---
    pod_id = input("Enter the pod ID from the previous step: ").strip()
    if not pod_id:
        console.print("[red]Pod ID is required. Exiting test.[/red]")
        return

    instructions_step_2 = (
        "Wait for about 2 minutes for the pod to run.\n\n"
        "Then, run the following command, replacing `{pod_id}` with the actual pod ID:\n\n"
        f"  [bold white]autopod info {pod_id}[/bold white]\n\n"
        "[bold]Expected Behavior:[/bold]\n"
        "1. The 'Runtime' should be approximately 2.0 minutes (or however long you waited).\n"
        "2. The 'Total cost' should be a non-zero value (e.g., $0.0133)."
    )
    print_step(2, "Verify Runtime and Cost Calculation", instructions_step_2)

    # --- Step 3: Verify `comfy info` Command ---
    instructions_step_3 = (
        "Run the `comfy info` command for your pod:\n\n"
        f"  [bold white]autopod comfy info {pod_id}[/bold white]\n\n"
        "[bold]Expected Behavior:[/bold]\n"
        "1. The command should first print the proxy URL: `https://{pod_id}-8188.proxy.runpod.net`.\n"
        "2. You should see a spinner with the text '[yellow]Checking ComfyUI status...[/yellow]'.\n"
        "3. After a few seconds, the spinner text should change to '[green]✓ ComfyUI is available.[/green]'.\n"
        "4. A panel with detailed system information should be displayed."
    )
    print_step(3, "Verify `comfy info` UX", instructions_step_3)

    # --- Step 4: Verify Manual Tunnel Management ---
    instructions_step_4 = (
        "First, manually start a tunnel to the pod. This will likely fail to connect but should create a process.\n\n"
        f"  [bold white]autopod tunnel start {pod_id}[/bold white]\n\n"
        "Next, verify the `stop-all` command works as a kill-switch.\n\n"
        "  [bold white]autopod tunnel stop-all -y[/bold white]\n\n"
        "[bold]Expected Behavior:[/bold]\n"
        "1. The `tunnel start` command will create a process.\n"
        "2. The `tunnel stop-all` command should report that it stopped 1 tunnel.\n"
        "3. Running `autopod tunnel list` afterwards should show no active tunnels."
    )
    print_step(4, "Verify Tunnel Kill-Switch", instructions_step_4)

    # --- Step 5: Terminate Pod ---
    instructions_step_5 = (
        "Finally, clean up the resources by terminating the pod.\n\n"
        f"  [bold white]autopod kill {pod_id} -y[/bold white]\n\n"
        "[bold]Expected Behavior:[/bold]\n"
        "The command should report that the pod was terminated successfully."
    )
    print_step(5, "Terminate the Pod", instructions_step_5)

    # --- End of Test ---
    console.print(Panel(
        "[bold green]✓ Manual Test Complete[/bold green]\n\n"
        "If all steps behaved as expected, the test is successful.",
        border_style="green"
    ))

if __name__ == "__main__":
    main()
