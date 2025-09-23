from core.server import ServerAPI
from service.device_manager import DeviceManager
import numpy as np
import threading
import queue
import logging
from typing import Optional
import time

class HeatmapRealtime:
    def __init__(self, api: ServerAPI):
        self.api = api
        self.device_manager = DeviceManager(api=api)
        self.logger = logging.getLogger("heatmap_realtime")

        # 업로드 큐와 스레드 관리
        self.upload_queue: queue.Queue = queue.Queue(maxsize=10)
        self.upload_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.queue_lock = threading.Lock()

        # 업로드 스레드 시작
        self._start_upload_thread()

    def _start_upload_thread(self):
        """백그라운드 업로드 스레드 시작"""
        if not self.is_running:
            self.is_running = True
            self.stop_event.clear()
            self.upload_thread = threading.Thread(target=self._upload_worker, daemon=True)
            self.upload_thread.start()
            self.logger.info("Heatmap upload thread started")

    def _upload_worker(self):
        """백그라운드에서 큐의 데이터를 서버로 업로드"""
        while self.is_running:
            try:
                # 큐에서 데이터 가져오기 (0.5초 타임아웃)
                if not self.stop_event.is_set():
                    try:
                        device_id, heatmap_data = self.upload_queue.get(timeout=0.5)

                        # 서버로 업로드
                        success = self.api.update_heatmap(device_id, heatmap_data)

                        if success:
                            self.logger.debug(f"Heatmap uploaded successfully for device {device_id}")
                        else:
                            self.logger.warning(f"Failed to upload heatmap for device {device_id}")

                        self.upload_queue.task_done()

                    except queue.Empty:
                        continue  # 큐가 비어있으면 계속 대기

            except Exception as e:
                self.logger.error(f"Error in upload worker: {e}")
                time.sleep(0.1)  # 에러 발생시 잠시 대기

            if self.stop_event.is_set():
                break

    def _clear_queue(self):
        """큐의 모든 데이터 제거"""
        with self.queue_lock:
            while not self.upload_queue.empty():
                try:
                    self.upload_queue.get_nowait()
                    self.upload_queue.task_done()
                except queue.Empty:
                    break

    def sync(self, heatmap: np.ndarray):
        """히트맵 데이터를 비동기로 서버에 동기화 (항상 최신 데이터만 유지)"""
        if not self.device_manager.is_registered():
            return

        device_id = self.device_manager.get_device_id()

        try:
            # 큐가 차있으면 기존 데이터 모두 제거 (최신 데이터 우선)
            if self.upload_queue.full():
                self._clear_queue()
                self.logger.debug("Cleared old heatmap data from queue")

            # 큐에 새 데이터 추가
            self.upload_queue.put_nowait((device_id, heatmap.copy()))  # copy로 데이터 보호
            self.logger.debug(f"Latest heatmap queued for upload")

        except queue.Full:
            # 이 경우는 발생하지 않아야 하지만, 안전을 위해 처리
            self._clear_queue()
            try:
                self.upload_queue.put_nowait((device_id, heatmap.copy()))
                self.logger.debug("Queued after clearing (fallback)")
            except:
                self.logger.error("Failed to queue heatmap even after clearing")
        except Exception as e:
            self.logger.error(f"Error queuing heatmap: {e}")

    def stop(self):
        """업로드 스레드 정지 및 남은 데이터 처리"""
        if self.is_running:
            self.logger.info("Stopping heatmap upload thread...")

            # 남은 큐 처리를 위해 잠시 대기 (최대 2초)
            timeout = 2.0
            start_time = time.time()

            while not self.upload_queue.empty() and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            # 스레드 종료
            self.is_running = False
            self.stop_event.set()

            if self.upload_thread and self.upload_thread.is_alive():
                self.upload_thread.join(timeout=1.0)

            if not self.upload_queue.empty():
                self.logger.info(f"Stopped with pending upload (latest data only)")

            self.logger.info("Heatmap upload thread stopped")

    def __del__(self):
        """객체 소멸시 스레드 정리"""
        self.stop()