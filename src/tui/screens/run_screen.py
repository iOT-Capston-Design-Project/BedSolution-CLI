from .base_screen import BaseScreen
from ..utils.keyboard import KeyHandler
from ..utils.server_validator import ServerValidator
from ..components.heatmap import HeatmapComponent
from ..components.log_table import LogTableComponent
from ..enums import DeviceStatus, PatientStatus
from service.device_register import DeviceRegister
from core.server.server_api import ServerAPI
from blessed import Terminal
from typing import Optional
import time
import threading


class RunScreen(BaseScreen):
    def __init__(self, terminal: Terminal, app, server_api: ServerAPI, device_register: DeviceRegister):
        super().__init__(terminal)
        self.app = app
        self.server_api = server_api
        self.device_register = device_register
        self.device_data = None
        self.patient_data = None
        self.device_status = DeviceStatus.CHECKING
        self.patient_status = PatientStatus.CHECKING
        self.heatmap = None
        self.log_table = None
        self.last_update = time.time()
        self.server_config_valid = False
        self.missing_server_settings = []
        
        # Check server configuration first
        self.server_config_valid, self.missing_server_settings = ServerValidator.validate_server_config()
        
        if self.server_config_valid and self.server_api and self.device_register:
            self.check_device_and_patient()
        elif not self.server_config_valid:
            self.device_status = DeviceStatus.SERVER_CONFIG_MISSING

    def check_device_and_patient(self):
        threading.Thread(target=self._check_device_and_patient_async, daemon=True).start()

    def _check_device_and_patient_async(self):
        try:
            if self.device_register.is_registered():
                device_id = self.device_register.get_device_id()
                self.device_data = self.server_api.fetch_device(device_id)
                
                if self.device_data:
                    self.device_status = DeviceStatus.REGISTERED
                    self.patient_data = self.server_api.fetch_patient_with_device(device_id)
                    
                    if self.patient_data:
                        self.patient_status = PatientStatus.CONNECTED
                        self.heatmap = HeatmapComponent(self.terminal)
                        self.log_table = LogTableComponent(self.terminal)
                    else:
                        self.patient_status = PatientStatus.NO_PATIENT
                else:
                    self.device_status = DeviceStatus.NOT_FOUND
            else:
                # Device not registered - try to auto-register
                self.device_status = DeviceStatus.REGISTERING
                if self.device_register.register_device():
                    # Registration successful, check again
                    device_id = self.device_register.get_device_id()
                    self.device_data = self.server_api.fetch_device(device_id)
                    
                    if self.device_data:
                        self.device_status = DeviceStatus.REGISTERED
                        self.patient_data = self.server_api.fetch_patient_with_device(device_id)
                        
                        if self.patient_data:
                            self.patient_status = PatientStatus.CONNECTED
                            self.heatmap = HeatmapComponent(self.terminal)
                            self.log_table = LogTableComponent(self.terminal)
                        else:
                            self.patient_status = PatientStatus.NO_PATIENT
                    else:
                        self.device_status = DeviceStatus.REGISTRATION_FAILED
                else:
                    self.device_status = DeviceStatus.REGISTRATION_FAILED
        except Exception:
            self.device_status = DeviceStatus.ERROR
            self.patient_status = PatientStatus.ERROR

    def render(self):
        self.clear_screen()
        self.draw_border("RUN - Real-time Monitoring")
        
        if self.device_status == DeviceStatus.CHECKING:
            self.center_text("Checking device registration...", self.height // 2, self.terminal.yellow)
            return
        elif self.device_status == DeviceStatus.REGISTERING:
            self.center_text("Registering device automatically...", self.height // 2, self.terminal.yellow)
            return
            
        if self.device_status == DeviceStatus.SERVER_CONFIG_MISSING:
            self._render_server_config_missing()
        elif self.device_status == DeviceStatus.NOT_REGISTERED:
            self._render_device_not_registered()
        elif self.device_status == DeviceStatus.REGISTRATION_FAILED:
            self._render_registration_failed()
        elif self.device_status == DeviceStatus.ERROR:
            self._render_error()
        elif self.patient_status == PatientStatus.NO_PATIENT:
            self._render_no_patient()
        elif self.patient_status == PatientStatus.CONNECTED:
            self._render_monitoring_view()
        else:
            # Fallback for any unknown status combination
            self.center_text(f"Unknown state: Device({self.device_status.value if hasattr(self.device_status, 'value') else self.device_status}), "
                           f"Patient({self.patient_status.value if hasattr(self.patient_status, 'value') else self.patient_status})",
                           self.height // 2 - 1, self.terminal.red)
            self.center_text("Press 'q' to return to main menu", self.height // 2 + 1, self.terminal.dim)

    def _render_server_config_missing(self):
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

    def _render_device_not_registered(self):
        self.draw_text("Device Status: Not Registered", 3, 3, self.terminal.red)
        self.draw_text("⚠️  Device registration required", 3, 5, self.terminal.yellow)
        self.draw_text("Please register your device first in Settings", 3, 6)
        self.draw_text("Press 'r' to retry registration, 'q' to return to main menu", 3, self.height - 3, self.terminal.dim)

    def _render_registration_failed(self):
        self.draw_text("Device Status: Registration Failed", 3, 3, self.terminal.red)
        self.draw_text("⚠️  Failed to register device automatically", 3, 5, self.terminal.yellow)
        self.draw_text("This may be due to server connection issues or invalid configuration", 3, 6)
        self.draw_text("Please check your server settings and try again", 3, 7)
        self.draw_text("Press 'r' to retry registration, 's' for Settings, 'q' to go back", 3, self.height - 3, self.terminal.dim)

    def _render_error(self):
        self.draw_text("Device Status: Connection Error", 3, 3, self.terminal.red)
        self.draw_text("⚠️  Unable to connect to server", 3, 5, self.terminal.yellow)
        self.draw_text("Please check your network connection and server settings", 3, 6)
        self.draw_text("Press 'q' to return to main menu", 3, self.height - 3, self.terminal.dim)

    def _render_no_patient(self):
        device_id = self.device_data.id if self.device_data else "Unknown"
        self.draw_text(f"Device Status: Registered (ID: {device_id})", 3, 3, self.terminal.green)
        self.draw_text("Patient Status: No patient connected", 3, 4, self.terminal.yellow)
        self.draw_text("⚠️  No patient information available", 3, 6, self.terminal.yellow)
        self.draw_text("Please connect a patient to this device", 3, 7)
        self.draw_text("Press 'q' to return to main menu", 3, self.height - 3, self.terminal.dim)

    def _render_monitoring_view(self):
        if not self.patient_data:
            return
            
        device_id = self.device_data.id if self.device_data else "Unknown"
        patient_id = self.patient_data.id
        created_date = self.patient_data.createdAt.strftime("%Y-%m-%d")
        
        self.draw_text(f"Patient ID: {patient_id} | Device: {device_id} | {created_date}", 3, 2, self.terminal.cyan)
        
        caution_areas = []
        if self.patient_data.occiput: caution_areas.append("Occiput ✓")
        else: caution_areas.append("Occiput ✗")
        if self.patient_data.scapula: caution_areas.append("Scapula ✓")
        else: caution_areas.append("Scapula ✗")
        if self.patient_data.elbow: caution_areas.append("Elbow ✓")
        else: caution_areas.append("Elbow ✗")
        if self.patient_data.heel: caution_areas.append("Heel ✓")
        else: caution_areas.append("Heel ✗")
        if self.patient_data.hip: caution_areas.append("Hip ✓")
        else: caution_areas.append("Hip ✗")
        
        caution_text = "Caution Areas: " + " | ".join(caution_areas)
        self.draw_text(caution_text, 3, 3, self.terminal.yellow)
        
        self.draw_text("─" * (self.width - 6), 3, 4)
        
        mid_x = self.width // 2
        
        self.draw_text("Pressure Heatmap", 6, 6, self.terminal.bold_white)
        self.draw_text("Pressure Log Records", mid_x + 2, 6, self.terminal.bold_white)
        
        self.draw_text("│", mid_x, 5)
        for i in range(7, self.height - 3):
            self.draw_text("│", mid_x, i)
        
        if self.heatmap:
            self.heatmap.render(6, 8, mid_x - 8, 15)
            
        if self.log_table:
            self.log_table.render(mid_x + 2, 8, self.width - mid_x - 6, 15)
        
        self.draw_text("Press 'q' to quit", 3, self.height - 2, self.terminal.dim)
        self.draw_text("Press ↑↓ to scroll logs", mid_x + 2, self.height - 2, self.terminal.dim)

    def handle_input(self, key: str) -> Optional[str]:
        if KeyHandler.is_quit(key):
            return "main_menu"
        elif key.lower() == 's' and self.device_status in [DeviceStatus.SERVER_CONFIG_MISSING, DeviceStatus.REGISTRATION_FAILED]:
            return "settings"
        elif key.lower() == 'r' and self.device_status in [DeviceStatus.NOT_REGISTERED, DeviceStatus.REGISTRATION_FAILED]:
            # Retry device registration
            self.device_status = DeviceStatus.CHECKING
            self.patient_status = PatientStatus.CHECKING
            self.check_device_and_patient()
        elif self.patient_status == PatientStatus.CONNECTED and self.log_table:
            if KeyHandler.is_arrow_up(key):
                self.log_table.scroll_up()
            elif KeyHandler.is_arrow_down(key):
                self.log_table.scroll_down()
                
        return None