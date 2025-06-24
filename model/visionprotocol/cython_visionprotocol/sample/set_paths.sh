#!/bin/bash

# Define the paths to add
VISION_PATH="/path/to/visionprotocol/cython_visionprotocol"

# Add to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$VISION_PATH

# Add to LD_LIBRARY_PATH
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$VISION_PATH

# Optionally, print out the updated paths to verify
echo "Updated PYTHONPATH: $PYTHONPATH"
echo "Updated LD_LIBRARY_PATH: $LD_LIBRARY_PATH"