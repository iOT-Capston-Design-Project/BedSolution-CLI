import datetime
from enum import Enum

class PostureType(Enum):
    UNKNOWN = 0
    SITTING = 1
    LEFT_SIDE = 2
    RIGHT_SIDE = 3
    SUPINE = 4
    PRONE = 5

class PressureLog:
    def __init__(self, id: int, day_id: int, createdAt: datetime.datetime, occiput: int, scapula: int, right_elbow: int, left_elbow: int, right_heel: int, left_heel: int, hip: int, posture: PostureType = PostureType.UNKNOWN, posture_change_required: bool = False):
        self.id = id
        self.day_id = day_id
        self.createdAt = createdAt
        self.occiput = occiput
        self.scapula = scapula
        self.right_elbow = right_elbow
        self.left_elbow = left_elbow
        self.hip = hip
        self.right_heel = right_heel
        self.left_heel = left_heel
        self.posture = posture
        self.posture_change_required = posture_change_required

    @staticmethod
    def from_dict(data: dict) -> "PressureLog":
        createdAt = datetime.datetime.fromisoformat(data["created_at"])
        return PressureLog(
            id=int(data["id"]),
            day_id=int(data["day_id"]),
            createdAt=createdAt,
            occiput=int(data["occiput"]),
            scapula=int(data["scapula"]),
            right_elbow=int(data["relbow"]),
            left_elbow=int(data["lelbow"]),
            right_heel=int(data["rheel"]),
            left_heel=int(data["lheel"]),
            hip=int(data["hip"]),
            posture=PostureType(data["posture_type"]),
            posture_change_required=data["posture_change_required"]
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "day_id": self.day_id,
            "created_at": self.createdAt.isoformat(),
            "occiput": self.occiput,
            "scapula": self.scapula,
            "relbow": self.right_elbow,
            "lelbow": self.left_elbow,
            "hip": self.hip,
            "rheel": self.right_heel,
            "lheel": self.left_heel,
            "posture_type": self.posture.value,
            "posture_change_required": self.posture_change_required
        }
