import os
import sys
import platform

try:
    from vision_api import *
except ModuleNotFoundError:
    py_version = f"{sys.version_info.major}{sys.version_info.minor}"
    platform_system = platform.system()
    
    if platform_system == "Linux":
        expected_file = f"visionprotocol.cpython-{py_version}-x86_64-linux-gnu.so"
    elif platform_system == "Windows":
        expected_file = f"visionprotocol.cp{py_version}-win_amd64.pyd"
    else:
        expected_file = "visionprotocol.<platform-dependent>.so or .pyd"

    print(f"[ERROR] Missing file: cython_visionprotocol/'{expected_file}'\n")
    print("To resolve this issue, please build the module using the following command:")
    print("  $ cd {visionprotocol_dir}/cython_visionprotocol")
    print("  $ python setup_linux.py build_ext --inplace" if platform_system == "Linux" else 
          "  $ python setup.py build_ext --inplace")
    print(f"After building, make sure the file '{expected_file}' is created.")
    exit(1)

def main():
    STREAM_W, STREAM_H, STREAM_C = 1280, 720, 3
    
    vpm_config = vision_user_config_t()
    vpm_config.netRole              = Role.CLIENT
    vpm_config.netInterface         = Interface.INTERFACE_ETHERNET
    vpm_config.netBuf.sendBufSize   = SYS_DEFAULT_BUFSIZE
    vpm_config.netBuf.recvBufSize   = SYS_DEFAULT_BUFSIZE
    vpm_config.ip                   = "127.0.0.1".encode('utf-8')
    vpm_config.port                 = 1234
    vpm_config.opMode               = OperationMode.STREAM_MODE
    vpm_config.reconnection         = ActivationState.OFF
    vpm_config.streamZeroCopy       = ActivationState.ON
    vpm_config.sendQ.maxDataSize    = STREAM_W * STREAM_H * STREAM_C
    vpm_config.sendQ.numQ           = 4
    vpm_config.recvQ.maxDataSize    = 0
    vpm_config.recvQ.numQ           = 0
    vpm = VisionProtocolModule(vpm_config)

    seqNum = 0
    timestamp = 0
    while(1):
        try:
            ret, pStreamInfo, pIndex = vpm.GetStreamSendBuffer()
            if ret == VISION_SUCCESS:
                pStreamInfo.id = 0x11
                pStreamInfo.length = vpm_config.sendQ.maxDataSize
                pStreamInfo.seqNum = seqNum
                pStreamInfo.timestamp = timestamp

                pBuffer, addr = vpm.buf2ndarray(pStreamInfo.pBuffer, pStreamInfo.length)
                pBuffer[:] = np.random.randint(0, 256, size=pBuffer.shape, dtype=np.uint8)
                
                ret = vpm.SendStream(pStreamInfo, pIndex)
                if ret == VISION_SUCCESS:
                    print(f"[SEND] [addr: {hex(addr)}] [idx: {pIndex}] [{hex(pStreamInfo.id)}, {pStreamInfo.length}, {pStreamInfo.seqNum}, {pStreamInfo.timestamp}, {pBuffer}]")
                    seqNum = seqNum + 1
                    timestamp = timestamp + 1
                
        except ZeroDivisionError:
            print("Error: Division by zero")
        except Exception as e:
            print("An error occurred:", e)

if __name__=="__main__":
    main()
