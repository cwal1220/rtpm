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

import struct
from .Packet import ISerializable

'''
typedef struct tagVision_MSG_NpuUsage{
	uint32_t npu0Dma;
	uint32_t npu0Comp;
	uint32_t npu1Dma;
	uint32_t npu1Comp;
} Vision_MSG_NpuUsage;
'''
SdkNpuUsageStructfmt = "<IIII"


class SdkNpuUsageClass(ISerializable):
    def __init__(self, buffer):
        self.struct_fmt = SdkNpuUsageStructfmt
        self.struct_len = struct.calcsize(self.struct_fmt)

        if buffer != None:
            unpacked = struct.unpack(self.struct_fmt, buffer[:self.struct_len])

            self.usage = unpacked

    def GetBytes(self):
        return struct.pack(
            self.struct_fmt,
            self.usage[0],
            self.usage[1],
            self.usage[2],
            self.usage[3]
        )

    def GetSize(self):
        return self.struct_len
