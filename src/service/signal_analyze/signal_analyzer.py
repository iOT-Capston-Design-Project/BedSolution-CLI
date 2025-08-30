from datetime import datetime
from typing import Optional
from src.service.signal_analyze.parts_detection import PartsDetector, PartPositions
from src.service.signal_analyze.posture_detection import PostureDetector, PostureType
import numpy as np
from scipy.interpolate import RectBivariateSpline
from enum import Enum

class InterpolationMethod(Enum):
    LINEAR = 'linear'
    CUBIC = 'cubic'
    QUINTIC = 'quintic'

class AnalyzeResult:
    def __init__(self, time: datetime, map: np.ndarray, parts: PartPositions, posture: PostureType):
        self.map = map
        self.parts = parts
        self.posture = posture

class SignalAnalyzer:
    def __init__(self):
        self.parts_detector = PartsDetector()
        self.posture_detector = PostureDetector()

    def _resize_with_interpolation(self, array: np.ndarray, target_size: tuple[int, int], 
                                 method: InterpolationMethod = InterpolationMethod.LINEAR) -> np.ndarray:
        current_rows, current_cols = array.shape
        target_rows, target_cols = target_size
        
        if current_rows == target_rows and current_cols == target_cols:
            return array
        
        # Create coordinate grids for original array
        x_orig = np.linspace(0, 1, current_cols)
        y_orig = np.linspace(0, 1, current_rows)
        
        # Create coordinate grids for target array
        x_new = np.linspace(0, 1, target_cols)
        y_new = np.linspace(0, 1, target_rows)
        
        # Create interpolation function
        if method == InterpolationMethod.LINEAR:
            kx = ky = 1
        elif method == InterpolationMethod.CUBIC:
            kx = ky = 3
        else:  # QUINTIC
            kx = ky = 5
            
        interp_func = RectBivariateSpline(y_orig, x_orig, array, kx=kx, ky=ky)
        
        # Generate resized array
        resized_array = interp_func(y_new, x_new)
        
        return resized_array

    def _merge(self, head: np.ndarray, body: np.ndarray, size: tuple[int, int], 
              interpolation_method: InterpolationMethod = InterpolationMethod.LINEAR) -> np.ndarray:
        target_rows, target_cols = size
        head_rows, head_cols = head.shape
        body_rows, body_cols = body.shape
        
        max_cols = max(head_cols, body_cols)
        total_rows = head_rows + body_rows
        
        if target_cols < max_cols or target_rows < total_rows:
            raise ValueError(f"Target size {size} must be at least ({total_rows}, {max_cols})")
        
        head_ratio = head_rows / total_rows
        new_head_rows = int(target_rows * head_ratio)
        new_body_rows = target_rows - new_head_rows  
        resized_head = self._resize_with_interpolation(head, (new_head_rows, target_cols), interpolation_method)
        resized_body = self._resize_with_interpolation(body, (new_body_rows, target_cols), interpolation_method)
        
        merged = np.concatenate((resized_head, resized_body), axis=0)
        
        return merged

    def analyze(self, date: datetime, head: np.ndarray, body: np.ndarray, size: Optional[tuple[int, int]] = None, 
               interpolation_method: InterpolationMethod = InterpolationMethod.LINEAR) -> AnalyzeResult:
        if size is None:
            size = (head.shape[0] + body.shape[0], max(head.shape[1], body.shape[1]))

        merged = self._merge(head, body, size, interpolation_method)
        parts = self.parts_detector.detect(merged)
        posture = self.posture_detector.detect(merged)

        return AnalyzeResult(
            time=date,
            map=merged,
            parts=parts,
            posture=posture
        )