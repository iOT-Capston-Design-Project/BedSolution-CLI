from datetime import datetime
from service.detection import PostureType

class PressureCache:
    def __init__(self, time: datetime, occiput: int, scapula: int, elbow: int, heel: int, hip: int, posture: PostureType):
        self.time = time
        self.occiput = occiput
        self.scapula = scapula
        self.elbow = elbow
        self.heel = heel
        self.hip = hip
        self.posture = posture

    def to_dict(self) -> dict:
        return {
            "time": self.time.isoformat(),
            "occiput": self.occiput,
            "scapula": self.scapula,
            "elbow": self.elbow,
            "heel": self.heel,
            "hip": self.hip,
            "posture": self.posture.value
        }
    
    @staticmethod
    def from_dict(data: dict) -> "PressureCache":
        return PressureCache(
            time=datetime.fromisoformat(data["time"]),
            occiput=int(data["occiput"]),
            scapula=int(data["scapula"]),
            elbow=int(data["elbow"]),
            heel=int(data["heel"]),
            hip=int(data["hip"]),
            posture=PostureType(data["posture"])
        )