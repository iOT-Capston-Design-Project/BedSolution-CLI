from .base_screen import BaseScreen
from ..utils.keyboard import KeyHandler
from ..components.heatmap import HeatmapComponent
from ..components.log_table import LogTableComponent
from blessed import Terminal
from typing import Optional
import time
import threading


class RunScreen(BaseScreen):
    def __init__(self, terminal: Terminal, app, server_api, device_register):
        super().__init__(terminal)
        self.app = app
        self.server_api = server_api
        self.device_register = device_register
        self.device_data = None
        self.patient_data = None
        self.device_status = "checking"
        self.patient_status = "checking"
        self.heatmap = None
        self.log_table = None
        self.last_update = time.time()
        
        if self.server_api and self.device_register:
            self.check_device_and_patient()

    def check_device_and_patient(self):
        threading.Thread(target=self._check_device_and_patient_async, daemon=True).start()

    def _check_device_and_patient_async(self):
        try:
            if self.device_register.is_registered():
                device_id = self.device_register.config_manager.get_setting("device", "device_id")
                self.device_data = self.server_api.fetch_device(device_id)
                
                if self.device_data:
                    self.device_status = "registered"
                    self.patient_data = self.server_api.fetch_patient_with_device(device_id)
                    
                    if self.patient_data:
                        self.patient_status = "connected"
                        self.heatmap = HeatmapComponent(self.terminal)
                        self.log_table = LogTableComponent(self.terminal)
                    else:
                        self.patient_status = "no_patient"
                else:
                    self.device_status = "not_found"
            else:
                self.device_status = "not_registered"
        except Exception as e:
            self.device_status = "error"

    def render(self):
        self.clear_screen()
        self.draw_border("RUN - Real-time Monitoring")
        
        if self.device_status == "checking":
            self.center_text("Checking device registration...", self.height // 2, self.terminal.yellow)
            return
            
        if self.device_status == "not_registered":
            self._render_device_not_registered()
        elif self.device_status == "error":
            self._render_error()
        elif self.patient_status == "no_patient":
            self._render_no_patient()
        elif self.patient_status == "connected":
            self._render_monitoring_view()
        else:
            self.center_text("Loading...", self.height // 2, self.terminal.yellow)

    def _render_device_not_registered(self):
        self.draw_text("Device Status: Not Registered", 3, 3, self.terminal.red)
        self.draw_text("⚠️  Device registration required", 3, 5, self.terminal.yellow)
        self.draw_text("Please register your device first in Settings", 3, 6)
        self.draw_text("Press 'q' to return to main menu", 3, self.height - 3, self.terminal.dim)

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
        elif self.patient_status == "connected" and self.log_table:
            if KeyHandler.is_arrow_up(key):
                self.log_table.scroll_up()
            elif KeyHandler.is_arrow_down(key):
                self.log_table.scroll_down()
                
        return None