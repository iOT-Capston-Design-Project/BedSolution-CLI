from .base_screen import BaseScreen
from ..components.menu import MenuComponent
from ..utils.keyboard import KeyHandler
from blessed import Terminal
from typing import Optional, Dict, Any
from core.config_manager import config_manager


class SettingsScreen(BaseScreen):
    def __init__(self, terminal: Terminal, app):
        super().__init__(terminal)
        self.app = app
        self.view_mode = "section_list"  # "section_list" or "section_detail"
        self.sections = ["Device Configuration", "Signal Processing", "Server Connection", "Debugging Options"]
        self.section_menu = MenuComponent(terminal, self.sections)
        self.current_section = None
        self.setting_items = []
        self.setting_menu = None
        
        self.settings_config = {
            "Device Configuration": {
                "device_id": {"type": "text", "description": "Device ID", "section": "device"},
                "serial_port": {"type": "text", "description": "Serial Port", "section": "device"},
                "baud_rate": {"type": "text", "description": "Baud Rate", "section": "device"}
            },
            "Signal Processing": {
                "sampling_rate": {"type": "text", "description": "Sampling Rate (Hz)", "section": "signal"},
                "filter_enabled": {"type": "boolean", "description": "Enable Signal Filter", "section": "signal"},
                "threshold_pressure": {"type": "text", "description": "Pressure Threshold", "section": "signal"}
            },
            "Server Connection": {
                "url": {"type": "text", "description": "Supabase URL", "section": "supabase"},
                "api_key": {"type": "text", "description": "Supabase API Key", "section": "supabase"},
                "auto_sync": {"type": "boolean", "description": "Auto Sync Data", "section": "server"}
            },
            "Debugging Options": {
                "debug_enabled": {"type": "boolean", "description": "Enable Debug Mode", "section": "debug"},
                "log_level": {"type": "text", "description": "Log Level", "section": "debug"},
                "save_raw_data": {"type": "boolean", "description": "Save Raw Data", "section": "debug"}
            }
        }

    def enter_section(self, section_name: str):
        self.current_section = section_name
        self.setting_items = list(self.settings_config[section_name].keys())
        self.setting_menu = MenuComponent(self.terminal, self.setting_items)
        self.view_mode = "section_detail"

    def get_setting_value(self, setting_key: str) -> str:
        if self.current_section not in self.settings_config:
            return ""
        
        setting_config = self.settings_config[self.current_section][setting_key]
        section = setting_config["section"]
        
        value = config_manager.get_setting(section, setting_key, fallback="")
        
        if setting_config["type"] == "boolean":
            return "Enabled" if value.lower() in ["true", "1", "yes", "on"] else "Disabled"
        
        return value or "Not Set"

    def toggle_boolean_setting(self, setting_key: str):
        if self.current_section not in self.settings_config:
            return
            
        setting_config = self.settings_config[self.current_section][setting_key]
        section = setting_config["section"]
        
        current_value = config_manager.get_setting(section, setting_key, fallback="false")
        new_value = "false" if current_value.lower() in ["true", "1", "yes", "on"] else "true"
        
        config_manager.update_setting(section, setting_key, new_value)

    def render(self):
        self.clear_screen()
        
        if self.view_mode == "section_list":
            self._render_section_list()
        elif self.view_mode == "section_detail":
            self._render_section_detail()

    def _render_section_list(self):
        self.draw_border("SETTINGS")
        
        self.center_text("Select a settings category to configure", 4, self.terminal.cyan)
        
        menu_y = 7
        menu_x = (self.width - 30) // 2
        self.section_menu.render(menu_x, menu_y)
        
        instructions = [
            "Press Enter to configure",
            "↑↓ to navigate",
            "'q' to quit"
        ]
        
        for i, instruction in enumerate(instructions):
            self.center_text(instruction, self.height - 5 + i, self.terminal.dim)

    def _render_section_detail(self):
        if not self.current_section:
            return
            
        self.draw_border(f"SETTINGS - {self.current_section.upper()}")
        
        start_y = 4
        
        if self.setting_menu and self.setting_items:
            for i, setting_key in enumerate(self.setting_items):
                item_y = start_y + i * 2
                if item_y >= self.height - 6:
                    break
                
                setting_config = self.settings_config[self.current_section][setting_key]
                description = setting_config["description"]
                value = self.get_setting_value(setting_key)
                
                # Highlight selected item
                if i == self.setting_menu.get_selected_index():
                    prefix = "➤ "
                    color = self.terminal.bold_cyan
                else:
                    prefix = "  "
                    color = self.terminal.normal
                
                setting_line = f"{prefix}{description}"
                value_line = f"   Current: {value}"
                
                self.draw_text(setting_line, 3, item_y, color)
                self.draw_text(value_line, 3, item_y + 1, self.terminal.yellow)
        
        instructions = [
            "Enter to edit/toggle",
            "'b' to go back",
            "↑↓ to navigate",
            "'q' to quit"
        ]
        
        for i, instruction in enumerate(instructions):
            self.draw_text(instruction, 3 + i * 20, self.height - 2, self.terminal.dim)

    def handle_input(self, key: str) -> Optional[str]:
        if KeyHandler.is_quit(key):
            return "main_menu"
        
        if self.view_mode == "section_list":
            if KeyHandler.is_arrow_up(key):
                self.section_menu.move_up()
            elif KeyHandler.is_arrow_down(key):
                self.section_menu.move_down()
            elif KeyHandler.is_enter(key):
                selected_section = self.section_menu.get_selected_item()
                self.enter_section(selected_section)
        
        elif self.view_mode == "section_detail":
            if key.lower() == 'b':
                self.view_mode = "section_list"
                self.current_section = None
            elif self.setting_menu:
                if KeyHandler.is_arrow_up(key):
                    self.setting_menu.move_up()
                elif KeyHandler.is_arrow_down(key):
                    self.setting_menu.move_down()
                elif KeyHandler.is_enter(key):
                    selected_index = self.setting_menu.get_selected_index()
                    if selected_index < len(self.setting_items):
                        setting_key = self.setting_items[selected_index]
                        setting_config = self.settings_config[self.current_section][setting_key]
                        
                        if setting_config["type"] == "boolean":
                            self.toggle_boolean_setting(setting_key)
                        else:
                            # For text settings, we would need to implement a text input dialog
                            # For now, just show a message
                            pass
        
        return None