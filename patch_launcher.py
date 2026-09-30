with open("shield.py", "r") as f:
    content = f.read()

old_loop = """    # Show interactive menu
    while True:
        choice = show_menu()
        if choice == 0:
            return 0
        elif choice == 1:
            # TUI Mode
            exit_code = run_tui_mode(["run"])
            if exit_code == 10:
                # User requested switch to server mode
                print("\\n[Switching to Server Mode...]")
                continue  # Loop back to menu, but auto-select server
            elif exit_code != 0:
                print(f"\\n[TUI exited with code {exit_code}]")
                return exit_code
            # Normal exit from TUI
            return 0
        elif choice == 2:
            # Server Mode
            exit_code = run_server_mode([])
            if exit_code == 10:
                # Server requested switch back to TUI
                print("\\n[Switching to TUI Mode...]")
                continue
            return exit_code"""

new_loop = """    # Show interactive menu
    choice = show_menu()
    while True:
        if choice == 0:
            return 0
        elif choice == 1:
            # TUI Mode
            exit_code = run_tui_mode(["run"])
            if exit_code == 10:
                # User requested switch to server mode
                print("\\n[Switching to Server Mode...]")
                choice = 2
                continue
            elif exit_code != 0:
                print(f"\\n[TUI exited with code {exit_code}]")
                return exit_code
            # Normal exit from TUI
            return 0
        elif choice == 2:
            # Server Mode
            exit_code = run_server_mode([])
            if exit_code == 10:
                # Server requested switch back to TUI
                print("\\n[Switching to TUI Mode...]")
                choice = 1
                continue
            return exit_code"""

content = content.replace(old_loop, new_loop)
with open("shield.py", "w") as f:
    f.write(content)
