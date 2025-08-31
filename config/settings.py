"""
This module replaces the YAML-based configuration.
"""

# NN SDK
PROJECTION = {
    "width": 1280,
    "height": 720,
    "channel": 3,
}

INJECTION = {
    "width": 1280,
    "height": 720,
    "channel": 3,
}

DETECT_TYPES = ["NPU0", "NPU1"]

# Path to the label file for COCO format categories
LABEL_PATH = "labels/coco.txt"

## Falcon Project (commented out)
# PROJECTION_FALCON = {
#     "width": 1920,
#     "height": 1080,
#     "channel": 3,
# }
#
# INJECTION_FALCON = {
#     "width": 1920,
#     "height": 1280,
#     "channel": 3,
# }
#
# DETECT_TYPES_FALCON = ["OD", "TSR", "HBA", "LD"]
#
# FEATURES_FALCON = {
#     "Performance": True,
#     "dewarp": True,
# }
