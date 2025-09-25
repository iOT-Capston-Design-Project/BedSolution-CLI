from datetime import date, datetime
from service.detection import PostureDetectionResult
from service.notifications.notification_manager import NotificationManager
from core.server.models import DayLog, PressureLog, Patient
from core.server import ServerAPI
from .day_cache import DayCache
from .pressure_cache import PressureCache
from logging import getLogger
from typing import Optional, Dict
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
        self.threshold = PartThreshold(50, 50, 50, 50, 50) # 기본값, 서버 설정이 있으면 덮어씀
        self.notification_manager = NotificationManager()
        self._notification_sent: Dict[str, bool] = {
            "occiput": False,
            "scapula": False,
            "elbow": False,
            "heel": False,
            "hip": False,
        }
        self._threshold_loaded_at: Optional[datetime] = None
        self._has_patient_threshold = False
        self.last_day_cache: Optional[DayCache] = None
        self.device_id = device_id
        self._refresh_threshold_from_server(force=True)

    def _get_daycache_filename(self, date: date) -> str:
        return f"daycache_{date.strftime('%Y%m%d')}.json"

    def _get_daycache_filepath(self, date: date) -> str:
        cache_dir = os.path.join(os.getcwd(), "pressure_cache")
        os.makedirs(cache_dir, exist_ok=True)
        filename = self._get_daycache_filename(date=date)
        return os.path.join(cache_dir, filename)

    def _reset_notification_flags(self):
        for key in self._notification_sent:
            self._notification_sent[key] = False

    def _threshold_from_patient(self, patient: Patient) -> PartThreshold:
        # 환자 설정은 분 단위로 들어온다고 가정하고 초 단위로 변환한다.
        to_seconds = lambda minutes: max(int(minutes) * 60, 0)
        return PartThreshold(
            to_seconds(patient.occiput),
            to_seconds(patient.scapula),
            to_seconds(patient.elbow),
            to_seconds(patient.heel),
            to_seconds(patient.hip)
        )

    def _refresh_threshold_from_server(self, force: bool = False):
        if not force and self._threshold_loaded_at:
            elapsed = (datetime.now() - self._threshold_loaded_at).total_seconds()
            refresh_interval = 600 if self._has_patient_threshold else 60
            if elapsed < refresh_interval:
                return

        try:
            patient = self.api.fetch_patient_with_device(self.device_id)
        except Exception as exc:
            self.logger.warning(f"Failed to fetch patient thresholds: {exc}")
            self._threshold_loaded_at = datetime.now()
            return

        if not patient:
            if force:
                self.logger.info("No patient configuration found; using default thresholds")
            self._has_patient_threshold = False
            self._threshold_loaded_at = datetime.now()
            return

        new_threshold = self._threshold_from_patient(patient)
        current_values = (
            self.threshold.occiput,
            self.threshold.scapula,
            self.threshold.elbow,
            self.threshold.heel,
            self.threshold.hip,
        )
        new_values = (
            new_threshold.occiput,
            new_threshold.scapula,
            new_threshold.elbow,
            new_threshold.heel,
            new_threshold.hip,
        )

        if current_values != new_values:
            self.logger.info(f"Updated patient thresholds to {new_values}")
            self.threshold = new_threshold
            self._reset_notification_flags()
        else:
            self.threshold = new_threshold

        self._has_patient_threshold = True
        self._threshold_loaded_at = datetime.now()

    def _trigger_notifications(self, pressure_log: PressureCache):
        if not self._has_patient_threshold or pressure_log is None:
            return

        exceed_occiput = pressure_log.occiput >= self.threshold.occiput
        exceed_scapula = pressure_log.scapula >= self.threshold.scapula
        exceed_elbow = pressure_log.elbow >= self.threshold.elbow
        exceed_heel = pressure_log.heel >= self.threshold.heel
        exceed_hip = pressure_log.hip >= self.threshold.hip

        notify_occiput = exceed_occiput and not self._notification_sent["occiput"]
        notify_scapula = exceed_scapula and not self._notification_sent["scapula"]
        notify_elbow = exceed_elbow and not self._notification_sent["elbow"]
        notify_heel = exceed_heel and not self._notification_sent["heel"]
        notify_hip = exceed_hip and not self._notification_sent["hip"]

        if not (notify_occiput or notify_scapula or notify_elbow or notify_heel or notify_hip):
            return

        sent = self.notification_manager.send_notification(
            str(self.device_id),
            exceed_occiput,
            exceed_scapula,
            exceed_elbow,
            exceed_heel,
            exceed_hip,
        )

        if not sent:
            self.logger.warning("Notification send failed; will retry when new thresholds are exceeded")
            return

        if notify_occiput:
            self._notification_sent["occiput"] = True
        if notify_scapula:
            self._notification_sent["scapula"] = True
        if notify_elbow:
            self._notification_sent["elbow"] = True
        if notify_heel:
            self._notification_sent["heel"] = True
        if notify_hip:
            self._notification_sent["hip"] = True
    
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
                return DayCache(int(date.strftime('%Y%m%d')), date, 0, 0, 0, 0, 0, [], True)
        else:
            return DayCache(int(date.strftime('%Y%m%d')), date, 0, 0, 0, 0, 0, [], True)

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

    def _log_locally(self, time: datetime, heatmap: np.ndarray, posture: PostureDetectionResult) -> tuple[DayCache, PressureCache, bool]:
        self.logger.info(f"Logging locally at {time}")

        self._refresh_threshold_from_server()

        # 이전 pressure_log값 가져오기
        last_log_result = self._get_last_pressure_log(time.date())
        last_log = last_log_result[1] if last_log_result else None
        last_log_idx = last_log_result[0] if last_log_result else None

        day_cache = self._open_daycache(time.date())

        accumulated_time = 0
        is_same_day = last_log is not None and last_log.time.date() == time.date()
        is_same_posture = last_log is not None and last_log.posture == posture.type
        reuse_existing_entry = last_log is not None and is_same_day and is_same_posture

        if reuse_existing_entry:
            accumulated_time = int((time - last_log.time).total_seconds())
            pressure_log = PressureCache(
                last_log.id,
                time,
                last_log.occiput,
                last_log.scapula,
                last_log.elbow,
                last_log.heel,
                last_log.hip,
                posture.type,
                created_at=last_log.created_at,
            )
        else:
            existing_ids = {log.id for log in day_cache.logs}
            pressure_log = PressureCache(
                self._generate_pressure_log_id(time, existing_ids),
                time,
                0,
                0,
                0,
                0,
                0,
                posture.type,
                created_at=time,
            )

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

        is_day_changed = last_log is None or (last_log and last_log.time.date() != time.date())

        if is_day_changed:
            self._refresh_threshold_from_server(force=True)
            self._reset_notification_flags()

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
        if not reuse_existing_entry or is_day_changed:
            day_cache.logs.append(pressure_log)
        elif last_log_idx is not None:  # Fixed: handle index 0 correctly
            day_cache.logs[last_log_idx] = pressure_log

        self._save_daycache(daycache=day_cache)
        self._trigger_notifications(pressure_log)
        needs_creation = not reuse_existing_entry or is_day_changed
        return day_cache, pressure_log, needs_creation

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
        return PressureLog(
            id=pressure.id,
            day_id=day_id,
            createdAt=pressure.created_at,
            occiput=pressure.occiput,
            scapula=pressure.scapula,
            elbow=pressure.elbow,
            heel=pressure.heel,
            hip=pressure.hip,
            posture=pressure.posture
        )

    def _generate_pressure_log_id(self, timestamp: datetime, existing_ids: set[int] | None = None) -> int:
        base_id = int(timestamp.strftime('%Y%m%d%H%M%S'))
        if not existing_ids:
            return base_id

        candidate = base_id
        while candidate in existing_ids:
            candidate += 1
        return candidate

    def _upload_to_server(self, daycache: DayCache, pressure_cache: PressureCache, created_new_log: bool) -> bool:
        self.logger.info(f"Uploading to server: {daycache.id} on {daycache.date}")

        try:
            if not daycache.logs:
                self.logger.warning("No pressure logs available to upload")
                return False

            day_log_payload = self._convert_to_daylog(daycache)
            created_daylog = False

            if daycache.is_new:
                self.logger.info(f"Creating daylog {day_log_payload.id}")
                day_log_response = self.api.create_daylog(daylog=day_log_payload)
                if not day_log_response or day_log_response is day_log_payload:
                    self.logger.warning(f"Failed to create daylog {day_log_payload.id}")
                    return False
                created_daylog = True
            else:
                day_log_response = self.api.update_daylog(daylog=day_log_payload)
                if not day_log_response:
                    self.logger.warning(f"Failed to update daylog {day_log_payload.id}")
                    return False
                if day_log_response is day_log_payload:
                    self.logger.info(f"Daylog {day_log_payload.id} missing on server, attempting creation")
                    day_log_response = self.api.create_daylog(daylog=day_log_payload)
                    if not day_log_response or day_log_response is day_log_payload:
                        self.logger.warning(f"Failed to create daylog {day_log_payload.id} after update fallback")
                        return False
                    created_daylog = True

            if created_daylog and daycache.is_new:
                daycache.is_new = False
                # Persist the state change so subsequent uploads use update logic
                self._save_daycache(daycache)

            day_log = day_log_response

            pressure_log_payload = self._convert_to_pressurelog(pressure_cache, day_log.id)
            if created_new_log:
                pressure_log_response = self.api.create_pressurelog(pressure_log_payload)
            else:
                pressure_log_response = self.api.update_pressurelog(pressure_log_payload)
                if not pressure_log_response or pressure_log_response is pressure_log_payload:
                    self.logger.info(
                        f"Pressurelog {pressure_log_payload.id} missing on server, attempting creation"
                    )
                    pressure_log_response = self.api.create_pressurelog(pressure_log_payload)

            if not pressure_log_response or pressure_log_response is pressure_log_payload:
                self.logger.warning(f"Failed to upload pressure_log for day {day_log.id}")
                return False
        except Exception as e:
            self.logger.warning(f"Failed to upload: {e}")
            return False

        return True

    def log(self, time: datetime, heatmap: np.ndarray, posture: PostureDetectionResult) -> bool:
        daycache, pressure_cache, created_new_log = self._log_locally(time, heatmap, posture)
        return self._upload_to_server(daycache, pressure_cache, created_new_log)
