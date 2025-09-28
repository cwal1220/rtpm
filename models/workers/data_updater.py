import time
import threading

from data_structures.enums import PerformanceDataType
import logging
logger = logging.getLogger(__name__)


class RtpmDataUpdater(threading.Thread):
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