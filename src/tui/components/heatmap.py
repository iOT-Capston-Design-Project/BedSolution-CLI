from blessed import Terminal
import random
import time
from typing import List


class HeatmapComponent:
    def __init__(self, terminal: Terminal):
        self.terminal = terminal
        self.width = 20
        self.height = 12
        self.data = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.last_update = time.time()
        self.update_interval = 0.5  # Update every 0.5 seconds
        
    def _generate_sample_data(self):
        current_time = time.time()
        if current_time - self.last_update > self.update_interval:
            for i in range(self.height):
                for j in range(self.width):
                    if 3 <= i <= 8 and 3 <= j <= 16:
                        base_pressure = 30 + random.randint(-10, 40)
                        
                        if (4 <= i <= 7 and 6 <= j <= 13):
                            base_pressure += random.randint(20, 50)
                        
                        self.data[i][j] = max(0, min(100, base_pressure))
                    else:
                        self.data[i][j] = random.randint(0, 10)
            self.last_update = current_time

    def _get_pressure_char(self, value: int) -> str:
        if value >= 80:
            return "██"
        elif value >= 60:
            return "▓▓"
        elif value >= 40:
            return "▒▒"
        elif value >= 20:
            return "░░"
        else:
            return "  "

    def _get_pressure_color(self, value: int):
        if value >= 80:
            return self.terminal.on_red + self.terminal.white
        elif value >= 60:
            return self.terminal.on_bright_red + self.terminal.white
        elif value >= 40:
            return self.terminal.on_yellow + self.terminal.black
        elif value >= 20:
            return self.terminal.on_green + self.terminal.black
        else:
            return self.terminal.normal

    def render(self, x: int, y: int, width: int, height: int):
        self._generate_sample_data()
        
        for i in range(min(self.height, height)):
            line = ""
            for j in range(min(self.width, width // 2)):
                if j < len(self.data[i]):
                    value = self.data[i][j]
                    char = self._get_pressure_char(value)
                    color = self._get_pressure_color(value)
                    line += color + char + self.terminal.normal
                else:
                    line += "  "
            
            with self.terminal.location(x, y + i):
                print(line)
        
        legend_y = y + self.height + 1
        self.draw_legend(x, legend_y)

    def draw_legend(self, x: int, y: int):
        legend_items = [
            ("██", "Critical (80-100)", self.terminal.on_red + self.terminal.white),
            ("▓▓", "High (60-79)", self.terminal.on_bright_red + self.terminal.white),
            ("▒▒", "Medium (40-59)", self.terminal.on_yellow + self.terminal.black),
            ("░░", "Low (20-39)", self.terminal.on_green + self.terminal.black),
            ("  ", "None (0-19)", self.terminal.normal)
        ]
        
        with self.terminal.location(x, y):
            print(self.terminal.bold + "Pressure Legend:" + self.terminal.normal)
        
        for i, (char, desc, color) in enumerate(legend_items):
            with self.terminal.location(x, y + 1 + i):
                print(f"{color}{char}{self.terminal.normal} {desc}")