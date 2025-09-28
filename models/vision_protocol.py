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
import json
import time

import threading
import numpy as np

from data_structures import msginfo
from data_structures.cpu_utilization import CpuUtilizationClass
from data_structures.enums import PerformanceDataType, ResultType
from data_structures.json_result_parser import JsonResultParser
from data_structures.sdk_mem_usage import SdkMemUsageClass
from data_structures.sdk_npu_usage import SdkNpuUsageClass

# Load C based Vision Protocol Library v2.x.x
from third_party.visionprotocol.cython_visionprotocol.vision_api import *
import logging
logger = logging.getLogger(__name__)


class VisionProtocol(threading.Thread):
    def __init__(self, inputMode, frameWidth, frameHeight, frameChannel):
        super(VisionProtocol, self).__init__()
        self._stop_event = threading.Event()
        self.__sendStreamSize = frameWidth * frameHeight * frameChannel
        self.__sendQueueSize = 4
        self.rtpmMode = inputMode

        self.__dataQueue = list()
        self.__dataLenMax = 10
        self.__resultQueue = list()
        self.__isRunning = False
        self.vpm_msg = None
        self.vpm_stream = None
        self.__reader = FrameReader(self)

    def run(self):
        messageConfig = vision_user_config_t()
        messageConfig.netRole              = Role.SERVER
        messageConfig.netInterface         = Interface.INTERFACE_ETHERNET
        messageConfig.netBuf.sendBufSize   = SYS_DEFAULT_BUFSIZE
        messageConfig.netBuf.recvBufSize   = SYS_DEFAULT_BUFSIZE
        messageConfig.ip                   = "0.0.0.0".encode('utf-8')
        messageConfig.port                 = 9999
        messageConfig.opMode               = OperationMode.MESSAGE_MODE
        messageConfig.reconnection         = ActivationState.OFF
        messageConfig.sendQ.maxDataSize    = (1024*320)
        messageConfig.sendQ.numQ           = 6
        messageConfig.recvQ.maxDataSize    = (1024*320)
        messageConfig.recvQ.numQ           = 6
        self.vpm_msg = VisionProtocolModule(messageConfig)
        
        streamConfig = vision_user_config_t()
        streamConfig.netRole              = Role.SERVER
        streamConfig.netInterface         = Interface.INTERFACE_ETHERNET
        streamConfig.netBuf.sendBufSize   = SYS_DEFAULT_BUFSIZE
        streamConfig.netBuf.recvBufSize   = SYS_DEFAULT_BUFSIZE
        streamConfig.ip                   = "0.0.0.0".encode('utf-8')
        streamConfig.port                 = 9998
        streamConfig.opMode               = OperationMode.STREAM_MODE
        streamConfig.reconnection         = ActivationState.OFF
        streamConfig.streamZeroCopy       = ActivationState.ON

        if self.rtpmMode == 0: # projection mode
            streamConfig.sendQ.maxDataSize    = 0
            streamConfig.sendQ.numQ           = 0
            streamConfig.recvQ.maxDataSize    = self.__sendStreamSize
            streamConfig.recvQ.numQ           = self.__sendQueueSize
        else: # injection mode
            streamConfig.sendQ.maxDataSize    = self.__sendStreamSize
            streamConfig.sendQ.numQ           = self.__sendQueueSize
            streamConfig.recvQ.maxDataSize    = 0
            streamConfig.recvQ.numQ           = 0
        self.vpm_stream = VisionProtocolModule(streamConfig)

        if self.rtpmMode == 0: # projection mode
            self.__reader.start()

        self.__isRunning = True
        while not self._stop_event.is_set():
            resultType, resultData = self.__receiveData()
            if resultType is None:
                time.sleep(0.001)
                continue

            if resultType == ResultType.DETECTION_RESULT:
                self.__resultQueue.append(resultData)
            elif resultType == ResultType.PERFORMANCE_RESULT:
                if len(self.__dataQueue) < self.__dataLenMax:
                    try:
                        for index in range(len(resultData['inferenceTime'])):
                            self.__dataQueue.append([
                                PerformanceDataType.INFERENCE_TIME, 
                                index, 
                                resultData['inferenceTime'][index], 
                                resultData['utilization'][index]
                            ])
                        self.__dataQueue.append([PerformanceDataType.FPS, 0, int(resultData['fps'])])
                    except Exception as e:
                        logger.error(f"Error processing performance data: {e}", exc_info=True)
            elif resultType == ResultType.MONITORING_DATA:
                if len(self.__dataQueue) < self.__dataLenMax:
                    self.__dataQueue.append(resultData)
            
            time.sleep(0.001)

    def getStatus(self):
        return self.__isRunning

    def sendFrame(self, frameData):
        return self.__sendData(frameData)

    def gerPerformanceData(self):
        if len(self.__dataQueue) > 0:
            return self.__dataQueue.pop(0)
        else:
            return None

    def getDetectionResult(self):
        if len(self.__resultQueue) > 0:
            return self.__resultQueue.pop(0)
        else:
            return None

    def detectionResultQueueClear(self):
        self.__resultQueue.clear()

    def getFrame(self):
        if len(self.__reader.frameQueue) > 0:
            return self.__reader.frameQueue.pop(0)
        else:
            return None

    def frameQueueClear(self):
        self.__reader.frameQueue.clear()

    def __sendData(self, data):
        if len(data[0]) == self.__sendStreamSize:
            ret, pStreamInfo, pIndex = self.vpm_stream.GetStreamSendBuffer(BLOCKING)
            if ret == VISION_SUCCESS:
                pStreamInfo.id = 0x11
                pStreamInfo.length = self.__sendStreamSize
                pStreamInfo.seqNum = data[1]
                pStreamInfo.timestamp = 0
                pBuffer, addr = self.vpm_stream.buf2ndarray(pStreamInfo.pBuffer, pStreamInfo.length)
                pBuffer[:] = data[0].astype(np.uint8)
                ret = self.vpm_stream.SendStream(pStreamInfo, pIndex)
                if ret == VISION_SUCCESS:
                    return True
        return False

    def __receiveData(self):
        ret, resultData = None, None
        header_size = ctypes.sizeof(VisionMessage)
        np_peek_header = np.array(bytearray(header_size), dtype=np.uint8)
        header = np.array(bytearray(header_size), dtype=np.uint8)

        if self.vpm_msg.PeekMessage(np_peek_header, header_size) != VISION_SUCCESS:
            return ret, resultData
        if self.vpm_msg.RecvMessage(header, header_size, BLOCKING) != VISION_SUCCESS:
            return ret, resultData

        recvheader  = VisionMessage(*(np.frombuffer(header, dtype=VisionMessage)[0]))
        recvMsgData = np.zeros(recvheader.length, dtype=np.uint8)
        if self.vpm_msg.RecvMessage(recvMsgData, recvheader.length, BLOCKING) != VISION_SUCCESS:
            return ret, resultData

        recvMsgData = recvMsgData.tobytes()

        if recvheader.id == msginfo.VISION_MSG_EVENT_CPU_UTILIZATION:
            cpuUtilization = CpuUtilizationClass(recvMsgData)
            ret, resultData = ResultType.MONITORING_DATA, [PerformanceDataType.CPU_PERFORMANCE, 0, cpuUtilization.utilization]
        elif recvheader.id == msginfo.VISION_MSG_EVENT_SDK_MEM_USAGE:
            memory = SdkMemUsageClass(recvMsgData)
            ret, resultData = ResultType.MONITORING_DATA, [PerformanceDataType.MEMORY, 0, memory.usage]
        elif recvheader.id == msginfo.VISION_MSG_EVENT_NPU_DRIVER_USAGE:
            npuUsage = SdkNpuUsageClass(recvMsgData)
            ret, resultData = ResultType.MONITORING_DATA, [PerformanceDataType.NPU_USAGE, 0, npuUsage.usage]
        elif recvheader.id == msginfo.VISION_MSG_EVENT_RESULT_DATA_JSON:
            try:
                jsonBytes = JsonResultParser(recvMsgData)
                resultData = json.loads(jsonBytes.data)
                ret = ResultType.DETECTION_RESULT
            except Exception as e:
                logger.error(f"JSON parsing error: {e}", exc_info=True)
        elif recvheader.id == msginfo.VISION_MSG_EVENT_RESULT_PERF_JSON:
            try:
                jsonBytes = JsonResultParser(recvMsgData)
                resultData = json.loads(jsonBytes.data)
                ret = ResultType.PERFORMANCE_RESULT
            except Exception as e:
                logger.error(f"JSON parsing error: {e}", exc_info=True)

        return ret, resultData

class FrameReader(threading.Thread):
    def __init__(self, parent):
        super(FrameReader, self).__init__()
        self.parent = parent
        self.frameQueue = list()
        self.frameLenMax = 3

    def run(self):
        while not self.parent._stop_event.is_set():
            ret, peekStreamInfo, peekIndex= self.parent.vpm_stream.PeekStream()
            if(ret == VISION_SUCCESS):
                ret, pStreamInfo, pIndex = self.parent.vpm_stream.RecvStream(BLOCKING)
                if(ret == VISION_SUCCESS):
                    pBuffer, addr = self.parent.vpm_stream.buf2ndarray(pStreamInfo.pBuffer, pStreamInfo.length)
                    self.frameQueue.append(pBuffer)
                    if len(self.frameQueue) > self.frameLenMax:
                        del self.frameQueue[0]
                    self.parent.vpm_stream.ReleaseStreamRecvBuffer(pStreamInfo, pIndex)
            time.sleep(0.001)
