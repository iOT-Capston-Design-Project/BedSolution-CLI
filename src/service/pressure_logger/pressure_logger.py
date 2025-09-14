from datetime import date, datetime
from service.signal_analyze.parts_detection import PartPositions
from src.core.server.models.pressure_log import PostureType
from core.server.server_api import ServerAPI
from .day_cache import DayCache
from .pressure_cache import PressureCache
from logging import getLogger
from typing import Optional
import numpy as np
import os, json

class PartThreshold:
    def __init__(self, occiput: int, scapula: int, elbow: int, heel: int, hip: int):
        self.occiput = occiput
        self.scapula = scapula
        self.elbow = elbow
        self.heel = heel
        self.hip = hip

class PressureLogger:
    def __init__(self, api: ServerAPI):
        self.logger = getLogger(__name__)
        self.api = api
        self.threshold = PartThreshold(50, 50, 50, 50, 50) # 나중에 config에서 가져오는걸로 수정
        self.last_day_cache: Optional[DayCache] = None

    def _get_daycache_filename(self, date: date) -> str:
        return f"daycache_{date.strftime('%Y%m%d')}.json"

    def _get_daycache_filepath(self, date: date) -> str:
        cache_dir = os.path.join(os.getcwd(), "pressure_cache")
        os.makedirs(cache_dir, exist_ok=True)
        filename = self._get_daycache_filename(date=date)
        return os.path.join(cache_dir, filename)
    
    def _get_daycache_count(self) -> int:
        cache_dir = os.path.join(os.getcwd(), "pressure_cache")
        if not os.path.exists(cache_dir):
            return 0
        return len([name for name in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, name)) and name.startswith("daycache_") and name.endswith(".json")])

    def _is_daycache_exist(self, date: date) -> bool:
        filepath = self._get_daycache_filepath(date=date)
        return os.path.exists(filepath)

    def _open_daycache(self, date: date) -> DayCache:
        if self._is_daycache_exist(date=date):
            filepath = self._get_daycache_filepath(date=date)
            with open(filepath, 'r') as f:
                data = json.load(f)
                return DayCache.from_dict(data=data)
        else:
            return DayCache(int(date.strftime('%Y%m%d')), date, 0, 0, 0, 0, 0, [])

    def _save_daycache(self, daycache: DayCache):
        self.last_day_cache = daycache
        filepath = self._get_daycache_filepath(date=daycache.date)
        with open(filepath, 'w') as f:
            json.dump(daycache.to_dict(), f)

    def _get_last_pressure_log(self, date: date) -> Optional[tuple[int, PressureCache]]:
        if self.last_day_cache is not None and self.last_day_cache.logs:
            return len(self.last_day_cache.logs)-1, self.last_day_cache.logs[-1]

        if self._get_daycache_count() == 0:
            return None
        if self._is_daycache_exist(date):
            daycache = self._open_daycache(date=date)
            if daycache.logs:
                self.last_day_cache = daycache
                return len(daycache.logs)-1, daycache.logs[-1]

        cache_dir = os.path.join(os.getcwd(), "pressure_cache")
        prefix, suffix = "daycache_", ".json"
        for filename in sorted(os.listdir(cache_dir), reverse=True):
            if filename.startswith(prefix) and filename.endswith(suffix):
                dstr = filename[len(prefix):-len(suffix)]
                try:
                    file_date = datetime.strptime(dstr, '%Y%m%d').date()
                    if file_date < date:
                        daycache = self._open_daycache(date=file_date)
                        if daycache.logs:
                            self.last_day_cache = daycache
                            return len(daycache.logs)-1, daycache.logs[-1]
                except ValueError:
                    continue
        return None
        
    def _filter_pressure(self, heatmap: np.ndarray, parts: PartPositions) -> tuple[bool, bool, bool, bool, bool]:
        occiput = parts.occiput is not None and heatmap[parts.occiput[1], parts.occiput[0]] >= self.threshold.occiput
        scapula = parts.scapula is not None and heatmap[parts.scapula[1], parts.scapula[0]] >= self.threshold.scapula
        elbow = parts.elbow is not None and heatmap[parts.elbow[1], parts.elbow[0]] >= self.threshold.elbow
        heel = parts.heel is not None and heatmap[parts.heel[1], parts.heel[0]] >= self.threshold.heel
        hip = parts.hip is not None and heatmap[parts.hip[1], parts.hip[0]] >= self.threshold.hip
        return occiput, scapula, elbow, heel, hip

    def _log_locally(self, time: datetime, heatmap: np.ndarray, parts: PartPositions, posture: PostureType) -> DayCache:
        self.logger.info(f"Logging locally at {time}")

        # 이전 pressure_log값 가져오기
        last_log_result = self._get_last_pressure_log(time.date())
        last_log = last_log_result[1] if last_log_result else None
        last_log_idx = last_log_result[0] if last_log_result else None

        
        is_posture_changed = last_log is None or (last_log and last_log.posture != posture)
        accumulated_time = 0
        if is_posture_changed:
            pressure_log = PressureCache(time, 0, 0, 0, 0, 0, posture)
        else:
            pressure_log = PressureCache(time, last_log.occiput, last_log.scapula, last_log.elbow, last_log.heel, last_log.hip, posture)
            accumulated_time = int((time - last_log.time).total_seconds())

        # 누적 시간 업데이트
        occiput, scapula, elbow, heel, hip = self._filter_pressure(heatmap, parts)
        if occiput:
            pressure_log.occiput += accumulated_time
        if scapula:
            pressure_log.scapula += accumulated_time
        if elbow:
            pressure_log.elbow += accumulated_time
        if heel:
            pressure_log.heel += accumulated_time
        if hip:
            pressure_log.hip += accumulated_time

        day_cache = self._open_daycache(time.date())
        is_day_changed = last_log is None or last_log and last_log.time.date() != time.date()
        
        # Pressure log 업데이트
        if is_posture_changed or is_day_changed:
            day_cache.logs.append(pressure_log)
        elif last_log_idx:
            day_cache.logs[last_log_idx] = pressure_log
            
        self._save_daycache(daycache=day_cache)
        return day_cache

    def _upload_to_server(self, daycache: DayCache):
        self.logger.info(f"Uploading to server: {daycache.id} on {daycache.date}")
        pass

    def log(self, time: datetime, heatmap: np.ndarray, parts: PartPositions, posture: PostureType):
        updated = self._log_locally(time, heatmap, parts, posture)
        self._upload_to_server(updated)

