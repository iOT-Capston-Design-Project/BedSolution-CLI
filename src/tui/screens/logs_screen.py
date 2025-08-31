from .base_screen import BaseScreen
from ..components.menu import MenuComponent
from ..components.log_table import LogTableComponent
from ..utils.keyboard import KeyHandler
from ..utils.server_validator import ServerValidator
from blessed import Terminal
from typing import Optional, List
import threading


class LogsScreen(BaseScreen):
    def __init__(self, terminal: Terminal, app, server_api):
        super().__init__(terminal)
        self.app = app
        self.server_api = server_api
        self.day_logs = []
        self.day_menu = None
        self.selected_day_log = None
        self.pressure_logs = []
        self.log_table = LogTableComponent(terminal)
        self.view_mode = "day_list"  # "day_list", "pressure_detail", or "server_config_missing"
        self.loading = True
        self.server_config_valid = False
        self.missing_server_settings = []
        
        # Check server configuration first
        self.server_config_valid, self.missing_server_settings = ServerValidator.validate_server_config()
        
        if self.server_config_valid and self.server_api:
            self.load_day_logs()
        elif not self.server_config_valid:
            self.view_mode = "server_config_missing"
            self.loading = False

    def load_day_logs(self):
        threading.Thread(target=self._load_day_logs_async, daemon=True).start()

    def _load_day_logs_async(self):
        try:
            self.day_logs = self.server_api.fetch_daylogs()
            if self.day_logs:
                menu_items = []
                for day_log in self.day_logs[:10]:  # Show max 10 items
                    date_str = day_log.day.strftime("%Y-%m-%d")
                    total_records = (day_log.accumulated_occiput + day_log.accumulated_scapula + 
                                   day_log.accumulated_elbow + day_log.accumulated_heel + 
                                   day_log.accumulated_hip)
                    menu_items.append(f"{date_str} - {total_records} accumulated points")
                
                self.day_menu = MenuComponent(self.terminal, menu_items)
            self.loading = False
        except Exception as e:
            self.loading = False

    def load_pressure_logs_for_day(self, day_log):
        self.selected_day_log = day_log
        threading.Thread(target=self._load_pressure_logs_async, daemon=True, args=(day_log.id,)).start()

    def _load_pressure_logs_async(self, day_id):
        try:
            self.pressure_logs = self.server_api.fetch_pressurelogs(day_id)
            self.view_mode = "pressure_detail"
        except Exception as e:
            pass

    def render(self):
        self.clear_screen()
        
        if self.view_mode == "server_config_missing":
            self._render_server_config_missing()
        elif self.view_mode == "day_list":
            self._render_day_list()
        elif self.view_mode == "pressure_detail":
            self._render_pressure_detail()

    def _render_server_config_missing(self):
        self.draw_border("PRESSURE LOG HISTORY")
        
        warning_lines = ServerValidator.get_server_config_warning_message(self.missing_server_settings)
        
        start_y = (self.height - len(warning_lines)) // 2
        for i, line in enumerate(warning_lines):
            if line.startswith("⚠️"):
                self.center_text(line, start_y + i, self.terminal.red)
            elif line.startswith("  •"):
                self.center_text(line, start_y + i, self.terminal.yellow)
            elif line.strip() == "":
                continue
            else:
                self.center_text(line, start_y + i)

    def _render_day_list(self):
        self.draw_border("PRESSURE LOG HISTORY")
        
        if self.loading:
            self.center_text("Loading day logs...", self.height // 2, self.terminal.yellow)
            return
            
        if not self.day_logs:
            self.center_text("No pressure logs found", self.height // 2, self.terminal.yellow)
            self.center_text("Press 'q' to return to main menu", self.height // 2 + 2, self.terminal.dim)
            return
        
        self.center_text("Select a date to view detailed pressure logs", 4, self.terminal.cyan)
        
        if self.day_menu:
            menu_y = 7
            menu_x = 10
            self.day_menu.render(menu_x, menu_y)
        
        instructions = [
            "Press Enter to view details",
            "↑↓ to navigate",
            "'q' to quit"
        ]
        
        for i, instruction in enumerate(instructions):
            self.center_text(instruction, self.height - 5 + i, self.terminal.dim)

    def _render_pressure_detail(self):
        if self.selected_day_log:
            date_str = self.selected_day_log.day.strftime("%Y-%m-%d")
            title = f"PRESSURE LOGS - {date_str}"
        else:
            title = "PRESSURE LOGS - DETAIL"
            
        self.draw_border(title)
        
        if self.selected_day_log:
            # Show day summary
            summary_y = 3
            self.draw_text(f"Date: {self.selected_day_log.day.strftime('%Y-%m-%d')}", 3, summary_y)
            self.draw_text(f"Device ID: {self.selected_day_log.device_id}", 3, summary_y + 1)
            
            summary_text = (f"Accumulated - Occiput: {self.selected_day_log.accumulated_occiput}, "
                          f"Scapula: {self.selected_day_log.accumulated_scapula}, "
                          f"Elbow: {self.selected_day_log.accumulated_elbow}, "
                          f"Heel: {self.selected_day_log.accumulated_heel}, "
                          f"Hip: {self.selected_day_log.accumulated_hip}")
            self.draw_text(summary_text, 3, summary_y + 2, self.terminal.cyan)
            
            self.draw_text("─" * (self.width - 6), 3, summary_y + 3)
        
        # Render pressure logs table
        table_y = 8
        table_height = self.height - table_y - 4
        
        if self.pressure_logs:
            # Convert pressure logs to format expected by log table
            self.log_table.logs = []
            for log in self.pressure_logs:
                self.log_table.logs.append({
                    'time': log.createdAt.strftime("%H:%M:%S"),
                    'occiput': log.occiput,
                    'scapula': log.scapula,
                    'elbow': log.elbow,
                    'heel': log.heel,
                    'hip': log.hip
                })
            
            self.log_table.render(3, table_y, self.width - 6, table_height)
        else:
            self.center_text("Loading pressure logs...", table_y + table_height // 2, self.terminal.yellow)
        
        instructions = [
            "Press 'b' to go back",
            "↑↓ to scroll logs",
            "'q' to go back"
        ]
        
        for i, instruction in enumerate(instructions):
            self.draw_text(instruction, 3 + i * 25, self.height - 2, self.terminal.dim)

    def handle_input(self, key: str) -> Optional[str]:
        if KeyHandler.is_quit(key):
            if self.view_mode == "pressure_detail":
                self.view_mode = "day_list"
                return None
            else:
                return "main_menu"
        elif key.lower() == 's' and self.view_mode == "server_config_missing":
            return "settings"
        
        if self.view_mode == "day_list":
            if self.day_menu:
                if KeyHandler.is_arrow_up(key):
                    self.day_menu.move_up()
                elif KeyHandler.is_arrow_down(key):
                    self.day_menu.move_down()
                elif KeyHandler.is_enter(key):
                    selected_index = self.day_menu.get_selected_index()
                    if selected_index < len(self.day_logs):
                        self.load_pressure_logs_for_day(self.day_logs[selected_index])
        
        elif self.view_mode == "pressure_detail":
            if key.lower() == 'b':
                self.view_mode = "day_list"
            elif KeyHandler.is_arrow_up(key):
                self.log_table.scroll_up()
            elif KeyHandler.is_arrow_down(key):
                self.log_table.scroll_down()
        
        return None