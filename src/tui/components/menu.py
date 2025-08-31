from blessed import Terminal
from typing import List


class MenuComponent:
    def __init__(self, terminal: Terminal, items: List[str], selected_index: int = 0):
        self.terminal = terminal
        self.items = items
        self.selected_index = selected_index

    def move_up(self):
        self.selected_index = (self.selected_index - 1) % len(self.items)

    def move_down(self):
        self.selected_index = (self.selected_index + 1) % len(self.items)

    def get_selected_item(self) -> str:
        return self.items[self.selected_index]

    def get_selected_index(self) -> int:
        return self.selected_index

    def render(self, x: int, y: int):
        for i, item in enumerate(self.items):
            item_y = y + i
            if i == self.selected_index:
                with self.terminal.location(x, item_y):
                    print(self.terminal.bold_cyan + "➤ " + item + self.terminal.normal)
            else:
                with self.terminal.location(x, item_y):
                    print("  " + item)