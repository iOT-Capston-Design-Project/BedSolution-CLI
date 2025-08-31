from enum import Enum


class DeviceStatus(Enum):
    CHECKING = "checking"
    REGISTERING = "registering"
    REGISTERED = "registered"
    NOT_REGISTERED = "not_registered"
    NOT_FOUND = "not_found"
    REGISTRATION_FAILED = "registration_failed"
    SERVER_CONFIG_MISSING = "server_config_missing"
    ERROR = "error"


class PatientStatus(Enum):
    CHECKING = "checking"
    CONNECTED = "connected"
    NO_PATIENT = "no_patient"
    ERROR = "error"