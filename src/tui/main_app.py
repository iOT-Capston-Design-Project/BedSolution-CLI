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
            if self.current_screen and self.current_screen.should_clear():
                print(self.terminal.home + self.terminal.clear, end='')
            if self.current_screen:
                self.current_screen.render()
            
            while self.running and self.current_screen:
                screen = self.current_screen
                key = self.key_handler.get_key()
                has_input = bool(key)
                needs_render = has_input or (screen and screen.needs_periodic_render())

                if not needs_render:
                    continue

                screen = self.current_screen
                if not screen:
                    break

                if screen.should_clear():
                    print(self.terminal.home + self.terminal.clear, end='')

                result = None
                if has_input:
                    result = screen.handle_input(key)

                if result:
                    self.navigate_to(result)
                    screen = self.current_screen
                    if not screen:
                        break
                    if screen.should_clear():
                        print(self.terminal.home + self.terminal.clear, end='')

                if screen:
                    screen.render()
                    
        except KeyboardInterrupt:
            pass
        finally:
            print(self.terminal.normal)

