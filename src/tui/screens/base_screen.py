from abc import ABC, abstractmethod
from blessed import Terminal
from typing import Optional


class BaseScreen(ABC):
    def __init__(self, terminal: Terminal):
        self.terminal = terminal
        # Use smaller fixed window size instead of full terminal
        self.height = min(35, terminal.height - 2)  # Max 35 rows, leave space for prompt
        self.width = min(120, terminal.width - 2)   # Max 120 cols, leave some margin
        self.running = True

    @abstractmethod
    def render(self):
        pass

    @abstractmethod
    def handle_input(self, key: str) -> Optional[str]:
        pass

    def clear_screen(self):
        print(self.terminal.home + self.terminal.clear)

    def draw_border(self, title: str = "", x: int = 0, y: int = 0, width: int = None, height: int = None):
        if width is None:
            width = self.width
        if height is None:
            height = self.height

        with self.terminal.location(x, y):
            print("┌" + "─" * (width - 2) + "┐")
            
        for i in range(1, height - 1):
            with self.terminal.location(x, y + i):
                print("│" + " " * (width - 2) + "│")
                
        with self.terminal.location(x, y + height - 1):
            print("└" + "─" * (width - 2) + "┘")

        if title:
            title_x = x + (width - len(title)) // 2
            with self.terminal.location(title_x, y):
                print(title)

    def draw_text(self, text: str, x: int, y: int, color=None):
        with self.terminal.location(x, y):
            if color:
                print(color + text + self.terminal.normal)
            else:
                print(text)

    def center_text(self, text: str, y: int, color=None):
        x = (self.width - len(text)) // 2
        self.draw_text(text, x, y, color)

    def quit(self):
        self.running = False