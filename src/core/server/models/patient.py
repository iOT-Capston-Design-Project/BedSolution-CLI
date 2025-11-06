import datetime

class Patient:
    def __init__(self, id: int, device_id: int, createdAt: datetime.datetime, occiput_threshold: int, scapula_threshold: int, right_elbow_threshold: int, left_elbow_threshold: int, hip_threshold: int, right_heel_threshold: int, left_heel_threshold: int):
        self.id = id
        self.device_id = device_id
        self.createdAt = createdAt
        self.occiput_threshold = occiput_threshold
        self.scapula_threshold = scapula_threshold
        self.right_elbow_threshold = right_elbow_threshold
        self.left_elbow_threshold = left_elbow_threshold
        self.hip_threshold = hip_threshold
        self.right_heel_threshold = right_heel_threshold
        self.left_heel_threshold = left_heel_threshold

    @staticmethod
    def from_dict(data: dict) -> "Patient":
        createdAt = datetime.datetime.fromisoformat(data["created_at"])
        return Patient(
            id=int(data["id"]),
            createdAt=createdAt,
            device_id=int(data["device_id"] or "120"),
            occiput_threshold=int(data["occiput_threshold"] or "120"),
            scapula_threshold=int(data["scapula_threshold"] or "120"),
            right_elbow_threshold=int(data["relbow_threshold"] or "120"),
            left_elbow_threshold=int(data["lelbow_threshold"] or "120"),
            hip_threshold=int(data["hip_threshold"] or "120"),
            right_heel_threshold=int(data["rheel_threshold"] or "120"),
            left_heel_threshold=int(data["lheel_threshold"] or "120"),
        )
