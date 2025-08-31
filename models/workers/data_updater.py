import time

from PySide6.QtCore import QThread, Signal

from data_structures.enums import PerformanceDataType
from utils.logger import logger


class RtpmDataUpdater(QThread):
    inference_time_updated = Signal(int, int, int)
    fps_updated = Signal(int, int)
    cpu_updated = Signal(int, int)
    memory_updated = Signal(int, int)
    npu_usage_updated = Signal(int, tuple)
    updater_finished = Signal()

    def __init__(self, vision_protocol):
        super().__init__()
        self.vision_protocol = vision_protocol
        self.is_running = False

    def run(self):
        self.is_running = True
        logger.info("Data updater started.")
        get_performance_data = self.vision_protocol.gerPerformanceData

        while self.is_running:
            data_list = get_performance_data()
            if data_list:
                data_type = data_list[0]
                if data_type == PerformanceDataType.INFERENCE_TIME:
                    self.inference_time_updated.emit(data_list[1], data_list[2], data_list[3])
                elif data_type == PerformanceDataType.FPS:
                    self.fps_updated.emit(data_list[1], data_list[2])
                elif data_type == PerformanceDataType.CPU_PERFORMANCE:
                    self.cpu_updated.emit(data_list[1], data_list[2])
                elif data_type == PerformanceDataType.MEMORY:
                    self.memory_updated.emit(data_list[1], data_list[2])
                elif data_type == PerformanceDataType.NPU_USAGE:
                    self.npu_usage_updated.emit(data_list[1], data_list[2])
            
            time.sleep(0.001) # Avoid busy waiting
        
        logger.info("Data updater finished.")
        self.updater_finished.emit()

    def start_updater(self):
        self.is_running = True
        self.start()

    def stop_updater(self):
        self.is_running = False