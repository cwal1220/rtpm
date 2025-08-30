from PySide6.QtCore import QThread
from datetime import datetime
import cv2
import time
from utils.logger import logger

class RtpmVideoRecorder(QThread):
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.command_status = False
        self.w_fps = 0
        self.w_frame_size = (0, 0)
        self.frame_list = None

    def run(self):
        self.is_running = True
        now = datetime.now()
        w_name = now.strftime("%H%M%S_%f") + '.mp4v'
        w_fourcc = cv2.VideoWriter_fourcc(*'h264')
        recorder_obj = cv2.VideoWriter(w_name, w_fourcc, self.w_fps, self.w_frame_size, isColor=True)
        
        if recorder_obj.isOpened():
            logger.info(f"Video recorder started. Saving to {w_name}")
            while self.is_running:
                if self.frame_list and len(self.frame_list) > 0:
                    frame = self.frame_list.pop(0)
                    recorder_obj.write(frame)
                else:
                    if not self.command_status:
                        self.is_running = False
                time.sleep(0.001) # Avoid busy waiting
            recorder_obj.release()
            logger.info(f'Saved file: {w_name}')
        else:
            logger.error("Error: Could not open video writer.")

    def start_recorder(self, frame_list, frame_size, fps):
        self.w_fps = fps
        self.w_frame_size = frame_size
        self.command_status = True
        self.is_running = True
        self.frame_list = frame_list
        self.start()

    def stop_recorder(self):
        self.command_status = False
