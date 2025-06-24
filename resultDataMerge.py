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

import json
import os
from time import time

TEST_RESULT_PATH = 'C:/Users/hglee/Desktop/test_image_15000_result'
RESULT_FILE_NAME = 'result_out_test.json'

bgn = time()
resultList = list()
dataResultPath = TEST_RESULT_PATH + '/data_result'
for fileName in os.listdir(dataResultPath):
    resultList.append(json.load(open(dataResultPath+'/'+fileName, 'r')))
sBgn = time()
with open('{}/{}'.format(TEST_RESULT_PATH, RESULT_FILE_NAME), 'w') as fp:
    json.dump(resultList, fp, sort_keys=False, indent=4, separators=(',', ':'))
end = time()
print('read time :', f"{sBgn-bgn:.5f}")
print('saved time :', f"{end-sBgn:.5f}")