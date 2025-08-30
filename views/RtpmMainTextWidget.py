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
		self.ui = QUiLoader().load("views/RtpmMainTextWidget.ui", self)
		
		# Create a layout for RtpmMainWidget and add self.ui to it
		main_layout = QVBoxLayout(self)
		main_layout.addWidget(self.ui)
		self.setLayout(main_layout)
		
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
		self.ui.togglePerformanceButton.clicked.connect(self.onTogglePerformanceView)

	def _setLabelStyle(self, label):
			label.setFont(QFont('Gulim', 12, weight=QFont.Weight.Bold))

	def _setLabelValueStyle(self, label):
			# Styling is primarily done via stylesheet now
			pass
     
	def initMonitoringView(self, settingData):
		self.__performanceWidgets = {}

		# Inference Time objects
		# These are now defined in the UI file
		self.__performanceWidgets["inference_time"] = [
			self.ui.inf0ValueLabel,
			self.ui.inf1ValueLabel
		]

		# NPU Utilization objects
		# These are now defined in the UI file
		self.__performanceWidgets["npu_utilization"] = [
			{
				"value_label": self.ui.npu0ValueLabel,
				"progress_bar": self.ui.npu0ProgressBar
			},
			{
				"value_label": self.ui.npu1ValueLabel,
				"progress_bar": self.ui.npu1ProgressBar
			}
		]

		self.__performanceWidgets["cpu"] = {
			"value_label": self.ui.cpuValueLabel,
			"progress_bar": self.ui.cpuProgressBar
		}

		self.__performanceWidgets["memory"] = {
			"value_label": self.ui.memValueLabel,
			"progress_bar": self.ui.memProgressBar
		}

		self.__performanceWidgets["fps"] = self.ui.fpsValueLabel

		self.__performanceWidgets["npu_details"] = {
			"npu0_dma": self.ui.npu0DmaValueLabel,
			"npu0_comp": self.ui.npu0CompValueLabel,
			"npu1_dma": self.ui.npu1DmaValueLabel,
			"npu1_comp": self.ui.npu1CompValueLabel
		}


	def __updateChart(self, key, index, value):
		if key == "inference_time":
			widgets = self.__performanceWidgets[key]
			if index < len(widgets):
				widgets[index].setText(f"{value} ms")
		elif key == "npu_utilization":
			# 'index' here refers to the NPU index (0 or 1)
			if index < len(self.__performanceWidgets[key]):
				npu_widgets = self.__performanceWidgets[key][index]
				npu_widgets["value_label"].setText(f"{value}%")
				npu_widgets["progress_bar"].setValue(value)
			else:
				print(f"Error: Invalid NPU index {index} for NPU utilization")
		elif key == "cpu":
			widgets = self.__performanceWidgets[key]
			widgets["value_label"].setText(f"{value}%")
			widgets["progress_bar"].setValue(value)
		elif key == "memory":
			widgets = self.__performanceWidgets[key]
			widgets["value_label"].setText(f"{value}%")
			widgets["progress_bar"].setValue(value)
		elif key == "fps":
			self.__performanceWidgets[key].setText(f"{value}")
		elif key == "npu_details":
			# 'index' here refers to the specific NPU detail (0_dma, 0_comp, etc.)
			# We need to map the index to the correct key in the npu_details dictionary
			npu_detail_keys = ["npu0_dma", "npu0_comp", "npu1_dma", "npu1_comp"]
			if index < len(npu_detail_keys):
				detail_key = npu_detail_keys[index]
				self.__performanceWidgets[key][detail_key].setText(f"{value}%")
			else:
				print(f"Error: Invalid index {index} for NPU details")
		else:
			print(f"Error: Unknown performance widget key: {key}")

	def __clearChart(self):
		for key, widgets in self.__performanceWidgets.items():
			if key == "inference_time":
				for widget in widgets:
					widget.setText("0 ms")
			elif key == "npu_utilization":
				for npu_widgets in widgets:
					npu_widgets["value_label"].setText("0%")
					npu_widgets["progress_bar"].setValue(0)
			elif key == "fps":
				widgets.setText("0")
			elif key == "npu_details":
				for detail_key in widgets:
					widgets[detail_key].setText("0%")
			else:
				print(f"Warning: Unknown performance widget key in __clearChart: {key}")

	# Gui update slot
	@Slot(int, int, int)
	def onUpdateResultPerfSlot(self, index, infTimeValue, npuUtilValue):
		self.__updateChart("inference_time", index, infTimeValue)
		self.__updateChart("npu_utilization", index, npuUtilValue)

	@Slot(int, int)	
	def onUpdateCpuGraphSlot(self, index, value):
		self.__updateChart("cpu", 0, value) # index 0 for value_label, index 1 for progress_bar
		self.__updateChart("cpu", 1, value)

	@Slot(int, int)	
	def onUpdateMemoryGraphSlot(self, index, value):
		self.__updateChart("memory", 0, value) # index 0 for value_label, index 1 for progress_bar
		self.__updateChart("memory", 1, value)

	@Slot(int, int)
	def onUpdateFpsGraphSlot(self, index, value):
		self.__updateChart("fps", 0, value) # FPS is a single QLabel, index 0 is arbitrary but consistent

	@Slot(int, tuple)
	def onUpdateNpuUsageGraphSlot(self, index, value):
		for idx, percent in enumerate(value):
			self.__updateChart("npu_details", idx, percent)

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
		except Exception as e:
			import traceback
			traceback.print_exc()
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

	@Slot()
	def onTogglePerformanceView(self):
		if self.ui.performanceGroup.isVisible():
			self.ui.performanceGroup.hide()
		else:
			self.ui.performanceGroup.show()

if __name__ == "__main__":
	app = QApplication([])
	window = RtpmMainWidget()
	window.show()
	sys.exit(app.exec_())