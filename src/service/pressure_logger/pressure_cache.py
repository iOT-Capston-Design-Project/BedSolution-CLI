from datetime import datetime
from typing import Optional

from service.detection import PostureType


class PressureCache:
    def __init__(
        self,
        log_id: int,
        time: datetime,
        occiput: int,
        scapula: int,
        elbow: int,
        heel: int,
        hip: int,
        posture: PostureType,
        created_at: Optional[datetime] = None,
        posture_change_required: bool = False,
    ):
        self.id = log_id
        self.time = time
        self.created_at = created_at or time
        self.occiput = occiput
        self.scapula = scapula
        self.elbow = elbow
        self.heel = heel
        self.hip = hip
        self.posture = posture
        self.posture_change_required = posture_change_required

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "time": self.time.isoformat(),
            "created_at": self.created_at.isoformat(),
            "occiput": self.occiput,
            "scapula": self.scapula,
            "elbow": self.elbow,
            "heel": self.heel,
            "hip": self.hip,
            "posture": self.posture.value,
            "posture_change_required": self.posture_change_required,
        }

    @staticmethod
    def from_dict(data: dict) -> "PressureCache":
        created_at_raw = data.get("created_at") or data.get("time")
        return PressureCache(
            log_id=int(data.get("id") or PressureCache._generate_log_id_from_time_str(data["time"])),
            time=datetime.fromisoformat(data["time"]),
            occiput=int(data["occiput"]),
            scapula=int(data["scapula"]),
            elbow=int(data["elbow"]),
            heel=int(data["heel"]),
            hip=int(data["hip"]),
            posture=PostureType(data["posture"]),
            created_at=datetime.fromisoformat(created_at_raw),
            posture_change_required=bool(data.get("posture_change_required", False)),
        )

    @staticmethod
    def _generate_log_id_from_time_str(timestr: str) -> int:
        dt = datetime.fromisoformat(timestr)
        return int(dt.strftime('%Y%m%d%H%M%S'))
