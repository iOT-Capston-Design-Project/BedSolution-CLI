import logging
import threading
from pathlib import Path
from typing import Optional

import numpy as np
from blessed import Terminal

from .base_screen import BaseScreen
from ..components.menu import MenuComponent
from ..components.text_input import TextInputDialog
from ..utils.keyboard import KeyHandler
from core.config import config_manager
from service.device_manager import DeviceManager
from service.notifications.notification_manager import NotificationManager


class SettingsScreen(BaseScreen):
    def __init__(self, terminal: Terminal, app, device_manager: DeviceManager):
        super().__init__(terminal)
        self.app = app
        self.device_manager = device_manager
        self.view_mode = "section_list"  # "section_list", "section_detail", or "text_input"
        self.sections = ["Device Registration", "Server Connection", "Debugging Options"]
        self.section_menu = MenuComponent(terminal, self.sections)
        self.current_section = None
        self.setting_items = []
        self.setting_menu = None
        self.text_input_dialog = None
        self.editing_setting = None
        self.logger = logging.getLogger(__name__)
        self.notification_manager = NotificationManager()
        self.notification_feedback = ""
        self.notification_feedback_color = None
        
        self.heatmap_broadcasting = False
        self.heatmap_thread: Optional[threading.Thread] = None
        self.heatmap_stop_event: Optional[threading.Event] = None
        self.current_heatmap_device_id: Optional[int] = None
        self.heatmap_broadcast_interval = 1.0
        
        self.settings_config = {
            "Device Registration": {
                "device_status": {"type": "status", "description": "Device Status", "section": "device"},
                "send_test_notification": {"type": "action", "description": "Send Test Notification", "section": "device"},
                "unregister_device": {"type": "action", "description": "Unregister Device", "section": "device"}
            },
            "Server Connection": {
                "url": {"type": "text", "description": "Supabase URL", "section": "supabase"},
                "api_key": {"type": "password", "description": "Supabase API Key", "section": "supabase"},
                "test_heatmap_broadcast": {"type": "action", "description": "Test Heatmap Broadcast", "section": "supabase"}
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
                if self.device_manager and self.device_manager.is_registered():
                    device_id = self.device_manager.get_device_id()
                    return f"Registered (ID: {device_id})"
                else:
                    return "Not Registered"
            elif setting_key == "log_file_path":
                debug_file = config_manager.get_setting("debug", "debug_file", fallback="debug.log")
                log_path = Path.cwd() / debug_file
                return str(log_path)
        elif setting_config["type"] == "action":
            if setting_key == "test_heatmap_broadcast":
                return "Running (press Enter to stop)" if self.heatmap_broadcasting else "Stopped (press Enter to start)"
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
            elif self.editing_setting in [
                "test_notification_success",
                "test_notification_error",
                "heatmap_broadcast_started",
                "heatmap_broadcast_stopped",
                "heatmap_broadcast_error"
            ]:
                if self.notification_feedback:
                    message = self.notification_feedback
                elif self.editing_setting.startswith("test_notification"):
                    message = "✅ Test notification sent successfully." if self.editing_setting.endswith("success") else "❌ Failed to send test notification."
                elif self.editing_setting == "heatmap_broadcast_started":
                    message = "✅ 랜덤 히트맵 브로드캐스트를 시작했습니다."
                elif self.editing_setting == "heatmap_broadcast_stopped":
                    message = "✅ 랜덤 히트맵 브로드캐스트를 중지했습니다."
                else:
                    message = "❌ 히트맵 브로드캐스트에 실패했습니다."

                color = self.notification_feedback_color
                if color is None:
                    color = self.terminal.red if self.editing_setting.endswith("error") else self.terminal.green

                self.draw_text(message,
                             dialog_x + 2, dialog_y + 3, color)
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
                        elif self.editing_setting in [
                            "unregister_success",
                            "unregister_error",
                            "test_notification_success",
                            "test_notification_error",
                            "heatmap_broadcast_started",
                            "heatmap_broadcast_stopped",
                            "heatmap_broadcast_error"
                        ]:
                            # Return to settings after showing result message
                            self.editing_setting = None
                            self.text_input_dialog = None
                            self.view_mode = "section_detail"
                            self.notification_feedback = ""
                            self.notification_feedback_color = None
                        else:
                            self.save_text_setting(new_value)
                elif result == "exit":
                    self.editing_setting = None
                    self.text_input_dialog = None
                    self.view_mode = "section_detail"
                    self.notification_feedback = ""
                    self.notification_feedback_color = None
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
                        elif setting_config["type"] == "action":
                            if setting_key == "unregister_device":
                                self.handle_device_unregistration()
                            elif setting_key == "send_test_notification":
                                self.handle_test_notification()
                            elif setting_key == "test_heatmap_broadcast":
                                self.handle_heatmap_broadcast_action()
                        elif setting_config["type"] in ["text", "password"]:
                            self.start_text_edit(setting_key)
        
        return None
    
    def _show_notification_feedback(self, status_key: str, title: str, message: str, color):
        self.editing_setting = status_key
        self.notification_feedback = message
        self.notification_feedback_color = color
        self.text_input_dialog = TextInputDialog(
            self.terminal,
            title,
            ""
        )
        self.view_mode = "text_input"

    def handle_test_notification(self):
        self.notification_feedback = ""
        self.notification_feedback_color = None

        if not self.device_manager or not self.device_manager.is_registered():
            self._show_notification_feedback(
                "test_notification_error",
                "Test Notification Failed",
                "❌ 등록된 디바이스가 없습니다. 먼저 디바이스를 등록하세요.",
                self.terminal.red
            )
            return

        device_id = str(self.device_manager.get_device_id())
        if not device_id or device_id == "0":
            self.logger.error("Device ID is missing or invalid. Cannot send test notification.")
            self._show_notification_feedback(
                "test_notification_error",
                "Test Notification Failed",
                "❌ 디바이스 ID를 확인할 수 없습니다.",
                self.terminal.red
            )
            return

        success = False
        if self.notification_manager:
            try:
                success = self.notification_manager.send_test_notification(device_id)
            except Exception as exc:
                self.logger.error("Failed to send test notification", exc_info=True)
                success = False
        else:
            self.logger.error("Notification manager is not initialized. Cannot send test notification.")

        if success:
            message = f"✅ 디바이스 ID {device_id}에 테스트 알림을 전송했습니다."
            self._show_notification_feedback(
                "test_notification_success",
                "Test Notification Sent",
                message,
                self.terminal.green
            )
        else:
            message = "❌ 테스트 알림 전송에 실패했습니다. Firebase 설정을 확인하세요."
            self._show_notification_feedback(
                "test_notification_error",
                "Test Notification Failed",
                message,
                self.terminal.red
            )


    def handle_heatmap_broadcast_action(self):
        if self.heatmap_broadcasting:
            device_id = self.current_heatmap_device_id
            stopped = self.stop_heatmap_broadcast()
            if stopped:
                message = "✅ 랜덤 히트맵 브로드캐스트를 중지했습니다."
                if device_id:
                    message = f"✅ 디바이스 ID {device_id}의 히트맵 전송을 중지했습니다."
                self._show_notification_feedback(
                    "heatmap_broadcast_stopped",
                    "Heatmap Broadcast",
                    message,
                    self.terminal.green
                )
            else:
                self._show_notification_feedback(
                    "heatmap_broadcast_error",
                    "Heatmap Broadcast",
                    "❌ 히트맵 브로드캐스트를 중지할 수 없습니다.",
                    self.terminal.red
                )
            return

        if not self.device_manager or not self.device_manager.is_registered():
            self._show_notification_feedback(
                "heatmap_broadcast_error",
                "Heatmap Broadcast",
                "❌ 등록된 디바이스가 없습니다. 먼저 디바이스를 등록하세요.",
                self.terminal.red
            )
            return

        device_id = self.device_manager.get_device_id()
        if not device_id or device_id <= 0:
            self._show_notification_feedback(
                "heatmap_broadcast_error",
                "Heatmap Broadcast",
                "❌ 디바이스 ID를 확인할 수 없습니다.",
                self.terminal.red
            )
            return

        server_api = getattr(self.app, "server_api", None)
        if not server_api or not getattr(server_api, "client", None):
            self._show_notification_feedback(
                "heatmap_broadcast_error",
                "Heatmap Broadcast",
                "❌ 서버 연결이 설정되지 않았습니다. Supabase 설정을 확인하세요.",
                self.terminal.red
            )
            return

        if self.start_heatmap_broadcast(device_id):
            message = f"✅ 디바이스 ID {device_id}에 랜덤 히트맵 전송을 시작했습니다."
            self._show_notification_feedback(
                "heatmap_broadcast_started",
                "Heatmap Broadcast",
                message,
                self.terminal.green
            )
        else:
            self._show_notification_feedback(
                "heatmap_broadcast_error",
                "Heatmap Broadcast",
                "❌ 히트맵 브로드캐스트를 시작할 수 없습니다.",
                self.terminal.red
            )

    def start_heatmap_broadcast(self, device_id: int) -> bool:
        if self.heatmap_broadcasting:
            return True

        server_api = getattr(self.app, "server_api", None)
        if not server_api:
            self.logger.error("Server API is not available. Cannot start heatmap broadcast.")
            return False

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._heatmap_broadcast_worker,
            args=(device_id, stop_event),
            daemon=True,
            name=f"HeatmapBroadcast-{device_id}"
        )

        self.heatmap_stop_event = stop_event
        self.heatmap_thread = thread
        self.current_heatmap_device_id = device_id
        self.heatmap_broadcasting = True

        try:
            thread.start()
        except Exception:
            self.logger.exception("Failed to start heatmap broadcast thread")
            self.heatmap_thread = None
            self.heatmap_stop_event = None
            self.current_heatmap_device_id = None
            self.heatmap_broadcasting = False
            return False

        self.logger.info("Started heatmap broadcast test for device %s", device_id)
        return True

    def stop_heatmap_broadcast(self) -> bool:
        if not self.heatmap_broadcasting:
            return False

        stop_event = self.heatmap_stop_event
        thread = self.heatmap_thread

        if stop_event:
            stop_event.set()

        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

        self.heatmap_thread = None
        self.heatmap_stop_event = None
        self.heatmap_broadcasting = False
        self.current_heatmap_device_id = None

        self.logger.info("Stopped heatmap broadcast test")
        return True

    def _heatmap_broadcast_worker(self, device_id: int, stop_event: threading.Event):
        server_api = getattr(self.app, "server_api", None)
        if not server_api:
            self.logger.error("Server API is not available inside heatmap broadcast worker")
            return

        while not stop_event.is_set():
            heatmap = np.random.randint(0, 100, size=(14, 7))
            try:
                success = server_api.update_heatmap_sync(device_id, heatmap)
                if not success:
                    self.logger.warning("Heatmap broadcast returned False for device %s", device_id)
            except Exception:
                self.logger.exception("Error broadcasting heatmap for device %s", device_id)

            if stop_event.wait(self.heatmap_broadcast_interval):
                break


    def handle_device_unregistration(self):
        self.notification_feedback = ""
        self.notification_feedback_color = None
        if not self.device_manager or not self.device_manager.is_registered():
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
            if self.device_manager and self.device_manager.unregister_device():
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
