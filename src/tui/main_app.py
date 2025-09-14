from blessed import Terminal
from typing import Dict, Optional

from .screens.base_screen import BaseScreen
from .screens.main_menu import MainMenuScreen
from .screens.run_screen import RunScreen
from .screens.settings_screen import SettingsScreen
from .utils.keyboard import KeyHandler
from core.server import ServerAPI
from service.device_manager import DeviceManager


class MainApp:
    def __init__(self):
        self.terminal = Terminal()
        self.key_handler = KeyHandler(self.terminal)
        self.current_screen: Optional[BaseScreen] = None
        self.screens: Dict[str, BaseScreen] = {}
        self.running = True
        self.server_api = ServerAPI()
        self.device_manager = DeviceManager(self.server_api)

    def initialize_screens(self):
        self.screens = {
            'main_menu': MainMenuScreen(self.terminal, self),
            'run': RunScreen(self.terminal, self, self.server_api, self.device_manager),
            'settings': SettingsScreen(self.terminal, self, self.device_manager)
        }
        self.current_screen = self.screens['main_menu']

    def navigate_to(self, screen_name: str):
        if screen_name in self.screens:
            self.current_screen = self.screens[screen_name]
        elif screen_name == 'quit':
            self.quit()

    def quit(self):
        self.running = False

    def run(self):
        try:
            self.initialize_screens()
            
            # Initial render
            print(self.terminal.home + self.terminal.clear, end='')
            if self.current_screen:
                self.current_screen.render()
            
            while self.running and self.current_screen:
                # Wait for input (blocking)
                key = self.key_handler.get_key()
                
                if key:  # Only process and re-render when there's input
                    # Clear and re-render only when input is received
                    print(self.terminal.home + self.terminal.clear, end='')
                    
                    # Handle input first
                    result = self.current_screen.handle_input(key)
                    if result:
                        self.navigate_to(result)
                    
                    # Render the (potentially new) current screen
                    if self.current_screen:
                        self.current_screen.render()
                    
        except KeyboardInterrupt:
            pass
        finally:
            print(self.terminal.normal)


