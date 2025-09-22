from firebase_admin import messaging, credentials, initialize_app
from logging import getLogger
import os

class NotificationManager:
    firebase_app = None

    def __init__(self):
        self.logger = getLogger(__name__)
        self._initialize_firebase()

    def _initialize_firebase(self):
        if NotificationManager.firebase_app:
            return
        cred_path = os.path.join(os.path.dirname(__file__), 'firebase-adminsdk.json')
        if not os.path.exists(cred_path):
            self.logger.error(f"Firebase credential file not found at {cred_path}")
            return
        cred = credentials.Certificate(cred_path)
        NotificationManager.firebase_app = initialize_app(cred)
        self.logger.info("Firebase app initialized.")


    def _generate_body_message(self, occiput: bool, scapula: bool, elbow: bool, heel: bool, hip: bool) -> str:
        issues = []
        if occiput:
            issues.append("후두부")
        if scapula:
            issues.append("견갑골")
        if elbow:
            issues.append("팔꿈치")
        if heel:
            issues.append("발뒤꿈치")
        if hip:
            issues.append("엉덩이")
        
        if not issues:
            return "No posture issues detected."
        
        return "압력 초과 부위: " + ", ".join(issues)
    
    def _send(self, body: str, device_id: str):
        if not NotificationManager.firebase_app:
            self.logger.error("Firebase app is not initialized. Cannot send notification.")
            return
        
        topic = f"{device_id}"
        message = messaging.Message(
            notification=messaging.Notification(
                title="압력 경고",
                body=body
            ),
            topic=topic
        )
        response = messaging.send(message=message)
        self.logger.info(f"Successfully sent message: {response}")

    def send_notification(self, device_id: str, occiput: bool, scapula: bool, elbow: bool, heel: bool, hip: bool):
        message = self._generate_body_message(occiput, scapula, elbow, heel, hip)
        self._send(message, device_id)