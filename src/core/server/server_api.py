import logging
from typing import Optional
from supabase import create_client, Client

from core.server.models import DayLog, DeviceData, Patient, PressureLog
from core.config_manager import config_manager


class ServerAPI:
    def __init__(self):
        self.supabase_url = config_manager.get_setting("supabase", "url")
        self.supabase_key = config_manager.get_setting("supabase", "api_key")
        self.server_logger = logging.getLogger("server_api")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Supabase URL and API key must be configured")
            
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)

    def fetch_device(self, device_id: str) -> Optional[DeviceData]:
        try:
            self.server_logger.info(f"Fetching device with id: {device_id}")
            response = self.supabase.table("devices").select("*").eq("id", device_id).execute()
            if response.data:
                self.server_logger.info(f"Device found: {device_id}")
                return DeviceData.from_dict(response.data[0])
            self.server_logger.warning(f"Device not found: {device_id}")
            return None
        except Exception as e:
            self.server_logger.error(f"Error fetching device {device_id}: {e}")
            return None
    
    def create_device(self, device: DeviceData) -> DeviceData:
        try:
            self.server_logger.info(f"Creating device with id: {device.id}")
            response = self.supabase.table("devices").insert(device.to_dict()).execute()
            if response.data:
                self.server_logger.info(f"Device created successfully: {device.id}")
                return DeviceData.from_dict(response.data[0])
            self.server_logger.warning(f"Device creation returned no data: {device.id}")
            return device
        except Exception as e:
            self.server_logger.error(f"Error creating device {device.id}: {e}")
            return device

    def remove_device(self, device_id: str) -> bool:
        try:
            self.server_logger.info(f"Removing device with id: {device_id}")
            response = self.supabase.table("devices").delete().eq("id", device_id).execute()
            success = len(response.data) > 0
            if success:
                self.server_logger.info(f"Device removed successfully: {device_id}")
            else:
                self.server_logger.warning(f"No device found to remove: {device_id}")
            return success
        except Exception as e:
            self.server_logger.error(f"Error removing device {device_id}: {e}")
            return False

    def fetch_patient_with_device(self, device_id: str) -> Optional[Patient]:
        try:
            self.server_logger.info(f"Fetching patient with device_id: {device_id}")
            response = self.supabase.table("patients").select("*").eq("device_id", device_id).execute()
            if response.data:
                self.server_logger.info(f"Patient found for device: {device_id}")
                return Patient.from_dict(response.data[0])
            self.server_logger.warning(f"No patient found for device: {device_id}")
            return None
        except Exception as e:
            self.server_logger.error(f"Error fetching patient with device {device_id}: {e}")
            return None

    def create_daylog(self, daylog: DayLog) -> DayLog:
        try:
            self.server_logger.info(f"Creating daylog for device: {daylog.device_id}, day: {daylog.day}")
            response = self.supabase.table("day_logs").insert(daylog.to_dict()).execute()
            if response.data:
                self.server_logger.info(f"Daylog created successfully: {daylog.id}")
                return DayLog.from_dict(response.data[0])
            self.server_logger.warning(f"Daylog creation returned no data for device: {daylog.device_id}")
            return daylog
        except Exception as e:
            self.server_logger.error(f"Error creating daylog for device {daylog.device_id}: {e}")
            return daylog

    def update_daylog(self, daylog: DayLog) -> DayLog:
        try:
            self.server_logger.info(f"Updating daylog: {daylog.id}")
            response = self.supabase.table("day_logs").update(daylog.to_dict()).eq("id", daylog.id).execute()
            if response.data:
                self.server_logger.info(f"Daylog updated successfully: {daylog.id}")
                return DayLog.from_dict(response.data[0])
            self.server_logger.warning(f"Daylog update returned no data: {daylog.id}")
            return daylog
        except Exception as e:
            self.server_logger.error(f"Error updating daylog {daylog.id}: {e}")
            return daylog

    def fetch_daylogs(self) -> list[DayLog]:
        try:
            self.server_logger.info("Fetching all daylogs")
            response = self.supabase.table("day_logs").select("*").execute()
            daylogs = [DayLog.from_dict(data) for data in response.data]
            self.server_logger.info(f"Found {len(daylogs)} daylogs")
            return daylogs
        except Exception as e:
            self.server_logger.error(f"Error fetching daylogs: {e}")
            return []

    def create_pressurelog(self, pressurelog: PressureLog) -> PressureLog:
        try:
            self.server_logger.info(f"Creating pressurelog for day: {pressurelog.day_id}")
            response = self.supabase.table("pressure_logs").insert(pressurelog.to_dict()).execute()
            if response.data:
                self.server_logger.info(f"Pressurelog created successfully: {pressurelog.id}")
                return PressureLog.from_dict(response.data[0])
            self.server_logger.warning(f"Pressurelog creation returned no data for day: {pressurelog.day_id}")
            return pressurelog
        except Exception as e:
            self.server_logger.error(f"Error creating pressurelog for day {pressurelog.day_id}: {e}")
            return pressurelog

    def fetch_pressurelogs(self, day_id: int) -> list[PressureLog]:
        try:
            self.server_logger.info(f"Fetching pressurelogs for day: {day_id}")
            response = self.supabase.table("pressure_logs").select("*").eq("day_id", day_id).execute()
            pressurelogs = [PressureLog.from_dict(data) for data in response.data]
            self.server_logger.info(f"Found {len(pressurelogs)} pressurelogs for day: {day_id}")
            return pressurelogs
        except Exception as e:
            self.server_logger.error(f"Error fetching pressurelogs for day {day_id}: {e}")
            return []
    