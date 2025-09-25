import numpy as np
from core.server.models import PostureType
from joblib import load
from logging import getLogger
from sklearn.preprocessing import MinMaxScaler
from sklearn.multioutput import MultiOutputClassifier
from typing import Optional
import os

class PostureDetectionResult:
    def __init__(self, type: PostureType, occiput: bool, scapula: bool, elbow: bool, heel: bool, hip: bool):
        self.type = type
        self.occiput = occiput
        self.scapula = scapula
        self.elbow = elbow
        self.heel = heel
        self.hip = hip

class PostureDetector:
    scaler: Optional[MinMaxScaler] = None
    predictor: Optional[MultiOutputClassifier] = None
    
    def __init__(self):
        self.logger = getLogger('PostureDetector')

    def _load_models(self) -> bool:
        if PostureDetector.scaler and PostureDetector.predictor:
           return True
        model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
        scaler_path = os.path.join(model_dir, 'scaler.pkl')
        predictor_path = os.path.join(model_dir, 'posture.pkl')

        if not os.path.exists(scaler_path) or not os.path.exists(predictor_path):
            self.logger.error("Model files not exit")
            return False
        
        PostureDetector.scaler = load(scaler_path)
        PostureDetector.predictor = load(predictor_path)

        return True

    # (16, 7)를 -> (1, 90)로 변경 (2행씩 묶어서 진행)
    def _convert(self, heatmap: np.ndarray) -> np.ndarray:
        head = heatmap[0:2, [0,3,6]].flatten().reshape(1,6) # 2x3으로 변경 -> 1x6으로 변경
        body = heatmap[2:14, :].flatten().reshape(1,84) # 12x7 -> 1x84로 변경

        return np.concatenate([head, body], axis=1)


    def detect(self, map: np.ndarray) -> PostureDetectionResult:
        if not self._load_models():
            self.logger.error('Models cant be loaded')
            return PostureDetectionResult(PostureType.UNKNOWN, False, False, False, False, False)

        raw = self._convert(map)
        scaled = PostureDetector.scaler.transform(raw)
        prediction = PostureDetector.predictor.predict(scaled)[0]
        posture = prediction[0]
        risky_part_flags = prediction[1:]
        upper_body, right_leg, left_leg, feet = risky_part_flags[0], risky_part_flags[1], risky_part_flags[2], risky_part_flags[3]

        result = PostureDetectionResult(
            PostureType.UNKNOWN, 
            False,
            upper_body,
            upper_body,
            feet,
            False
        )
        self.logger.debug(f"Posture: {posture}, Occiput: True, Scapula: {upper_body}, Elbow: {upper_body}, Heel: {feet}, Hip: False")
        match posture:
            case 0: # 정자세
                result.type = PostureType.SUPINE
                result.occiput = True
                result.scapula = True
                result.hip = True
            case 1: # 측면왼
                result.type = PostureType.LEFT_SIDE
                result.elbow = True
                result.heel = True
            case 2: # 측면오
                result.type = PostureType.RIGHT_SIDE
                result.elbow = True
                result.heel = True
            case 3: # 엎드림
                result.type = PostureType.PRONE
            case 5: # 앉음
                result.type = PostureType.SITTING
                result.hip = True

        return result