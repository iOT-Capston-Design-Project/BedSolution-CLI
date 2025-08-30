import datetime

class Patient:
    def __init__(self, id: int, device_id: int, createdAt: datetime.datetime, occiput: bool, scapula: bool, elbow: bool, heel: bool, hip: bool):
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
            device_id=int(data["device_id"]),
            occiput=bool(data["caution_occiput"]),
            scapula=bool(data["caution_scapula"]),
            elbow=bool(data["caution_elbow"]),
            heel=bool(data["caution_heel"]),
            hip=bool(data["caution_hip"])
        )
