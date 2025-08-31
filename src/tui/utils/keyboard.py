from blessed import Terminal


class KeyHandler:
    def __init__(self, terminal: Terminal):
        self.terminal = terminal

    def get_key(self):
        with self.terminal.cbreak(), self.terminal.hidden_cursor():
            key = self.terminal.inkey(timeout=0.1)
            if not key:
                return ""
            
            if key.is_sequence:
                return key.name
            else:
                # Check if there are more characters waiting (for paste operations)
                result = str(key)
                while True:
                    next_key = self.terminal.inkey(timeout=0.01)
                    if not next_key:
                        break
                    if next_key.is_sequence:
                        # If we hit a sequence key, put it back and break
                        break
                    result += str(next_key)
                    # Limit paste size to prevent buffer overflow
                    if len(result) > 1000:
                        break
                return result

    @staticmethod
    def is_arrow_up(key: str) -> bool:
        return key == 'KEY_UP'

    @staticmethod
    def is_arrow_down(key: str) -> bool:
        return key == 'KEY_DOWN'

    @staticmethod
    def is_arrow_left(key: str) -> bool:
        return key == 'KEY_LEFT'

    @staticmethod
    def is_arrow_right(key: str) -> bool:
        return key == 'KEY_RIGHT'

    @staticmethod
    def is_enter(key: str) -> bool:
        return key in ('KEY_ENTER', '\n', '\r')

    @staticmethod
    def is_quit(key: str) -> bool:
        return key.lower() == 'q'

    @staticmethod
    def is_escape(key: str) -> bool:
        return key == 'KEY_ESCAPE'