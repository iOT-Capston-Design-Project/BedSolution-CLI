from service.signal_analyze.signal_analyzer import AnalyzeResult
from core.server.server_api import ServerAPI
from core.config_manager import config_manager
from core.server.models.pressure_log import PressureLog
from service.signal_analyze.posture_detection import PostureType
from service.server_sync.csv_handler import CSVManager
from enum import Enum
from threading import Lock, Thread, Event
import time
import datetime
from typing import Optional
import numpy as np
from pathlib import Path
import json

class SyncStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"   

class ServerSync:
    _status = SyncStatus.PENDING
    _status_lock = Lock()

    @staticmethod
    def _get_min_duration():
        min_duration = config_manager.get_setting("sync", "min_duration", fallback="300")
        return int(min_duration) if min_duration else 300

    @staticmethod
    def _get_synctime():
        sync_time = config_manager.get_setting("sync", "sync_time", fallback="10")
        return int(sync_time) if sync_time else 10

    def __init__(self, api: ServerAPI):
        self.api = api
        self.buffer = []
        self.sync_thread = None
        self.stop_event = Event()
        self.last_pressure_log = None
        self.last_posture = None
        self.last_check_time = None
        self.offline_queue = []
        self.data_dir = Path("cache")
        self.data_dir.mkdir(exist_ok=True)
        self.csv_manager = CSVManager(self.data_dir)
        self._load_last_pressure_log_from_cache()
        self._invalid_position = np.array([-1, -1])
        self._max_buffer_size = 1000  # Prevent memory overflow

    def push(self, data: AnalyzeResult):
        self.buffer.append(data)
        
        # Prevent buffer overflow
        if len(self.buffer) > self._max_buffer_size:
            self.buffer = self.buffer[-self._max_buffer_size//2:]
            
        self.csv_manager.save_analyze_result(data)

    def current_status(self):
        with self._status_lock:
            return self._status

    def start_sync(self):
        if self.sync_thread and self.sync_thread.is_alive():
            return
        
        with self._status_lock:
            self._status = SyncStatus.IN_PROGRESS
        
        self.stop_event.clear()
        self.sync_thread = Thread(target=self._sync_worker)
        self.sync_thread.daemon = True
        self.sync_thread.start()

    def stop_sync(self):
        self.stop_event.set()
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join()
        
        with self._status_lock:
            self._status = SyncStatus.PENDING
    
    def _sync_worker(self):
        sync_time = self._get_synctime()
        while not self.stop_event.is_set():
            try:
                self._process_buffer()
                self._retry_offline_uploads()
            except Exception as e:
                print(f"Sync error: {e}")

            time.sleep(sync_time)

    def _process_buffer(self):
        if not self.buffer:
            return
            
        current_time = time.time()
        min_duration = self._get_min_duration()
        
        should_upload = False
        
        if len(self.buffer) > 0:
            latest_data = self.buffer[-1]
            
            if self.last_check_time is None:
                self.last_check_time = current_time
                self.last_posture = latest_data.posture
                return
            
            posture_changed = self.last_posture != latest_data.posture
            duration_exceeded = (current_time - self.last_check_time) >= min_duration
            
            if posture_changed or duration_exceeded:
                should_upload = True
                
        if should_upload:
            pressure_log = self._calculate_pressure_log()
            if pressure_log:
                self._upload_pressure_log(pressure_log)
            self.last_check_time = current_time
            if self.buffer:
                self.last_posture = self.buffer[-1].posture
    
    def _calculate_pressure_log(self) -> Optional[PressureLog]:
        if not self.buffer:
            return None
            
        current_time = time.time()
        duration = current_time - (self.last_check_time or current_time)
        
        cumulative_data = {
            'occiput': 0,
            'scapula': 0, 
            'elbow': 0,
            'heel': 0,
            'hip': 0
        }
        
        total_samples = len(self.buffer)
        if total_samples > 0:
            sample_duration = int(duration / total_samples)
            for data in self.buffer:
                # Optimized position checks using cached invalid position
                if not np.array_equal(data.parts.occiput, self._invalid_position):
                    cumulative_data['occiput'] += sample_duration
                if not np.array_equal(data.parts.scapula, self._invalid_position):
                    cumulative_data['scapula'] += sample_duration
                if not np.array_equal(data.parts.elbow, self._invalid_position):
                    cumulative_data['elbow'] += sample_duration
                if not np.array_equal(data.parts.heel, self._invalid_position):
                    cumulative_data['heel'] += sample_duration
                if not np.array_equal(data.parts.hip, self._invalid_position):
                    cumulative_data['hip'] += sample_duration
        
        pressure_log = PressureLog(
            id=0,
            day_id=1,
            createdAt=datetime.datetime.now(),
            occiput=cumulative_data['occiput'],
            scapula=cumulative_data['scapula'],
            elbow=cumulative_data['elbow'],
            heel=cumulative_data['heel'],
            hip=cumulative_data['hip']
        )
        
        return pressure_log
    
    def _upload_pressure_log(self, pressure_log: PressureLog):
        try:
            self.api.create_pressurelog(pressure_log)
            self.csv_manager.save_pressure_log(pressure_log)
            self.last_pressure_log = pressure_log
            # Save to cache for next startup
            current_posture = self.buffer[-1].posture if self.buffer else PostureType.UNKNOWN
            self._save_last_pressure_log_to_cache(pressure_log, current_posture)
            self.buffer.clear()
        except Exception as e:
            print(f"Upload failed: {e}")
            self.offline_queue.append(pressure_log)
    
    def _retry_offline_uploads(self):
        if not self.offline_queue:
            return
            
        failed_uploads = []
        
        for pressure_log in self.offline_queue:
            try:
                # Direct API call to avoid recursion in _upload_pressure_log
                self.api.create_pressurelog(pressure_log)
                self.csv_manager.save_pressure_log(pressure_log)
                print(f"Successfully retried upload for pressure log: {pressure_log.id}")
            except Exception as e:
                print(f"Retry failed for pressure log {pressure_log.id}: {e}")
                failed_uploads.append(pressure_log)
        
        self.offline_queue = failed_uploads
    
    def _load_last_pressure_log_from_cache(self):
        try:
            cache_file = self.data_dir / "last_pressure_log_cache.json"
            if not cache_file.exists():
                return
                
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # Reconstruct PressureLog from cache
            timestamp = datetime.datetime.fromisoformat(cache_data['created_at'])
            self.last_pressure_log = PressureLog(
                id=cache_data['id'],
                day_id=cache_data['day_id'],
                createdAt=timestamp,
                occiput=cache_data['occiput'],
                scapula=cache_data['scapula'],
                elbow=cache_data['elbow'],
                heel=cache_data['heel'],
                hip=cache_data['hip']
            )
            
            self.last_check_time = timestamp.timestamp()
            self.last_posture = PostureType(cache_data['posture'])
            
            print(f"Loaded last pressure log from cache: {timestamp}")
            
        except Exception as e:
            print(f"Error loading last pressure log from cache: {e}")
    
    def _save_last_pressure_log_to_cache(self, pressure_log: PressureLog, posture: PostureType):
        try:
            cache_file = self.data_dir / "last_pressure_log_cache.json"
            cache_data = {
                'id': pressure_log.id,
                'day_id': pressure_log.day_id,
                'created_at': pressure_log.createdAt.isoformat(),
                'occiput': pressure_log.occiput,
                'scapula': pressure_log.scapula,
                'elbow': pressure_log.elbow,
                'heel': pressure_log.heel,
                'hip': pressure_log.hip,
                'posture': posture.value
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving last pressure log to cache: {e}")
    
