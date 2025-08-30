from enum import Enum, auto

class ResultType(Enum):
    DETECTION_RESULT = 0
    PERFORMANCE_RESULT = 1
    MONITORING_DATA = 10

class PerformanceDataType(Enum):
    INFERENCE_TIME = 1
    FPS = 2
    CPU_PERFORMANCE = 3
    MEMORY = 4
    NPU_USAGE = 5
