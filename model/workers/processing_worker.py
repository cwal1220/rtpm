from PySide6.QtCore import QThread, Signal
import time
import cv2
import json
import os
import sys
from numpy import frombuffer
from msg.logger import logger

class WorkerConfig:
    """A data class to hold configuration for the processing worker."""
    def __init__(self, view_model):
        self.is_file_mode = view_model._MainViewModel__mode
        self.is_saving_files = view_model._MainViewModel__fileSaveStatus
        self.vision_protocol = view_model.visionProtocol
        self.post_processor = view_model.postProcessor
        self.frame_list = view_model._MainViewModel__frameList
        self.save_frame_list = view_model._MainViewModel__saveFrameList
        self.folder_mode_path = view_model.folder_mode_path
        self.data_result_path = view_model.data_result_path
        self.frame_width = view_model._MainViewModel__frameWidth
        self.frame_height = view_model._MainViewModel__frameHeight
        self.proj_frame_channel = view_model._MainViewModel__projframeChannel
        self.proj_frame_height = view_model._MainViewModel__projframeHeight
        self.proj_frame_width = view_model._MainViewModel__projframeWidth
        self.proj_frame_height_yv12 = view_model._MainViewModel__projframeHeightYV12

class ProcessingWorker(QThread):
    frame_processed = Signal(list)
    processing_finished = Signal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.is_running = False

    def run(self):
        self.is_running = True
        logger.info("Processing worker started.")
        cfg = self.config

        cfg.vision_protocol.detectionResultQueueClear()
        cfg.vision_protocol.frameQueueClear()

        while self.is_running:
            if cfg.is_file_mode:
                self._process_file_mode(cfg)
            else:
                self._process_stream_mode(cfg)
            
            time.sleep(0.001)

        self._cleanup(cfg)
        logger.info("Processing worker finished.")
        self.processing_finished.emit()

    def _process_file_mode(self, cfg):
        result_list = cfg.vision_protocol.getDetectionResult()
        if not result_list:
            return

        try:
            if not cfg.frame_list:
                logger.warning("Frame list is empty in file mode.")
                return
            frame_data = cfg.frame_list.pop(0)
            if frame_data[1] != result_list['info'][0]:
                logger.warning(f"Frame sync mismatch: expected {result_list['info'][0]}, got {frame_data[1]}")
                return # Not the corresponding frame

            draw_ratio = [frame_data[0].shape[1] / cfg.frame_width, frame_data[0].shape[0] / cfg.frame_height]
            
            # Drawing logic here...
            for key, value in result_list.items():
                if isinstance(value, dict) and 'od' in value:
                    frame_data[0] = cfg.post_processor.drawBoundingBoxforDistance(frame_data[0], value['od'], draw_ratio)

            if cfg.is_saving_files:
                cfg.save_frame_list.append(frame_data[:])
                if len(frame_data) > 2:
                    cfg.post_processor.saveResultData(frame_data[2], cfg.folder_mode_path, frame_data[0].shape, result_list)
            
            self.frame_processed.emit([frame_data[0]])

        except Exception as e:
            logger.error(f"Error in processing worker (file mode): {e}", exc_info=True)

    def _process_stream_mode(self, cfg):
        result_frame = cfg.vision_protocol.getFrame()
        if result_frame is None:
            return
        try:
            if cfg.proj_frame_channel == 3:
                np_frame = frombuffer(result_frame, dtype='uint8').reshape(cfg.proj_frame_height, cfg.proj_frame_width, cfg.proj_frame_channel)
            elif cfg.proj_frame_channel == 1:
                np_frame = frombuffer(result_frame, dtype='uint8').reshape(cfg.proj_frame_height_yv12, cfg.proj_frame_width, cfg.proj_frame_channel)
                np_frame = cv2.cvtColor(np_frame, cv2.COLOR_YUV420p2RGB)
            
            self.frame_processed.emit([np_frame])

            if cfg.is_saving_files:
                cfg.save_frame_list.append([np_frame, 0])

        except Exception as e:
            logger.error(f"Error in processing worker (stream mode): {e}", exc_info=True)

    def _cleanup(self, cfg):
        if cfg.is_saving_files and cfg.folder_mode_path:
            result_list = []
            result_path = cfg.folder_mode_path + '_result'
            data_result_path = os.path.join(result_path, cfg.data_result_path.strip('/'))
            if os.path.exists(data_result_path):
                for file_name in os.listdir(data_result_path):
                    with open(os.path.join(data_result_path, file_name), 'r') as f:
                        try:
                            result_list.append(json.load(f))
                        except json.JSONDecodeError as e:
                            logger.error(f"Error decoding JSON from {file_name}: {e}")
                with open(os.path.join(result_path, 'result_out.json'), 'w') as fp:
                    json.dump(result_list, fp, sort_keys=False, indent=4)
            else:
                logger.warning(f"Data result path does not exist: {data_result_path}")

    def stop(self):
        self.is_running = False