#!/usr/bin/env python3

import sys
import logging
import os
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

from tui.main_app import MainApp
from core.config_manager import config_manager


def setup_logging():
    """Setup logging based on debug configuration."""
    debug_enabled = config_manager.get_setting("debug", "debug_enabled", fallback="false")
    debug_enabled = debug_enabled if debug_enabled else "false"
    
    if debug_enabled.lower() in ["true", "1", "yes", "on"]:
        # Create logs directory
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        # Get debug file name from config
        debug_file = config_manager.get_setting("debug", "debug_file", fallback="debug.log")
        log_filename = os.path.join(log_dir, debug_file)
        
        # Configure root logger - file only
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_filename, encoding='utf-8')]
        )


def main():
    """
    Main entry point for the Bed Solution TUI application.
    """
    setup_logging()
    
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