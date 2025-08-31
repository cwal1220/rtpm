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

## 6. 추가 디버깅 및 안정화

리팩토링 이후 발생한 여러 문제들을 해결하고 애플리케이션의 안정성을 높였습니다.

### 6.1. UI 위젯 렌더링 오류 (`TypeError`) 해결
*   **문제**: `RtpmMainTextWidget.py`에서 `QGridLayout.addWidget` 호출 시 `TypeError`가 지속적으로 발생하며 UI가 렌더링되지 않았습니다.
*   **해결**:
    *   근본 원인을 찾기 어려운 `QGridLayout` 관련 문제를 회피하기 위해, `infBox`와 `npuBox`의 레이아웃을 `QVBoxLayout`으로 변경하여 문제를 해결했습니다.
    *   `QUiLoader`로 로드된 UI 위젯에 접근 시 `self.ui` 접두사가 누락되어 발생한 `AttributeError`를 수정했습니다. 모든 위젯 접근 코드를 `self.ui.widgetName` 형태로 변경하여 UI 요소에 정상적으로 접근하도록 했습니다.

### 6.2. `numpy` 호환성 문제 해결
*   **문제**: 가상 환경 재구성 후, `numpy.dtype size changed` `ValueError`가 발생하며 애플리케이션이 시작되지 않았습니다. 이는 컴파일된 Cython 모듈(`visionprotocol`)과 설치된 `numpy` 버전 간의 바이너리 비호환성 문제였습니다.
*   **해결**: `numpy` 버전을 호환성이 확인된 `1.26.4`로 다운그레이드하여 문제를 해결했습니다.

### 6.3. `VisionProtocol` 초기화 블로킹 문제 해결
*   **문제**: `VisionProtocol` 객체 생성자(`__init__`)의 블로킹 동작으로 인해 UI 스레드가 멈춰 화면이 나타나지 않는 현상이 있었습니다.
*   **해결**:
    *   `VisionProtocol`의 생성자에서는 간단한 변수 초기화만 수행하도록 변경했습니다.
    *   `VisionProtocolModule` 생성과 같이 시간이 오래 걸리는 블로킹 코드들을 `run` 메서드로 이동시켰습니다.
    *   `main_view_model.py`에서 `VisionProtocol` 스레드를 `on_start_stop` 슬롯 내에서, 즉 **Start** 버튼 클릭 시점에 시작하도록 변경하여 UI 블로킹을 완전히 해결했습니다.

### 6.4. 불필요한 코드 제거
*   **`view/RtpmMainTextWidget.py`**:
    *   사용되지 않는 `__initTextView`와 `onUpdateInferenceTimeGraphSlot` 메서드를 제거했습니다.
    *   관련된 주석 처리된 코드 블록도 함께 삭제하여 코드 가독성을 높였습니다.
*   **`controller/main_view_model.py`**:
    *   사용되지 않는 `__captureFrame` 인스턴스 변수를 제거했습니다.

### 6.5. 데이터 처리 오류 (`KeyError`) 수정
*   **문제**: `processing_worker.py`에서 탐지 결과(`result_list`) 처리 시, 데이터 구조가 중첩되어 있거나 특정 키(`'od'`)가 없는 경우 `KeyError`가 발생했습니다.
*   **해결**: `result_list`를 순회하며 `'od'` 키가 존재하는지 먼저 확인하고, 중첩된 구조 안의 데이터도 정상적으로 처리하도록 로직을 수정하여 안정성을 높였습니다.

### 6.6. 프로그레스 바 업데이트 오류 수정
*   **문제**: 파일 처리 시 프로그레스 바가 갱신되지 않았습니다. 이는 **Start** 버튼을 누를 때마다 `RtpmFileReader` 워커가 새로 생성되지만, 이 새 워커의 시그널이 UI 슬롯에 연결되지 않았기 때문입니다.
*   **해결**: `main_view_model.py`의 구조를 리팩토링하여, 워커가 새로 생성될 때마다 시그널-슬롯 연결이 다시 이루어지도록 `_connect_worker_signals` 메서드를 도입하고 호출 로직을 수정했습니다.

## 7. Performance Tab UI/Logic Refinement

The "Performance" tab's UI and underlying logic were significantly refactored to improve readability, modernize its appearance, and correctly display per-NPU metrics.

### 7.1. UI (`RtpmMainTextWidget.ui`) Changes

*   **Widget Type Transition**: Replaced all `QLCDNumber` instances with `QLabel` for value displays to allow for more flexible styling and modern typography.
*   **Progress Bar Integration**: Added `QProgressBar` widgets for percentage-based metrics (CPU, Memory, NPU Utilization) to provide intuitive visual feedback alongside numerical values.
*   **Refined Styling**:
    *   Adjusted `QLabel[objectName$="ValueLabel"]` font size from `24pt` to `18pt` and changed color from vibrant green (`#00FF00`) to a softer, more professional green (`#66BB6A`).
    *   Updated `QProgressBar::chunk` background color to match the new softer green (`#66BB6A`).
    *   Applied consistent padding (`10px`) to `QGroupBox` elements for better visual spacing.
*   **Per-NPU Metric Display**:
    *   Modified `infBox` (Inference Time) to include separate `QLabel`s (`inf0ValueLabel`, `inf1ValueLabel`) for NPU 0 and NPU 1 inference times. Static labels ("NPU 0", "NPU 1") were added for clarity.
    *   Modified `npuBox` (NPU Utilization) to include separate `QLabel`s (`npu0ValueLabel`, `npu1ValueLabel`) and `QProgressBar`s (`npu0ProgressBar`, `npu1ProgressBar`) for NPU 0 and NPU 1 utilization. Static labels ("NPU 0", "NPU 1") were added.
*   **UI File Integrity Fix**: Corrected an XML parsing error (`Unexpected element string`) in the `styleSheet` property by removing a nested `<string notr="true">` tag, ensuring the UI file loads correctly.

### 7.2. Python Logic (`RtpmMainTextWidget.py`) Changes

*   **Widget Management Refactoring**:
    *   Replaced the list-of-lists `self.__dataEditList` with a more readable and maintainable dictionary `self.__performanceWidgets`. This dictionary now stores widgets (or dictionaries of widgets for combined displays like value/progress bar) under descriptive string keys (e.g., `"inference_time"`, `"npu_utilization"`, `"cpu"`).
    *   Updated `initMonitoringView` to populate `self.__performanceWidgets` by directly referencing the newly defined UI widgets (e.g., `self.ui.inf0ValueLabel`, `self.ui.npu0ProgressBar`), removing dynamic widget creation for these specific metrics.
*   **Dynamic Update Logic Adaptation**:
    *   `__updateChart` function was significantly refactored to accept string keys (e.g., `"inference_time"`) instead of integer indices. It now intelligently updates `QLabel`s (using `setText()` with appropriate formatting like "ms" or "%") and `QProgressBar`s (using `setValue()`) based on the widget type and the performance metric. It also correctly handles per-NPU updates for "inference_time" and "npu_utilization" based on the `index` parameter.
    *   `__clearChart` function was updated to iterate through the new `self.__performanceWidgets` dictionary and clear/reset all performance display widgets (both `QLabel`s and `QProgressBar`s) to their initial states.
*   **Signal Slot Adaptations**:
    *   All `onUpdate...Slot` functions (`onUpdateResultPerfSlot`, `onUpdateCpuGraphSlot`, `onUpdateMemoryGraphSlot`, `onUpdateFpsGraphSlot`, `onUpdateNpuUsageGraphSlot`) were updated to pass the new string keys (e.g., `"inference_time"`, `"cpu"`) to `__updateChart`, aligning with the refactored widget management.
*   **Indentation Fix**: Corrected an `IndentationError` in the `initMonitoringView` function, ensuring proper Python syntax.
*   **Improved Debugging**: Enhanced error handling in `onUpdateImageSlot` to print full tracebacks, aiding in future debugging efforts.

## 8. COCO 포맷 예측 데이터 저장 및 시각화 개선

### 8.1. COCO 포맷 예측 데이터 저장
*   **설정 파일 통합**: `config/Setting.yaml`을 `config/settings.py`로 마이그레이션하고, `pyyaml` 의존성을 제거했습니다.
*   **버전 정보 관리**: 애플리케이션 버전 정보를 `main.py`에서 `version.py` 파일로 분리하고, 시작 시 버전이 출력되도록 했습니다.
*   **라벨 관리 시스템**: 프로젝트 루트에 `labels` 디렉토리를 생성하고, `coco.txt` 파일을 통해 COCO 카테고리 이름을 관리하도록 했습니다.
*   **`PostProcessor.py` 리팩토링**:
    *   `saveResultData` 함수를 제거하고, `create_image_entry` 및 `create_prediction_annotations` 헬퍼 함수를 도입했습니다.
    *   `_create_coco_annotation` 함수에서 모델의 0-기반 `category_id`를 COCO 표준 1-기반으로 변환하도록 수정했습니다.
    *   `score` 값을 0-100 범위에서 0.0-1.0 범위로 정규화하도록 수정했습니다.
*   **`processing_worker.py` 리팩토링**:
    *   `PostProcessor`의 헬퍼 함수들을 사용하여 이미지별 `image` 객체와 `annotation` 리스트를 누적하도록 변경했습니다.
    *   모든 처리가 완료된 후, 누적된 `image` 객체, `annotation` 리스트, `categories` 정보를 포함하는 **단일 `coco_predictions.json` 파일**을 생성하도록 `_cleanup` 메서드를 수정했습니다. 이 파일은 `classification` 결과와 같은 비표준 필드도 `image` 객체 내에 포함합니다.

### 8.2. 시각화 개선
*   **동적 색상 생성**: `PostProcessor.py`에서 하드코딩된 `COLOR_LIST`를 제거하고, `_get_color_for_id` 헬퍼 함수를 통해 `category_id` 또는 `npu_index`에 따라 동적으로 색상을 생성하도록 변경했습니다.
*   **`draw_object_detection_boxes` 함수 개선**:
    *   바운딩 박스 텍스트에 `npu_index` 정보 추가.
    *   텍스트 가시성 향상: 텍스트 뒤에 배경 사각형을 그리고, 텍스트 색상과 폰트 크기/두께를 조정하여 가독성을 높였습니다.
*   **함수명 변경**:
    *   `drawBoundingBox` → `draw_object_detection_boxes`
    *   `printClassification` → `draw_classification_results`

## 9. 버그 수정 및 안정화

*   **`NameError` 수정**: `view_models/main_view_model.py`에서 `settings` 모듈 import 누락으로 인한 `NameError`를 수정했습니다.
*   **`AttributeError` 수정**: `models/VisionProtocol.py`에서 `time` 모듈 import 오류로 인한 `AttributeError`를 수정했습니다.
*   **`ruff` 코드 스타일 적용**: 프로젝트 전체에 `ruff`를 적용하여 불필요한 import 제거 및 import 순서 정렬 등 코드 스타일을 최적화했습니다. (단, `third_party` 폴더는 제외)