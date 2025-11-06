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
        right_elbow: int,
        left_elbow: int,
        right_heel: int,
        left_heel: int,
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
        self.right_elbow = right_elbow
        self.left_elbow = left_elbow
        self.hip = hip
        self.right_heel = right_heel
        self.left_heel = left_heel
        self.posture = posture
        self.posture_change_required = posture_change_required

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "time": self.time.isoformat(),
            "created_at": self.created_at.isoformat(),
            "occiput": self.occiput,
            "scapula": self.scapula,
            "relbow": self.right_elbow,
            "lelbow": self.left_elbow,
            "hip": self.hip,
            "rheel": self.right_heel,
            "lheel": self.left_heel,
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
            right_elbow=int(data["relbow"]),
            left_elbow=int(data["lelbow"]),
            hip=int(data["hip"]),
            right_heel=int(data["rheel"]),
            left_heel=int(data["lheel"]),
            posture=PostureType(data["posture"]),
            created_at=datetime.fromisoformat(created_at_raw),
            posture_change_required=bool(data.get("posture_change_required", False)),
        )

    @staticmethod
    def _generate_log_id_from_time_str(timestr: str) -> int:
        dt = datetime.fromisoformat(timestr)
        return int(dt.strftime('%Y%m%d%H%M%S'))
