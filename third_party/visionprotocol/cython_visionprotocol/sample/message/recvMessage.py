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
    vpm_config = vision_user_config_t()
    vpm_config.netRole              = Role.SERVER
    vpm_config.netInterface         = Interface.INTERFACE_ETHERNET
    vpm_config.netBuf.sendBufSize   = SYS_DEFAULT_BUFSIZE
    vpm_config.netBuf.recvBufSize   = SYS_DEFAULT_BUFSIZE
    vpm_config.ip                   = "127.0.0.1".encode('utf-8')
    vpm_config.port                 = 3333
    vpm_config.opMode               = OperationMode.MESSAGE_MODE
    vpm_config.reconnection         = ActivationState.OFF
    vpm_config.streamZeroCopy       = ActivationState.OFF
    vpm_config.sendQ.maxDataSize    = 0
    vpm_config.sendQ.numQ           = 0
    vpm_config.recvQ.maxDataSize    = 10000
    vpm_config.recvQ.numQ           = 50
    vpm = VisionProtocolModule(vpm_config)

    np_peek_header = np.array(bytearray(ctypes.sizeof(VisionMessage)), dtype=np.uint8)
    np_header = np.array(bytearray(ctypes.sizeof(VisionMessage)), dtype=np.uint8)
    while(1):
        try:
            ret = vpm.PeekMessage(np_peek_header, ctypes.sizeof(VisionMessage))
            if ret == VISION_SUCCESS:
                peekHeader = VisionMessage(*(np.frombuffer(np_peek_header, dtype=VisionMessage)[0]))
                # print(f"[PEEK] [{hex(peekHeader.id)}, {peekHeader.length}, {peekHeader.seqNum}, {peekHeader.timestamp}]")

                ret = vpm.RecvMessage(np_header, ctypes.sizeof(VisionMessage), BLOCKING)
                if ret == VISION_SUCCESS:
                    header = VisionMessage(*(np.frombuffer(np_header, dtype=VisionMessage)[0]))
                    np_payload = np.zeros(header.length, dtype=np.uint8)
                    ret = vpm.RecvMessage(np_payload, header.length, BLOCKING)
                    if ret == VISION_SUCCESS:
                        print(f"[RECV] [{hex(header.id)}, {header.length}, {header.seqNum}, {header.timestamp}] [{np_payload}]")
            time.sleep(1)
        except ZeroDivisionError:
            print("Error: Division by zero")
        except Exception as e:
            print("An error occurred:", e)

if __name__=="__main__":
    main()
