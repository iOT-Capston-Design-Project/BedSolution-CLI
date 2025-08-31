from .base_screen import BaseScreen
from ..components.menu import MenuComponent
from ..utils.keyboard import KeyHandler
from blessed import Terminal
from typing import Optional


class MainMenuScreen(BaseScreen):
    def __init__(self, terminal: Terminal, app):
        super().__init__(terminal)
        self.app = app
        self.menu = MenuComponent(
            terminal, 
            ["Run", "Pressure Logs", "Settings", "Exit"]
        )

    def render(self):
        self.clear_screen()
        self.draw_border()
        
        # ASCII art title for "BED SOLUTION"
        ascii_title = [
            "██████  ███████ ██████      ███████  ██████  ██      ██    ██ ████████ ██  ██████  ███    ██",
            "██   ██ ██      ██   ██     ██      ██    ██ ██      ██    ██    ██    ██ ██    ██ ████   ██",
            "██████  █████   ██   ██     ███████ ██    ██ ██      ██    ██    ██    ██ ██    ██ ██ ██  ██",
            "██   ██ ██      ██   ██          ██ ██    ██ ██      ██    ██    ██    ██ ██    ██ ██  ██ ██",
            "██████  ███████ ██████      ███████  ██████  ███████  ██████     ██    ██  ██████  ██   ████",
            "",
            "Smart Bed Pressure Monitoring System"
        ]
        
        start_y = 3
        for i, line in enumerate(ascii_title):
            if line == "":
                continue
            elif "Smart Bed Pressure" in line:
                self.center_text(line, start_y + i, self.terminal.yellow)
            else:
                self.center_text(line, start_y + i, self.terminal.bold_cyan)
        
        menu_y = start_y + len(ascii_title) + 2
        menu_x = (self.width - 20) // 2
        self.menu.render(menu_x, menu_y)
        
        self.center_text("Use ↑↓ to navigate, Enter to select", self.height - 4, self.terminal.dim)

    def handle_input(self, key: str) -> Optional[str]:
        if KeyHandler.is_arrow_up(key):
            self.menu.move_up()
        elif KeyHandler.is_arrow_down(key):
            self.menu.move_down()
        elif KeyHandler.is_enter(key):
            selected = self.menu.get_selected_item()
            if selected == "Run":
                return "run"
            elif selected == "Pressure Logs":
                return "logs"
            elif selected == "Settings":
                return "settings"
            elif selected == "Exit":
                return "quit"
        elif KeyHandler.is_quit(key):
            return "quit"
            
        return None