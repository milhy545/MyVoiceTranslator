#!/usr/bin/env python3
"""
MyVoiceTranslator - Unified Launcher
Entry point that provides a menu to choose between TUI Mode and Server Mode.
"""

from __future__ import annotations

import sys

from interview_shield.cli import main as cli_main


def show_menu() -> int:
    """Display the mode selection menu and return user's choice."""
    print("\n" + "=" * 50)
    print("  MyVoiceTranslator - Interview Shield")
    print("=" * 50)
    print()
    print("  Select mode:")
    print("  [1] TUI Mode (Local Microphone)")
    print("  [2] Server Mode (Chrome Extension)")
    print("  [q] Quit")
    print()
    
    while True:
        try:
            choice = input("  Enter choice [1/2/q]: ").strip().lower()
            if choice == "1":
                return 1  # TUI Mode
            elif choice == "2":
                return 2  # Server Mode
            elif choice in ("q", "quit", "exit"):
                return 0  # Quit
            else:
                print("  Invalid choice. Please enter 1, 2, or q.")
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            return 0


def run_tui_mode(args: list[str]) -> int:
    """Run the TUI mode, returning exit code.
    
    Returns:
        0: Normal exit
        10: Switch to Server Mode requested
        Other: Error code
    """
    # Remove the 'run' subcommand if present, as we're calling main directly
    filtered_args = [a for a in args if a != "run"]
    if not filtered_args or filtered_args[0] not in ("run", "test-file", "test-live-mic", "test-live-monitor", "test-live-dual", "doctor", "devices", "prepare-fixtures"):
        # Default to run command
        filtered_args = ["run"] + filtered_args
    
    try:
        return cli_main(filtered_args)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1


def run_server_mode(args: list[str]) -> int:
    """Run the Server mode (FastAPI backend for Chrome extension)."""
    from interview_shield.server import run_server
    return run_server(args)


def main(argv: list[str] | None = None) -> int:
    """Main entry point with mode selection menu."""
    if argv is None:
        argv = sys.argv[1:]
    
    # If explicit subcommand given, bypass menu
    if argv and argv[0] in ("run", "test-file", "test-live-mic", "test-live-monitor", "test-live-dual", "doctor", "devices", "prepare-fixtures", "server"):
        if argv[0] == "server":
            return run_server_mode(argv[1:])
        return cli_main(argv)
    
    # Check for --test shortcut (legacy)
    if argv and argv[0] == "--test":
        return cli_main(argv)
    
    # Show interactive menu
    choice = show_menu()
    while True:
        if choice == 0:
            return 0
        elif choice == 1:
            # TUI Mode
            exit_code = run_tui_mode(["run"])
            if exit_code == 10:
                # User requested switch to server mode
                print("\n[Switching to Server Mode...]")
                choice = 2
                continue
            elif exit_code != 0:
                print(f"\n[TUI exited with code {exit_code}]")
                return exit_code
            # Normal exit from TUI
            return 0
        elif choice == 2:
            # Server Mode
            exit_code = run_server_mode([])
            if exit_code == 10:
                # Server requested switch back to TUI
                print("\n[Switching to TUI Mode...]")
                choice = 1
                continue
            return exit_code
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())