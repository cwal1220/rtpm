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

from PyQt5.QtCore import *
from model import *
import cv2
from time import time
from datetime import datetime
import os
import sys
import json
from numpy import *
from PIL import Image

# global
global gFolderModePath
global gImageResultPath
gImageResultPath = '/image_result'
global gDataResultPath
gDataResultPath = '/data_result'

# Result type of cluster
TYPE_CLASSIFICATION = 0
TYPE_OBJECTDETECTION = 1

class RtpmController(QThread):
    def __init__(self, parent, settingData):
        super(RtpmController, self).__init__()
        self.parent = parent
        self.__frameWidth = settingData['Injection']['width']
        self.__frameHeight = settingData['Injection']['height']
        self.__frameChannel = settingData['Injection']['channel']
        self.__projframeWidth = settingData['Projection']['width']
        self.__projframeHeight = settingData['Projection']['height']
        self.__projframeChannel = settingData['Projection']['channel']
        self.__projframeHeightYV12 = self.__projframeHeight + \
            (self.__projframeHeight >> 1)
        self.__videoFps = 30

        # set worker
        self.__reader = RtpmFileReader(
            parent, (self.__frameHeight, self.__frameWidth, self.__frameChannel))
        self.__updater = RtpmDataUpdater(parent)
        self.__recorder = RtpmVideoRecorder(parent)
        self.__imageSaver = RtpmImageSaver(parent)

        self.__monitoringStatus = False
        self.__controlStatus = False
        self.__fileSaveStatus = False
        self.__mode = False
        self.__frameList = list()
        # self.__frameListMax = 1
        self.__frameListMax = 5
        self.__windowWidth = 1920
        self.__windowHeight = 1080
        self.__saveFrameList = list()
        self.__captureFrame = False

        self.__initSlots()
        self.__clearVariables()

    def __initSlots(self):
        self.parent.rtpmMainWidget.rtpmStartStopSignal.connect(
            self.rtpmStartStopSlot)
        self.parent.rtpmMainWidget.rtpmFrameLabelSizeSignal.connect(
            self.rtpmFrameLabelSizeSlot)
        self.__reader.rtpmReaderStopSignal.connect(self.rtpmReaderStopSlot)

    def __clearVariables(self):
        self.__frameList.clear()

    def run(self):
        # set class
        rtpmMainWidget = self.parent.rtpmMainWidget
        visionProtocol = self.parent.visionProtocol
        postProcessor = self.parent.postProcessor

        # set worker
        self.__updater.startUpdate()

        visionProtocol.detectionResultQueueClear()
        visionProtocol.frameQueueClear()

        global gFolderModePath
        global gDataResultPath

        while self.__monitoringStatus:
            # How to receive frame by mode
            if self.__mode:  # read file
                # List > [0 : SyncStamp][1 : Result total by detection type][2 : Result data by detection type]
                resultList = visionProtocol.getDetectionResult()
                if resultList is not None:
                    try:
                        while True:
                            frameList = self.__frameList.pop(0)
                            if frameList[1] == resultList['info'][0]:  # compare syncStamp
                                bgn = time()
                                # print('processing :', len(self.__frameList), resultList['info'][0])
                                drawRatio = [
                                    frameList[0].shape[1]/self.__frameWidth, frameList[0].shape[0]/self.__frameHeight]

                                if ('cluster1' in resultList) or ('cluster2' in resultList):
                                    # Draw result for cluster1
                                    if resultList['cluster1']['type'] == TYPE_CLASSIFICATION:
                                        frameList[0] = postProcessor.printClass(
                                            frameList[0], resultList['cluster1']['cl'], 1, 50, 50)
                                    else: # TYPE_OBJECTDETECTION
                                        frameList[0] = postProcessor.drawBoundingBox(
                                            frameList[0], resultList['cluster1']['od'], 1, drawRatio)

                                    # Draw result for cluster2
                                    if resultList['cluster2']['type'] == TYPE_CLASSIFICATION:
                                        frameList[0] = postProcessor.printClass(
                                            frameList[0], resultList['cluster2']['cl'], 2, 50, 100)
                                    else: # TYPE_OBJECTDETECTION
                                        frameList[0] = postProcessor.drawBoundingBox(
                                            frameList[0], resultList['cluster2']['od'], 2, drawRatio)
                                else:
                                    # Draw OD
                                    frameList[0] = postProcessor.drawBoundingBoxforDistance(
                                        frameList[0], resultList['od'], drawRatio)

                                # For Save file
                                # sbgn = time()
                                if self.__fileSaveStatus:
                                    self.__saveFrameList.append(frameList[:])
                                    if len(frameList) > 2:
                                        postProcessor.saveResultData(
                                            frameList[2], gFolderModePath, frameList[0].shape, resultList)
                                # print('save : {} s'.format(f"{time() - sbgn:.5f}"))

                                # Update frame
                                rtpmMainWidget.updateImageSignal.emit(
                                    [frameList[0]])
                                break
                            self.usleep(1000)
                    except Exception as e:
                        _, _, tb = sys.exc_info()
                        print(__name__, tb.tb_lineno, e)
            else:  # receive frame
                resultFrame = visionProtocol.getFrame()
                if resultFrame is not None:
                    try:
                        # Convert byte array to np array
                        # RGB888
                        if self.__projframeChannel == 3:
                            npFrame = frombuffer(resultFrame, dtype='uint8').reshape(self.__projframeHeight, self.__projframeWidth, self.__projframeChannel)
                        elif self.__projframeChannel == 1:
                        #VGA_YUV420
                            npFrame = frombuffer(resultFrame, dtype='uint8').reshape(self.__projframeHeightYV12, self.__projframeWidth, self.__projframeChannel)
                            npFrame = cv2.cvtColor(npFrame, cv2.COLOR_YUV420p2RGB)

                        # VGA_Y
                        # npFrame = frombuffer(resultFrame, dtype='uint8').reshape(self.__projframeHeight, self.__projframeWidth)



                        rtpmMainWidget.updateImageSignal.emit([npFrame])

                        # For Save Video
                        if self.__fileSaveStatus:
                            self.__saveFrameList.append([npFrame, 0])

                        # For Save Capture Frame
                        if self.__captureFrame:
                            self.__saveFrameList.append([npFrame, 0])
                            self.__captureFrame = False

                    except Exception as e:
                        _, _, tb = sys.exc_info()
                        print(__name__, tb.tb_lineno, e)

            if self.__controlStatus:
                if len(self.__frameList) == 0:
                    self.__monitoringStatus = False
            self.usleep(1000)
        else:
            if self.__fileSaveStatus and (gFolderModePath != ''):
                resultList = list()
                resultPath = gFolderModePath + '_result'
                dataResultPath = resultPath + gDataResultPath
                for fileName in os.listdir(dataResultPath):
                    resultList.append(
                        json.load(open(dataResultPath+'/'+fileName, 'r')))
                with open('{}/result_out.json'.format(resultPath), 'w') as fp:
                    json.dump(resultList, fp, sort_keys=False,
                              indent=4, separators=(',', ':'))

            self.__recorder.stopRecord()
            self.__imageSaver.stopSave()
            self.__updater.stopUpdate()
            self.__clearVariables()

            rtpmMainWidget.clearProgressBarSignal.emit()
            rtpmMainWidget.clearImageSignal.emit()

    @pyqtSlot(bool, str, int, bool)
    def rtpmStartStopSlot(self, status, filePath, inputMode, savingMode):
        global gFolderModePath
        global gImageResultPath
        global gDataResultPath
        # [Saving mode] bool
        # [Input mode] 0 : Camera (EVB) / 1 : file / 2 : folder
        if status:
            if self.__monitoringStatus is False:
                self.__monitoringStatus = status
                self.__controlStatus = False
                self.__fileSaveStatus = savingMode
                self.__mode = True if inputMode > 0 else False

                # initialize model
                stream_width = self.__frameWidth if self.__mode else self.__projframeWidth
                if self.__projframeChannel == 1:
                    stream_height = self.__frameHeight if self.__mode else self.__projframeHeightYV12
                else:
                    stream_height = self.__frameHeight if self.__mode else self.__projframeHeight
                stream_channel = self.__frameChannel if self.__mode else self.__projframeChannel
                self.initModel(inputMode, stream_width, stream_height, stream_channel)

                # start controller thread
                self.start()
                if self.__fileSaveStatus:
                    gFolderModePath = ''
                    if inputMode == 0:  # projection mode
                        # self.__recorder.startRecord(
                        #     self.__saveFrameList, (self.__frameWidth, self.__frameHeight), self.__videoFps)
                        gFolderModePath = str(datetime.today().strftime("%Y%m%d_%H%M%S"))
                        rootDir = gFolderModePath + '_result'
                        if os.path.isdir(rootDir) is False:
                            os.mkdir(rootDir)
                        self.__imageSaver.startSave(
                            self.__saveFrameList, rootDir, "projection")
                    elif inputMode == 1:  # file
                        rootDir = 'test_results'
                        if os.path.isdir(rootDir) is False:
                            os.mkdir(rootDir)
                        fileName = os.path.basename(filePath)
                        self.__imageSaver.startSave(
                            self.__saveFrameList, rootDir, fileName)
                    else:  # folder
                        gFolderModePath = filePath
                        rootDir = filePath + '_result'
                        if os.path.isdir(rootDir) is False:
                            os.mkdir(rootDir)
                        resultImgPath = rootDir + gImageResultPath
                        if os.path.isdir(resultImgPath) is False:
                            os.mkdir(resultImgPath)
                        dataResultPath = rootDir + gDataResultPath
                        if os.path.isdir(dataResultPath) is False:
                            os.mkdir(dataResultPath)
                        self.__imageSaver.startSave(
                            self.__saveFrameList, rootDir)
                else:
                    if inputMode == 0:  # projection mode
                        rootDir = "projection_capture"
                        fileName = "proj_frame"
                        self.__imageSaver.startSave(
                            self.__saveFrameList, rootDir, fileName)
                if self.__mode:
                    self.__reader.startRead(
                        filePath, self.__frameList, self.__frameListMax)
                else:
                    self.__mode = False
        else:
            if self.__monitoringStatus is True:
                if self.__mode is True:
                    self.__reader.stopRead()
                else:
                    self.__controlStatus = True

    @pyqtSlot(int, int)
    def rtpmFrameLabelSizeSlot(self, width, height):
        self.__windowWidth = width
        self.__windowHeight = height

    @pyqtSlot()
    def rtpmReaderStopSlot(self):
        self.__controlStatus = True

    @pyqtSlot()
    def rtpmCaptureSlot(self):
        # check projection mode and vision protocol status
        if not self.__mode and self.parent.visionProtocol.getStatus():
            self.__captureFrame = True

    def initModel(self, inputMode, streamWidth, streamHeight, streamChannel):
        if self.parent.visionProtocol is None or not isinstance(self.parent.visionProtocol, VisionProtocol):
            visionProtocol = VisionProtocol(inputMode, streamWidth, streamHeight, streamChannel)
            postProcessor = PostProcessor(
                self.__frameWidth, self.__frameHeight)
            self.parent.visionProtocol = visionProtocol
            self.parent.postProcessor = postProcessor

            # Waiting for vision protocol
            while not isinstance(visionProtocol, VisionProtocol) and not visionProtocol.getStatus():
                print("waiting for initialize vision protocol...")
                self.usleep(10000)


class RtpmVideoRecorder(QThread):
    def __init__(self, parent):
        super(RtpmVideoRecorder, self).__init__(parent)
        self.parent = parent
        self.__savingStatus = False
        self.__commandStatus = False

    def run(self):
        # Create object for recording
        now = datetime.now()
        wName = now.strftime("%H%M%S_%f")+'.mp4v'
        wFourcc = cv2.VideoWriter_fourcc(*'h264')  # four character code
        recorderObj = cv2.VideoWriter(
            wName, wFourcc, self.__wFps, self.__wFrameSize, isColor=True)
        isOpened = recorderObj.isOpened()
        if isOpened:
            while self.__commandStatus or self.__savingStatus:
                if len(self.__frameList) > 0:
                    frame = self.__frameList.pop(0)
                    # print(type(frame), frame.shape, frame.dtype)
                    recorderObj.write(frame)
                else:
                    if self.__commandStatus == False:
                        print('saved file :', wName)
                        self.__savingStatus = False
                self.usleep(100)
            else:
                recorderObj.release()
        else:
            self.savingStatus = False

    def startRecord(self, frameList, frameSize, fps):
        self.__wFps = fps
        self.__wFrameSize = frameSize
        self.__commandStatus = True
        self.__savingStatus = True
        self.__frameList = frameList
        self.start()

    def stopRecord(self):
        self.__commandStatus = False
        while self.__savingStatus:
            self.usleep(1000)


class RtpmImageSaver(QThread):
    def __init__(self, parent):
        super(RtpmImageSaver, self).__init__(parent)
        self.parent = parent
        self.__savingStatus = False
        self.__commandStatus = False
        self.__rootDir = ''

    def run(self):
        # Create object for recording
        global gFolderModePath
        while self.__savingStatus:
            if len(self.__frameList) > 0:
                frameList = self.__frameList.pop(0)
                if self.__fileName != '':
                    now = datetime.now()
                    sTime = now.strftime("%H%M%S_%f")
                    fileNameList = os.path.splitext(self.__fileName)
                    # cv2.imwrite('{}/{}_{}_{}.jpeg'.format(self.__rootDir,
                    #             fileNameList[0], frameList[1], sTime), frameList[0])
                    cv2.imwrite('{}/{}_{}.jpeg'.format(self.__rootDir, fileNameList[0], sTime), frameList[0])
                    resultList = self.parent.visionProtocol.getDetectionResult()
                    if(resultList != None):
                        with open('{}/{}_{}.json'.format(self.__rootDir, fileNameList[0], sTime), 'w', encoding='utf-8') as json_file:
                            json.dump(resultList, json_file, ensure_ascii=False, indent=4)

                else:
                    fileNameList = os.path.splitext(frameList[2])
                    cv2.imwrite(
                        '{}_result/image_result/{}.jpeg'.format(gFolderModePath, fileNameList[0]), frameList[0])
            else:
                if self.__commandStatus == False:
                    self.__savingStatus = False
            self.usleep(1000)
        else:
            pass

    def startSave(self, frameList, rootDir='', fileName=''):
        self.__commandStatus = True
        self.__savingStatus = True
        self.__frameList = frameList
        self.__rootDir = rootDir
        self.__fileName = fileName
        if not os.path.exists(self.__rootDir):
            os.mkdir(self.__rootDir)
        self.start()

    def stopSave(self):
        self.__commandStatus = False
        while self.__savingStatus:
            self.usleep(1000)


class RtpmDataUpdater(QThread):
    def __init__(self, parent):
        super(RtpmDataUpdater, self).__init__(parent)
        self.parent = parent
        self.__status = False

    def run(self):
        # set class
        gerPerformanceData = self.parent.visionProtocol.gerPerformanceData
        rtpmMainWidget = self.parent.rtpmMainWidget

        while self.__status:
            # Performance Data update
            dataList = gerPerformanceData()
            if dataList is not None:
                dataType = dataList[0]
                if dataType == 1:  # Inference Time / Utilization
                    rtpmMainWidget.onUpdateResultPerfSignal.emit(
                        dataList[1], dataList[2], dataList[3])
                elif dataType == 2:  # FPS
                    rtpmMainWidget.updateFpsGraphSignal.emit(
                        dataList[1], dataList[2])
                elif dataType == 3:  # CPU Performance
                    rtpmMainWidget.updateCpuGraphSignal.emit(
                        dataList[1], dataList[2])
                elif dataType == 4:  # Memory
                    rtpmMainWidget.updateMemoryGraphSignal.emit(
                        dataList[1], dataList[2])
                elif dataType == 5:  # npuUsage
                    rtpmMainWidget.updateNpuUsageSignal.emit(
                        dataList[1], dataList[2])
                else:
                    pass
            self.usleep(1000)
        else:
            rtpmMainWidget.clearAllGraphSignal.emit()

    def startUpdate(self):
        self.__status = True
        self.start()

    def stopUpdate(self):
        self.__status = False


class RtpmFileReader(QThread):
    rtpmReaderStopSignal = pyqtSignal()
    def __init__(self, parent, baseSizeTuple):
        super(RtpmFileReader, self).__init__(parent)
        self.parent = parent
        self.__baseSize = baseSizeTuple
        self.__status = False
        self.__filePath = ''
        self.__imageExt = ['.jpg', '.jpeg', '.png', '.bmp']
        self.__videoExt = ['.mp4', '.avi']

        # set class
        self.__rtpmMainWidget = parent.rtpmMainWidget
        self.__visionProtocol = None  # variable

    def run(self):
        # reference vision protocol instance
        self.__visionProtocol = self.parent.visionProtocol

        # Check file type
        timeStamp = 0
        if os.path.isdir(self.__filePath):  # case of folder
            sendFlag = True
            while self.__status:
                if sendFlag:
                    fileList = os.listdir(self.__filePath)
                    fileList = [file for file in fileList if file.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
                    fileNum = len(fileList)
                    self.__rtpmMainWidget.updateProgressBarSignal.emit(
                        timeStamp, fileNum)
                    for fileName in fileList:
                        if os.path.splitext(fileName)[1] in self.__imageExt:
                            while len(self.__frameList) >= self.__frameListMax:
                                self.usleep(1000)
                            if self.__status is False:
                                break
                            filePath = self.__filePath + '/' + fileName
                            try:
                                image = cv2.imread(filePath)
                                timeStamp += 1
                                if image.shape != self.__baseSize:
                                    # Use OpenCV
                                    rImage = cv2.resize(
                                        image, (self.__baseSize[1], self.__baseSize[0]))
                                    frameRaw = ravel(
                                        rImage[..., ::-1], order='C')
                                    # Use PIL
                                    # img = Image.open(filePath)
                                    # img_resize = img.resize((self.__baseSize[1], self.__baseSize[0]), Image.LANCZOS)
                                    # img_resize = img_resize.convert('RGB')
                                    # rImage = asarray(img_resize)
                                    # frameRaw = ravel(rImage[...,::], order='C')
                                else:
                                    frameRaw = ravel(
                                        image[..., ::-1], order='C')
                                ret = self.__visionProtocol.sendFrame(
                                    [frameRaw, timeStamp])
                                if ret is True:
                                    self.__rtpmMainWidget.updateProgressBarSignal.emit(
                                        timeStamp, fileNum)
                                    self.__frameList.append(
                                        [image, timeStamp, fileName])
                                    # print('read file :', fileName)
                                else:
                                    print(
                                        'Image : {} / Frame : {} / ret : {}'.format(filePath, 1, ret))
                            except Exception as e:
                                _, _, tb = sys.exc_info()
                                print(__name__, tb.tb_lineno, e)
                    sendFlag = False
                self.usleep(1000)
            else:
                self.__status = False
        else:  # case of video
            fileType = os.path.splitext(self.__filePath)
            if fileType[1] in self.__videoExt:
                videoObj = cv2.VideoCapture(self.__filePath)  # CAP_FFMPEG
                isOpened = videoObj.isOpened()
                if isOpened and (self.__frameList is not None):
                    prevTime = 0
                    currentFrameCount = 0
                    totalFrameCount = int(
                        videoObj.get(cv2.CAP_PROP_FRAME_COUNT))
                    videoFps = videoObj.get(cv2.CAP_PROP_FPS)
                    msTime = int((1.0/videoFps) * 1000)
                    fpsTime = msTime * 0.001
                    while self.__status:
                        currentTime = time() - prevTime
                        if (currentTime >= fpsTime) and (currentFrameCount <= totalFrameCount):
                            prevTime = time()
                            ret, frame = videoObj.read()
                            currentFrameCount += 1
                            if ret:
                                # frame output
                                self.__rtpmMainWidget.updateProgressBarSignal.emit(
                                    currentFrameCount, totalFrameCount)
                                if len(self.__frameList) < self.__frameListMax:
                                    if frame.shape != self.__baseSize:
                                        # Use OpenCV
                                        # rFrame = cv2.resize(frame, (self.__baseSize[1], self.__baseSize[0]))
                                        # frameRaw = ravel(rFrame[...,::], order='C')
                                        # Use PIL
                                        img = Image.fromarray(
                                            frame[..., ::-1])  # BGR => RGB
                                        img_resize = img.resize(
                                            (self.__baseSize[1], self.__baseSize[0]), Image.LANCZOS)
                                        img_resize = img_resize.convert('RGB')
                                        rImage = asarray(img_resize)
                                        frameRaw = ravel(
                                            rImage[..., ::], order='C')
                                    else:
                                        frameRaw = ravel(
                                            frame[..., ::], order='C')
                                    timeStamp = msTime * \
                                        (currentFrameCount - 1)
                                    ret = self.__visionProtocol.sendFrame(
                                        [frameRaw, timeStamp])
                                    if ret is True:
                                        self.__frameList.append(
                                            [frame, timeStamp])
                                    else:
                                        print(
                                            'Video Frame : {} / ret : {}'.format(currentFrameCount, ret))
                        self.usleep(1000)
                    else:
                        videoObj.release()
                else:
                    self.__status = False
                    self.__rtpmMainWidget.showMessageBoxSignal.emit(
                        'Message', "Can't open file : " + self.__filePath)
            elif fileType[1] in self.__imageExt:
                sendFlag = True
                while self.__status:
                    if sendFlag:
                        try:
                            image = cv2.imread(self.__filePath)
                            self.__rtpmMainWidget.updateProgressBarSignal.emit(
                                1, 1)
                            if image.shape != self.__baseSize:
                                # USE OpenCV
                                # rImage = cv2.resize(image, (self.__baseSize[1], self.__baseSize[0]))
                                # frameRaw = ravel(rImage[...,::-1], order='C')
                                # Use PIL
                                img = Image.open(self.__filePath)
                                img_resize = img.resize(
                                    (self.__baseSize[1], self.__baseSize[0]), Image.LANCZOS)
                                img_resize = img_resize.convert('RGB')
                                rImage = asarray(img_resize)
                                frameRaw = ravel(rImage[..., ::], order='C')
                            else:
                                frameRaw = ravel(image[..., ::-1], order='C')
                            ret = self.__visionProtocol.sendFrame(
                                [frameRaw, timeStamp])
                            if ret is True:
                                self.__frameList.append([image, timeStamp])
                            else:
                                print(
                                    'Image : {} / Frame : {} / ret : {}'.format(self.__filePath, 1, ret))
                        except Exception as e:
                            _, _, tb = sys.exc_info()
                            print(__name__, tb.tb_lineno, e)
                        sendFlag = False
                    self.usleep(1000)
                else:
                    self.__status = False
            else:
                self.__rtpmMainWidget.showMessageBoxSignal.emit(
                    'Error', "Can't open file : " + self.__filePath)

        self.rtpmReaderStopSignal.emit()

    def startRead(self, filePath, frameList, frameListMax):
        self.__filePath = filePath
        self.__status = True
        self.__frameList = frameList
        self.__frameListMax = frameListMax
        self.start()

    def stopRead(self):
        self.__status = False
