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
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import uic
import sys
from time import time
class RtpmMainWidget(QWidget):
	"""
	Description
	----------
	Realtime Performance Monitor Widget

	Attributes
	----------
	fileSelectButton
	startButton
	stopButton
	filePathEdit
	frameLabel
	playProgress
	frameCountEdit
	inferenceTimeEdit
	inferenceTimeView
	utilizationEdit
	utilizationView
	cpuEdit
	cpuView
	memoryEdit
	memoryView
	fpsEdit
	fpsView
	"""
	# Widget event signal
	rtpmStartStopSignal = pyqtSignal(bool, str, int, bool)
	rtpmFrameLabelSizeSignal = pyqtSignal(int, int)

	# GUI update signal
	updateImageSignal = pyqtSignal(list)
	clearImageSignal = pyqtSignal()
	updateProgressBarSignal = pyqtSignal(int, int)
	clearProgressBarSignal = pyqtSignal()
	clearAllGraphSignal = pyqtSignal()
	updateCpuGraphSignal = pyqtSignal(int, int)
	updateMemoryGraphSignal = pyqtSignal(int, int)
	updateFpsGraphSignal = pyqtSignal(int, int)
	updateNpuUsageSignal = pyqtSignal(int, tuple)
	showMessageBoxSignal = pyqtSignal(str, str)
	onUpdateResultPerfSignal = pyqtSignal(int, int, int)

	def __init__(self, settingData):
		'''
		Description
		----------
		RtpmMainWidget 생성자

		Parameters
		----------
		None

		Return
		------
		None
		'''
		QWidget.__init__(self)
		self.ui = uic.loadUi("view/RtpmMainTextWidget.ui", self)
		
		self.initMonitoringView(settingData)
		self.initSlots()

	def resizeEvent(self, a0: QResizeEvent) -> None:
		# print(a0.size())
		# print(self.frameLabel.width(), self.frameLabel.height())
		self.rtpmFrameLabelSizeSignal.emit(self.frameLabel.width(), self.frameLabel.height())

	def initSlots(self):
		'''
		Description
		----------
		signal, slot 초기화 (connect)

		Parameters
		----------
		None

		Return
		------
		None
		'''
		self.updateImageSignal.connect(self.onUpdateImageSlot)
		self.clearImageSignal.connect(self.onClearImageSlot)
		self.updateProgressBarSignal.connect(self.onUpdateProgressBarSlot)
		self.clearAllGraphSignal.connect(self.onClearAllGraphSlot)
		self.clearProgressBarSignal.connect(self.onClearProgressBarSlot)
		self.onUpdateResultPerfSignal.connect(self.onUpdateResultPerfSlot)
		self.updateCpuGraphSignal.connect(self.onUpdateCpuGraphSlot)
		self.updateMemoryGraphSignal.connect(self.onUpdateMemoryGraphSlot)
		self.updateFpsGraphSignal.connect(self.onUpdateFpsGraphSlot)
		self.updateNpuUsageSignal.connect(self.onUpdateNpuUsageGraphSlot)
		self.showMessageBoxSignal.connect(self.onShowMessageBoxSlot)

		self.fileSelectButton.clicked.connect(self.onFileSelectButtonClicked)
		self.startButton.clicked.connect(self.onStartButtonClicked)
		self.stopButton.clicked.connect(self.onStopButtonClicked)
		self.inputComboBox.currentIndexChanged.connect(self.onInputComboBoxIndexChanged)

	def _setLabelStyle(self, label):
			label.setFont(QFont('Gulim', 12, weight=QFont.Weight.Bold))

	def _setLcdNumberStyle(self, lcdNumber):
			lcdNumber.setMaximumWidth(80)
			lcdNumber.setMaximumHeight(30)
			lcdNumber.setMinimumWidth(80)
			lcdNumber.setMinimumHeight(30)
			lcdNumber.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
			lcdNumber.setFont(QFont('Agency', 9))
     
	def initMonitoringView(self, settingData):
		self.__dataEditList = list()
		tempList = list()
		self.infLcdList = list()
		self.npuLcdList = list()

		# inference time object
		infLayout = QGridLayout()
		for idx, value in enumerate(settingData['DetectTypes']):
			# Label
			label = QLabel(value)
			self._setLabelStyle(label)
			infLayout.addWidget(label, idx, 0)
			# LCD Number
			lcdNumber = QLCDNumber()
			self._setLcdNumberStyle(lcdNumber)
			self.infLcdList.append(lcdNumber)

			infLayout.addWidget(self.infLcdList[idx], idx, 1)
			tempList.append(self.infLcdList[idx])
			self.infBox.setLayout(infLayout)
		self.__dataEditList.append(tempList[:]) # 0
		tempList.clear()

		# npu util object
		npuLayout = QGridLayout()
		for idx, value in enumerate(settingData['DetectTypes']):
			# Label
			label = QLabel(value)
			self._setLabelStyle(label)
			npuLayout.addWidget(label, idx, 0)
			# LCD Number
			lcdNumber = QLCDNumber()
			self._setLcdNumberStyle(lcdNumber)
			self.npuLcdList.append(lcdNumber)

			npuLayout.addWidget(self.npuLcdList[idx], idx, 1)
			tempList.append(self.npuLcdList[idx])
			self.npuBox.setLayout(npuLayout)
		self.__dataEditList.append(tempList[:]) # 1
		tempList.clear()

		tempList.append(self.cpuLcd)
		self.__dataEditList.append(tempList[:]) # 2
		tempList.clear()
		tempList.append(self.memLcd)
		self.__dataEditList.append(tempList[:]) # 3
		tempList.clear()
		tempList.append(self.fpsLcd)			# 4
		self.__dataEditList.append(tempList[:])
		tempList.clear()
		tempList.append(self.npu0DmaPer)
		tempList.append(self.npu0CompPer)
		tempList.append(self.npu1DmaPer)
		tempList.append(self.npu1CompPer)
		self.__dataEditList.append(tempList[:])  # 5
		tempList.clear()
		self.__dataEditList.append(tempList[:])
		tempList.clear()

		# Dynamic
		# self.__initTextView('Inference Time', 1, 'ms')
		# self.__initTextView('NPU', 1, '%')
		# self.__initTextView('Cpu', 1, '%')
		# self.__initTextView('Memory', 1, '%')
		# self.__initTextView('Fps', 1, 'FPS')
		# self.performanceLayout.addItem(QSpacerItem(10, 100, QSizePolicy.Expanding))

	def __initTextView(self, title, dataNum, suffix):
		titleLabel = QLabel(title)
		titleLabel.setFont(QFont('Consolas', 25))
		self.performanceLayout.addWidget(titleLabel)
		tempList = list()
		for idx in range(dataNum):
			suffixLabel = QLabel(suffix)
			suffixLabel.setFont(QFont('Consolas', 25))
			tempLayout = QHBoxLayout()
			self.performanceLayout.addLayout(tempLayout)
			# tempLayout.addWidget(QLabel(str(idx)))
			tempList.append(QTextEdit())
			tempLayout.addWidget(tempList[idx])
			# tempList[idx].setTextColor(QColor(0, 0, 255))
			tempList[idx].setReadOnly(True)
			tempList[idx].setFixedSize(120, 60)
			tempList[idx].setFont(QFont('Consolas', 30, QFont.Bold))
			tempLayout.addWidget(suffixLabel)
		hLine = QFrame()
		hLine.setFrameShape(QFrame.HLine)
		hLine.setFrameShadow(QFrame.Sunken)
		self.performanceLayout.addWidget(hLine)	
		self.__dataEditList.append(tempList)

	def __updateChart(self, editIndex, index, value):
		# self.__dataEditList[editIndex][index].setText(str(value))
		self.__dataEditList[editIndex][index].display(value)

	def __clearChart(self):
		for idx1 in range(len(self.__dataEditList)):
			for idx2 in range(len(self.__dataEditList[idx1])):
				# self.__dataEditList[idx1][idx2].clear()
				self.__dataEditList[idx1][idx2].display(0)

	# Gui update slot
	@pyqtSlot(int, int, int)
	def onUpdateResultPerfSlot(self, index, infTimeValue, npuUtilValue):
		self.__updateChart(0, index, infTimeValue)
		self.__updateChart(1, index, npuUtilValue)

	@pyqtSlot(int, int)
	def onUpdateInferenceTimeGraphSlot(self, index, value):
		self.__updateChart(0, index, value)

	@pyqtSlot(int, int)	
	def onUpdateCpuGraphSlot(self, index, value):
		self.__updateChart(2, index, value)

	@pyqtSlot(int, int)	
	def onUpdateMemoryGraphSlot(self, index, value):
		self.__updateChart(3, index, value)

	@pyqtSlot(int, int)
	def onUpdateFpsGraphSlot(self, index, value):
		self.__updateChart(4, index, value)

	@pyqtSlot(int, tuple)
	def onUpdateNpuUsageGraphSlot(self, index, value):
		for idx, percent in enumerate(value):
			self.__updateChart(5, idx, percent)

	@pyqtSlot()
	def onClearAllGraphSlot(self):
		self.__clearChart()

	@pyqtSlot(int, int)
	def onUpdateProgressBarSlot(self, currentFrame, totalFrame):
		try:
			self.frameCountEdit.setText(str(currentFrame) + ' / ' + str(totalFrame))
			percent = int((currentFrame * 100)/totalFrame)
			self.playProgress.setValue(percent)
		except Exception as e:
			print(__name__, e)
			self.frameCountEdit.setText('0 / 0')
			self.playProgress.setValue(0)

	@pyqtSlot()
	def onClearProgressBarSlot(self):
		self.frameCountEdit.setText('0 / 0')
		self.playProgress.setValue(0)

	@pyqtSlot(list)
	def onUpdateImageSlot(self, frame):
		# bgn = time()
		inputMode = self.inputComboBox.currentIndex()
		projectFitMode = self.projectionFitSizeCheckBox.isChecked() if inputMode == 0 else False
		frameWidth = self.frameLabel.width()
		frameHeight = self.frameLabel.height()
		try:
			shapeFlag = True
			if len(frame[0].shape) == 2:
				h, w = frame[0].shape
				bytesPerLine = w
				colorFormat = QImage.Format_Grayscale8
			elif len(frame[0].shape) == 3:
				h, w, ch = frame[0].shape
				bytesPerLine = ch * w
				colorFormat = QImage.Format_BGR888
			else:
				shapeFlag = False
				self.frameLabel.clear()

			if shapeFlag:
				convertToQtFormat = QImage(frame[0].data, w, h, bytesPerLine, colorFormat)
				scaleRatio = 0.5 if inputMode == 0 and not projectFitMode else 1.0
				scaledSize = [w, h] if inputMode == 2 else [int(frameWidth*scaleRatio), int(frameHeight*scaleRatio)]
				scaledSize[0] = frameWidth if scaledSize[0] > frameWidth else scaledSize[0]
				scaledSize[1] = frameHeight if scaledSize[1] > frameHeight else scaledSize[1]
				widthOffset = int((frameWidth - scaledSize[0])*0.5) if not projectFitMode else 10
				widthOffset = 10 if widthOffset < 10 else widthOffset
				self.frameLabel.move(widthOffset, 10)
				image = convertToQtFormat.scaled(scaledSize[0], scaledSize[1])
				self.frameLabel.setPixmap(QPixmap.fromImage(image))
				# print('update time : {}'.format(f"{time() - bgn:.5f} s"))	
		except:
			self.frameLabel.clear()

	@pyqtSlot()
	def onClearImageSlot(self):
		self.frameLabel.clear()
		self.__setEnableControlButton(True, False)

	@pyqtSlot(str, str)
	def onShowMessageBoxSlot(self, title, message):
		self.__showMessageBox(title, message)

	@pyqtSlot()
	def onFileSelectButtonClicked(self):
		filePath = ''
		inputMode = self.inputComboBox.currentIndex()
		if inputMode == 1: # File
			filePathTuple = QFileDialog.getOpenFileName(self, "Open", "", "Select file (*.*)")
			filePath = filePathTuple[0]
		elif inputMode == 2: # Folder
			filePath = QFileDialog.getExistingDirectory(self, "Select Directory")
		else:
			pass

		if filePath != '':
			self.filePathEdit.setText(filePath)

	@pyqtSlot()
	def onStartButtonClicked(self):
		filePath = self.filePathEdit.text()
		self.__setEnableControlButton(False, True)
		saveMode = self.saveCheckBox.isChecked()
		inputIndex = self.inputComboBox.currentIndex() # 0 : Camera (EVB) / 1 : file / 2 : folder
		self.rtpmStartStopSignal.emit(True, filePath, inputIndex, saveMode)

	@pyqtSlot()
	def onStopButtonClicked(self):
		self.__setEnableControlButton(False, False)
		self.rtpmStartStopSignal.emit(False, '', 0, True)

	@pyqtSlot(int)
	def onInputComboBoxIndexChanged(self, index):
		self.filePathEdit.clear()
		if index > 0:
			self.fileSelectButton.setEnabled(True)
		else:
			self.fileSelectButton.setEnabled(False)

	def __setEnableControlButton(self, startBtnStatus, stopBtnStatus):
		self.startButton.setEnabled(startBtnStatus)
		self.stopButton.setEnabled(stopBtnStatus)

	def __showMessageBox(self, title, message):
		msg = QMessageBox()
		msg.setWindowTitle(title)
		msg.setText(message)
		msg.exec()

if __name__ == "__main__":
	app = QApplication([])
	window = RtpmMainWidget()
	window.show()
	sys.exit(app.exec_())