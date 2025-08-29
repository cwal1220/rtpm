# RTPM 프로젝트 리팩토링 로그

## 1. 서론

본 문서는 Telechips RTPM(Real-Time Performance Monitoring) 프로젝트에 대한 대규모 리팩토링 작업 내용을 상세히 기록합니다. 이번 리팩토링의 주요 목표는 다음과 같습니다.

*   **MVVM(Model-View-ViewModel) 아키텍처 도입**: 코드의 관심사를 명확히 분리하고, UI와 비즈니스 로직 간의 결합도를 낮춰 유지보수성, 확장성, 테스트 용이성을 향상시킵니다.
*   **PySide6로 GUI 프레임워크 전환**: 기존 PyQt5의 라이선스 제약(GPL)을 해결하고, Qt의 공식 Python 바인딩인 PySide6(LGPL)를 사용하여 최신 기능과 안정성을 확보합니다.
*   **코드 품질 향상**: 전역 변수 제거, 매직 넘버/문자열 상수화, 로깅 시스템 도입, 대규모 클래스/메서드 분리 등을 통해 코드의 가독성, 안정성, 디버깅 용이성을 높입니다.

## 2. 상위 수준 변경 사항 요약

### 2.1. PySide6로 GUI 프레임워크 전환
*   `requirements.txt`에서 `PyQt5`, `PyQt5-Qt5`, `PyQt5-sip`, `PySide2`, `shiboken2` 등의 의존성을 제거하고 `PySide6`로 통일했습니다.
*   프로젝트 내 모든 `.py` 파일에서 `PyQt5` 임포트 구문을 `PySide6`로 변경하고, `@pyqtSlot`을 `@Slot`으로, `pyqtSignal`을 `Signal`로 변경했습니다.
*   `.ui` 파일 로딩 방식(`uic.loadUi`)을 `PySide6.QtUiTools.QUiLoader`를 사용하는 방식으로 변경했습니다.

### 2.2. MVVM 아키텍처 도입
*   기존의 `controller/RtpmController.py` 파일을 `controller/main_view_model.py`로 이름을 변경하고, `QThread` 상속 대신 `QObject`를 상속하는 `MainViewModel` 클래스로 리팩토링했습니다.
*   `RtpmController` 내부에 있던 `RtpmVideoRecorder`, `RtpmImageSaver`, `RtpmDataUpdater`, `RtpmFileReader` 클래스들을 `model/workers` 디렉토리 아래 별도의 파일로 분리했습니다.
*   애플리케이션의 핵심 처리 로직을 담당하는 `ProcessingWorker` 클래스를 새로 도입하여 `MainViewModel`로부터 분리했습니다.
*   뷰(View), 뷰모델(ViewModel), 워커(Worker) 간의 통신을 직접적인 객체 참조 대신 `Signal`과 `Slot` 메커니즘을 통해 이루어지도록 변경하여 결합도를 최소화했습니다.
*   `main.py` 파일은 이제 `MainViewModel`과 `RtpmMainWidget`(View)을 생성하고 연결하는 역할을 담당합니다.

### 2.3. 로깅 시스템 통합
*   `msg/logger.py` 파일을 생성하여 중앙 집중식 로깅 시스템을 구축했습니다.
*   `VisionProtocol.py` 및 모든 워커 클래스(`file_reader.py`, `image_saver.py`, `video_recorder.py`, `data_updater.py`, `processing_worker.py`) 내의 `print()` 구문을 `logger.info()`, `logger.warning()`, `logger.error()` 등의 로거 호출로 대체하여 체계적인 로그 관리가 가능하도록 했습니다.

### 2.4. 상수 및 Enum 도입
*   `msg/enums.py` 파일을 생성하여 `ResultType`, `PerformanceDataType` 등 코드 내에 하드코딩되어 있던 "매직 넘버"들을 의미 있는 Enum으로 정의했습니다.
*   `model/VisionProtocol.py` 및 `model/workers/data_updater.py` 등 관련 모듈에서 이 Enum들을 사용하여 코드의 가독성과 유지보수성을 향상시켰습니다.

## 3. 세부 변경 사항

### 3.1. `requirements.txt`
*   **변경 전**: `opencv-python==4.6.0.66`, `PyQt5==5.15.7`, `PyQt5-Qt5==5.15.2`, `PyQt5-sip==12.11.0`, `PySide2==5.15.2.1`, `shiboken2==5.15.2.1`, `imagesize==1.4.1`, `matplotlib==3.8.0`, `pyyaml==6.0.1`
*   **변경 후**: `PySide6==6.7.0`, `opencv-python==4.6.0.66`, `imagesize==1.4.1`, `matplotlib==3.8.0`, `pyyaml==6.0.1`, `numpy`
*   **내용**: 불필요한 PyQt5/PySide2 의존성을 제거하고 PySide6로 단일화했습니다.

### 3.2. `main.py`
*   **변경 내용**:
    *   `from controller import *` 대신 `from controller.main_view_model import MainViewModel`을 임포트하도록 변경했습니다.
    *   `PySide6.QtWidgets.QApplication` 및 `QWidget`를 직접 임포트하도록 수정했습니다.
    *   `Main` 클래스 내에서 `initControllers()`를 `init_view_model()`로, `initViews()`를 `init_views()`로 이름을 변경했습니다.
    *   `init_view_model()`에서 `MainViewModel`을 인스턴스화하고, `start()` 메서드에서 `viewModel.connect_signals(self.rtpmMainWidget)`를 호출하여 뷰와 뷰모델을 연결하도록 했습니다.
    *   `app.exec_()`를 `app.exec()`로 변경했습니다.

### 3.3. `controller/main_view_model.py` (이전 `controller/RtpmController.py`)
*   **파일 이름 변경**: `RtpmController.py` -> `main_view_model.py`
*   **클래스 이름 및 상속 변경**: `class RtpmController(QThread)` -> `class MainViewModel(QObject)`
*   **전역 변수 제거**: `gFolderModePath`, `gImageResultPath`, `gDataResultPath` 등의 전역 변수를 `MainViewModel`의 인스턴스 변수(`self.folder_mode_path` 등)로 변경했습니다.
*   **워커 클래스 분리 및 임포트**:
    *   파일 내부에 정의되어 있던 `RtpmVideoRecorder`, `RtpmImageSaver`, `RtpmDataUpdater`, `RtpmFileReader` 클래스 정의를 모두 제거했습니다.
    *   `from model.workers import ...` 구문을 통해 분리된 워커 클래스들을 임포트하도록 변경했습니다.
    *   `ProcessingWorker` 및 `WorkerConfig`를 `model.workers.processing_worker`에서 임포트하도록 했습니다.
*   **`run` 메서드 제거**: `MainViewModel`이 더 이상 스레드가 아니므로 `run` 메서드를 제거하고, 해당 로직은 `ProcessingWorker`로 완전히 이관했습니다.
*   **워커 인스턴스화 및 관리**:
    *   `_init_workers()` 메서드에서 각 워커 클래스들을 인스턴스화하도록 했습니다.
    *   `ProcessingWorker`는 `on_start_stop` 메서드 내에서 `WorkerConfig` 객체와 함께 동적으로 생성되도록 변경하여, ViewModel의 상태를 워커에 명시적으로 전달하도록 했습니다.
*   **시그널/슬롯 연결 강화**:
    *   뷰(View)에서 발생하는 시그널을 뷰모델의 슬롯(`on_start_stop` 등)에 연결했습니다.
    *   뷰모델에서 뷰로 데이터를 전달하기 위한 새로운 시그널들(`update_image_signal`, `update_progress_bar_signal` 등)을 정의했습니다.
    *   각 워커에서 발생하는 시그널을 뷰모델의 슬롯에 연결하고, 뷰모델은 이를 받아 뷰로 다시 시그널을 발생시키는 브리지 역할을 하도록 했습니다.
*   **메서드 단순화**: `on_start_stop` 메서드 내의 복잡한 로직을 `_setup_model()`, `_setup_save_paths()` 등으로 분리하여 가독성을 높였습니다.
*   **로깅 적용**: `logger`를 임포트하고 `print()` 구문을 로거 호출로 대체했습니다.

### 3.4. `model/workers/` 디렉토리 및 워커 파일들
*   **디렉토리 생성**: `model/workers/` 디렉토리를 새로 생성했습니다.
*   **`__init__.py`**: `model/workers/__init__.py` 파일을 생성하고, 분리된 워커 클래스들을 임포트하도록 했습니다.
*   **각 워커 파일 리팩토링**:
    *   **`video_recorder.py` (RtpmVideoRecorder)**:
        *   `parent` 의존성을 제거하고, `__init__` 메서드를 단순화했습니다.
        *   `startRecord`를 `start_recorder`로 이름을 변경하고, 필요한 모든 인자를 명시적으로 받도록 했습니다.
        *   `print()` 구문을 `logger` 호출로 대체했습니다.
    *   **`image_saver.py` (RtpmImageSaver)**:
        *   `parent` 의존성 및 `global gFolderModePath`를 제거했습니다.
        *   `startSave`를 `start_saver`로 이름을 변경하고, `vision_protocol` 및 `folder_mode_path`를 포함한 모든 인자를 명시적으로 받도록 했습니다.
        *   `print()` 구문을 `logger` 호출로 대체했습니다.
    *   **`data_updater.py` (RtpmDataUpdater)**:
        *   `parent` 의존성을 제거하고, `__init__`에서 `vision_protocol`을 직접 받도록 했습니다.
        *   `startUpdate`를 `start_updater`로, `stopUpdate`를 `stop_updater`로 이름을 변경했습니다.
        *   데이터 타입 비교에 `msg.enums.PerformanceDataType`를 사용하도록 변경했습니다.
        *   `print()` 구문을 `logger` 호출로 대체했습니다.
        *   `inference_time_updated`, `fps_updated` 등 각 데이터 타입별 시그널을 정의하여 뷰모델로 데이터를 전달하도록 했습니다.
    *   **`file_reader.py` (RtpmFileReader)**:
        *   `parent` 의존성 및 `__rtpmMainWidget` 참조를 제거했습니다.
        *   `__init__`에서 `vision_protocol`과 `base_size_tuple`을 직접 받도록 했습니다.
        *   `startRead`를 `start_reader`로, `stopRead`를 `stop_reader`로 이름을 변경했습니다.
        *   `progress_updated`, `file_read`, `error_occurred` 등 새로운 시그널을 정의하여 뷰모델로 상태 및 데이터를 전달하도록 했습니다.
        *   `print()` 구문을 `logger` 호출로 대체했습니다.
    *   **`processing_worker.py` (ProcessingWorker)**:
        *   새로 생성된 핵심 워커 클래스입니다.
        *   `WorkerConfig` 데이터 클래스를 도입하여 `MainViewModel`의 상태를 명시적으로 전달받도록 했습니다.
        *   기존 `RtpmController.run` 메서드의 핵심 로직을 이관했습니다.
        *   `frame_processed`, `processing_finished` 시그널을 통해 뷰모델과 통신합니다.
        *   `print()` 구문을 `logger` 호출로 대체했습니다.

### 3.5. `msg/enums.py`
*   **생성**: `msg/enums.py` 파일을 새로 생성했습니다.
*   **내용**:
    ```python
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
    ```
*   **내용**: 코드 내의 매직 넘버를 대체할 Enum들을 정의했습니다.

### 3.6. `msg/logger.py`
*   **생성**: `msg/logger.py` 파일을 새로 생성했습니다.
*   **내용**:
    ```python
    import logging
    import sys

    def setup_logger():
        logger = logging.getLogger('RTPM_APP')
        logger.setLevel(logging.DEBUG)

        if logger.hasHandlers():
            return logger

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.INFO)
        file_handler = logging.FileHandler('rtpm_app.log')
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stdout_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(stdout_handler)
        logger.addHandler(file_handler)

        return logger

    logger = setup_logger()
    ```
*   **내용**: 애플리케이션 전반에 걸쳐 사용될 중앙 집중식 로깅 설정을 정의했습니다.

### 3.7. `model/VisionProtocol.py`
*   **Enum 사용**: `msg.enums`에서 `ResultType`과 `PerformanceDataType`을 임포트하여 `run` 및 `__receiveData` 메서드 내의 매직 넘버를 대체했습니다.
*   **로깅 적용**: `msg.logger`에서 `logger`를 임포트하고 `print()` 구문을 `logger` 호출로 대체했습니다.

### 3.8. `model/PostProcessor.py`
*   **변경 없음**: 이번 리팩토링 단계에서는 `PostProcessor.py` 파일의 내용에 직접적인 변경은 적용되지 않았습니다. 주로 `RtpmController`에서 워커 분리 및 MVVM 아키텍처 적용에 중점을 두었기 때문입니다. 향후 추가적인 리팩토링 시 고려될 수 있습니다.

### 3.9. `__init__.py` 파일들
*   **`controller/__init__.py`**: `from .RtpmController import *` 대신 `from .main_view_model import MainViewModel`을 임포트하도록 변경했습니다.
*   **`model/__init__.py`**: `PyQt5` 관련 임포트 구문을 제거하고, `from .VisionProtocol import *`, `from .PostProcessor import *`, `from .YoloToCoCo import *`만 남겼습니다.
*   **`view/__init__.py`**: `PyQt5` 관련 임포트 구문을 제거하고, `from .RtpmMainTextWidget import *`만 남겼습니다.
*   **`model/workers/__init__.py`**: `from .file_reader import RtpmFileReader`, `from .data_updater import RtpmDataUpdater`, `from .image_saver import RtpmImageSaver`, `from .video_recorder import RtpmVideoRecorder`를 임포트하도록 추가했습니다.

## 4. 리팩토링의 이점

이번 리팩토링을 통해 다음과 같은 이점들을 얻었습니다.

*   **향상된 가독성**: 코드의 각 부분이 명확한 역할을 가지며, 매직 넘버가 제거되어 코드의 의미를 쉽게 파악할 수 있습니다.
*   **쉬운 유지보수**: 컴포넌트 간의 낮은 결합도로 인해 한 부분을 변경해도 다른 부분에 미치는 영향이 최소화됩니다.
*   **높은 테스트 용이성**: UI에 의존하지 않는 ViewModel과 워커들을 독립적으로 테스트하기 용이해졌습니다.
*   **확장성**: 새로운 기능 추가 시 기존 코드에 미치는 영향을 줄이고, 새로운 컴포넌트를 쉽게 통합할 수 있습니다.
*   **안정성 및 디버깅 용이성**: 체계적인 로깅 시스템 도입으로 애플리케이션의 동작을 추적하고 문제 발생 시 원인을 파악하기 쉬워졌습니다.
*   **라이선스 문제 해결**: PySide6 전환으로 상업적 활용에 대한 라이선스 제약이 완화되었습니다.

## 5. 향후 작업 (선택 사항)

*   `PostProcessor.py`의 그리기 로직을 더 추상화하거나, `TYPE_CLASSIFICATION`, `TYPE_OBJECTDETECTION`과 같은 매직 넘버를 Enum으로 대체하는 추가 리팩토링을 고려할 수 있습니다.
*   `VisionProtocol`의 C-바인딩 호출에서 발생하는 오류에 대한 더 강력하고 세분화된 오류 처리를 구현할 수 있습니다.
*   `ProcessingWorker` 내의 `_process_file_mode`에서 `frame_list` 동기화 메커니즘을 더 견고하게 만들 수 있습니다.

---
