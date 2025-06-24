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

from time import time
import json
import sys
import struct
from PyQt5.QtCore import *
import numpy as np

# Load C based Vision Protocol Library v2.x.x
from model.visionprotocol.cython_visionprotocol.vision_api import *

from msg import msginfo
from msg.CpuUtilization import CpuUtilizationClass
from msg.SdkMemUsage import SdkMemUsageClass
from msg.SdkNpuUsage import SdkNpuUsageClass
from msg.JsonResultParser import JsonResultParser


class VisionProtocol(QThread):
    def __init__(self, inputMode, frameWidth, frameHeight, frameChannel):
        super(VisionProtocol, self).__init__()
        self.__sendStreamSize = frameWidth * frameHeight * frameChannel
        self.__sendQueueSize = 4
        self.rtpmMode = inputMode

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

        self.__reader = FrameReader(self)
        if self.rtpmMode == 0: # projection mode
            self.__reader.start()

        self.__dataQueue = list()
        self.__dataLenMax = 10
        self.__resultQueue = list()
        # self.__resultLenMax = 20
        self.start()
        self.__isRunning = False

    def run(self):
        while True:
            # data
            resultType, resultData = self.__receiveData()
            if resultType is None:
                self.usleep(1000)
            elif resultType == 0:  # Detection Result Data
                self.__resultQueue.append(resultData)
                self.usleep(1000)
            elif resultType == 1:  # Result Performance
                if len(self.__dataQueue) < self.__dataLenMax:
                    try:
                        for index in range(len(resultData['inferenceTime'])):
                            self.__dataQueue.append(
                                [1, index, resultData['inferenceTime'][index], resultData['utilization'][index]])
                        self.__dataQueue.append([2, 0, int(resultData['fps'])])
                    except Exception as e:
                        print(e)
                self.usleep(1000)
            else:  # resultType == 10 # Monitoring Data for common resource
                if len(self.__dataQueue) < self.__dataLenMax:
                    self.__dataQueue.append(resultData)
                self.usleep(1000)

            # enable vision protocol running flag
            self.__isRunning = True

    def getStatus(self):
        return self.__isRunning

    def sendFrame(self, frameData):
        return self.__sendData(frameData)

    def sendMsgData(self, msg):
        return self.__sendMsgData(msg)

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
        # to evb
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
                    # print(f"[SEND] [addr: {hex(addr)}] [idx: {pIndex}] [{hex(pStreamInfo.id)}, {pStreamInfo.length}, {pStreamInfo.seqNum}, {pStreamInfo.timestamp}] [{pBuffer}]")
                    return True
        return False

    def __sendMsgData(self, msg):
        # send to evb
        msg_array = np.frombuffer(msg.GetBytes(), dtype=np.uint8)
        ret = self.vpm_msg.SendMessage(msg_array, msg.GetSize(), BLOCKING)
        if ret != VISION_SUCCESS:
            print("[__sendMsgData] ERROR")
        return ret

    def __receiveData(self):
        ret, resultData = None, [None]

        header_size = ctypes.sizeof(VisionMessage)
        np_peek_header = np.array(bytearray(header_size), dtype=np.uint8)
        header = np.array(bytearray(header_size), dtype=np.uint8)

        ret = self.vpm_msg.PeekMessage(np_peek_header, header_size)
        if ret == VISION_SUCCESS:
            ret = self.vpm_msg.RecvMessage(header, header_size, BLOCKING)
            if ret == VISION_SUCCESS:
                recvheader  = VisionMessage(*(np.frombuffer(header, dtype=VisionMessage)[0]))

                recvMsgData = np.zeros(recvheader.length, dtype=np.uint8)
                ret = self.vpm_msg.RecvMessage(recvMsgData, recvheader.length, BLOCKING)
                if ret == VISION_SUCCESS:
                    recvMsgData = recvMsgData.tobytes()

                    if recvheader.id == msginfo.VISION_MSG_EVENT_CPU_UTILIZATION:
                        cpuUtilization = CpuUtilizationClass(recvMsgData)
                        ret, resultData = 10, [3, 0, cpuUtilization.utilization]
                    elif recvheader.id == msginfo.VISION_MSG_EVENT_SDK_MEM_USAGE:
                        memory = SdkMemUsageClass(recvMsgData)
                        ret, resultData = 10, [4, 0, memory.usage]
                    elif recvheader.id == msginfo.VISION_MSG_EVENT_NPU_DRIVER_USAGE:
                        npuUsage = SdkNpuUsageClass(recvMsgData)
                        ret, resultData = 10, [5, 0, npuUsage.usage]
                    else:
                        ret = None
                        try:
                            if recvheader.id == msginfo.VISION_MSG_EVENT_RESULT_DATA_JSON:
                                ret = 0
                            else:  # == msginfo.VISION_MSG_EVENT_RESULT_PERF_JSON
                                ret = 1
                            jsonBytes = JsonResultParser(recvMsgData)
                            resultData = json.loads(jsonBytes.data)
                        except Exception as e:
                            # resultData = [None]
                            ret, resultData = None, [None]
                            print(__name__, e)
                else:
                    ret, resultData = None, [None]
            else:
                ret, resultData = None, [None]
        else:
            ret, resultData = None, [None]

        return ret, resultData

class FrameReader(QThread):
    def __init__(self, parent):
        super(FrameReader, self).__init__(parent)
        self.parent = parent

        self.frameQueue = list()
        self.frameLenMax = 3

    def run(self):
        while True:

            ret, peekStreamInfo, peekIndex= self.parent.vpm_stream.PeekStream()
            if(ret == VISION_SUCCESS):
                # print(f"[PEEK] [idx: {peekIndex}] [{hex(peekStreamInfo.id)}, {peekStreamInfo.length}, {peekStreamInfo.seqNum}, {peekStreamInfo.timestamp}]")
                ret, pStreamInfo, pIndex = self.parent.vpm_stream.RecvStream(BLOCKING)
                if(ret == VISION_SUCCESS):
                    pBuffer, addr = self.parent.vpm_stream.buf2ndarray(pStreamInfo.pBuffer, pStreamInfo.length)
                    # print(f"[RECV] [addr: {hex(addr)}] [idx: {pIndex}] [{hex(pStreamInfo.id)}, {pStreamInfo.length}, {pStreamInfo.seqNum}, {pStreamInfo.timestamp}] [{pBuffer}]")
                    
                    self.frameQueue.append(pBuffer)
                    if len(self.frameQueue) > self.frameLenMax:
                        del self.frameQueue[0]
                    self.parent.vpm_stream.ReleaseStreamRecvBuffer(pStreamInfo, pIndex)
            self.usleep(100)

if __name__ == "__main__":
    visionProtocol = VisionProtocol()
