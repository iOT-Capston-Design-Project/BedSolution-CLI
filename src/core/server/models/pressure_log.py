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
    def __init__(self, id: int, day_id: int, createdAt: datetime.datetime, occiput: int, scapula: int, elbow: int, heel: int, hip: int, posture: PostureType = PostureType.UNKNOWN):
        self.id = id
        self.day_id = day_id
        self.createdAt = createdAt
        self.occiput = occiput
        self.scapula = scapula
        self.elbow = elbow
        self.heel = heel
        self.hip = hip
        self.posture = posture

    @staticmethod
    def from_dict(data: dict) -> "PressureLog":
        createdAt = datetime.datetime.fromisoformat(data["created_at"])
        return PressureLog(
            id=int(data["id"]),
            day_id=int(data["day_id"]),
            createdAt=createdAt,
            occiput=int(data["occiput"]),
            scapula=int(data["scapula"]),
            elbow=int(data["elbow"]),
            heel=int(data["heel"]),
            hip=int(data["hip"]),
            posture=PostureType(data["posture_type"])
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "day_id": self.day_id,
            "created_at": self.createdAt.isoformat(),
            "occiput": self.occiput,
            "scapula": self.scapula,
            "elbow": self.elbow,
            "heel": self.heel,
            "hip": self.hip,
            "posture_type": self.posture.value
        }
