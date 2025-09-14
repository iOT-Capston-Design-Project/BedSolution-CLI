from .base_screen import BaseScreen
from ..utils.keyboard import KeyHandler
from ..utils.server_validator import ServerValidator
from ..components.heatmap import HeatmapComponent
from ..components.log_table import LogTableComponent
from ..enums import DeviceStatus, PatientStatus
from service.device_manager import DeviceManager
from service.signal_pipeline import SignalPipeline
from core.server import ServerAPI
from core.serialcm import SerialCommunication
from blessed import Terminal
from typing import Optional
import time
import threading
import numpy as np
from datetime import datetime

# Rich imports for Live display
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console, Group
from rich.columns import Columns
from rich.align import Align


class RunScreen(BaseScreen):
    def __init__(self, terminal: Terminal, app, server_api: ServerAPI, device_register: DeviceManager):
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
        
        # Real-time monitoring components
        self.serial_comm = None
        self.signal_pipeline = None
        self.sensor_thread = None
        self.signal_feeder_thread = None
        self.sensor_active = False
        self.monitoring_mode = False
        
        # Real-time data storage
        self.current_pressure_map = None
        self.current_parts = None
        self.current_posture = None
        self.pressure_logs = []
        self.data_lock = threading.Lock()
        
        # Rich components for live display
        self.console = Console()
        self.live_display = None
        
        # Check server configuration first
        self.server_config_valid, self.missing_server_settings = ServerValidator.validate_server_config()
        
        if self.server_config_valid and self.server_api and self.device_register:
            self.check_device_and_patient()
        elif not self.server_config_valid:
            self.device_status = DeviceStatus.SERVER_CONFIG_MISSING
    
    def _initialize_monitoring_components(self):
        """Initialize components for real-time monitoring"""
        if not self.serial_comm:
            self.serial_comm = SerialCommunication()
            device_id = self.device_register.get_device_id()
            self.signal_pipeline = SignalPipeline(self.server_api, device_id)

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

    def _start_sensor_monitoring(self):
        """Start real-time sensor monitoring"""
        self._initialize_monitoring_components()

        if self.serial_comm.start():
            self.sensor_active = True

            # Start two threads: one for feeding signals, one for processing results
            self.signal_feeder_thread = threading.Thread(
                target=self._signal_feeder_loop,
                daemon=True,
                name="SignalFeeder"
            )
            self.signal_feeder_thread.start()

            self.sensor_thread = threading.Thread(
                target=self._sensor_processing_loop,
                daemon=True,
                name="SensorProcessor"
            )
            self.sensor_thread.start()
            return True
        return False
    
    def _signal_feeder_loop(self):
        """Feed signals from serial communication to pipeline"""
        try:
            for signal in self.serial_comm.stream():
                if not self.sensor_active:
                    break
                # Feed signal to pipeline for processing
                self.signal_pipeline.process(signal)
        except Exception as e:
            print(f"Signal feeder error: {e}")
            self.sensor_active = False

    def _sensor_processing_loop(self):
        """Process results from signal pipeline and update display"""
        try:
            # Get processed results from pipeline's stream
            for heatmap, parts, posture in self.signal_pipeline.stream():
                if not self.sensor_active:
                    break

                # Update current data for display
                with self.data_lock:
                    self.current_pressure_map = heatmap
                    self.current_parts = parts
                    self.current_posture = posture

                    # Add to pressure logs
                    log_entry = {
                        'time': datetime.now().strftime("%H:%M:%S"),
                        'posture': str(posture.name if hasattr(posture, 'name') else posture),
                        'occiput': 'Yes' if not np.array_equal(parts.occiput, [-1, -1]) else 'No',
                        'scapula': 'Yes' if not np.array_equal(parts.scapula, [-1, -1]) else 'No',
                        'elbow': 'Yes' if not np.array_equal(parts.elbow, [-1, -1]) else 'No',
                        'heel': 'Yes' if not np.array_equal(parts.heel, [-1, -1]) else 'No',
                        'hip': 'Yes' if not np.array_equal(parts.hip, [-1, -1]) else 'No'
                    }
                    self.pressure_logs.append(log_entry)
                    # Keep only last 50 logs
                    if len(self.pressure_logs) > 50:
                        self.pressure_logs = self.pressure_logs[-50:]

        except Exception as e:
            print(f"Sensor processing error: {e}")
            self.sensor_active = False
    
    def _stop_sensor_monitoring(self):
        """Stop sensor monitoring and cleanup"""
        self.sensor_active = False

        # Stop signal feeder thread
        if self.signal_feeder_thread:
            self.signal_feeder_thread.join(timeout=2.0)

        # Stop sensor processing thread
        if self.sensor_thread:
            self.sensor_thread.join(timeout=2.0)

        # Stop serial communication
        if self.serial_comm:
            self.serial_comm.stop()

        # Stop signal pipeline
        if self.signal_pipeline:
            self.signal_pipeline.stop()
    
    def _create_rich_layout(self) -> Layout:
        """Create Rich layout for live display"""
        layout = Layout()
        
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=1)
        )
        
        layout["body"].split_row(
            Layout(name="heatmap", ratio=1),
            Layout(name="logs", ratio=1)
        )
        
        return layout
    
    def _generate_header_panel(self) -> Panel:
        """Generate header panel with patient info"""
        if not self.patient_data:
            return Panel("No patient connected", title="Waiting", border_style="yellow")
        
        device_id = self.device_data.id if self.device_data else "Unknown"
        patient_id = self.patient_data.id
        created_date = self.patient_data.createdAt.strftime("%Y-%m-%d")
        
        # Caution areas
        caution_areas = []
        caution_areas.append(f"[green]Occiput ✓[/]" if self.patient_data.occiput else "[red]Occiput ✗[/]")
        caution_areas.append(f"[green]Scapula ✓[/]" if self.patient_data.scapula else "[red]Scapula ✗[/]")
        caution_areas.append(f"[green]Elbow ✓[/]" if self.patient_data.elbow else "[red]Elbow ✗[/]")
        caution_areas.append(f"[green]Heel ✓[/]" if self.patient_data.heel else "[red]Heel ✗[/]")
        caution_areas.append(f"[green]Hip ✓[/]" if self.patient_data.hip else "[red]Hip ✗[/]")
        
        info_text = f"[cyan]Patient ID: {patient_id} | Device: {device_id} | {created_date}[/]\n"
        info_text += "[yellow]Caution Areas:[/] " + " | ".join(caution_areas)
        
        return Panel(Text.from_markup(info_text), title="Patient Monitoring", border_style="cyan")
    
    def _generate_heatmap_panel(self) -> Panel:
        """Generate heatmap panel"""
        if self.current_pressure_map is None:
            return Panel(
                Align.center("Waiting for sensor data...", vertical="middle"),
                title="Pressure Heatmap",
                border_style="blue"
            )
        
        with self.data_lock:
            pressure_map = self.current_pressure_map.copy()
        
        # Convert pressure map to colored text
        rows = []
        max_val = np.max(pressure_map) if np.max(pressure_map) > 0 else 1
        min_val = np.min(pressure_map)
        
        for y in range(pressure_map.shape[0]):
            row_chars = []
            for x in range(pressure_map.shape[1]):
                value = pressure_map[y, x]
                char, color = self._pressure_to_rich_char(value, min_val, max_val)
                row_chars.append(f"[{color}]{char}[/]")
            rows.append(" ".join(row_chars))
        
        heatmap_text = "\n".join(rows)
        
        # Add legend
        legend = Text.from_markup(
            "\n[blue]░[/] Low  [cyan]▒[/] Medium  [yellow]▓[/] High  [red]█[/] Very High"
        )
        
        content = Group(
            Text.from_markup(heatmap_text),
            Text(""),
            legend
        )
        
        return Panel(content, title="Pressure Heatmap", border_style="green")
    
    def _pressure_to_rich_char(self, value: float, min_val: float, max_val: float) -> tuple[str, str]:
        """Convert pressure value to Rich character and color"""
        if max_val == min_val:
            normalized = 0.5
        else:
            normalized = (value - min_val) / (max_val - min_val)
        
        if normalized < 0.2:
            return "░", "blue"
        elif normalized < 0.4:
            return "▒", "cyan"
        elif normalized < 0.6:
            return "▓", "yellow"
        elif normalized < 0.8:
            return "█", "red"
        else:
            return "█", "bright_red"
    
    def _generate_logs_table_panel(self) -> Panel:
        """Generate logs table panel"""
        table = Table(show_header=True, header_style="bold magenta")
        
        table.add_column("Time", style="cyan", no_wrap=True)
        table.add_column("Posture", style="green")
        table.add_column("Occiput", justify="center")
        table.add_column("Scapula", justify="center")
        table.add_column("Elbow", justify="center")
        table.add_column("Heel", justify="center")
        table.add_column("Hip", justify="center")
        
        # Add last 10 logs
        with self.data_lock:
            logs_to_show = self.pressure_logs[-10:] if self.pressure_logs else []
        
        for log in logs_to_show:
            table.add_row(
                log['time'],
                log['posture'],
                self._format_detection(log['occiput']),
                self._format_detection(log['scapula']),
                self._format_detection(log['elbow']),
                self._format_detection(log['heel']),
                self._format_detection(log['hip'])
            )
        
        if not logs_to_show:
            table.add_row("--:--:--", "No data", "-", "-", "-", "-", "-")
        
        return Panel(table, title="Pressure Detection Logs", border_style="blue")
    
    def _format_detection(self, detected: str) -> str:
        """Format detection status with color"""
        if detected == 'Yes':
            return "[green]●[/]"
        else:
            return "[dim]○[/]"
    
    def _generate_footer_panel(self) -> Panel:
        """Generate footer panel with instructions"""
        return Panel(
            Text.from_markup("[dim]Press 'q' to exit monitoring mode[/]"),
            border_style="dim"
        )
    
    def _run_rich_live_monitoring(self):
        """Run Rich Live monitoring display"""
        # Start sensor monitoring if not started
        if not self.sensor_active:
            if not self._start_sensor_monitoring():
                self.center_text("Failed to start sensor monitoring", self.height // 2, self.terminal.red)
                self.center_text("Press 'q' to return", self.height // 2 + 2, self.terminal.dim)
                return
        
        # Create layout
        layout = self._create_rich_layout()
        
        # Create Live display
        with Live(layout, console=self.console, screen=True, refresh_per_second=10) as live:
            self.monitoring_mode = True
            
            while self.monitoring_mode:
                # Update layout components
                layout["header"].update(self._generate_header_panel())
                layout["heatmap"].update(self._generate_heatmap_panel())
                layout["logs"].update(self._generate_logs_table_panel())
                layout["footer"].update(self._generate_footer_panel())
                
                # Check for exit key (non-blocking)
                time.sleep(0.1)
                
                # Note: In real implementation, we'd need proper keyboard handling
                # For now, monitoring_mode will be set to False by handle_input
    
    def _render_monitoring_view(self):
        # Use Rich Live display for monitoring
        self._run_rich_live_monitoring()
        return
        
        # Legacy code below (kept for reference)
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
            # Stop monitoring if active
            if self.monitoring_mode:
                self.monitoring_mode = False
                self._stop_sensor_monitoring()
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