'''
 * Copyright Telechips Inc.
 *
 * TCC Version 1.0
 *
 * This source code contains confidential information of Telechips.
 *
 * Any unauthorized use without a written permission of Telechips including not
 * limited to re-distribution in source or binary form is strictly prohibited.
 *
 * This source code is provided "AS IS" and nothing contained in this source code
 * shall constitute any express or implied warranty of any kind, including without
 * limitation, any warranty of merchantability, fitness for a particular purpose
 * or non-infringement of any patent, copyright or other third party intellectual
 * property right.
 * No warranty is made, express or implied, regarding the information's accuracy,
 * completeness, or performance.
 *
 * In no event shall Telechips be liable for any claim, damages or other
 * liability arising from, out of or in connection with this source code or
 * the use in the source code.
 *
 * This source code is provided subject to the terms of a Mutual Non-Disclosure
 * Agreement between Telechips and Company.
'''

from PySide6.QtCore import QObject, Signal, Slot
from model import VisionProtocol, PostProcessor
from model.workers import RtpmFileReader, RtpmDataUpdater, RtpmImageSaver, RtpmVideoRecorder
from model.workers.processing_worker import ProcessingWorker, WorkerConfig

from datetime import datetime
import os

class MainViewModel(QObject):
    # Signals to be emitted to the View
    update_image_signal = Signal(list)
    clear_image_signal = Signal()
    update_progress_bar_signal = Signal(int, int)
    clear_progress_bar_signal = Signal()
    update_result_perf_signal = Signal(int, int, int)
    update_fps_graph_signal = Signal(int, int)
    update_cpu_graph_signal = Signal(int, int)
    update_memory_graph_signal = Signal(int, int)
    update_npu_usage_signal = Signal(int, tuple)
    clear_all_graph_signal = Signal()
    show_message_box_signal = Signal(str, str)

    def __init__(self, parent, settingData):
        super().__init__(parent)
        self.parent = parent
        self.settingData = settingData
        self.visionProtocol = None
        self.postProcessor = None
        self.__processing_worker = None

        self._init_settings()
        self._init_state()
        self._setup_model(0)
        self._init_workers()

    def _init_settings(self):
        self.__frameWidth = self.settingData['Injection']['width']
        self.__frameHeight = self.settingData['Injection']['height']
        self.__frameChannel = self.settingData['Injection']['channel']
        self.__projframeWidth = self.settingData['Projection']['width']
        self.__projframeHeight = self.settingData['Projection']['height']
        self.__projframeChannel = self.settingData['Projection']['channel']
        self.__projframeHeightYV12 = self.__projframeHeight + (self.__projframeHeight >> 1)
        self.__videoFps = 30

    def _init_state(self):
        self.__monitoringStatus = False
        self.__controlStatus = False
        self.__fileSaveStatus = False
        self.__mode = False
        self.__frameList = []
        self.__frameListMax = 5
        self.__saveFrameList = []
        self.__captureFrame = False
        self.folder_mode_path = ''
        self.image_result_path = '/image_result'
        self.data_result_path = '/data_result'

    def _init_workers(self):
        self.__reader = RtpmFileReader(self.visionProtocol, (self.__frameHeight, self.__frameWidth, self.__frameChannel))
        self.__updater = RtpmDataUpdater(self.visionProtocol)
        self.__recorder = RtpmVideoRecorder()
        self.__imageSaver = RtpmImageSaver()

    def connect_signals(self, view):
        # View -> ViewModel
        view.rtpmStartStopSignal.connect(self.on_start_stop)

        # ViewModel -> View
        self.update_image_signal.connect(view.onUpdateImageSlot)
        self.clear_image_signal.connect(view.onClearImageSlot)
        self.update_progress_bar_signal.connect(view.onUpdateProgressBarSlot)
        self.clear_progress_bar_signal.connect(view.onClearProgressBarSlot)
        self.update_result_perf_signal.connect(view.onUpdateResultPerfSlot)
        self.update_fps_graph_signal.connect(view.onUpdateFpsGraphSlot)
        self.update_cpu_graph_signal.connect(view.onUpdateCpuGraphSlot)
        self.update_memory_graph_signal.connect(view.onUpdateMemoryGraphSlot)
        self.update_npu_usage_signal.connect(view.onUpdateNpuUsageGraphSlot)
        self.clear_all_graph_signal.connect(view.onClearAllGraphSlot)
        self.show_message_box_signal.connect(view.onShowMessageBoxSlot)

        # Worker -> ViewModel
        self.__reader.reader_stopped.connect(self.on_reader_stopped)
        self.__reader.progress_updated.connect(self.update_progress_bar_signal)
        self.__reader.error_occurred.connect(self.show_message_box_signal)
        self.__updater.inference_time_updated.connect(self.update_result_perf_signal)
        self.__updater.fps_updated.connect(self.update_fps_graph_signal)
        self.__updater.cpu_updated.connect(self.update_cpu_graph_signal)
        self.__updater.memory_updated.connect(self.update_memory_graph_signal)
        self.__updater.npu_usage_updated.connect(self.update_npu_usage_signal)
        self.__updater.updater_finished.connect(self.clear_all_graph_signal)

    @Slot(bool, str, int, bool)
    def on_start_stop(self, start, file_path, input_mode, save_mode):
        if start and not self.__monitoringStatus:
            self.__monitoringStatus = True
            self.__controlStatus = False
            self.__fileSaveStatus = save_mode
            self.__mode = True if input_mode > 0 else False

            self._setup_model(input_mode)
            self._init_workers()
            self._setup_save_paths(input_mode, file_path)

            config = WorkerConfig(self)
            self.__processing_worker = ProcessingWorker(config)
            self.__processing_worker.frame_processed.connect(self._on_frame_processed)
            self.__processing_worker.processing_finished.connect(self._on_processing_finished)
            self.__processing_worker.start()
            
            self.__updater.start_updater()

            if self.__mode:
                self.__reader.start_reader(file_path, self.__frameList, self.__frameListMax)

        elif not start and self.__monitoringStatus:
            if self.__mode:
                self.__reader.stop_reader()
            else:
                self.__controlStatus = True
                if self.__processing_worker:
                    self.__processing_worker.stop()
            self.__updater.stop_updater()
            self.__imageSaver.stop_saver()
            self.__recorder.stop_recorder()

    def _setup_model(self, input_mode):
        if self.visionProtocol is None or self.visionProtocol.rtpmMode != input_mode:
            stream_width = self.__frameWidth if self.__mode else self.__projframeWidth
            stream_height = self.__frameHeight if self.__mode else self.__projframeHeight
            if self.__projframeChannel == 1:
                stream_height = self.__projframeHeightYV12
            stream_channel = self.__frameChannel if self.__mode else self.__projframeChannel
            self.visionProtocol = VisionProtocol(input_mode, stream_width, stream_height, stream_channel)
            self.postProcessor = PostProcessor(self.__frameWidth, self.__frameHeight)

    def _setup_save_paths(self, input_mode, file_path):
        if not self.__fileSaveStatus:
            return
        
        root_dir = ''
        file_name = ''

        if input_mode == 0:
            self.folder_mode_path = str(datetime.today().strftime("%Y%m%d_%H%M%S"))
            root_dir = self.folder_mode_path + '_result'
            file_name = "projection"
        elif input_mode == 1:
            root_dir = 'test_results'
            file_name = os.path.basename(file_path)
        else: # folder
            self.folder_mode_path = file_path
            root_dir = file_path + '_result'
            os.makedirs(os.path.join(root_dir, self.image_result_path), exist_ok=True)
            os.makedirs(os.path.join(root_dir, self.data_result_path), exist_ok=True)

        self.__imageSaver.start_saver(self.__saveFrameList, self.visionProtocol, root_dir, file_name, self.folder_mode_path)

    @Slot()
    def on_reader_stopped(self):
        self.__controlStatus = True
        if self.__processing_worker:
            self.__processing_worker.stop()

    @Slot(list)
    def _on_frame_processed(self, frame):
        self.update_image_signal.emit(frame)

    @Slot()
    def _on_processing_finished(self):
        self.__monitoringStatus = False
        self.clear_progress_bar_signal.emit()
        self.clear_image_signal.emit()