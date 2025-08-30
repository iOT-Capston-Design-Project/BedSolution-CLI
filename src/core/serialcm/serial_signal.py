from datetime import datetime

class SerialSignal:
    def __init__(self, time: datetime, head: np.ndarray, body: np.ndarray):
        self.time = time
        self.head = head
        self.body = body