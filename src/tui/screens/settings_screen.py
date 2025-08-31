from .base_screen import BaseScreen
from ..components.menu import MenuComponent
from ..components.text_input import TextInputDialog
from ..utils.keyboard import KeyHandler
from blessed import Terminal
from typing import Optional, Dict, Any
from core.config_manager import config_manager
from service.device_register import DeviceRegister
from pathlib import Path
import os


class SettingsScreen(BaseScreen):
    def __init__(self, terminal: Terminal, app, device_register: DeviceRegister):
        super().__init__(terminal)
        self.app = app
        self.device_register = device_register
        self.view_mode = "section_list"  # "section_list", "section_detail", or "text_input"
        self.sections = ["Device Registration", "Device Configuration", "Signal Processing", "Server Connection", "Debugging Options"]
        self.section_menu = MenuComponent(terminal, self.sections)
        self.current_section = None
        self.setting_items = []
        self.setting_menu = None
        self.text_input_dialog = None
        self.editing_setting = None
        
        self.settings_config = {
            "Device Registration": {
                "device_status": {"type": "status", "description": "Device Status", "section": "device"},
                "unregister_device": {"type": "action", "description": "Unregister Device", "section": "device"}
            },
            "Device Configuration": {
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
                "api_key": {"type": "password", "description": "Supabase API Key", "section": "supabase"}
            },
            "Debugging Options": {
                "debug_enabled": {"type": "boolean", "description": "Enable Debug Mode", "section": "debug"},
                "debug_file": {"type": "text", "description": "Debug Log File Name", "section": "debug"},
                "log_file_path": {"type": "status", "description": "Current Log File Path", "section": "debug"}
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
        
        if setting_config["type"] == "status":
            if setting_key == "device_status":
                if self.device_register and self.device_register.is_registered():
                    device_id = self.device_register.get_device_id()
                    return f"Registered (ID: {device_id})"
                else:
                    return "Not Registered"
            elif setting_key == "log_file_path":
                debug_file = config_manager.get_setting("debug", "debug_file", fallback="debug.log")
                log_path = Path.cwd() / debug_file
                return str(log_path)
        elif setting_config["type"] == "action":
            return "Click to execute"
        
        section = setting_config["section"]
        value = config_manager.get_setting(section, setting_key, fallback="")
        
        if setting_config["type"] == "boolean":
            return "Enabled" if value.lower() in ["true", "1", "yes", "on"] else "Disabled"
        elif setting_config["type"] == "password":
            if not value:
                return "Not Set"
            # Show first 4 chars + asterisks + last 4 chars for long values
            if len(value) > 12:
                return f"{value[:4]}{'*' * 8}{value[-4:]}"
            else:
                return "*" * len(value)
        
        return value or "Not Set"

    def toggle_boolean_setting(self, setting_key: str):
        if self.current_section not in self.settings_config:
            return
            
        setting_config = self.settings_config[self.current_section][setting_key]
        section = setting_config["section"]
        
        current_value = config_manager.get_setting(section, setting_key, fallback="false")
        new_value = "false" if current_value.lower() in ["true", "1", "yes", "on"] else "true"
        
        config_manager.update_setting(section, setting_key, new_value)

    def start_text_edit(self, setting_key: str):
        if self.current_section not in self.settings_config:
            return
            
        setting_config = self.settings_config[self.current_section][setting_key]
        section = setting_config["section"]
        current_value = config_manager.get_setting(section, setting_key, fallback="")
        
        is_password = setting_config["type"] == "password"
        
        self.editing_setting = setting_key
        self.text_input_dialog = TextInputDialog(
            self.terminal, 
            f"Edit {setting_config['description']}", 
            current_value,
            masked=is_password
        )
        self.view_mode = "text_input"

    def save_text_setting(self, new_value: str):
        if not self.editing_setting or self.current_section not in self.settings_config:
            return
            
        setting_config = self.settings_config[self.current_section][self.editing_setting]
        section = setting_config["section"]
        
        config_manager.update_setting(section, self.editing_setting, new_value)
        
        # If server config was updated, reconnect to server
        if section == "supabase":
            self.app.server_api.reconnect()
        
        self.editing_setting = None
        self.text_input_dialog = None
        self.view_mode = "section_detail"

    def render(self):
        self.clear_screen()
        
        if self.view_mode == "section_list":
            self._render_section_list()
        elif self.view_mode == "section_detail":
            self._render_section_detail()
        elif self.view_mode == "text_input":
            self._render_text_input()

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
            "'q' to go back"
        ]
        
        for i, instruction in enumerate(instructions):
            self.draw_text(instruction, 3 + i * 20, self.height - 2, self.terminal.dim)

    def _render_text_input(self):
        # Render the section detail in the background
        self._render_section_detail()
        
        # Overlay the text input dialog
        if self.text_input_dialog:
            dialog_width = min(60, self.width - 10)
            dialog_height = 12
            dialog_x = (self.width - dialog_width) // 2
            dialog_y = (self.height - dialog_height) // 2
            
            self.text_input_dialog.render(dialog_x, dialog_y, dialog_width, dialog_height)
            
            # Add additional context for special dialogs
            if self.editing_setting == "confirm_unregister":
                self.draw_text("⚠️  This will remove the device from the server.", 
                             dialog_x + 2, dialog_y + 3, self.terminal.yellow)
                self.draw_text("Type 'CONFIRM' to proceed:", 
                             dialog_x + 2, dialog_y + 4, self.terminal.white)
            elif self.editing_setting == "unregister_success":
                self.draw_text("✅ Operation completed successfully!", 
                             dialog_x + 2, dialog_y + 3, self.terminal.green)
                self.draw_text("Press Enter to continue", 
                             dialog_x + 2, dialog_y + 4, self.terminal.dim)
            elif self.editing_setting == "unregister_error":
                self.draw_text("❌ Check server connection and try again", 
                             dialog_x + 2, dialog_y + 3, self.terminal.red)
                self.draw_text("Press Enter to continue", 
                             dialog_x + 2, dialog_y + 4, self.terminal.dim)

    def handle_input(self, key: str) -> Optional[str]:
        if self.view_mode == "text_input":
            if self.text_input_dialog:
                result = self.text_input_dialog.handle_input(key)
                if result == "save":
                    new_value = self.text_input_dialog.get_result()
                    if new_value is not None:
                        if self.editing_setting == "confirm_unregister":
                            self.confirm_device_unregistration(new_value)
                        elif self.editing_setting in ["unregister_success", "unregister_error"]:
                            # Return to settings after showing result message
                            self.editing_setting = None
                            self.text_input_dialog = None
                            self.view_mode = "section_detail"
                        else:
                            self.save_text_setting(new_value)
                elif result == "exit":
                    self.editing_setting = None
                    self.text_input_dialog = None
                    self.view_mode = "section_detail"
            return None
        
        if KeyHandler.is_quit(key):
            if self.view_mode == "section_detail":
                self.view_mode = "section_list"
                self.current_section = None
                return None
            else:
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
                        elif setting_config["type"] == "action" and setting_key == "unregister_device":
                            self.handle_device_unregistration()
                        elif setting_config["type"] in ["text", "password"]:
                            self.start_text_edit(setting_key)
        
        return None
    
    def handle_device_unregistration(self):
        if not self.device_register or not self.device_register.is_registered():
            return
        
        # Create a confirmation dialog using the text input dialog
        self.editing_setting = "confirm_unregister"
        self.text_input_dialog = TextInputDialog(
            self.terminal,
            "Confirm Device Unregistration",
            ""
        )
        self.view_mode = "text_input"
    
    def confirm_device_unregistration(self, confirmation_text: str):
        if confirmation_text.strip().upper() == "CONFIRM":
            if self.device_register and self.device_register.unregister_device():
                # Show success message briefly
                self.editing_setting = "unregister_success"
                self.text_input_dialog = TextInputDialog(
                    self.terminal,
                    "Device Unregistered Successfully",
                    ""
                )
            else:
                # Show error message
                self.editing_setting = "unregister_error"
                self.text_input_dialog = TextInputDialog(
                    self.terminal,
                    "Failed to Unregister Device",
                    ""
                )
        else:
            # Cancelled - return to settings
            self.editing_setting = None
            self.text_input_dialog = None
            self.view_mode = "section_detail"