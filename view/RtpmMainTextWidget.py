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

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtUiTools import QUiLoader
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
	rtpmStartStopSignal = Signal(bool, str, int, bool)
	rtpmFrameLabelSizeSignal = Signal(int, int)

	# GUI update signal
	updateImageSignal = Signal(list)
	clearImageSignal = Signal()
	updateProgressBarSignal = Signal(int, int)
	clearProgressBarSignal = Signal()
	clearAllGraphSignal = Signal()
	updateCpuGraphSignal = Signal(int, int)
	updateMemoryGraphSignal = Signal(int, int)
	updateFpsGraphSignal = Signal(int, int)
	updateNpuUsageSignal = Signal(int, tuple)
	showMessageBoxSignal = Signal(str, str)
	onUpdateResultPerfSignal = Signal(int, int, int)

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
		self.ui = QUiLoader().load("view/RtpmMainTextWidget.ui", self)
		
		self.initMonitoringView(settingData)
		self.initSlots()

	def resizeEvent(self, a0: QResizeEvent) -> None:
		# print(a0.size())
		# print(self.ui.frameLabel.width(), self.ui.frameLabel.height())
		self.rtpmFrameLabelSizeSignal.emit(self.ui.frameLabel.width(), self.ui.frameLabel.height())

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

		self.ui.fileSelectButton.clicked.connect(self.onFileSelectButtonClicked)
		self.ui.startButton.clicked.connect(self.onStartButtonClicked)
		self.ui.stopButton.clicked.connect(self.onStopButtonClicked)
		self.ui.inputComboBox.currentIndexChanged.connect(self.onInputComboBoxIndexChanged)

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
		infLayout = QVBoxLayout()
		for idx, value in enumerate(settingData['DetectTypes']):
			# Label
			label = QLabel(value)
			self._setLabelStyle(label)
			infLayout.addWidget(label)
			# LCD Number
			lcdNumber = QLCDNumber()
			self._setLcdNumberStyle(lcdNumber)
			self.infLcdList.append(lcdNumber)

			infLayout.addWidget(self.infLcdList[idx])
			tempList.append(self.infLcdList[idx])
		self.ui.infBox.setLayout(infLayout)
		self.__dataEditList.append(tempList[:]) # 0
		tempList.clear()

		# npu util object
		npuLayout = QVBoxLayout()
		for idx, value in enumerate(settingData['DetectTypes']):
			# Label
			label = QLabel(value)
			self._setLabelStyle(label)
			npuLayout.addWidget(label)
			# LCD Number
			lcdNumber = QLCDNumber()
			self._setLcdNumberStyle(lcdNumber)
			self.npuLcdList.append(lcdNumber)

			npuLayout.addWidget(self.npuLcdList[idx])
			tempList.append(self.npuLcdList[idx])
		self.ui.npuBox.setLayout(npuLayout)
		self.__dataEditList.append(tempList[:]) # 1
		tempList.clear()

		tempList.append(self.ui.cpuLcd)
		self.__dataEditList.append(tempList[:]) # 2
		tempList.clear()
		tempList.append(self.ui.memLcd)
		self.__dataEditList.append(tempList[:]) # 3
		tempList.clear()
		tempList.append(self.ui.fpsLcd)			# 4
		self.__dataEditList.append(tempList[:])
		tempList.clear()
		tempList.append(self.ui.npu0DmaPer)
		tempList.append(self.ui.npu0CompPer)
		tempList.append(self.ui.npu1DmaPer)
		tempList.append(self.ui.npu1CompPer)
		self.__dataEditList.append(tempList[:])  # 5
		tempList.clear()
		self.__dataEditList.append(tempList[:])
		tempList.clear()

	def __updateChart(self, editIndex, index, value):
		# self.__dataEditList[editIndex][index].setText(str(value))
		self.__dataEditList[editIndex][index].display(value)

	def __clearChart(self):
		for idx1 in range(len(self.__dataEditList)):
			for idx2 in range(len(self.__dataEditList[idx1])):
				# self.__dataEditList[idx1][idx2].clear()
				self.__dataEditList[idx1][idx2].display(0)

	# Gui update slot
	@Slot(int, int, int)
	def onUpdateResultPerfSlot(self, index, infTimeValue, npuUtilValue):
		self.__updateChart(0, index, infTimeValue)
		self.__updateChart(1, index, npuUtilValue)

	@Slot(int, int)	
	def onUpdateCpuGraphSlot(self, index, value):
		self.__updateChart(2, index, value)

	@Slot(int, int)	
	def onUpdateMemoryGraphSlot(self, index, value):
		self.__updateChart(3, index, value)

	@Slot(int, int)
	def onUpdateFpsGraphSlot(self, index, value):
		self.__updateChart(4, index, value)

	@Slot(int, tuple)
	def onUpdateNpuUsageGraphSlot(self, index, value):
		for idx, percent in enumerate(value):
			self.__updateChart(5, idx, percent)

	@Slot()
	def onClearAllGraphSlot(self):
		self.__clearChart()

	@Slot(int, int)
	def onUpdateProgressBarSlot(self, currentFrame, totalFrame):
		try:
			self.ui.frameCountEdit.setText(str(currentFrame) + ' / ' + str(totalFrame))
			percent = int((currentFrame * 100)/totalFrame)
			self.ui.playProgress.setValue(percent)
		except Exception as e:
			print(__name__, e)
			self.ui.frameCountEdit.setText('0 / 0')
			self.ui.playProgress.setValue(0)

	@Slot()
	def onClearProgressBarSlot(self):
		self.ui.frameCountEdit.setText('0 / 0')
		self.ui.playProgress.setValue(0)

	@Slot(list)
	def onUpdateImageSlot(self, frame):
		# bgn = time()
		inputMode = self.ui.inputComboBox.currentIndex()
		projectFitMode = self.ui.projectionFitSizeCheckBox.isChecked() if inputMode == 0 else False
		frameWidth = self.ui.frameLabel.width()
		frameHeight = self.ui.frameLabel.height()
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
				self.ui.frameLabel.clear()

			if shapeFlag:
				convertToQtFormat = QImage(frame[0].data, w, h, bytesPerLine, colorFormat)
				scaleRatio = 0.5 if inputMode == 0 and not projectFitMode else 1.0
				scaledSize = [w, h] if inputMode == 2 else [int(frameWidth*scaleRatio), int(frameHeight*scaleRatio)]
				scaledSize[0] = frameWidth if scaledSize[0] > frameWidth else scaledSize[0]
				scaledSize[1] = frameHeight if scaledSize[1] > frameHeight else scaledSize[1]
				widthOffset = int((frameWidth - scaledSize[0])*0.5) if not projectFitMode else 10
				widthOffset = 10 if widthOffset < 10 else widthOffset
				self.ui.frameLabel.move(widthOffset, 10)
				image = convertToQtFormat.scaled(scaledSize[0], scaledSize[1])
				self.ui.frameLabel.setPixmap(QPixmap.fromImage(image))
				# print('update time : {}'.format(f"{time() - bgn:.5f} s"))	
		except:
			self.ui.frameLabel.clear()

	@Slot()
	def onClearImageSlot(self):
		self.ui.frameLabel.clear()
		self.__setEnableControlButton(True, False)

	@Slot(str, str)
	def onShowMessageBoxSlot(self, title, message):
		self.__showMessageBox(title, message)

	@Slot()
	def onFileSelectButtonClicked(self):
		filePath = ''
		inputMode = self.ui.inputComboBox.currentIndex()
		if inputMode == 1: # File
			filePathTuple = QFileDialog.getOpenFileName(self, "Open", "", "Select file (*.*)")
			filePath = filePathTuple[0]
		elif inputMode == 2: # Folder
			filePath = QFileDialog.getExistingDirectory(self, "Select Directory")
		else:
			pass

		if filePath != '':
			self.ui.filePathEdit.setText(filePath)

	@Slot()
	def onStartButtonClicked(self):
		filePath = self.ui.filePathEdit.text()
		self.__setEnableControlButton(False, True)
		saveMode = self.ui.saveCheckBox.isChecked()
		inputIndex = self.ui.inputComboBox.currentIndex() # 0 : Camera (EVB) / 1 : file / 2 : folder
		self.rtpmStartStopSignal.emit(True, filePath, inputIndex, saveMode)

	@Slot()
	def onStopButtonClicked(self):
		self.__setEnableControlButton(False, False)
		self.rtpmStartStopSignal.emit(False, '', 0, True)

	@Slot(int)
	def onInputComboBoxIndexChanged(self, index):
		self.ui.filePathEdit.clear()
		if index > 0:
			self.ui.fileSelectButton.setEnabled(True)
		else:
			self.ui.fileSelectButton.setEnabled(False)

	def __setEnableControlButton(self, startBtnStatus, stopBtnStatus):
		self.ui.startButton.setEnabled(startBtnStatus)
		self.ui.stopButton.setEnabled(stopBtnStatus)

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