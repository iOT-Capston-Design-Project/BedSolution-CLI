import datetime

class PressureLog:
    def __init__(self, id: int, day_id: int, createdAt: datetime.datetime, occiput: int, scapula: int, elbow: int, heel: int, hip: int):
        self.id = id
        self.day_id = day_id
        self.createdAt = createdAt
        self.occiput = occiput
        self.scapula = scapula
        self.elbow = elbow
        self.heel = heel
        self.hip = hip

    @staticmethod
    def from_dict(data: dict) -> "PressureLog":
        createdAt = datetime.datetime.fromisoformat(data["created_at"])
        return PressureLog(
            id=int(data["id"]),
            day_id=int(data["day_id"]),
            createdAt=createdAt,
            occiput=int(data["caution_occiput"]),
            scapula=int(data["caution_scapula"]),
            elbow=int(data["caution_elbow"]),
            heel=int(data["caution_heel"]),
            hip=int(data["caution_hip"])
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "day_id": self.day_id,
            "created_at": self.createdAt.isoformat(),
            "caution_occiput": self.occiput,
            "caution_scapula": self.scapula,
            "caution_elbow": self.elbow,
            "caution_heel": self.heel,
            "caution_hip": self.hip
        }
