from core.server.models import PostureType
from .base_screen import BaseScreen
from ..utils.keyboard import KeyHandler
from ..utils.server_validator import ServerValidator
from ..enums import DeviceStatus, PatientStatus
from service.device_manager import DeviceManager
from service.signal_pipeline import SignalPipeline
from core.server import ServerAPI
from core.serialcm import SerialCommunication
from blessed import Terminal
from typing import Optional
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
        self.server_config_valid = False
        self.missing_server_settings = []
        
        # Real-time monitoring components
        self.serial_comm = None
        self.signal_pipeline = None
        self.sensor_thread = None
        self.signal_feeder_thread = None
        self.sensor_active = False
        self.monitoring_mode = False
        self.monitoring_error = None
        
        # Real-time data storage
        self.current_pressure_map = None
        self.current_posture = None
        self.pressure_logs = []
        self.data_lock = threading.RLock()  # Use RLock for potential re-entrant cases
        self.max_logs_display = 10
        self.log_scroll_offset = 0
        self.log_follow_latest = True
        
        # Rich components for live display
        self.console = Console()
        self.live_display = None
        self.live_layout = None
        
        # Render coordination
        self.render_event = threading.Event()
        self.render_event.set()
        
        # Check server configuration first
        self.server_config_valid, self.missing_server_settings = ServerValidator.validate_server_config()
        if not self.server_config_valid:
            self.device_status = DeviceStatus.SERVER_CONFIG_MISSING
        
        # Defer device/patient check until the screen is rendered
        self._initial_check_pending = self.server_config_valid and bool(self.server_api and self.device_register)
        self._device_patient_thread = None
        self._device_patient_stop_event: Optional[threading.Event] = None
    
    def _initialize_monitoring_components(self) -> bool:
        """Initialize components for real-time monitoring"""
        if self.serial_comm and self.signal_pipeline:
            return True

        if not self.device_register or not self.device_register.is_registered():
            self.monitoring_error = "Device is not registered."
            return False

        device_id = self.device_register.get_device_id()
        if not device_id:
            self.monitoring_error = "Invalid device identifier."
            return False

        self.serial_comm = SerialCommunication()
        self.signal_pipeline = SignalPipeline(self.server_api, device_id)
        return True

    def check_device_and_patient(self, force: bool = False):
        if not self.server_config_valid or not self.server_api or not self.device_register:
            return

        if force:
            self._cancel_device_patient_check()
        elif self._device_patient_thread and self._device_patient_thread.is_alive():
            return

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._check_device_and_patient_async,
            args=(stop_event,),
            daemon=True,
            name="DevicePatientCheck"
        )
        self._device_patient_stop_event = stop_event
        self._device_patient_thread = thread
        thread.start()

    def _check_device_and_patient_async(self, stop_event: threading.Event):
        try:
            if stop_event.is_set():
                return

            if self.device_register.is_registered():
                device_id = self.device_register.get_device_id()
                self.device_data = self.server_api.fetch_device(device_id) if not stop_event.is_set() else None
                
                if stop_event.is_set():
                    return

                if self.device_data:
                    self.device_status = DeviceStatus.REGISTERED
                    self.patient_data = (
                        self.server_api.fetch_patient_with_device(device_id)
                        if not stop_event.is_set()
                        else None
                    )
                    
                    if self.patient_data:
                        self.patient_status = PatientStatus.CONNECTED
                        self.monitoring_error = None
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
                            self.monitoring_error = None
                        else:
                            self.patient_status = PatientStatus.NO_PATIENT
                    else:
                        self.device_status = DeviceStatus.REGISTRATION_FAILED
                else:
                    self.device_status = DeviceStatus.REGISTRATION_FAILED
        except Exception:
            self.device_status = DeviceStatus.ERROR
            self.patient_status = PatientStatus.ERROR
        finally:
            self.mark_dirty()
            if threading.current_thread() is self._device_patient_thread:
                self._device_patient_thread = None
                self._device_patient_stop_event = None

    def mark_dirty(self):
        self.render_event.set()

    def should_clear(self) -> bool:
        return not self.monitoring_mode

    def needs_periodic_render(self) -> bool:
        if self.monitoring_mode:
            return True
        if self.render_event.is_set():
            return True
        if self.device_status in (DeviceStatus.CHECKING, DeviceStatus.REGISTERING):
            return True
        if self.patient_status == PatientStatus.CHECKING:
            return True
        return False

    def render(self):
        if self.server_config_valid and self._initial_check_pending:
            self._initial_check_pending = False
            self.check_device_and_patient()

        if self.monitoring_mode and self.monitoring_error:
            self._stop_sensor_monitoring(preserve_error=True)

        if self.monitoring_mode and self.patient_status != PatientStatus.CONNECTED:
            self._stop_sensor_monitoring()

        if not self.monitoring_mode:
            self.render_event.clear()

        if (self.monitoring_mode or self.patient_status == PatientStatus.CONNECTED) and not self.monitoring_error:
            if self._render_live_monitor():
                return

        # Live monitoring not running (or failed to start) - fall back to blessed UI
        if self.monitoring_mode:
            self.monitoring_mode = False

        self.clear_screen()
        self.draw_border("RUN - Real-time Monitoring")

        if self.device_status == DeviceStatus.CHECKING:
            self.render_event.set()
            self.center_text("Checking device registration...", self.height // 2, self.terminal.yellow)
            return
        if self.device_status == DeviceStatus.REGISTERING:
            self.render_event.set()
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
        elif self.patient_status == PatientStatus.CHECKING:
            self.render_event.set()
            self.center_text("Checking patient assignment...", self.height // 2, self.terminal.yellow)
        elif self.patient_status == PatientStatus.CONNECTED:
            self._render_monitoring_unavailable()
        else:
            self.center_text(f"Unknown state: Device({getattr(self.device_status, 'value', self.device_status)}), "
                             f"Patient({getattr(self.patient_status, 'value', self.patient_status)})",
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

    def _render_monitoring_unavailable(self):
        device_id = self.device_data.id if self.device_data else "Unknown"
        message = self.monitoring_error or "Unable to start real-time monitoring."
        self.draw_text(f"Device Status: Registered (ID: {device_id})", 3, 3, self.terminal.green)
        self.draw_text("Patient Status: Connected", 3, 4, self.terminal.green)
        self.draw_text(f"⚠️  {message}", 3, 6, self.terminal.yellow)
        threshold_line = self._build_threshold_text()
        if threshold_line:
            self.draw_text(threshold_line, 3, 7, self.terminal.cyan)
        self.draw_text("Press 'r' to retry start, 'q' to return to main menu", 3, self.height - 3, self.terminal.dim)

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

    def _start_sensor_monitoring(self) -> bool:
        """Start real-time sensor monitoring"""
        if self.sensor_active:
            return True

        if not self._initialize_monitoring_components():
            return False

        if not self.serial_comm.start():
            self.monitoring_error = "Failed to connect to serial devices."
            if self.signal_pipeline:
                self.signal_pipeline.stop()
            self.serial_comm = None
            self.signal_pipeline = None
            return False

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
    
    def _signal_feeder_loop(self):
        """Feed signals from serial communication to pipeline"""
        if not self.serial_comm or not self.signal_pipeline:
            return
        try:
            for signal in self.serial_comm.stream():
                if not self.sensor_active:
                    break
                # Feed signal to pipeline for processing
                self.signal_pipeline.process(signal)
        except Exception as e:
            print(f"Signal feeder error: {e}")
            self.sensor_active = False
            self.monitoring_error = str(e)
            self.mark_dirty()

    def _posture_to_str(self, type: PostureType, left_leg: bool, right_leg: bool) -> str:
        match type:
            case PostureType.SUPINE:
                if left_leg and right_leg: 
                    return "정자세"
                elif left_leg:
                    return "정자세 (좌)"
                elif left_leg:
                    return "정자세 (우)"
                else:
                    return "정자세 (다리접음)"
            case PostureType.LEFT_SIDE:
                return "좌눕기"
            case PostureType.RIGHT_SIDE:
                return "우눕기"
            case PostureType.PRONE:
                return "엎드림"
            case PostureType.SITTING:
                return "앉음"
            case _:
                return "없음"
        

    def _sensor_processing_loop(self):
        """Process results from signal pipeline and update display"""
        if not self.signal_pipeline:
            return
        try:
            # Get processed results from pipeline's stream
            for heatmap, posture, timestamp in self.signal_pipeline.stream():
                if not self.sensor_active:
                    break

                # Prepare log entry outside of lock
                log_entry = {
                    'time': timestamp.strftime("%H:%M:%S"),
                    'posture': self._posture_to_str(posture.type, posture.left_leg, posture.right_leg),
                    'occiput': 'Yes' if posture.occiput else 'No',
                    'scapula': 'Yes' if posture.scapula else 'No',
                    'elbow': 'Yes' if posture.elbow else 'No',
                    'heel': 'Yes' if posture.heel else 'No',
                    'hip': 'Yes' if posture.hip else 'No'
                }

                # Minimize lock hold time - just update references
                with self.data_lock:
                    self.current_pressure_map = heatmap
                    self.current_posture = posture
                    self.pressure_logs.append(log_entry)

                    # Keep only last 50 logs
                    if len(self.pressure_logs) > 50:
                        self.pressure_logs = self.pressure_logs[-50:]

                    max_offset = max(0, len(self.pressure_logs) - self.max_logs_display)
                    if self.log_follow_latest or max_offset == 0:
                        self.log_scroll_offset = 0
                        self.log_follow_latest = True
                    else:
                        self.log_scroll_offset = min(self.log_scroll_offset, max_offset)

                self.mark_dirty()

        except Exception as e:
            print(f"Sensor processing error: {e}")
            self.sensor_active = False
            self.monitoring_error = str(e)
            self.mark_dirty()
    
    def _stop_sensor_monitoring(self, preserve_error: bool = False):
        """Stop sensor monitoring and cleanup"""
        self.sensor_active = False

        # Stop background services first so worker threads exit promptly
        if self.signal_pipeline:
            self.signal_pipeline.stop()

        if self.serial_comm:
            self.serial_comm.stop()

        # Stop signal feeder thread
        if self.signal_feeder_thread:
            self.signal_feeder_thread.join(timeout=2.0)
            self.signal_feeder_thread = None

        # Stop sensor processing thread
        if self.sensor_thread:
            self.sensor_thread.join(timeout=2.0)
            self.sensor_thread = None
        
        # Reset monitoring state
        self.serial_comm = None
        self.signal_pipeline = None
        self.monitoring_mode = False
        if not preserve_error:
            self.monitoring_error = None

        if self.live_display:
            self.live_display.stop()
            self.live_display = None
            self.live_layout = None

        # Clear cached data to avoid stale display
        with self.data_lock:
            self.current_pressure_map = None
            self.current_posture = None

        self.mark_dirty()
    
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

    def _update_live_layout(self):
        if not self.live_layout:
            return

        self.live_layout["header"].update(self._generate_header_panel())
        self.live_layout["heatmap"].update(self._generate_heatmap_panel())
        self.live_layout["logs"].update(self._generate_logs_table_panel())
        self.live_layout["footer"].update(self._generate_footer_panel())
    
    def _format_threshold_value(self, raw_value) -> tuple[str, bool]:
        """Return a human-readable threshold and whether it is active."""
        try:
            minutes = int(raw_value)
        except (TypeError, ValueError):
            return "Unknown", False

        if minutes <= 0:
            return "Off", False

        hours, remainder = divmod(minutes, 60)
        if hours and remainder:
            return f"{hours}h {remainder:02d}m", True
        if hours:
            return f"{hours}h", True
        return f"{remainder}m", True

    def _build_threshold_markup(self) -> Optional[str]:
        if not self.patient_data:
            return None

        thresholds = [
            ("Occiput", getattr(self.patient_data, "occiput", None)),
            ("Scapula", getattr(self.patient_data, "scapula", None)),
            ("Elbow", getattr(self.patient_data, "elbow", None)),
            ("Heel", getattr(self.patient_data, "heel", None)),
            ("Hip", getattr(self.patient_data, "hip", None)),
        ]

        parts = []
        for label, raw_value in thresholds:
            value_text, is_active = self._format_threshold_value(raw_value)
            if is_active:
                parts.append(f"[green]{label}: {value_text}[/]")
            else:
                parts.append(f"[dim]{label}: {value_text}[/]")

        return " | ".join(parts)

    def _build_threshold_text(self) -> Optional[str]:
        if not self.patient_data:
            return None

        thresholds = [
            ("Occiput", getattr(self.patient_data, "occiput", None)),
            ("Scapula", getattr(self.patient_data, "scapula", None)),
            ("Elbow", getattr(self.patient_data, "elbow", None)),
            ("Heel", getattr(self.patient_data, "heel", None)),
            ("Hip", getattr(self.patient_data, "hip", None)),
        ]

        parts = []
        for label, raw_value in thresholds:
            value_text, _ = self._format_threshold_value(raw_value)
            parts.append(f"{label}: {value_text}")

        return "Thresholds: " + " | ".join(parts)

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

        threshold_markup = self._build_threshold_markup()
        if threshold_markup:
            info_text += f"\n[magenta]Thresholds:[/] {threshold_markup}"
        
        return Panel(Text.from_markup(info_text), title="Patient Monitoring", border_style="cyan")
    
    def _generate_heatmap_panel(self) -> Panel:
        """Generate heatmap panel"""
        if self.current_pressure_map is None:
            return Panel(
                Align.center("Waiting for sensor data...", vertical="middle"),
                title="Pressure Heatmap",
                border_style="blue"
            )

        # Quick reference grab - minimize lock time
        with self.data_lock:
            pressure_map = self.current_pressure_map

        # Copy outside of lock if needed
        if pressure_map is not None:
            pressure_map = pressure_map.copy()
        
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
        elif normalized < 0.3:
            return "▒", "cyan"
        elif normalized < 0.5:
            return "▓", "yellow"
        elif normalized < 0.7:
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
        
        with self.data_lock:
            total_logs = len(self.pressure_logs)
            logs_to_show = []
            visible_range = (0, 0)

            if total_logs:
                max_offset = max(0, total_logs - self.max_logs_display)
                offset = min(self.log_scroll_offset, max_offset)
                end_index = total_logs - offset
                start_index = max(0, end_index - self.max_logs_display)
                logs_to_show = self.pressure_logs[start_index:end_index]
                visible_range = (start_index + 1, end_index)
        
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

        panel = Panel(table, title="Pressure Detection Logs", border_style="blue")

        if total_logs > self.max_logs_display:
            start, end = visible_range
            scroll_info = f"({start}-{end} of {total_logs})"
            table.caption = scroll_info
            table.caption_style = "dim"

        return panel
    
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
    
    def _render_live_monitor(self) -> bool:
        """Update or start the Rich live monitoring display."""
        if not self.sensor_active and not self._start_sensor_monitoring():
            self.render_event.set()
            return False

        if not self.live_layout:
            self.live_layout = self._create_rich_layout()

        if not self.live_display:
            self.live_display = Live(
                self.live_layout,
                console=self.console,
                screen=True,
                refresh_per_second=10,
            )
            self.live_display.start()

        self.monitoring_mode = True
        self.monitoring_error = None

        try:
            self._update_live_layout()
            self.live_display.update(self.live_layout)
        except Exception as exc:
            self.monitoring_error = f"Display error: {exc}"
            self._stop_sensor_monitoring()
            self.render_event.set()
            return False

        return True
    
    def handle_input(self, key: str) -> Optional[str]:
        if KeyHandler.is_quit(key):
            self._cleanup_on_exit()
            return "main_menu"
        elif key.lower() == 's' and self.device_status in [DeviceStatus.SERVER_CONFIG_MISSING, DeviceStatus.REGISTRATION_FAILED]:
            self._cleanup_on_exit()
            return "settings"
        elif key.lower() == 'r':
            if self.device_status in [DeviceStatus.NOT_REGISTERED, DeviceStatus.REGISTRATION_FAILED]:
                # Retry device registration
                self.device_status = DeviceStatus.CHECKING
                self.patient_status = PatientStatus.CHECKING
                self.mark_dirty()
                self.check_device_and_patient(force=True)
            elif self.patient_status == PatientStatus.CONNECTED and not self.monitoring_mode:
                # Retry starting monitoring after a failure
                self.monitoring_error = None
                with self.data_lock:
                    self.log_scroll_offset = 0
                    self.log_follow_latest = True
                self.mark_dirty()
        elif self.patient_status == PatientStatus.CONNECTED:
            if KeyHandler.is_arrow_up(key):
                with self.data_lock:
                    max_offset = max(0, len(self.pressure_logs) - self.max_logs_display)
                    if max_offset > 0:
                        self.log_scroll_offset = min(self.log_scroll_offset + 1, max_offset)
                        if self.log_scroll_offset > 0:
                            self.log_follow_latest = False
                self.mark_dirty()
            elif KeyHandler.is_arrow_down(key):
                with self.data_lock:
                    if self.log_scroll_offset > 0:
                        self.log_scroll_offset -= 1
                    if self.log_scroll_offset == 0:
                        self.log_follow_latest = True
                self.mark_dirty()
                
        return None

    def _cleanup_on_exit(self):
        self._initial_check_pending = self.server_config_valid and bool(self.server_api and self.device_register)
        self._cancel_device_patient_check()
        if self.monitoring_mode or self.sensor_active:
            self.monitoring_mode = False
            self._stop_sensor_monitoring()

    def _cancel_device_patient_check(self):
        if self._device_patient_stop_event:
            self._device_patient_stop_event.set()
        thread = self._device_patient_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        self._device_patient_thread = None
        self._device_patient_stop_event = None
