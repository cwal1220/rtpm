# Build Guide
This guide explains how to build the Python extension module on Linux and Windows systems.

-------

## Prerequisites
- Python 3.6 or higher
- A C/C++ compiler
- Install required Python packages:

``` bash
pip install setuptools cython "numpy<2"
```

## Build on Linux
Install build tools (e.g., on Ubuntu):

``` bash
sudo apt update
sudo apt install build-essential python3-dev
```

``` bash
python setup.py build_ext --inplace
```
The built module (visionprotocol.cpython-<version>-<platform>.so) will appear in the project directory.

-------

## Build on Windows
Install Visual Studio Build Tools.

Run the build command:

``` bash
python setup.py build_ext --inplace --plat-name win-amd64
Note: Use --plat-name win32 for 32-bit Python.
```

The built module (your_module_name.cp<version>-win_amd64.pyd) will appear in the project directory.

**Note**: If you need to convert a DLL file into a shared library (.lib), use the makelib.bat script provided in the project.


# Running Sample Code

The test scripts recvStream.py and sendStream.py are located in the sample directory. After building the module and setting the environment variables, you can run these scripts to verify that everything is working correctly.

## Run on Linux
``` bash
# Terminal 1
cd visionprotocol/cython_visionprotocol
source ./sample/set_paths.sh # File internal paths need to be modified.
python ./sample/stream/recvStream.py # or ./sample/message/recvMessage.py

# Terminal 2
cd visionprotocol/cython_visionprotocol
source ./sample/set_paths.sh # File internal paths need to be modified.
python ./sample/stream/sendStream.py # or ./sample/message/sendMessage.py

```

## Run on Windows
``` powershell

# Terminal 1
cd visionprotocol\cython_visionprotocol
.\sample\set_paths.ps1 # File internal paths need to be modified.
python .\sample\stream\recvStream.py # or .\sample\message\recvMessage.py

# Terminal 2
cd visionprotocol\cython_visionprotocol
.\sample\set_paths.ps1 # File internal paths need to be modified.
python .\sample\stream\sendStream.py # or .\sample\message\sendMessage.py

```
