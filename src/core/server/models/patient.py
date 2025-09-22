import datetime

class Patient:
    def __init__(self, id: int, device_id: int, createdAt: datetime.datetime, occiput: int, scapula: int, elbow: int, heel: int, hip: int):
        self.id = id
        self.device_id = device_id
        self.createdAt = createdAt
        self.occiput = occiput
        self.scapula = scapula
        self.elbow = elbow
        self.heel = heel
        self.hip = hip

    @staticmethod
    def from_dict(data: dict) -> "Patient":
        createdAt = datetime.datetime.fromisoformat(data["created_at"])
        return Patient(
            id=int(data["id"]),
            createdAt=createdAt,
            device_id=int(data["device_id"] or "120"),
            occiput=int(data["occiput_time"] or "120"),
            scapula=int(data["scapula_time"] or "120"),
            elbow=int(data["elbow_time"] or "120"),
            heel=int(data["heel_time"] or "120"),
            hip=int(data["hip_time"] or "120")
        )
