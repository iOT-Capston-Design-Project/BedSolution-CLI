import csv
import datetime
import time
from pathlib import Path
from typing import List, Dict, Any
from abc import ABC, abstractmethod

from service.signal_analyze.signal_analyzer import AnalyzeResult
from core.server.models.pressure_log import PressureLog


class CSVHandler(ABC):
    """Abstract base class for CSV file operations"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
    
    @abstractmethod
    def save(self, data: Any) -> None:
        """Save data to CSV file"""
        pass
    
    def _write_csv_row(self, file_path: Path, headers: List[str], row: List[Any]) -> None:
        """Generic CSV writing method"""
        try:
            file_exists = file_path.exists()
            
            with open(file_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                if not file_exists:
                    writer.writerow(headers)
                
                writer.writerow(row)
                
        except Exception as e:
            print(f"Error writing to CSV file {file_path}: {e}")


class AnalyzeResultCSVHandler(CSVHandler):
    """Handler for AnalyzeResult CSV operations"""
    
    def save(self, data: AnalyzeResult) -> None:
        """Save AnalyzeResult to daily CSV file"""
        today = datetime.date.today().isoformat()
        csv_path = self.data_dir / f"analyze_results_{today}.csv"
        
        flattened_map = data.map.flatten()
        
        headers = ['timestamp', 'posture'] + [f'map_{i}' for i in range(len(flattened_map))]
        row = [time.time(), data.posture.value] + flattened_map.tolist()
        
        self._write_csv_row(csv_path, headers, row)


class PressureLogCSVHandler(CSVHandler):
    """Handler for PressureLog CSV operations"""
    
    def save(self, data: PressureLog) -> None:
        """Save PressureLog to daily CSV file"""
        today = datetime.date.today().isoformat()
        csv_path = self.data_dir / f"pressure_logs_{today}.csv"
        
        headers = ['id', 'day_id', 'created_at', 'occiput', 'scapula', 'elbow', 'heel', 'hip']
        row = [
            data.id,
            data.day_id,
            data.createdAt.isoformat(),
            data.occiput,
            data.scapula,
            data.elbow,
            data.heel,
            data.hip
        ]
        
        self._write_csv_row(csv_path, headers, row)


class CSVManager:
    """Manager class that orchestrates different CSV handlers"""
    
    def __init__(self, data_dir: Path):
        self.analyze_result_handler = AnalyzeResultCSVHandler(data_dir)
        self.pressure_log_handler = PressureLogCSVHandler(data_dir)
    
    def save_analyze_result(self, data: AnalyzeResult) -> None:
        """Save AnalyzeResult to CSV"""
        self.analyze_result_handler.save(data)
    
    def save_pressure_log(self, data: PressureLog) -> None:
        """Save PressureLog to CSV"""
        self.pressure_log_handler.save(data)