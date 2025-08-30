from PySide6.QtCore import QThread, Signal
import os
import cv2
from PIL import Image
from numpy import ravel, asarray
import time
import sys
from msg.logger import logger

class RtpmFileReader(QThread):
    reader_stopped = Signal()
    progress_updated = Signal(int, int)
    file_read = Signal(list)
    error_occurred = Signal(str, str)

    def __init__(self, vision_protocol, base_size_tuple):
        super().__init__()
        self.vision_protocol = vision_protocol
        self.base_size = base_size_tuple
        self.is_running = False
        self.file_path = ''
        self.image_ext = ['.jpg', '.jpeg', '.png', '.bmp']
        self.video_ext = ['.mp4', '.avi']
        self.frame_list = None
        self.frame_list_max = 0

    def run(self):
        self.is_running = True
        time_stamp = 0

        if os.path.isdir(self.file_path):
            self._read_folder()
        else:
            self._read_file()

        self.reader_stopped.emit()

    def _read_folder(self):
        file_list = [f for f in os.listdir(self.file_path) if f.lower().endswith(tuple(self.image_ext))]
        file_num = len(file_list)
        self.progress_updated.emit(0, file_num)

        for idx, file_name in enumerate(file_list):
            if not self.is_running:
                break
            
            while len(self.frame_list) >= self.frame_list_max:
                time.sleep(0.001)

            full_path = os.path.join(self.file_path, file_name)
            try:
                image = cv2.imread(full_path)
                if image is None:
                    logger.warning(f"Could not read image file: {full_path}")
                    continue
                
                time_stamp = idx + 1
                frame_raw = self._resize_image(image)
                ret = self.vision_protocol.sendFrame([frame_raw, time_stamp])

                if ret:
                    self.progress_updated.emit(time_stamp, file_num)
                    self.frame_list.append([image, time_stamp, file_name])
                else:
                    logger.warning(f'Failed to send frame: {full_path}')
            except Exception as e:
                logger.error(f"Error reading file {full_path}: {e}", exc_info=True)

    def _read_file(self):
        file_ext = os.path.splitext(self.file_path)[1].lower()
        if file_ext in self.video_ext:
            self._read_video()
        elif file_ext in self.image_ext:
            self._read_image()
        else:
            self.error_occurred.emit('Error', f"Can't open file: {self.file_path}")

    def _read_image(self):
        try:
            image = cv2.imread(self.file_path)
            self.progress_updated.emit(1, 1)
            frame_raw = self._resize_image(image)
            ret = self.vision_protocol.sendFrame([frame_raw, 0])
            if ret:
                self.frame_list.append([image, 0])
            else:
                logger.warning(f'Failed to send frame: {self.file_path}')
        except Exception as e:
            logger.error(f"Error reading image {self.file_path}: {e}", exc_info=True)

    def _read_video(self):
        video_obj = cv2.VideoCapture(self.file_path)
        if not video_obj.isOpened():
            self.error_occurred.emit('Message', f"Can't open file: {self.file_path}")
            return

        total_frame_count = int(video_obj.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = video_obj.get(cv2.CAP_PROP_FPS)
        fps_time = 1.0 / video_fps if video_fps > 0 else 0
        prev_time = 0
        current_frame_count = 0

        while self.is_running:
            if time() - prev_time < fps_time:
                time.sleep(0.001)
                continue
            
            prev_time = time()
            ret, frame = video_obj.read()
            if not ret:
                break

            current_frame_count += 1
            self.progress_updated.emit(current_frame_count, total_frame_count)

            if len(self.frame_list) < self.frame_list_max:
                frame_raw = self._resize_image(frame, use_pil=True)
                time_stamp = int((1000.0 / video_fps) * (current_frame_count - 1))
                ret = self.vision_protocol.sendFrame([frame_raw, time_stamp])
                if ret:
                    self.frame_list.append([frame, time_stamp])
                else:
                    logger.warning(f'Video Frame: {current_frame_count} / ret: {ret}')
        
        video_obj.release()

    def _resize_image(self, image, use_pil=False):
        if image.shape[:2] == (self.base_size[0], self.base_size[1]):
            return ravel(image[..., ::-1], order='C')

        if use_pil:
            img = Image.fromarray(image[..., ::-1])  # BGR -> RGB
            img_resize = img.resize((self.base_size[1], self.base_size[0]), Image.LANCZOS)
            r_image = asarray(img_resize)
            return ravel(r_image, order='C')
        else:
            r_image = cv2.resize(image, (self.base_size[1], self.base_size[0]))
            return ravel(r_image[..., ::-1], order='C')

    def start_reader(self, filePath, frameList, frameListMax):
        self.file_path = filePath
        self.is_running = True
        self.frame_list = frameList
        self.frame_list_max = frameListMax
        self.start()

    def stop_reader(self):
        self.is_running = False
