
# Check Python version
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
    vpm_config.netRole              = Role.CLIENT
    vpm_config.netInterface         = Interface.INTERFACE_ETHERNET
    vpm_config.netBuf.sendBufSize   = SYS_DEFAULT_BUFSIZE
    vpm_config.netBuf.recvBufSize   = SYS_DEFAULT_BUFSIZE
    vpm_config.ip                   = "127.0.0.1".encode('utf-8')
    vpm_config.port                 = 3333
    vpm_config.opMode               = OperationMode.MESSAGE_MODE
    vpm_config.reconnection         = ActivationState.OFF
    vpm_config.streamZeroCopy       = ActivationState.OFF
    vpm_config.sendQ.maxDataSize    = 10000
    vpm_config.sendQ.numQ           = 50 
    vpm_config.recvQ.maxDataSize    = 0
    vpm_config.recvQ.numQ           = 0 
    vpm = VisionProtocolModule(vpm_config)
    
    PAYLOAD_SIZE = 10000
    header = VisionMessage()
    np_message = np.array(bytearray(PAYLOAD_SIZE), dtype=np.uint8)
    cnt = 0
    while(1):
        try:
            # make payload
            np_message[:] = np.random.randint(0, 256, size=PAYLOAD_SIZE, dtype=np.uint8)

            # make header
            header.id = 0x13
            header.length = PAYLOAD_SIZE
            header.seqNum = cnt
            header.timestamp = cnt
            np_header = np.array(bytearray(header), dtype=np.uint8)

            # make packet(hader + payload)
            np_packet       = np.hstack((np_header, np_message))
            np_packet_size  = ctypes.sizeof(VisionMessage()) + header.length

            ## send MESSAGE packet
            ret = vpm.SendMessage(np_packet, np_packet_size)
            if(ret == VISION_SUCCESS):
               print(f"[SEND] [{hex(header.id)}, {header.length}, {header.seqNum}, {header.timestamp}] [{np_message}]")
               cnt = cnt + 1

            time.sleep(1)
            
        except ZeroDivisionError:
            print("Error: Division by zero")
        except Exception as e:
            print("An error occurred:", e)

if __name__=="__main__":
    main()
