from blessed import Terminal
from typing import Optional


class TextInputDialog:
    def __init__(self, terminal: Terminal, title: str, current_value: str = ""):
        self.terminal = terminal
        self.title = title
        self.current_value = current_value
        self.input_value = current_value
        self.cursor_pos = len(current_value)
        self.cancelled = False

    def render(self, x: int, y: int, width: int, height: int):
        # Draw dialog box
        self._draw_box(x, y, width, height)
        
        # Title
        title_x = x + (width - len(self.title)) // 2
        with self.terminal.location(title_x, y + 1):
            print(self.terminal.bold + self.title + self.terminal.normal)
        
        # Current value label
        current_label = f"Current: {self.current_value}"
        with self.terminal.location(x + 2, y + 3):
            print(self.terminal.dim + current_label + self.terminal.normal)
        
        # Input field
        input_label = "New value: "
        with self.terminal.location(x + 2, y + 5):
            print(input_label, end="")
        
        # Input box
        input_box_x = x + 2 + len(input_label)
        input_box_width = width - 4 - len(input_label)
        
        with self.terminal.location(input_box_x, y + 5):
            print("┌" + "─" * (input_box_width - 2) + "┐")
        with self.terminal.location(input_box_x, y + 6):
            # Display input text with cursor
            display_text = self.input_value
            if len(display_text) > input_box_width - 4:
                # Scroll text if too long
                start_pos = max(0, self.cursor_pos - (input_box_width - 6))
                display_text = display_text[start_pos:start_pos + input_box_width - 4]
                cursor_display_pos = self.cursor_pos - start_pos
            else:
                cursor_display_pos = self.cursor_pos
            
            print("│", end="")
            for i, char in enumerate(display_text):
                if i == cursor_display_pos:
                    print(self.terminal.reverse + char + self.terminal.normal, end="")
                else:
                    print(char, end="")
            
            # Show cursor at end if needed
            remaining_space = input_box_width - 4 - len(display_text)
            if cursor_display_pos == len(display_text) and remaining_space > 0:
                print(self.terminal.reverse + " " + self.terminal.normal, end="")
                remaining_space -= 1
            
            print(" " * remaining_space + "│")
            
        with self.terminal.location(input_box_x, y + 7):
            print("└" + "─" * (input_box_width - 2) + "┘")
        
        # Instructions
        instructions = "Press Enter to save, Esc to cancel, ←→ to move cursor"
        instr_x = x + (width - len(instructions)) // 2
        with self.terminal.location(instr_x, y + height - 2):
            print(self.terminal.dim + instructions + self.terminal.normal)

    def _draw_box(self, x: int, y: int, width: int, height: int):
        # Top border
        with self.terminal.location(x, y):
            print("┌" + "─" * (width - 2) + "┐")
        
        # Side borders
        for i in range(1, height - 1):
            with self.terminal.location(x, y + i):
                print("│" + " " * (width - 2) + "│")
        
        # Bottom border
        with self.terminal.location(x, y + height - 1):
            print("└" + "─" * (width - 2) + "┘")

    def handle_input(self, key: str) -> Optional[str]:
        if key == 'KEY_ESCAPE':
            self.cancelled = True
            return "exit"
        elif key in ('KEY_ENTER', '\n', '\r'):
            return "save"
        elif key == 'KEY_BACKSPACE' or key == '\x7f':  # Backspace
            if self.cursor_pos > 0:
                self.input_value = (self.input_value[:self.cursor_pos-1] + 
                                  self.input_value[self.cursor_pos:])
                self.cursor_pos -= 1
        elif key == 'KEY_DELETE':
            if self.cursor_pos < len(self.input_value):
                self.input_value = (self.input_value[:self.cursor_pos] + 
                                  self.input_value[self.cursor_pos+1:])
        elif key == 'KEY_LEFT':
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
        elif key == 'KEY_RIGHT':
            if self.cursor_pos < len(self.input_value):
                self.cursor_pos += 1
        elif key == 'KEY_HOME':
            self.cursor_pos = 0
        elif key == 'KEY_END':
            self.cursor_pos = len(self.input_value)
        elif len(key) == 1 and key.isprintable():
            # Regular character input
            self.input_value = (self.input_value[:self.cursor_pos] + 
                              key + self.input_value[self.cursor_pos:])
            self.cursor_pos += 1
        
        return None

    def get_result(self) -> Optional[str]:
        if self.cancelled:
            return None
        return self.input_value