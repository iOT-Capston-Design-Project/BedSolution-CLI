import numpy as np
    
class HeatmapData:
    def __init__(self, id: int, device_id: int, data: np.ndarray):
        self.id = id
        self.device_id = device_id
        self.data = data

    @staticmethod
    def from_dict(data: dict) -> "HeatmapData":
        return HeatmapData(
            id=data["id"],
            device_id=data["device_id"],
            data=np.array(data["sensors"]).reshape((14, 7))
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "sensors": self.data.flatten().tolist()
        }