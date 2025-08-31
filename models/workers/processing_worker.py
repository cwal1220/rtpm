import json
import os
import time

import cv2
from numpy import frombuffer
from PySide6.QtCore import QThread, Signal

from utils.logger import logger


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
        self.all_images = []
        self.all_annotations = []

    def run(self):
        self.is_running = True
        self.all_images = []
        self.all_annotations = []
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
                return

            draw_ratio = [frame_data[0].shape[1] / cfg.frame_width, frame_data[0].shape[0] / cfg.frame_height]
            
            # --- Drawing Logic ---
            for key, value in result_list.items():
                if not key.startswith('cluster') or not isinstance(value, dict):
                    continue
                try:
                    cluster_index = int(key[len('cluster'):]) - 1
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse index from cluster key: {key}")
                    continue

                if 'od' in value:
                    frame_data[0] = cfg.post_processor.draw_object_detection_boxes(
                        frame=frame_data[0],
                        object_detection_results=value['od'],
                        npu_index=cluster_index,
                        draw_ratio_list=draw_ratio
                    )
                if 'cl' in value:
                    frame_data[0] = cfg.post_processor.draw_classification_results(
                        frame=frame_data[0],
                        classification_result=value['cl'],
                        npu_index=cluster_index
                    )

            # --- Data Accumulation ---
            if cfg.is_saving_files:
                image_entry = cfg.post_processor.create_image_entry(frame_data[2], frame_data[0].shape, result_list)
                self.all_images.append(image_entry)

                annotations = cfg.post_processor.create_prediction_annotations(result_list, frame_data[0].shape)
                self.all_annotations.extend(annotations)
                
                # Keep saving frame images if needed for video
                cfg.save_frame_list.append(frame_data[:])
            
            self.frame_processed.emit([frame_data[0]])

        except Exception as e:
            logger.error(f"Error in processing worker (file mode): {e}", exc_info=True)

    def _process_stream_mode(self, cfg):
        # This mode does not currently support saving predictions.
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
        """Saves the accumulated predictions to a single COCO-style JSON file."""
        if not cfg.is_saving_files or not self.all_annotations:
            return

        if cfg.folder_mode_path:
            result_path = cfg.folder_mode_path + '_result'
            output_path = os.path.join(result_path, 'coco_predictions.json')
            
            final_coco = {
                'info': { 'description': 'RTPM Prediction Results' },
                'licenses': [],
                'images': self.all_images,
                'annotations': self.all_annotations,
                'categories': cfg.post_processor.categories
            }

            try:
                os.makedirs(result_path, exist_ok=True)
                with open(output_path, 'w') as fp:
                    json.dump(final_coco, fp, sort_keys=False, indent=4)
                logger.info(f"Successfully saved COCO prediction file to {output_path}")
            except IOError as e:
                logger.error(f"Failed to save prediction file to {output_path}: {e}")

    def stop(self):
        self.is_running = False