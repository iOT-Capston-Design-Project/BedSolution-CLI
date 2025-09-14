import numpy as np
from typing import List, Tuple, Any
from core.config.config_manager import config_manager

class PartPositions:
    def __init__(self, occiput: np.ndarray, scapula: np.ndarray, elbow: np.ndarray, heel: np.ndarray, hip: np.ndarray):
        self.occiput = occiput
        self.scapula = scapula
        self.elbow = elbow
        self.heel = heel
        self.hip = hip

class _PressureComponent:
    def __init__(self, center: np.ndarray, size: int, max_pressure: float):
        self.center = center
        self.size = size
        self.max_pressure = max_pressure
        self.y_pos = float(center[0])
        self.x_pos = float(center[1])

class PartsDetector:
    def __init__(self):
        min_pressure_setting = config_manager.get_setting('parts_detection', 'min_pressure')
        self.min_pressure = float(min_pressure_setting if min_pressure_setting is not None else '100')

        max_pressure_setting = config_manager.get_setting('parts_detection', 'max_pressure')
        self.max_pressure = float(max_pressure_setting if max_pressure_setting is not None else '900')
        
        percentile_p_setting = config_manager.get_setting('parts_detection', 'percentile_p')
        self.percentile_p = float(percentile_p_setting if percentile_p_setting is not None else '70.0')

    def _normalize_pressure_map(self, map: np.ndarray) -> np.ndarray:
        pressure_map = np.copy(map)
        pressure_map[pressure_map < self.min_pressure] = 0
        pressure_map[pressure_map > self.max_pressure] = self.max_pressure
        return pressure_map
    
    def _find_high_pressure_regions(self, pressure_map: np.ndarray) -> np.ndarray:
        pressure_mask = pressure_map > 0
        if not pressure_mask.any():
            return np.zeros_like(pressure_map, dtype=bool)
        
        threshold = np.percentile(pressure_map[pressure_mask], self.percentile_p)
        return pressure_map > threshold
    
    def _extract_components(self, pressure_map: np.ndarray, high_pressure_mask: np.ndarray) -> List[_PressureComponent]:
        from scipy.ndimage import label, center_of_mass
        
        label_result: Tuple[Any, Any] = label(high_pressure_mask)  # type: ignore
        labeled_array: np.ndarray = label_result[0]
        num_features: int = int(label_result[1])
        
        components = []
        for i in range(1, num_features + 1):
            component_mask = labeled_array == i
            center = center_of_mass(pressure_map, component_mask)
            size = int(np.sum(component_mask))
            max_pressure = float(np.max(pressure_map[component_mask]))

            center_array = np.array([int(center[0]), int(center[1])]) # type: ignore

            component = _PressureComponent(
                center=center_array,
                size=size,
                max_pressure=max_pressure,
            )
            components.append(component)
        
        return sorted(components, key=lambda x: x.y_pos)
    
    def _detect_occiput(self, components: List[_PressureComponent]) -> np.ndarray:
        if len(components) >= 1:
            return components[0].center
        return np.array([-1, -1])
    
    def _detect_scapula(self, components: List[_PressureComponent]) -> np.ndarray:
        if len(components) >= 2:
            for comp in components[1:]:
                if comp.size > components[0].size * 1.5:
                    return comp.center
        return np.array([-1, -1])
    
    def _detect_hip(self, components: List[_PressureComponent]) -> np.ndarray:
        if len(components) >= 3:
            mid_idx = len(components) // 2
            avg_size = np.mean([c.size for c in components])
            for i in range(max(1, mid_idx - 1), min(len(components), mid_idx + 2)):
                if components[i].size > avg_size:
                    return components[i].center
        return np.array([-1, -1])
    
    def _detect_heel(self, components: List[_PressureComponent]) -> np.ndarray:
        if len(components) >= 4:
            return components[-1].center
        return np.array([-1, -1])
    
    def _detect_elbow(self, components: List[_PressureComponent], scapula: np.ndarray) -> np.ndarray:
        if scapula[0] == -1 or not components:
            return np.array([-1, -1])
        
        for comp in components:
            if (abs(comp.y_pos - scapula[0]) < 20 and 
                comp.size < components[0].size and
                abs(comp.x_pos - scapula[1]) > 10):
                return comp.center
        return np.array([-1, -1])
    
    def detect(self, map: np.ndarray) -> PartPositions:
        # 압력 맵 전처리
        pressure_map = self._normalize_pressure_map(map)
        
        # 높은 압력 영역 찾기
        high_pressure_mask = self._find_high_pressure_regions(pressure_map)
        if not high_pressure_mask.any():
            return PartPositions(
                occiput=np.array([-1, -1]),
                scapula=np.array([-1, -1]),
                elbow=np.array([-1, -1]),
                heel=np.array([-1, -1]),
                hip=np.array([-1, -1])
            )
        
        # 컴포넌트 추출
        components = self._extract_components(pressure_map, high_pressure_mask)
        if not components:
            return PartPositions(
                occiput=np.array([-1, -1]),
                scapula=np.array([-1, -1]),
                elbow=np.array([-1, -1]),
                heel=np.array([-1, -1]),
                hip=np.array([-1, -1])
            )
        
        # 각 신체 부위 감지
        occiput = self._detect_occiput(components)
        scapula = self._detect_scapula(components)
        hip = self._detect_hip(components)
        heel = self._detect_heel(components)
        elbow = self._detect_elbow(components, scapula)
        
        return PartPositions(
            occiput=occiput,
            scapula=scapula,
            elbow=elbow,
            heel=heel,
            hip=hip
        )