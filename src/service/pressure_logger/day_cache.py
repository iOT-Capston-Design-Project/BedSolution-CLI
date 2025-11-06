from datetime import date
from .pressure_cache import PressureCache

class DayCache:
    def __init__(
        self,
        id: int,
        date: date,
        total_occiput: int,
        total_scapula: int,
        total_right_elbow: int,
        total_left_elbow: int,
        total_hip: int,
        total_right_heel: int,
        total_left_heel: int,
        logs: list[PressureCache],
        is_new: bool = False,
    ):
        self.id = id
        self.date = date
        self.total_occiput = total_occiput
        self.total_scapula = total_scapula
        self.total_right_elbow = total_right_elbow
        self.total_left_elbow = total_left_elbow
        self.total_hip = total_hip
        self.total_right_heel = total_right_heel
        self.total_left_heel = total_left_heel
        self.logs = logs
        self.is_new = is_new

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "total_occiput": self.total_occiput,
            "total_scapula": self.total_scapula,
            "total_relbow": self.total_right_elbow,
            "total_lelbow": self.total_left_elbow,
            "total_hip": self.total_hip,
            "total_rheel": self.total_right_heel,
            "total_lheel": self.total_left_heel,
            "is_new": self.is_new,
            "logs": [log.to_dict() for log in self.logs]
        }
    
    @staticmethod
    def from_dict(data: dict) -> "DayCache":
        return DayCache(
            id=int(data["id"]),
            date=date.fromisoformat(data["date"]),
            total_occiput=int(data["total_occiput"]),
            total_scapula=int(data["total_scapula"]),
            total_right_elbow=int(data["total_relbow"]),
            total_left_elbow=int(data["total_lelbow"]),
            total_hip=int(data["total_hip"]),
            total_right_heel=int(data["total_rheel"]),
            total_left_heel=int(data["total_lheel"]),
            logs=[PressureCache.from_dict(log) for log in data.get("logs", [])],
            is_new=bool(data.get("is_new", False)),
        )
