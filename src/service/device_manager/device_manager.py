import uuid
from datetime import datetime
from core.server.models import DeviceData
from core.config import config_manager
from core.server import ServerAPI
import logging

class DeviceManager:
    def __init__(self, api: ServerAPI):
        self.api = api
        self.logger = logging.getLogger("DeviceRegister")

    def is_registered(self) -> bool:
        raw_device_id = config_manager.get_setting("device", "device_id", fallback=None)
        if not raw_device_id or not str(raw_device_id).strip():
            self.logger.info("No device_id stored in configuration")
            return False

        try:
            device_id = int(raw_device_id)
        except ValueError:
            self.logger.warning(f"Invalid device_id in config: {raw_device_id}")
            return False

        is_registered = device_id > 0
        self.logger.info(f"Checking registration for device_id: {device_id} -> {is_registered}")
        return is_registered
    
    def get_device_id(self) -> int:
        device_id = config_manager.get_setting("device", "device_id", fallback=None)
        if not device_id or not str(device_id).strip():
            return 0
        try:
            return int(device_id)
        except ValueError:
            self.logger.warning(f"Invalid device_id in config: {device_id}")
            return 0

    def _generate_device_id(self) -> int:
        generated = uuid.uuid4().int & 0x7FFFFFFF
        return generated if generated != 0 else 1
    
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
