# Define the path to add
$VISION_PATH = "\path\to\visionprotocol\cython_visionprotocol\"

# Add to PYTHONPATH (append the path if already exists)
$env:PYTHONPATH += ";$VISION_PATH"

# Verify the updated PYTHONPATH
echo "PYTHONPATH: $env:PYTHONPATH"