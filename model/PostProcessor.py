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

from datetime import datetime
from PyQt5.QtCore import *
import numpy as np
import cv2
import json
import os, sys

class PostProcessor(QThread):
	def __init__(self, frameWidth, frameHeight):
		self.colorList = [(255, 0, 0), (0, 255, 0), (0, 0, 255)
						, (255, 255, 0), (255, 0, 255)]
		self.resultName = ['OD/TSR', 'LD', 'HBA']
		self.__frameWidth = frameWidth
		self.__frameHeight = frameHeight

	def drawBoundingBox(self, frame, odResult, num, drawRatioList=[1.0, 1.0]): # for NN
		resultNum = len(odResult)
		if resultNum > 0:
			for lData in odResult:
				try:
					startPoint = (int(lData['bbox'][0]*drawRatioList[0]), int(lData['bbox'][1]*drawRatioList[1]))
					endPoint = (int((lData['bbox'][0]+lData['bbox'][2])*drawRatioList[0]), int((lData['bbox'][1]+lData['bbox'][3])*drawRatioList[1]))
					cv2.rectangle(frame, startPoint, endPoint, self.colorList[num], 2)
					cv2.putText(frame, '[{}][{:.1f}%]'.format(lData['category_id'], lData['score']), (startPoint[0]-8, startPoint[1]-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colorList[num], 2)
				except Exception as e:
					_, _ , tb = sys.exc_info()
					print(__name__, tb.tb_lineno, e)
		return frame

	def drawBoundingBoxforDistance(self, frame, odResult, drawRatioList=[1.0, 1.0]): # for Falcon
		resultNum = len(odResult)
		if resultNum > 0:
			for lData in odResult:
				try:
					cId = lData['category_id']
					startPoint = (int(lData['bbox'][0]*drawRatioList[0]), int(lData['bbox'][1]*drawRatioList[1]))
					endPoint = (int((lData['bbox'][0]+lData['bbox'][2])*drawRatioList[0]), int((lData['bbox'][1]+lData['bbox'][3])*drawRatioList[1]))
					cv2.rectangle(frame, startPoint, endPoint, self.colorList[cId], 2)
					if cId != 4:
						cv2.putText(frame, '[{}][{:.1f}%] {:.1f}m'.format(lData['desc'], lData['score'], lData['distance']), (startPoint[0]-8, startPoint[1]-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colorList[lData['category_id']], 2)
						lData['desc'] = ''
					else:
						cv2.putText(frame, '[{}][{:.1f}%]'.format(lData['desc'], lData['score']), (startPoint[0]-8, startPoint[1]-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.colorList[lData['category_id']], 2)
						lData['distance'] = 0.0
					lData['score'] = lData['score']/100.0
				except Exception as e:
					_, _ , tb = sys.exc_info()
					print(__name__, tb.tb_lineno, e)
		return frame

	def drawLane(self, frame, laneResult, drawRatioList=[1.0, 1.0]):
		resultNum = len(laneResult)
		if resultNum > 0:
			for pointList in laneResult:
				pointList = np.multiply(pointList, drawRatioList)
				pointList = pointList.astype('int32')
				cv2.polylines(frame, [pointList], False, (224, 32, 100), 3)
		return frame

	def printHBA(self, frame, hbaResult):
		if len(hbaResult) > 0:
			# hbaResult['state'] - high / low
			cv2.putText(frame, 'HBA : ' + hbaResult['state'], (50, frame.shape[0] - 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
		return frame

	def printClass(self, frame, clResult, num, posX, posY):
		cv2.putText(frame, 'Cluster_{} : {}'.format(num, clResult), (posX, posY), cv2.FONT_HERSHEY_SIMPLEX, 1, self.colorList[num], 2)
		return frame

	def saveResultData(self, fileName, fileDir, imageShape, resultDict):
		data = dict()
		try:
			fileNameList = os.path.splitext(fileName)
			path = os.path.splitdrive(fileDir)
			data['images'] = {'file_path' : fileDir + '/' + fileName}
			data['images']['file_name'] = fileNameList[0]
			data['images']['sub_dir'] = str(path[1][1:])
			data['images']['height'] = imageShape[0]
			data['images']['width'] = imageShape[1]

			height_factor = imageShape[0] / self.__frameHeight
			width_factor = imageShape[1] / self.__frameWidth

			scaledOdList = []
			if 'cluster1' in resultDict and "od" in resultDict['cluster1']:
				for object in resultDict['cluster1']['od']:
					newDict = dict()
					newDict['id'] = object['id']
					newDict['category_id'] = object['category_id']
					newDict['score'] = object['score']
					newDict['desc'] = object['desc']
					newDict['distance'] = object['distance']
					newDict['bbox'] = [round(object['bbox'][0] * width_factor)
										, round(object['bbox'][1] * height_factor)
										, round(object['bbox'][2] * width_factor)
										, round(object['bbox'][3] * height_factor)]
					scaledOdList.append(newDict)

			if 'od' in resultDict:
				for object in resultDict['od']:
					newDict = dict()
					newDict['id'] = object['id']
					newDict['category_id'] = object['category_id']
					newDict['score'] = object['score']
					newDict['desc'] = object['desc']
					newDict['distance'] = object['distance']
					newDict['bbox'] = [round(object['bbox'][0] * width_factor)
										, round(object['bbox'][1] * height_factor)
										, round(object['bbox'][2] * width_factor)
										, round(object['bbox'][3] * height_factor)]
					scaledOdList.append(newDict)

			# data['annotations'] =  resultDict['od']
			data['annotations'] = scaledOdList
			if 'hba' in resultDict:
				data['hba'] = resultDict['hba']
			
			with open('{}_result/data_result/{}.json'.format(fileDir, fileNameList[0]), 'w') as fp:
				json.dump(data, fp, sort_keys=False, indent=4, separators=(',', ':'))

		except Exception as e:
			_, _ , tb = sys.exc_info()
			print(__name__, tb.tb_lineno, e)

	def saveResultList(self, resultNumList, resultList):
		now = datetime.now()
		try:
			f = open(now.strftime("%Y-%m-%d_%H%M") + '.txt', 'w')
			for i in range(len(resultNumList)):
				f.write('[{}] total : {}'.format(self.resultName[i], resultNumList[i]) + '\n')
				for ri in range(len(resultList[i])):
					f.write('({}) : '.format(ri) + str(resultList[i][ri]) + '\n')
			f.close()
		except Exception as e:
			_, _ , tb = sys.exc_info()
			print(__name__, tb.tb_lineno, e)

if __name__ == "__main__":
	img = cv2.imread('test_files/test.jpg')
	dstimg = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
	print(img.shape)
	img.save("test_files/filename.jpeg")
	cv2.imshow('test', dstimg)
	cv2.waitKey()
	cv2.destroyAllWindows()