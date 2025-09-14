import uuid
from datetime import datetime
from core.server.models import DeviceData
from core.config import config_manager
from core.server import ServerAPI
import logging

class DeviceManager:
    def __init__(self, api: ServerAPI):
        self.api = api
        self.logger = logging.Logger("DeviceRegister")

    def is_registered(self) -> bool:
        device_id = config_manager.get_setting("device", "device_id", fallback=None)
        self.logger.info(f"Checking registration for device_id: {device_id}")
        return device_id is not None
    
    def get_device_id(self) -> int:
        device_id = config_manager.get_setting("device", "device_id", fallback=None)
        return int(device_id) if device_id is not None else 0

    def _generate_device_id(self) -> int:
        id = uuid.uuid4()
        return id.int & 0xFF - 128
    
    def register_device(self) -> bool:
        if self.is_registered():
            return True
        device_id = self._generate_device_id()
        try:
            result = self.api.create_device(device=DeviceData(device_id, datetime.now()))
            if result:
                config_manager.update_setting("device", "device_id", str(device_id))
                self.logger.info(f"Device registered successfully: {device_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error registering device: {e}")
        self.logger.error("Device registration failed")
        return False
    
    def unregister_device(self) -> bool:
        if not self.is_registered():
            return True
        
        device_id = self.get_device_id()
        try:
            result = self.api.remove_device(device_id)
            if result:
                config_manager.remove_setting("device", "device_id")
                self.logger.info(f"Device unregistered successfully: {device_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error unregistering device: {e}")
        
        self.logger.error("Device unregistration failed")
        return False
