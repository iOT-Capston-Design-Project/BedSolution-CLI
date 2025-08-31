from blessed import Terminal
import time
import random
from datetime import datetime
from typing import List, Dict


class LogTableComponent:
    def __init__(self, terminal: Terminal):
        self.terminal = terminal
        self.logs: List[Dict] = []
        self.scroll_offset = 0
        self.max_display_rows = 20
        self.last_update = time.time()
        self.update_interval = 1.0  # Update every 1 second
        
    def _generate_sample_log(self):
        current_time = datetime.now()
        return {
            'time': current_time.strftime("%H:%M:%S"),
            'occiput': round(random.uniform(20, 95), 1),
            'scapula': round(random.uniform(15, 80), 1),
            'elbow': round(random.uniform(10, 70), 1),
            'heel': round(random.uniform(25, 85), 1),
            'hip': round(random.uniform(30, 90), 1)
        }

    def _update_logs(self):
        current_time = time.time()
        if current_time - self.last_update > self.update_interval:
            new_log = self._generate_sample_log()
            self.logs.insert(0, new_log)  # Add to beginning
            
            # Keep only the latest 100 logs
            if len(self.logs) > 100:
                self.logs = self.logs[:100]
            
            self.last_update = current_time

    def scroll_up(self):
        if self.scroll_offset > 0:
            self.scroll_offset -= 1

    def scroll_down(self):
        max_scroll = max(0, len(self.logs) - self.max_display_rows)
        if self.scroll_offset < max_scroll:
            self.scroll_offset += 1

    def render(self, x: int, y: int, width: int, height: int):
        self._update_logs()
        
        # Header
        header = f"{'Time':>8} | {'Occiput':>7} | {'Scapula':>7} | {'Elbow':>7} | {'Heel':>7} | {'Hip':>7}"
        with self.terminal.location(x, y):
            print(self.terminal.bold + header[:width] + self.terminal.normal)
        
        # Separator
        separator = "─" * min(len(header), width)
        with self.terminal.location(x, y + 1):
            print(separator)
        
        # Data rows
        display_height = min(height - 2, self.max_display_rows)
        end_index = min(self.scroll_offset + display_height, len(self.logs))
        
        for i, log in enumerate(self.logs[self.scroll_offset:end_index]):
            row_y = y + 2 + i
            if row_y >= y + height:
                break
                
            # Color based on pressure values
            max_pressure = max(log['occiput'], log['scapula'], log['elbow'], log['heel'], log['hip'])
            if max_pressure >= 80:
                color = self.terminal.red
            elif max_pressure >= 60:
                color = self.terminal.yellow
            else:
                color = self.terminal.green
            
            row_text = f"{log['time']:>8} | {log['occiput']:>7.1f} | {log['scapula']:>7.1f} | {log['elbow']:>7.1f} | {log['heel']:>7.1f} | {log['hip']:>7.1f}"
            
            with self.terminal.location(x, row_y):
                print(color + row_text[:width] + self.terminal.normal)
        
        # Scroll indicator
        if len(self.logs) > self.max_display_rows:
            scroll_info = f"({self.scroll_offset + 1}-{min(self.scroll_offset + display_height, len(self.logs))} of {len(self.logs)})"
            with self.terminal.location(x + width - len(scroll_info), y + height - 1):
                print(self.terminal.dim + scroll_info + self.terminal.normal)