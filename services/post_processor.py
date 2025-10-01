import json
import os
import sys

import cv2
import numpy as np


class PostProcessor:
    """Handles post-processing of detection results, including drawing on frames and creating annotations."""

    def __init__(self, frame_width, frame_height, label_path):
        self._frame_width = frame_width
        self._frame_height = frame_height
        self.categories = self._load_categories(label_path)

    def _load_categories(self, path):
        """Loads category names from a text file."""
        categories = []
        try:
            with open(path, 'r') as f:
                for i, line in enumerate(f):
                    categories.append({'id': i + 1, 'name': line.strip(), 'supercategory': 'object'})
        except FileNotFoundError:
            print(f"Warning: Label file not found at {path}. Categories will be empty.")
        return categories

    def _get_color_for_id(self, id_):
        """Generates a unique and vibrant color based on an ID."""
        # Use a prime number to spread hues more evenly
        hue = (id_ * 37) % 180
        # Create a color in HSV, then convert to BGR for OpenCV
        hsv_color = np.uint8([[[hue, 255, 255]]])
        bgr_color = cv2.cvtColor(hsv_color, cv2.COLOR_HSV2BGR)[0][0]
        return tuple(map(int, bgr_color))

    def draw_object_detection_boxes(self, frame, object_detection_results, npu_index, draw_ratio_list=[1.0, 1.0]):
        """Draws bounding boxes for object detection results."""
        if not object_detection_results:
            return frame

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        font_thickness = 2

        for detection in object_detection_results:
            try:
                start_point = (int(detection['bbox'][0] * draw_ratio_list[0]), int(detection['bbox'][1] * draw_ratio_list[1]))
                end_point = (int((detection['bbox'][0] + detection['bbox'][2]) * draw_ratio_list[0]), int((detection['bbox'][1] + detection['bbox'][3]) * draw_ratio_list[1]))
                
                category_id = detection.get('category_id', 0)
                color = self._get_color_for_id(category_id)
                
                # Draw bounding box
                cv2.rectangle(frame, start_point, end_point, color, 2)
                
                # Prepare text
                text = f"[NPU:{npu_index}][{detection['category_id']}][{detection['score']:.1f}%]"
                text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
                
                # Draw text background
                text_bg_start = (start_point[0], start_point[1] - text_size[1] - 10) # 10 pixels padding above text
                text_bg_end = (start_point[0] + text_size[0], start_point[1])
                cv2.rectangle(frame, text_bg_start, text_bg_end, (0, 0, 0), -1) # Black background

                # Draw text
                cv2.putText(frame, text, (start_point[0], start_point[1] - 5), font, font_scale, (255, 255, 255), font_thickness) # White text

            except (IndexError, KeyError) as e:
                _, _, tb = sys.exc_info()
                print(f"{__name__} Error at line {tb.tb_lineno}: {e}")
        return frame

    def draw_classification_results(self, frame, classification_result, npu_index):
        """Prints classification results on the frame at a position based on the NPU index."""
        pos_x = 10
        pos_y = 30 + (npu_index * 30)
        color = self._get_color_for_id(npu_index)
        text = f"Cluster_{npu_index} : {classification_result}"
        cv2.putText(frame, text, (pos_x, pos_y), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        return frame

    def create_image_entry(self, file_name, image_shape, result_dict):
        """Creates a COCO-style image entry, including non-standard classification results."""
        image_id = result_dict.get('info', [0])[0]
        
        classification_results = {}
        for key, value in result_dict.items():
            if key.startswith('cluster') and 'cl' in value:
                cluster_index = int(key[len('cluster'):]) - 1
                classification_results[f'cluster_{cluster_index}_cl'] = value['cl']

        return {
            'id': image_id,
            'file_name': file_name,
            'height': image_shape[0],
            'width': image_shape[1],
            **classification_results
        }

    def create_prediction_annotations(self, result_dict, image_shape):
        """Creates a list of COCO-style prediction annotations from a result dictionary."""
        try:
            image_id = result_dict.get('info', [0])[0]
            annotations = []
            height_factor = image_shape[0] / self._frame_height
            width_factor = image_shape[1] / self._frame_width
            
            od_sources = [value.get('od', []) for key, value in result_dict.items() if key.startswith('cluster')]

            for od_list in od_sources:
                for od_object in od_list:
                    annotations.append(
                        self._create_coco_annotation(od_object, image_id, width_factor, height_factor)
                    )
            return annotations
        except (KeyError, IndexError, TypeError) as e:
            _, _, tb = sys.exc_info()
            print(f"{__name__} Error in create_prediction_annotations at line {tb.tb_lineno}: {e}")
            return []

    def _create_coco_annotation(self, od_object, image_id, width_factor, height_factor):
        """Creates a COCO-compliant annotation entry from an OD object."""
        bbox = od_object.get('bbox', [0, 0, 0, 0])
        scaled_bbox = [
            round(bbox[0] * width_factor),
            round(bbox[1] * height_factor),
            round(bbox[2] * width_factor),
            round(bbox[3] * height_factor)
        ]
        
        category_id_from_model = od_object.get('category_id', -1)
        coco_category_id = category_id_from_model + 1
        
        score_from_model = od_object.get('score', 0.0)
        normalized_score = score_from_model / 100.0

        return {
            'image_id': image_id,
            'category_id': coco_category_id,
            'bbox': scaled_bbox,
            'score': normalized_score,
            'area': scaled_bbox[2] * scaled_bbox[3],
            'iscrowd': 0,
        }
