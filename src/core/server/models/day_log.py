from datetime import datetime

class DayLog:
    def __init__(self, id: int, day: datetime, device_id: int, accumulated_occiput: int, accumulated_scapula: int, accumulated_elbow: int, accumulated_heel: int, accumulated_hip: int):
        self.id = id
        self.day = day
        self.device_id = device_id
        self.accumulated_occiput = accumulated_occiput
        self.accumulated_scapula = accumulated_scapula
        self.accumulated_elbow = accumulated_elbow
        self.accumulated_heel = accumulated_heel
        self.accumulated_hip = accumulated_hip

    @staticmethod
    def from_dict(data: dict) -> "DayLog":
        day = datetime.fromisoformat(data["day"])
        return DayLog(
            id=int(data["id"]),
            day=day,
            device_id=int(data["device_id"]),
            accumulated_occiput=int(data["accumulated_occiput"]),
            accumulated_scapula=int(data["accumulated_scapula"]),
            accumulated_elbow=int(data["accumulated_elbow"]),
            accumulated_heel=int(data["accumulated_heel"]),
            accumulated_hip=int(data["accumulated_hip"])
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "day": self.day.isoformat(),
            "device_id": self.device_id,
            "accumulated_occiput": self.accumulated_occiput,
            "accumulated_scapula": self.accumulated_scapula,
            "accumulated_elbow": self.accumulated_elbow,
            "accumulated_heel": self.accumulated_heel,
            "accumulated_hip": self.accumulated_hip
        }
