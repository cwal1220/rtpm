'''
 * Copyright Telechips Inc.
 *
 * TCC Version 1.0
 *
 * This source code contains confidential information of Telechips.
 *
 * Any unauthorized use without a written permission of Telechips including not
 * limited to re-distribution in source or binary form is strictly prohibited.
 *
 * This source code is provided "AS IS" and nothing contained in this source code
 * shall constitute any express or implied warranty of any kind, including without
 * limitation, any warranty of merchantability, fitness for a particular purpose
 * or non-infringement of any patent, copyright or other third party intellectual
 * property right.
 * No warranty is made, express or implied, regarding the information's accuracy,
 * completeness, or performance.
 *
 * In no event shall Telechips be liable for any claim, damages or other
 * liability arising from, out of or in connection with this source code or
 * the use in the source code.
 *
 * This source code is provided subject to the terms of a Mutual Non-Disclosure
 * Agreement between Telechips and Company.
'''
try: # rtpm
    from model.visionprotocol.cython_visionprotocol import visionprotocol as vpm
except ImportError:
    import visionprotocol as vpm

import ctypes
import numpy as np
import time

# Define ctypes equivalents of C types and enums
uint64_t = ctypes.c_ulonglong
uint32_t = ctypes.c_ulong
uint16_t = ctypes.c_ushort
uint8_t = ctypes.c_ubyte

# Blocking/NonBlocking Mode (value > 0 : timeout mode)
NONBLOCKING = 0 # Indicates that the operation is set to non-blocking mode. 
                # In this mode, the module attempts to enqueue or dequeue data from the internal send/receive queue without waiting. 
                # If the queue is unavailable, the operation returns immediately, allowing the application to continue other tasks without delay.
BLOCKING = -1   # Indicates that the operation is set to blocking mode. 
                # In this mode, the module waits until the operation can successfully enqueue or dequeue from the internal send/receive queue. (Note: timeout mode when the value exceeds 0.)

# SYSTEM_DEFAULT_SOCKET_BUFSIZE
SYS_DEFAULT_BUFSIZE = 0         # Indicates the user-system default buffer size for TCP sockets , related to SNDBUF and RCVBUF settings in TCP/IP configuration.

# vision_api function return value
VISION_SUCCESS          = 0     # Indicates that the operation was successfully completed.
VISION_ERROR            = -1    # Indicates that the operation failed.
ARGUMENT_ERROR          = -2    # Indicates that an invalid argument was passed to the function.
CONNECTION_ERROR        = -3    # Indicates an issue occurred during a connection-related operation.
AUTHENTICATION_ERROR    = -4    # Indicates an issue occurred during an authentication-related operation.
QUEUE_OVERFLOW          = -5    # Indicates that the queue is full or lacks enough space to accommodate the length of the enqueue operation.
QUEUE_UNDERFLOW         = -6    # Indicates that the queue is empty or lacks enough data for the dequeue operation.
TIMEOUT_ERROR           = -7    # Indicates that the function terminated due to a timeout.
MEMORY_ALLOCATION_ERROR = -8    # Indicates that the system lacks sufficient resources for memory allocation.
BUF_REGISTRATION_ERROR  = -9    # Indicates that a buffer registration error occurred.
RECONNECTING            = -10   # Indicates that the connection with the peer was lost, and the system is waiting for a new connection.

class OperationMode(ctypes.c_int):
    """
    MESSAGE_MODE -> Set the module's mode of operation to MESSAGE_MODE.
        Buffers data in the module's own heap memory, involving data copying into and out of the queue.
        Note: Recommended to use MESSAGE_MODE when the user needs to send small, event-based data.

    STREAM_MODE -> Set the module's mode of operation to STREAM_MODE.
        Buffers data in the user-allocated buffer, preventing unnecessary internal data copying within the module.
        Note: Recommended to use STREAM_MODE when the user needs to send large, continuous data streams.
    """
    MESSAGE_MODE = 0
    STREAM_MODE = 1

class Interface(ctypes.c_int):
    """
    Enumeration type representing the network interface of the module.
    """
    INTERFACE_ETHERNET = 0  # Set when the physical transmission medium used is ETHERNET.
    INTERFACE_PCIE = 1      # This feature is currently not supported.

class Role(ctypes.c_int):
    """
    Enumeration type representing the network role of the module.

    Note: The concepts of SERVER and CLIENT only exist during the initialization process. 
    After that, they no longer exist as distinct roles in the module's operation. 
    If multiple connections are required, use the multi-handle. and each handle can only establish a one-to-one connection.
    """
    SERVER = 0  # Sets the module's network role to SERVER.
    CLIENT = 1  # Sets the SO_RCVBUF value of the TCP/IP Protocol

class ActivationState(ctypes.c_int):
    """
    Enumeration type representing the ON/OFF state of a specific operation.
    """
    OFF = 0     # Sets the state of the specific operation to OFF.
    ON = 1      # Sets the state of the specific operation to ON.

class QueueInfo(ctypes.Structure):
    """
    Structure representing the queue information of the module.

    Note: During the initialization process, the module creates an internal circular queue for buffering. 
    The size of this queue is determined by two parameters, maxDataSize and numQ.
    In MESSAGE_MODE, The queue size is allocated based on the product of maxDataSize and numQ. 
    This means the total buffer size is determined by both the maximum data size and the number of queues. 
    In STREAM_MODE, only numQ is considered for allocation, and maxDataSize is not taken into account. 
    This is because in STREAM_MODE, buffering is performed using the buffer addresses that are registered by the user.
    
    Note: During the connection process, the authentication step ensures that certain parameters between the host and target match to establish a valid connection. Specifically:
    - Host's sendQ.maxDataSize must be less than or equal to Target's recvQ.maxDataSize.
    - Host's recvQ.maxDataSize must be greater than or equal to Target's sendQ.maxDataSize.
    
    Note: The queue configuration should be determined by considering factors such as message size, transmission frequency, network performance, and system resources. 
    In practice, it is essential to adjust the queue size dynamically through testing to ensure the system operates efficiently and to verify that no performance issues, 
    such as buffer overflow or underflow, occur.
    """
    _fields_ = [
        ("maxDataSize", uint32_t),  # Sets the maximum data size.
        ("numQ", uint8_t)           # Sets the number of queues.
    ]

class NetworkBufSize(ctypes.Structure):
    """
    Structure for setting the buffer size of the module's network socket.
    Note: Setting to 0 or the SYS_DEFAULT_BUFSIZE macro will apply the default value of SO_SNDBUF and SO_RCVBUF for the user's system.
    """
    _fields_ = [
        ("sendBufSize", uint32_t), # Sets the SO_SNDBUF value of the TCP/IP Protocol.
        ("recvBufSize", uint32_t)  # Sets the SO_RCVBUF value of the TCP/IP Protocol
    ]

class vision_user_config_t(ctypes.Structure):
    """
    Structure representing the user config of the module.
    """
    _fields_ = [
        ("netInterface", uint8_t),  # Defines the physical transmission medium being used.
        ("netRole", uint8_t),       # Configures the network role of the module. 
                                    # 0: Client (initiates connection)
                                    # 1: Server (listens for connections).
        ("netBuf", NetworkBufSize), # Sets the buffer size for the module’s network socket.
        ("ip", ctypes.c_char * 16), # Sets the network IP address for the module.
                                    # - Server: Typically set to a static IP (e.g., "192.168.1.100").
                                    #          Use "0.0.0.0" to listen on all available network interfaces.
                                    # - Client: Set this to the server's IP address to establish a connection.
        ("port", uint16_t),         # Sets the port number for the module. 
        ("opMode", uint8_t),        # Configures the operation mode of the module. (0: MESSAGE_MODE, 1: STREAM_MODE)
        ("reconnection", uint8_t),  # Enables or disables the reconnection feature.
                                    # - 0:OFF
                                    # - 1:ON, provides the functionality to automatically attempt reconnection when the target is disconnected abnormally.
        ("streamZeroCopy", uint8_t),# Enables or disables the streamZeroCopy feature. This feature is only applicable in STREAM_MODE and is not related to zero-copy mechanisms in the TCP/IP protocol.
                                    # - 0:OFF (buffer copy): Data is copied from the application’s registered buffer to heap memory before transmission.
                                    # - 1:ON (direct buffer use): Data is transmitted directly from the application’s registered buffer, avoiding additional copies within the module.
        ("sendQ", QueueInfo),       # Configures the Send Queue used by the module.
        ("recvQ", QueueInfo)        # Configures the Receive Queue used by the module.
    ]

class VisionStreamInfo(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint32),                     # Header ID information.
        ("pBuffer", ctypes.POINTER(ctypes.c_uint8)), # Payload, representing the actual data to be sent or received, is one of the buffers registered by the user during initialization.
        ("length", ctypes.c_uint32),                 # Header information, representing the length of the payload.
        ("seqNum", ctypes.c_uint64),                 # Header information, representing the sequence number.
        ("timestamp", ctypes.c_uint64)               # Header information, representing the timestamp.
    ]

class VisionMessage(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint32),                    # Header ID information.
        ("length", ctypes.c_uint32),                # Header information, representing the length of the payload.
        ("seqNum", ctypes.c_uint64),                # Header information, representing the sequence number.
        ("timestamp", ctypes.c_uint64)              # Header information, representing the timestamp.
    ]

class VisionProtocolModule():
    """
    The Vision Protocol module provides communication middleware designed to facilitate the transmission of large-scale data and control signals between heterogeneous devices. 
    Delivered as a C-language-based library, this module leverages the TCP/IP Protocol to ensure reliable and stable data transfer.
    """
    def __init__(self, config):
        """
        Constructor for the VisionProtocolModule class.
        Initializes the module, configures the buffers, and establishes a connection.
        """
        super(VisionProtocolModule, self).__init__()

        self.handle = 0
        ret = self.Initialization(config)
        if(ret == VISION_SUCCESS):
            self.sbuf = [None] * 0xFF
            self.rbuf = [None] * 0xFF
            if(config.opMode == OperationMode.STREAM_MODE):
                for i in range(config.sendQ.numQ):
                    self.sbuf[i] = np.array(bytearray(config.sendQ.maxDataSize), dtype=np.uint8)
                    ret, addr = self.RegisterStreamSendBuffer(self.sbuf[i], config.sendQ.maxDataSize)
                    if ret == VISION_SUCCESS:
                        print(f"[SUCCESS][RegisterSendBuf] idx: {i}, addr: {addr}")
                    else:
                        print(f"[ERROR][RegisterSendBuf] idx: {i}")
                
                for i in range(config.recvQ.numQ):
                    self.rbuf[i] = np.array(bytearray(config.recvQ.maxDataSize), dtype=np.uint8)
                    ret, addr = self.RegisterStreamRecvBuffer(self.rbuf[i], config.recvQ.maxDataSize)
                    if ret == VISION_SUCCESS:
                        print(f"[SUCCESS][RegisterRecvBuf] idx: {i}, addr: {addr}")
                    else:
                        print(f"[ERROR][RegisterRecvBuf] idx: {i}")

            ret = self.Connection()
            if(ret < 0):
                print("[ERROR] Connection failed. The program will now terminate")
                exit(0)
    
    def Initialization(self, config):
        """
        Initializes the module based on the UserConfig and returns a handle used for module management and interaction through the user API.
        
        Args:
            - config (vision_user_config_t): User-defined module configuration information.

        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
        """
        self.handle = np.array(bytearray(1), dtype=np.uint64)
        ret = vpm.Vision_API_Initialization_Cython(config, self.handle)
        print("Initialization :", ret, "   handle :", self.handle)
        return ret
    
    def Deinitialization(self):
        """
        Releases the allocated resource and handle, and should be called when the handle is no longer needed.

        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
        """
        ret = vpm.Vision_API_Deinitialization_Cython(self.handle)
        print("Deinitialization :", ret)
        return ret
    
    def RegisterStreamSendBuffer(self, buf, length):
        """
        Registers user-defined send buffer for use in STREAM_MODE and is available only when UserConfig's operation mode is set to STREAM_MODE.
        
        Args:
            - buf (np.ndarray[np.uint8_t, ndim=1]): Pointer to the user-allocated send buffer.
            - length (uint32_t): Size of the user-allocated send buffer.

        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
            - addr (int): The memory address of the registered buffer
        """
        ret, addr = vpm.Vision_API_RegisterStreamSendBuffer_Cython(self.handle, buf, length)
        return ret, addr
    
    def RegisterStreamRecvBuffer(self, buf, length):
        """
        Registers user-defined receive buffer for use in STREAM_MODE and is available only when UserConfig's operation mode is set to STREAM_MODE.
        
        Args:
            - buf (np.ndarray[np.uint8_t, ndim=1]): Pointer to the user-allocated receive buffer.
            - length (uint32_t): Size of the user-allocated receive buffer.

        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
            - addr (int): The memory address of the registered buffer
        """
        ret, addr = vpm.Vision_API_RegisterStreamRecvBuffer_Cython(self.handle, buf, length)
        return ret, addr

    def Connection(self):
        """
        Attempts to connect to the target based on the network configuration information in handle, 
        and also performs a module version check and verifies the send/receive data size between the server and client configurations for authentication.
        
        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
        """
        ret = vpm.Vision_API_Connection_Cython(self.handle)
        print("Connection :", ret)
        return ret
    
    def Disconnection(self):
        """
        Attempts to disconnect from the target.

        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
        """
        ret = vpm.Vision_API_Disconnection_Cython(self.handle)
        print("Disconnection :", ret)
        return ret

    def SendMessage(self, packet, length, timeout=BLOCKING):
        """
        Enqueues data into the Message Send Queue.
        Note: The module automatically dequeues data from the Message Send Queue and transmits it to the target.

        Args:
            - packet (np.ndarray[np.uint8_t, ndim=1]): Pointer to the data received from the module.
            - length (uint32_t): The length of the data to be received. If it exceeds recvQ.maxDataSize, an ERROR will be returned.
            - timeout (int16_t): Specifies the timeout for the function's operation. 
                (-1: BLOCKING, 0: Non-BLOCKING, >0: timeout mode with the specified time (in milliseconds).)
        
        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
        """
        ret = vpm.Vision_API_SendMessage_Cython(self.handle, packet, length, timeout)
        return ret

    def RecvMessage(self, packet, length, timeout=BLOCKING):
        """
        Dequeues data from the Message Recv Queue.
        Note: The module automatically enqueues data received from the target into the Message Recv Queue.
        
        Args:
            - packet (np.ndarray[np.uint8_t, ndim=1]): Pointer to the data received from the module.
            - length (uint32_t): The length of the data to be received. If it exceeds recvQ.maxDataSize, an ERROR will be returned.
            - timeout (int16_t): Specifies the timeout for the function's operation. 
                (-1: BLOCKING, 0: Non-BLOCKING, >0: timeout mode with the specified time (in milliseconds).)
        
        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
        """
        ret = vpm.Vision_API_RecvMessage_Cython(self.handle, packet, length, timeout)
        return ret
    
    def PeekMessage(self, packet, length):
        """
        Peeks at data from the Message Recv Queue.

        Args:
            - packet (np.ndarray[np.uint8_t, ndim=1]): Pointer to the data received from the module.
            - length (uint32_t): The length of the data to be received. If it exceeds recvQ.maxDataSize, an ERROR will be returned.
        
        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
        """
        ret = vpm.Vision_API_PeekMessage_Cython(self.handle, packet, length)
        return ret

    def GetStreamSendBuffer(self, timeout=BLOCKING):
        """
        Retrieves the available pStreamInfo and Index from the user-registered send buffer.

        Args:
            timeout (int16_t): Specifies the timeout for the function's operation. 
            (-1: BLOCKING, 0: Non-BLOCKING, >0: timeout mode with the specified time (in milliseconds).)

        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
            - pStreamInfo (VisionStreamInfo or 0): Pointer to the available StreamInfo retrieved from the user-registered send buffer, which should be processed and then provided as input to SendStream.
            - pIndex (uint8_t): Pointer to the index value associated with the StreamInfo and which should be provided as input to SendStream. 
        """
        ret, x_addr, pIndex = vpm.Vision_API_GetStreamSendBuffer_Cython(self.handle, timeout)
        if ret == VISION_SUCCESS:
            x_ptr = ctypes.cast(x_addr, ctypes.POINTER(VisionStreamInfo))
            pStreamInfo = x_ptr.contents
        else:
            return ret, 0, 0
        return ret, pStreamInfo, pIndex

    def SendStream(self, pStreamInfo, pIndex):
        """
        Enqueues data into the Stream Send Queue.
        Note: The module automatically dequeues data from the Stream Send Queue and transmits it to the target.

        Args:
            - pStreamInfo (VisionStreamInfo): Pointer to the available StreamInfo retrieved from the user-registered send buffer.
            - pIndex (uint8_t): The index value associated with the StreamInfo, used to identify its position within the user-registered receive buffer.
        
        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
        """
        x_addr = ctypes.addressof(pStreamInfo)
        ret = vpm.Vision_API_SendStream_Cython(self.handle, x_addr, pIndex)
        return ret
    
    def RecvStream(self, timeout=BLOCKING):
        """
        Dequeues data from the Stream Recv Queue.
        Note: The module automatically enqueues data received from the target into the Stream Recv Queue.

        Args:
            timeout (int16_t): Specifies the timeout for the function's operation. 
            (-1: BLOCKING, 0: Non-BLOCKING, >0: timeout mode with the specified time (in milliseconds).)

        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
            - pStreamInfo (VisionStreamInfo or 0): Pointer to the StreamInfo containing the data received from the target.
            - pIndex (uint8_t): The index value associated with the StreamInfo, used to identify its position within the user-registered receive buffer.
        """
        ret, x_addr, pIndex = vpm.Vision_API_RecvStream_Cython(self.handle, timeout)
        if ret == VISION_SUCCESS:
            x_ptr = ctypes.cast(x_addr, ctypes.POINTER(VisionStreamInfo))
            pStreamInfo = x_ptr.contents
            return ret, pStreamInfo, pIndex
        else:
            return ret, 0, 0

    def PeekStream(self):
        """
        Peeks at data from the Stream Recv Queue.

        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
            - pStreamInfo (VisionStreamInfo or 0): Pointer to the StreamInfo containing the data received from the target.
            - pIndex (uint8_t): The index value associated with the StreamInfo, used to identify its position within the user-registered receive buffer.
        """
        ret, x_addr, pIndex = vpm.Vision_API_PeekStream_Cython(self.handle)
        if ret == VISION_SUCCESS:
            x_ptr = ctypes.cast(x_addr, ctypes.POINTER(VisionStreamInfo))
            pStreamInfo = x_ptr.contents
            return ret, pStreamInfo, pIndex
        else:
            return ret, 0, 0
    
    def ReleaseStreamRecvBuffer(self, pStreamInfo, pIndex):
        """
        Releases the StreamInfo and index received via RecvStream after use

        Args:
            - pStreamInfo (VisionStreamInfo): Pointer to the StreamInfo containing the data received from the target.
            - pIndex (uint8_t): The index value associated with the StreamInfo, used to identify its position within the user-registered receive buffer.

        Returns:
            - ret(int): The result of the operation. (0: Success, < 0: Failure)
        """
        x_addr = ctypes.addressof(pStreamInfo)
        ret = vpm.Vision_API_ReleaseStreamRecvBuffer_Cython(self.handle, x_addr, pIndex)
        return ret
    
    def buf2ndarray(self, pBuffer, len):
        """
        Converts a raw buffer (pointer) to a NumPy array and returns the array along with its memory address.
        
        Args:
            - pBuffer (ctypes.POINTER): A pointer to a raw memory buffer.
            - len (int): The length of the buffer, specifying the size of the resulting NumPy array.

        Returns:
            - pBuffer (numpy.ndarray): A NumPy array representing the buffer data.
            - pBuffer_Addr (int): The memory address of the buffer data.
        """
        # Cast the address to uint8
        x_ptr = ctypes.cast(pBuffer, ctypes.POINTER(ctypes.c_uint8))
        pBuffer = np.ctypeslib.as_array(x_ptr, shape=(len,))
        pBuffer_Addr = ctypes.addressof(x_ptr.contents)
        return pBuffer, pBuffer_Addr