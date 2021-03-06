from functools import reduce
from .utils import flatten
from .ir_converter import IRConverter

class DaikinAircon:
    periodic_time = 435
    carrier_freq= 38.0
    customer_code = [17, 218, 7]

    def __init__(self):
        self.irconv = IRConverter(leader_pulse=[8, 4], space_pulse=[1, 1], mark_pulse=[1, 3])

    # convert from integer to bool array
    def bool(self, i, digits):
        return reversed([c == '1' for c in format(i, "0{}b".format(digits))])

    def frame(self, seq):
        return flatten([self.bool(i, 4 if index in [2, 3] else 8) for index, i in enumerate(seq)])

    def pack(self, work=True, mode='auto', temp=0, speed=-1, swing=True):
        first = [2, 0, 2, 0, 0, 0, 0, -1, 0, 0, 16, 0, 16, 0, 0, 0, 0, -1]
        if work == False:
            first[7] = 0x02
        elif mode == 'auto':
            first[7] = 0x0d
        elif mode == 'cool':
            first[7] = 0x0e
        elif mode == 'heat':
            first[7] = 0x10
        elif mode == 'dry':
            first[7] = 0x0f
        elif mode == 'fan':
            first[7] = 0x1a
        if swing:
            first[10] = 0
        first[-1] = 0xff & (sum(self.customer_code[0:2]) + ((first[0] << 4) | (self.customer_code[2])) + sum(first[1:-2]))
        first = self.customer_code + first
        payload = self.code(work, mode, temp, speed, swing)
        encoded = [self.irconv.encode_frame(self.frame(f), self.periodic_time) for f in [first, payload]]
        return reduce(lambda x, y: x + [35000] + y, encoded)

    def code(self, work=True, mode='auto', temp=0, speed=-1, swing=True):
        data = [0] * 17
        data[0] = 2
        data[3] = 9 if work else 8
        data[13] = 195

        if speed not in range(-1, 5 + 1):
            raise ValueError('invalid speed')
        # speed = -1 => auto
        data[6] = (((speed + (2 if speed > 0 else 11)) << 4)) | (0xf if swing else 0)

        if mode == 'auto':
            if temp not in range(-5, 5 + 1):
                raise ValueError('temp out of range')
            data[4] = 192 | ((temp * 2) & 0b11111)
            data[5] = 128
        elif mode == 'cool':
            if temp not in range(18, 32 + 1):
                raise ValueError('temp out of range')
            data[3] |= 0b0011 << 4
            data[4] = (temp * 2) & 0xff
        elif mode == 'heat':
            if temp not in range(14, 30 + 1):
                raise ValueError('temp out of range')
            data[3] |= 0b0100 << 4
            data[4] = (temp * 2) & 0xff
        elif mode == 'dry':
            if temp not in range(-2, 2 + 1):
                raise ValueError('temp out of range')
            data[3] |= 0b0010 << 4
            data[4] = 192 | ((temp * 2) & 0b11111)
            data[5] = 128
        elif mode == 'fan':
            data[3] |= 0b0110 << 4
            data[4] = (25 * 2) & 0xff
        else:
            if work:
                raise ValueError('invalid mode')

        checksum = sum(self.customer_code[0:2]) + (((data[0] << 4) | (self.customer_code[2])) & 0xff) + sum(data[1:-2])
        data[-1] = checksum & 0xff
        return self.customer_code + data
