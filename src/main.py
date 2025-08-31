#!/usr/bin/env python3

import sys
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

from tui.main_app import MainApp


def main():
    """
    Main entry point for the Bed Solution TUI application.
    """
    try:
        app = MainApp()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()