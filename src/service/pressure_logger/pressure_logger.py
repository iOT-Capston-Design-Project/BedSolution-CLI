from datetime import date, datetime
from service.detection import PostureDetectionResult
from core.server.models import PostureType, DayLog, PressureLog
from core.server import ServerAPI
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
    def __init__(self, api: ServerAPI, device_id: int):
        self.logger = getLogger(__name__)
        self.api = api
        self.threshold = PartThreshold(50, 50, 50, 50, 50) # 나중에 config에서 가져오는걸로 수정
        self.last_day_cache: Optional[DayCache] = None
        self.device_id = device_id

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
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    return DayCache.from_dict(data=data)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to read daycache file {filepath}: {e}")
                return DayCache(int(date.strftime('%Y%m%d')), date, 0, 0, 0, 0, 0, [])
        else:
            return DayCache(int(date.strftime('%Y%m%d')), date, 0, 0, 0, 0, 0, [])

    def _save_daycache(self, daycache: DayCache):
        # Update cache only for today's data to avoid confusion
        from datetime import datetime
        if daycache.date == datetime.now().date():
            self.last_day_cache = daycache

        filepath = self._get_daycache_filepath(date=daycache.date)
        try:
            with open(filepath, 'w') as f:
                json.dump(daycache.to_dict(), f)
        except IOError as e:
            self.logger.error(f"Failed to save daycache to {filepath}: {e}")

    def _get_last_pressure_log(self, date: date) -> Optional[tuple[int, PressureCache]]:
        # Check if cached data is from the same date
        if (self.last_day_cache is not None and
            self.last_day_cache.date == date and
            self.last_day_cache.logs):
            return len(self.last_day_cache.logs)-1, self.last_day_cache.logs[-1]

        if self._get_daycache_count() == 0:
            return None

        # First check current date
        if self._is_daycache_exist(date):
            daycache = self._open_daycache(date=date)
            if daycache.logs:
                # Cache only today's data
                if date == datetime.now().date():
                    self.last_day_cache = daycache
                return len(daycache.logs)-1, daycache.logs[-1]

        # Then check previous dates for the last log
        cache_dir = os.path.join(os.getcwd(), "pressure_cache")
        prefix, suffix = "daycache_", ".json"
        try:
            filenames = sorted([f for f in os.listdir(cache_dir)
                              if f.startswith(prefix) and f.endswith(suffix)],
                             reverse=True)
        except OSError as e:
            self.logger.warning(f"Failed to list cache directory: {e}")
            return None

        for filename in filenames:
            dstr = filename[len(prefix):-len(suffix)]
            try:
                file_date = datetime.strptime(dstr, '%Y%m%d').date()
                # Look for most recent log before or on the given date
                if file_date <= date:
                    daycache = self._open_daycache(date=file_date)
                    if daycache.logs:
                        # Only cache today's data
                        if file_date == datetime.now().date():
                            self.last_day_cache = daycache
                        return len(daycache.logs)-1, daycache.logs[-1]
            except ValueError:
                continue
        return None

    def _log_locally(self, time: datetime, heatmap: np.ndarray, posture: PostureDetectionResult) -> DayCache:
        self.logger.info(f"Logging locally at {time}")

        # 이전 pressure_log값 가져오기
        last_log_result = self._get_last_pressure_log(time.date())
        last_log = last_log_result[1] if last_log_result else None
        last_log_idx = last_log_result[0] if last_log_result else None

        
        is_posture_changed = last_log is None or (last_log and last_log.posture != posture)
        accumulated_time = 0
        if is_posture_changed:
            pressure_log = PressureCache(time, 0, 0, 0, 0, 0, posture.type)
        else:
            pressure_log = PressureCache(time, last_log.occiput, last_log.scapula, last_log.elbow, last_log.heel, last_log.hip, posture.type)
            accumulated_time = int((time - last_log.time).total_seconds())

        # 누적 시간 업데이트
        if posture.occiput:
            pressure_log.occiput += accumulated_time
        if posture.scapula:
            pressure_log.scapula += accumulated_time
        if posture.elbow:
            pressure_log.elbow += accumulated_time
        if posture.heel:
            pressure_log.heel += accumulated_time
        if posture.hip:
            pressure_log.hip += accumulated_time

        day_cache = self._open_daycache(time.date())
        is_day_changed = last_log is None or (last_log and last_log.time.date() != time.date())

        # Update DayCache accumulated times (add to total daily accumulation)
        if accumulated_time > 0 and not is_day_changed:
            if posture.occiput:
                day_cache.accumulated_occiput += accumulated_time
            if posture.scapula:
                day_cache.accumulated_scapula += accumulated_time
            if posture.elbow:
                day_cache.accumulated_elbow += accumulated_time
            if posture.heel:
                day_cache.accumulated_heel += accumulated_time
            if posture.hip:
                day_cache.accumulated_hip += accumulated_time
        
        # Pressure log 업데이트
        if is_posture_changed or is_day_changed:
            day_cache.logs.append(pressure_log)
        elif last_log_idx is not None:  # Fixed: handle index 0 correctly
            day_cache.logs[last_log_idx] = pressure_log
            
        self._save_daycache(daycache=day_cache)
        return day_cache

    def _convert_to_daylog(self, day_cache: DayCache) -> DayLog:
        return DayLog(
            day_cache.id,
            day_cache.date,
            self.device_id,
            day_cache.accumulated_occiput,
            day_cache.accumulated_scapula,
            day_cache.accumulated_elbow,
            day_cache.accumulated_heel,
            day_cache.accumulated_hip
        )

    def _convert_to_pressurelog(self, pressure: PressureCache, day_id: int) -> PressureLog:
        # 시간을 정수형 ID로 변환 (YYYYMMDDHHMISS 형태)
        time_id = int(pressure.time.strftime('%Y%m%d%H%M%S'))

        return PressureLog(
            id=time_id,
            day_id=day_id,
            createdAt=pressure.time,
            occiput=pressure.occiput,
            scapula=pressure.scapula,
            elbow=pressure.elbow,
            heel=pressure.heel,
            hip=pressure.hip,
            posture=pressure.posture
        )

    def _upload_to_server(self, daycache: DayCache) -> bool:
        self.logger.info(f"Uploading to server: {daycache.id} on {daycache.date}")

        try:
            day_log = self._convert_to_daylog(daycache)
            day_log = self.api.update_daylog(daylog=day_log)
            if not day_log:
                self.logger.warning(f"Failed to upload {day_log}")
                return False

            pressure_log = self._convert_to_pressurelog(daycache.logs[-1], day_log.id)
            pressure_log = self.api.create_pressurelog(pressure_log)
            if not pressure_log:
                self.logger.warning(f"Failed to upload pressure_log")
                return False
        except Exception as e:
            self.logger.warning(f"Failed to upload: {e}")
            return False

        return True

    def log(self, time: datetime, heatmap: np.ndarray, posture: PostureDetectionResult) -> bool:
        updated = self._log_locally(time, heatmap, posture)
        return self._upload_to_server(updated)

