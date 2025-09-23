from datetime import date
from .pressure_cache import PressureCache

class DayCache:
    def __init__(
        self,
        id: int,
        date: date,
        accumulated_occiput: int,
        accumulated_scapula: int,
        accumulated_elbow: int,
        accumulated_heel: int,
        accumulated_hip: int,
        logs: list[PressureCache],
        is_new: bool = False,
    ):
        self.id = id
        self.date = date
        self.accumulated_occiput = accumulated_occiput
        self.accumulated_scapula = accumulated_scapula
        self.accumulated_elbow = accumulated_elbow
        self.accumulated_heel = accumulated_heel
        self.accumulated_hip = accumulated_hip
        self.logs = logs
        self.is_new = is_new

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "accumulated_occiput": self.accumulated_occiput,
            "accumulated_scapula": self.accumulated_scapula,
            "accumulated_elbow": self.accumulated_elbow,
            "accumulated_heel": self.accumulated_heel,
            "accumulated_hip": self.accumulated_hip,
            "is_new": self.is_new,
            "logs": [log.to_dict() for log in self.logs]
        }
    
    @staticmethod
    def from_dict(data: dict) -> "DayCache":
        return DayCache(
            id=int(data["id"]),
            date=date.fromisoformat(data["date"]),
            accumulated_occiput=int(data["accumulated_occiput"]),
            accumulated_scapula=int(data["accumulated_scapula"]),
            accumulated_elbow=int(data["accumulated_elbow"]),
            accumulated_heel=int(data["accumulated_heel"]),
            accumulated_hip=int(data["accumulated_hip"]),
            logs=[PressureCache.from_dict(log) for log in data.get("logs", [])],
            is_new=bool(data.get("is_new", False)),
        )
