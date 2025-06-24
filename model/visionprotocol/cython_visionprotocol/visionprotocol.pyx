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
import ctypes
cimport cython
import numpy as np
cimport numpy as np
from libc.string cimport strcpy
from libc.stdint cimport uintptr_t
from libc.stdint cimport uint8_t, uint16_t, uint32_t, uint64_t, int16_t
import struct

# intialized Numpy. must do.
np.import_array()

cdef extern from "vision_api.h" nogil:
    ctypedef enum operation_mode_t:
        MESSAGE_MODE = 0
        STREAM_MODE = 1

    ctypedef enum network_interface_t:
        INTERFACE_ETHERNET = 0
        INTERFACE_PCIE = 1

    ctypedef enum network_role_t:
        SERVER = 0
        CLIENT = 1

    ctypedef enum activation_state_t:
        OFF = 0
        ON = 1

    ctypedef struct queue_info_t:
        uint32_t maxDataSize
        uint8_t numQ
    
    ctypedef struct network_bufsize_t:
        uint32_t sendBufSize
        uint32_t recvBufSize

    ctypedef struct vision_user_config_t:
        network_interface_t netInterface
        network_role_t netRole
        network_bufsize_t netBuf
        char ip[16]
        uint16_t port
        operation_mode_t opMode
        activation_state_t reconnection
        activation_state_t streamZeroCopy
        queue_info_t sendQ
        queue_info_t recvQ
    
    int Vision_API_Initialization(vision_user_config_t *config, uint64_t *pHandle)
    int Vision_API_Deinitialization(uint64_t *pHandle)
    int Vision_API_Connection(uint64_t pHandle) 
    int Vision_API_Disconnection(uint64_t *pHandle)

    int Vision_API_SendMessage(uint64_t pHandle, uint8_t *pBuffer, uint32_t length, int16_t timeout_ms)
    int Vision_API_RecvMessage(uint64_t pHandle, uint8_t *pBuffer, uint32_t length, int16_t timeout_ms)
    int Vision_API_PeekMessage(uint64_t pHandle, uint8_t *pBuffer, uint32_t length)

    int Vision_API_RegisterStreamSendBuffer(uint64_t pHandle, uint8_t *pBuffer, uint32_t length)
    int Vision_API_RegisterStreamRecvBuffer(uint64_t pHandle, uint8_t *pBuffer, uint32_t length)

    int Vision_API_GetStreamSendBuffer(uint64_t pHandle, uint64_t *pStreamInfo, uint8_t *pIndex, int16_t timeout_ms)
    int Vision_API_SendStream(uint64_t pHandle, uint64_t pStreamInfo, uint8_t index)
    int Vision_API_RecvStream(uint64_t pHandle, uint64_t *pStreamInfo, uint8_t *pIndex, int16_t timeout_ms)
    int Vision_API_PeekStream(uint64_t pHandle, uint64_t *pStreamInfo, uint8_t *pIndex)
    int Vision_API_ReleaseStreamRecvBuffer(uint64_t pHandle, uint64_t pStreamInfo, uint8_t index)

def Vision_API_Initialization_Cython(   pUserConfig,\
                                        np.ndarray[np.uint64_t, ndim=1] pHandle):
    x = vision_user_config_t()
    x.netInterface      = pUserConfig.netInterface
    x.netRole           = pUserConfig.netRole
    x.netBuf.sendBufSize = pUserConfig.netBuf.sendBufSize
    x.netBuf.recvBufSize = pUserConfig.netBuf.recvBufSize
    strcpy(x.ip, pUserConfig.ip)
    x.port              = pUserConfig.port
    x.opMode            = pUserConfig.opMode
    x.reconnection      = pUserConfig.reconnection
    x.streamZeroCopy    = pUserConfig.streamZeroCopy

    x.sendQ.maxDataSize = pUserConfig.sendQ.maxDataSize
    x.sendQ.numQ        = pUserConfig.sendQ.numQ
    x.recvQ.maxDataSize = pUserConfig.recvQ.maxDataSize
    x.recvQ.numQ        = pUserConfig.recvQ.numQ

    ret = Vision_API_Initialization(&x, &pHandle[0])
    return ret

def Vision_API_Deinitialization_Cython( np.ndarray[np.uint64_t, ndim=1] pHandle):
    return Vision_API_Deinitialization(&pHandle[0])

def Vision_API_RegisterStreamSendBuffer_Cython(np.ndarray[np.uint64_t, ndim=1] pHandle,\
                                                 np.ndarray[np.uint8_t, ndim=1] pBuffer, \
                                                 uint32_t length):
    x_ptr = (pBuffer).ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
    x_ptr_addr = hex(ctypes.addressof(x_ptr.contents))
    ret = Vision_API_RegisterStreamSendBuffer(pHandle[0], &pBuffer[0], length)
    return ret, x_ptr_addr

def Vision_API_RegisterStreamRecvBuffer_Cython(np.ndarray[np.uint64_t, ndim=1] pHandle,\
                                                 np.ndarray[np.uint8_t, ndim=1] pBuffer,\
                                                 uint32_t length):
    x_ptr = (pBuffer).ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
    x_ptr_addr = hex(ctypes.addressof(x_ptr.contents))
    ret = Vision_API_RegisterStreamRecvBuffer(pHandle[0], &pBuffer[0], length)
    return ret, x_ptr_addr 

def Vision_API_Connection_Cython(np.ndarray[np.uint64_t, ndim=1] pHandle):
    return Vision_API_Connection(pHandle[0])

def Vision_API_Disconnection_Cython(np.ndarray[np.uint64_t, ndim=1] pHandle):
    return Vision_API_Disconnection(&pHandle[0])

def Vision_API_SendMessage_Cython(  np.ndarray[np.uint64_t, ndim=1] pHandle,\
                                    np.ndarray[np.uint8_t, ndim=1] pBuffer,\
                                    uint32_t length, int16_t timeout_ms):
    return Vision_API_SendMessage(pHandle[0], &pBuffer[0], length, timeout_ms)

def Vision_API_RecvMessage_Cython(  np.ndarray[np.uint64_t, ndim=1] pHandle,\
                                    np.ndarray[np.uint8_t, ndim=1] pBuffer,\
                                    uint32_t length, int16_t timeout_ms):
    return Vision_API_RecvMessage(pHandle[0], &pBuffer[0], length, timeout_ms)

def Vision_API_PeekMessage_Cython(  np.ndarray[np.uint64_t, ndim=1] pHandle,\
                                    np.ndarray[np.uint8_t, ndim=1] pBuffer,\
                                    uint32_t length):
    return Vision_API_PeekMessage(pHandle[0], &pBuffer[0], length)

def Vision_API_GetStreamSendBuffer_Cython(  np.ndarray[np.uint64_t, ndim=1] pHandle, int16_t timeout_ms):
    
    cdef uint64_t pStreamInfo
    cdef uint8_t pIndex

    ret = Vision_API_GetStreamSendBuffer(pHandle[0], &pStreamInfo, &pIndex, timeout_ms)
    return ret, pStreamInfo, pIndex

def Vision_API_SendStream_Cython(   np.ndarray[np.uint64_t, ndim=1] pHandle,\
                                    uint64_t pStreamInfo,\
                                    uint8_t pIndex):
    return Vision_API_SendStream(pHandle[0], pStreamInfo, pIndex)

def Vision_API_RecvStream_Cython(   np.ndarray[np.uint64_t, ndim=1] pHandle, int16_t timeout_ms):

    cdef uint64_t pStreamInfo
    cdef uint8_t pIndex

    ret = Vision_API_RecvStream(pHandle[0], &pStreamInfo, &pIndex, timeout_ms)
    return ret, pStreamInfo, pIndex

def Vision_API_PeekStream_Cython(   np.ndarray[np.uint64_t, ndim=1] pHandle):

    cdef uint64_t pStreamInfo
    cdef uint8_t pIndex

    ret = Vision_API_PeekStream(pHandle[0], &pStreamInfo, &pIndex)
    return ret, pStreamInfo, pIndex

def Vision_API_ReleaseStreamRecvBuffer_Cython(  np.ndarray[np.uint64_t, ndim=1] pHandle,\
                                                uint64_t pStreamInfo,\
                                                uint8_t pIndex):
    return Vision_API_ReleaseStreamRecvBuffer(pHandle[0], pStreamInfo, pIndex)
