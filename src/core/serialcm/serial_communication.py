from datetime import datetime
from typing import Optional, Union
import time
import re
import serial
import threading
import logging
from glob import glob

import numpy as np
from core.serialcm.serial_signal import SerialSignal
from src.core.config_manager import config_manager

BOARDS = [f"UNO{i}_" for i in range(0, 7)]  # UNO0_ ~ UNO6_
HEAD_BOARD = "UNO0_"
"""
- UNO0 (무MUX): C0~C5 → A: C0~C2, B: C3~C5  (7칸 폭 '가운데 정렬')
- UNO1~UNO6 (MUX): A: C0~C6, B: C7~C13
- 허용 포맷:
  1) UNO{n}_Ck : v
  2) [UNO{n}] Ck=v
"""

class BoardData:
    def __init__(self, board: str, receive_time: datetime, data: dict):
        self.board = board
        self.receive_time = receive_time
        self.data = data

class SerialCommunication:
    boards = {}  # {board: Device}
    boards_lock = threading.Lock()
    update_cv = threading.Condition(boards_lock)
    revision = 0
    communication_logger = logging.getLogger("serial_communication")
    
    @staticmethod
    def _get_baud_rate():
        baud_rate = config_manager.get_setting("serial", "baud_rate", fallback="9600")
        return int(baud_rate if baud_rate else 9600)

    @staticmethod
    def _get_timeout():
        serial_timeout = config_manager.get_setting("serial", "timeout", fallback="2.0")
        return float(serial_timeout if serial_timeout else 2.0)

    def __init__(self):
        self.ports = []  # list of serial ports
        self.threads = []  # list of serial threads

    def start(self):
        if not self._find_ports():
            return False
        self._generate_serial_threads()
        return True

    def _convert_to_matrix(self, boards: dict) -> tuple[np.ndarray, np.ndarray]:
        """Convert board data to matrix format (head, body)"""
        head = np.zeros((2, 3))
        body = np.zeros((12, 7))

        for idx, board in enumerate(BOARDS):
            data = boards.get(board)
            if not data:
                continue
            data = data.data
            if not data:
                continue

            top = 2 * idx
            bottom = top + 1

            if board == HEAD_BOARD:
                for c in range(3):
                    val = data.get(f"{board}C{c}")
                    if val:
                        head[top][c] = val
                for c in range(3):
                    val = data.get(f"{board}C{3 + c}")
                    if val:
                        head[bottom][c] = val
            else:
                for c in range(7):
                    val = data.get(f"{board}C{c}")
                    if val:
                        body[top-2][c] = val
                for c in range(7):
                    val = data.get(f"{board}C{7 + c}")
                    if val:
                        body[bottom-2][c] = val
        return head, body

    def stream(self):
        min_interval = config_manager.get_setting("stream", "min_interval", fallback="0.1")
        timeout = config_manager.get_setting("stream", "timeout", fallback="0.1")
        min_interval = float(min_interval if min_interval else 0.1)
        timeout = float(timeout if timeout else 0.1)

        last_rev = -1
        last_emit = 0.0
        while True:
            with self.update_cv:
                self.update_cv.wait(timeout=timeout)
                rev_now = self.revision
                board_snapshot = SerialCommunication.boards
                now = time.time()

            if rev_now == last_rev and (now - last_emit) < min_interval:
                continue

            head, body = self._convert_to_matrix(board_snapshot)
            last_rev = rev_now
            last_emit = now
            yield SerialSignal(datetime.fromtimestamp(now), head, body)

    def _find_ports(self) -> list:
        self.ports = sorted(glob("/dev/ttyACM*") + glob("/dev/ttyUSB*"))
        self.communication_logger.info(f"Found {len(self.ports)} ports")
        return self.ports

    @staticmethod
    def _parse(line: str, port: str) -> Optional[BoardData]:
        line = line.strip()
        if not line:
            SerialCommunication.communication_logger.debug(f"Empty line received from {port}")
            return None
        
        SerialCommunication.communication_logger.debug(f"Parsing line from {port}: {line}")
        
        matched_str = re.search(r"\b(UNO[0-6]_)C\d+\s*[:=]\s*-?\d+\b", line, flags=re.IGNORECASE)
        if matched_str:
            board = matched_str.group(1).upper()  # UNO0_
            data = {}
            for matched_str in re.finditer(rf"({board}C(\d+))\s*[:=]\s*(-?\d+)", line, flags=re.IGNORECASE):
                ch = int(matched_str.group(2))
                val = int(matched_str.group(3))
                data[f"{board}C{ch}"] = val
            SerialCommunication.communication_logger.info(f"Successfully parsed UNO format data from {port}: {data}")
            return BoardData(board, datetime.now(), data)
        
        matched_str = re.search(r"\[\s*(UNO[0-6])\s*\]", line, flags=re.IGNORECASE)
        if matched_str:
            bnorm = matched_str.group(1).upper()  # UNO0
            board = f"{bnorm}_"
            rest = re.sub(r'^\s*\[\s*' + bnorm + r'\s*\]\s*', '', line, flags=re.IGNORECASE)
            data = {}
            for matched_str in re.finditer(r'\bC\s*(\d+)\s*[:=]\s*(-?\d+)\b', rest):
                ch = int(matched_str.group(1))
                val = int(matched_str.group(2))
                data[f"{board}C{ch}"] = val
            SerialCommunication.communication_logger.info(f"Successfully parsed bracket format data from {port}: {data}")
            return BoardData(board, datetime.now(), data)
        
        SerialCommunication.communication_logger.warning(f"Failed to parse line from {port}: {line}")
        return None

    @staticmethod
    def _serial_thread(port):
        SerialCommunication.communication_logger.info(f"Starting serial thread for {port}")
        try:
            baud_rate = SerialCommunication._get_baud_rate()
            timeout = SerialCommunication._get_timeout()
            s = serial.Serial(port, baud_rate, timeout=timeout)
            SerialCommunication.communication_logger.info(f"Serial connection established for {port}")
            time.sleep(2.0)  # wait for arduino to reset
            s.reset_input_buffer()
            SerialCommunication.communication_logger.info(f"Input buffer reset for {port}")

            while True:
                line = s.readline()
                if not line:
                    continue
                try:
                    line = line.decode("utf-8").strip()
                except UnicodeDecodeError:
                    SerialCommunication.communication_logger.warning(f"Unicode decode error for {port}: {line}")
                    continue
                except Exception as e:
                    SerialCommunication.communication_logger.error(f"Error decoding line from {port}: {e}")
                    continue

                data = SerialCommunication._parse(line, port)
                if not data:
                    continue
                with SerialCommunication.update_cv:
                    SerialCommunication.boards[data.board] = data
                    SerialCommunication.revision += 1
                    SerialCommunication.update_cv.notify_all()
                    SerialCommunication.communication_logger.debug(f"Device data updated for {data.board}: {data.data}")
        except Exception as e:
            SerialCommunication.communication_logger.error(f"Serial thread error for {port}: {e}")
            return

    def _generate_serial_threads(self):
        for port in self.ports:
            new_thread = threading.Thread(target=SerialCommunication._serial_thread, args=(port,), daemon=True)
            self.threads.append(new_thread)
            self.communication_logger.info(f"Started thread for {port}")
            new_thread.start()