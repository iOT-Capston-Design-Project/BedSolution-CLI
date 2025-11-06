from datetime import date
from itertools import accumulate


class DayLog:
    def __init__(self, id: int, day: date, device_id: int, total_occiput: int, total_scapula: int, total_right_elbow: int, total_left_elbow: int, total_hip: int, total_right_heel: int, total_left_heel: int):
        self.id = id
        self.day = day
        self.device_id = device_id
        self.total_occiput = total_occiput
        self.total_scapula = total_scapula
        self.total_right_elbow = total_right_elbow
        self.total_left_elbow = total_left_elbow
        self.total_hip = total_hip
        self.total_right_heel = total_right_heel
        self.total_left_heel = total_left_heel

    @staticmethod
    def from_dict(data: dict) -> "DayLog":
        day = date.fromisoformat(data["day"])
        return DayLog(
            id=int(data["id"]),
            day=day,
            device_id=int(data["device_id"]),
            total_occiput=int(data["total_occiput"]),
            total_scapula=int(data["total_scapula"]),
            total_right_elbow=int(data["total_relbow"]),
            total_left_elbow=int(data["total_lelbow"]),
            total_hip=int(data["total_hip"]),
            total_right_heel=int(data["total_rheel"]),
            total_left_heel=int(data["total_lheel"]),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "day": self.day.isoformat(),
            "device_id": self.device_id,
            "total_occiput": self.total_occiput,
            "total_scapula": self.total_scapula,
            "total_relbow": self.total_right_elbow,
            "total_lelbow": self.total_left_elbow,
            "total_hip": self.total_hip,
            "total_rheel": self.total_right_heel,
            "total_lheel": self.total_left_heel,
        }
