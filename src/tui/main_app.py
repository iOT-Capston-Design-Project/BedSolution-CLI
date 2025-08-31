from blessed import Terminal
from typing import Dict, Optional
import sys
import os

from .screens.base_screen import BaseScreen
from .screens.main_menu import MainMenuScreen
from .screens.run_screen import RunScreen
from .screens.logs_screen import LogsScreen
from .screens.settings_screen import SettingsScreen
from .utils.keyboard import KeyHandler
from core.server.server_api import ServerAPI
from service.device_register import DeviceRegister


class MainApp:
    def __init__(self):
        self.terminal = Terminal()
        self.key_handler = KeyHandler(self.terminal)
        self.current_screen: Optional[BaseScreen] = None
        self.screens: Dict[str, BaseScreen] = {}
        self.running = True
        
        try:
            self.server_api = ServerAPI()
            self.device_register = DeviceRegister(self.server_api)
        except Exception as e:
            print(f"Failed to initialize server connection: {e}")
            self.server_api = None
            self.device_register = None

    def initialize_screens(self):
        self.screens = {
            'main_menu': MainMenuScreen(self.terminal, self),
            'run': RunScreen(self.terminal, self, self.server_api, self.device_register),
            'logs': LogsScreen(self.terminal, self, self.server_api),
            'settings': SettingsScreen(self.terminal, self)
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
        print(self.terminal.enter_fullscreen)
        try:
            self.initialize_screens()
            
            while self.running and self.current_screen:
                self.current_screen.clear_screen()
                self.current_screen.render()
                
                key = self.key_handler.get_key()
                result = self.current_screen.handle_input(key)
                
                if result:
                    self.navigate_to(result)
                    
        except KeyboardInterrupt:
            pass
        finally:
            print(self.terminal.exit_fullscreen)
            print(self.terminal.normal)


