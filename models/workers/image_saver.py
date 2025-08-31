import json
import os
import time
from datetime import datetime

import cv2
from PySide6.QtCore import QThread

from utils.logger import logger


class RtpmImageSaver(QThread):
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.command_status = False
        self.root_dir = ''
        self.file_name = ''
        self.frame_list = None
        self.vision_protocol = None
        self.folder_mode_path = ''

    def run(self):
        self.is_running = True
        while self.is_running:
            if self.frame_list and len(self.frame_list) > 0:
                frame_data = self.frame_list.pop(0)
                if self.file_name != '':
                    now = datetime.now()
                    s_time = now.strftime("%H%M%S_%f")
                    file_name_list = os.path.splitext(self.file_name)
                    try:
                        cv2.imwrite(f'{self.root_dir}/{file_name_list[0]}_{s_time}.jpeg', frame_data[0])
                    except Exception as e:
                        logger.error(f"Error saving image {self.root_dir}/{file_name_list[0]}_{s_time}.jpeg: {e}", exc_info=True)

                    result_list = self.vision_protocol.getDetectionResult()
                    if result_list:
                        try:
                            with open(f'{self.root_dir}/{file_name_list[0]}_{s_time}.json', 'w', encoding='utf-8') as json_file:
                                json.dump(result_list, json_file, ensure_ascii=False, indent=4)
                        except Exception as e:
                            logger.error(f"Error saving JSON result {self.root_dir}/{file_name_list[0]}_{s_time}.json: {e}", exc_info=True)

                else:
                    file_name_list = os.path.splitext(frame_data[2])
                    save_path = os.path.join(self.folder_mode_path + '_result', 'image_result', f'{file_name_list[0]}.jpeg')
                    try:
                        cv2.imwrite(save_path, frame_data[0])
                    except Exception as e:
                        logger.error(f"Error saving image {save_path}: {e}", exc_info=True)
            else:
                if not self.command_status:
                    self.is_running = False
            time.sleep(0.001) # Avoid busy waiting

    def start_saver(self, frame_list, vision_protocol, root_dir='', file_name='', folder_mode_path=''):
        self.command_status = True
        self.is_running = True
        self.frame_list = frame_list
        self.vision_protocol = vision_protocol
        self.root_dir = root_dir
        self.file_name = file_name
        self.folder_mode_path = folder_mode_path
        if self.root_dir and not os.path.exists(self.root_dir):
            try:
                os.makedirs(self.root_dir)
            except Exception as e:
                logger.error(f"Error creating directory {self.root_dir}: {e}", exc_info=True)
        self.start()

    def stop_saver(self):
        self.command_status = False
