from service.detection import PartsDetector, PartPositions, PostureDetector, PostureType
from service.heatmap_tools import HeatmapConverter, HeatmapInterpolationMethod, HeatmapRealtime
from core.serialcm import SerialSignal
from core.server import ServerAPI
from datetime import datetime
from service.pressure_logger.pressure_logger import PressureLogger
import numpy as np
import threading
from queue import Queue, Empty
from typing import Generator, Tuple
from dataclasses import dataclass
import logging

@dataclass
class DetectionTask:
    """워커 스레드에 전달할 작업 데이터"""
    heatmap: np.ndarray
    timestamp: datetime
    
@dataclass
class DetectionResult:
    """워커 스레드에서 반환할 결과 데이터"""
    heatmap: np.ndarray
    parts: PartPositions
    posture: PostureType
    timestamp: datetime
    synced: bool

class SignalPipeline:
    def __init__(self, api: ServerAPI, device_id: int):
        self.parts_detector = PartsDetector()
        self.posture_detector = PostureDetector()
        self.heatmap_converter = HeatmapConverter()
        self.pressure_cache = PressureLogger(api=api, device_id=device_id)
        self.heatmap_rt = HeatmapRealtime(api=api)
        
        # 스레드 관련
        self.task_queue: Queue[DetectionTask] = Queue()
        self.result_queue: Queue[DetectionResult] = Queue()
        self.stop_event = threading.Event()
        
        # 로거 설정
        self.logger = logging.getLogger(__name__)
        
        # 워커 스레드 시작
        self.detector_thread = threading.Thread(
            target=self._detector_worker, 
            daemon=True,
            name="DetectorWorker"
        )
        self.detector_thread.start()
        self.logger.info("SignalPipeline initialized with detector worker thread")
    
    def _detector_worker(self) -> None:
        """parts와 posture를 순차적으로 처리하는 워커 스레드"""
        self.logger.info("Detector worker thread started")
        
        while not self.stop_event.is_set():
            try:
                # DetectionTask 객체 가져오기
                task: DetectionTask = self.task_queue.get(timeout=0.1)
                
                # 오래 걸리는 작업들을 순차적으로 처리
                parts_position = self.parts_detector.detect(task.heatmap)
                posture_type = self.posture_detector.detect(task.heatmap)

                # 로컬 저장 및 서버 업로드
                is_synced = self.pressure_cache.log(task.timestamp, task.heatmap, parts_position, posture_type)
                
                # DetectionResult 객체 생성 및 큐에 추가
                result = DetectionResult(
                    heatmap=task.heatmap,
                    parts=parts_position,
                    posture=posture_type,
                    timestamp=task.timestamp,
                    synced=is_synced
                )
                
                self.result_queue.put(result)

                self.logger.debug(f"Detection completed for timestamp {task.timestamp}")
                
            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in detector worker: {e}", exc_info=True)
                continue
        
        self.logger.info("Detector worker thread stopped")
    
    def process(self, signal: SerialSignal) -> None:
        """신호를 받아 처리 작업을 큐에 추가"""
        now = datetime.now()
        
        # Heatmap 변환
        heatmap = self.heatmap_converter.convert(
            signal.head, 
            signal.body, 
            method=HeatmapInterpolationMethod.CUBIC
        )
        self.heatmap_rt.sync(heatmap)
        
        # DetectionTask 객체 생성 및 큐에 추가
        task = DetectionTask(
            heatmap=heatmap,
            timestamp=now
        )
        self.task_queue.put(task)
        self.logger.debug(f"Task added to queue for timestamp {now}")
    
    def stream(self) -> Generator[Tuple[np.ndarray, PartPositions, PostureType], None, None]:
        """처리된 결과를 연속적으로 yield하는 generator
        
        Yields:
            Tuple[np.ndarray, PartPositions, PostureType]: (heatmap, parts, posture)
        """
        self.logger.info("Stream generator started")
        
        while True:
            try:
                # DetectionResult 객체 가져오기
                result: DetectionResult = self.result_queue.get(timeout=0.1)
                
                # 튜플 형태로 yield
                yield (
                    result.heatmap,
                    result.parts,
                    result.posture
                )
                
                self.logger.debug(f"Result yielded for timestamp {result.timestamp}")
                
            except Empty:
                # 큐가 비어있으면 계속 대기
                continue
            except Exception as e:
                self.logger.error(f"Error in stream: {e}", exc_info=True)
                continue
    
    def stop(self) -> None:
        """스레드 정리 및 종료"""
        self.logger.info("Stopping SignalPipeline")
        
        # 종료 신호 설정
        self.stop_event.set()
        
        # 스레드 종료 대기
        self.detector_thread.join(timeout=2.0)
        
        if self.detector_thread.is_alive():
            self.logger.warning("Detector thread did not stop gracefully")
        
        # 남은 작업 큐 비우기
        task_count = 0
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
                task_count += 1
            except Empty:
                break
        
        if task_count > 0:
            self.logger.info(f"Cleared {task_count} pending tasks from task queue")
        
        # 남은 결과 큐 비우기
        result_count = 0
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
                result_count += 1
            except Empty:
                break
        
        if result_count > 0:
            self.logger.info(f"Cleared {result_count} pending results from result queue")
        
        self.logger.info("SignalPipeline stopped")
    
    def get_queue_sizes(self) -> Tuple[int, int]:
        """큐 상태 확인용 메서드 (디버깅용)
        
        Returns:
            Tuple[int, int]: (task_queue_size, result_queue_size)
        """
        return self.task_queue.qsize(), self.result_queue.qsize()