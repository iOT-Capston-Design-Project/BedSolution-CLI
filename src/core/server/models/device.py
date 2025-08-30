import datetime

class DeviceData:
    def __init__(self, id: int, createdAt: datetime.datetime):
        self.id = id
        self.createdAt = createdAt

    @staticmethod
    def from_dict(data: dict) -> "DeviceData":
        createdAt = datetime.datetime.fromisoformat(data["created_at"])
        return DeviceData(
            id=int(data["id"]),
            createdAt=createdAt
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.createdAt.isoformat()
        }
