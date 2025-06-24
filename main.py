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

from model import *
from view import *
from controller import *
import sys
import yaml

_VERSION_MAJOR = 2
_VERSION_MINOR = 0
_VERSION_PATCH = 5
_VERSION = f"{_VERSION_MAJOR}.{_VERSION_MINOR}.{_VERSION_PATCH}"

class Main(QWidget):
	def __init__(self):
		super(Main, self).__init__()

		self.visionProtocol = None	# variable
		self.postProcessor = None	# variable
		self.settingData = None
		try:
			with open('Setting.yaml') as f:
				self.settingData = yaml.load(f, Loader=yaml.FullLoader)
		except:
			# default setting
			self.settingData = {
					'Projection': {'width': 1280, 'height': 720, 'channel': 3}, 
					'Injection'	: {'width': 1280, 'height': 720, 'channel': 3}, 
					'DetectType': ['NPU0', 'NPU1']
					}

		self.initViews()
		self.initControllers()

	# Initialize Controller
	def initControllers(self):
		self.rtpmController = RtpmController(self, self.settingData)

	# Initialize View(GUI)
	def initViews(self):
		self.rtpmMainWidget = RtpmMainWidget(self.settingData)

	def start(self):
		self.rtpmMainWidget.show()
		self.rtpmMainWidget.resize(1400, 900) # default size

if __name__ == '__main__':
	app = QApplication([])
	main = Main()
	main.start()
	sys.exit(app.exec_())
