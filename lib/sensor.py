from smbus2 import SMBus

class Sensor:
    def __init__(self):
        self.bus_number = 1
        self.i2c_address = 0x76
        self.bus = SMBus(self.bus_number)
        self.setup()

    def write_reg(self, reg_address, data):
        self.bus.write_byte_data(self.i2c_address, reg_address, data)

    def get_calib_param(self):
        calib = []

        for i in range (0x88, 0x88 + 24):
            calib.append(self.bus.read_byte_data(self.i2c_address, i))
        calib.append(self.bus.read_byte_data(self.i2c_address, 0xA1))
        for i in range (0xE1, 0xE1 + 7):
            calib.append(self.bus.read_byte_data(self.i2c_address, i))

        digT = [
            (calib[1] << 8) | calib[0],
            (calib[3] << 8) | calib[2],
            (calib[5] << 8) | calib[4]
        ]
        digP = [
            (calib[7] << 8) | calib[6],
            (calib[9] << 8) | calib[8],
            (calib[11] << 8) | calib[10],
            (calib[13] << 8) | calib[12],
            (calib[15] << 8) | calib[14],
            (calib[17] << 8) | calib[16],
            (calib[19] << 8) | calib[18],
            (calib[21] << 8) | calib[20],
            (calib[23] << 8) | calib[22],
        ]
        digH = [
            calib[24],
            (calib[26] << 8) | calib[25],
            calib[27],
            (calib[28] << 4) | (0x0F & calib[29]),
            (calib[30] << 4) | ((calib[29] >> 4) & 0x0F),
            calib[31]
        ]

        for i in range(1, 2):
            if digT[i] & 0x8000:
                digT[i] = (-digT[i] ^ 0xFFFF) + 1

        for i in range(1, 8):
            if digP[i] & 0x8000:
                digP[i] = (-digP[i] ^ 0xFFFF) + 1

        for i in range(0, 6):
            if digH[i] & 0x8000:
                digH[i] = (-digH[i] ^ 0xFFFF) + 1

        return (digT, digH, digP)

    # raw_temp: raw temp value(adc_T)
    # dig: compensation parameters(digT)
    @classmethod
    def calc_fine(cls, raw_temp, dig):
        v1 = (raw_temp / 16384.0 - dig[0] / 1024.0) * dig[1]
        v2 = (raw_temp / 131072.0 - dig[0] / 8192.0) * (raw_temp / 131072.0 - dig[0] / 8192.0) * dig[2]
        return v1 + v2

    # t_fine: calculated compensation parameter by calc_fine
    # values: measured raw values
    # dig: compensation parameter
    @classmethod
    def compensate(cls, values, dig):
        t_fine = cls.calc_fine(values[0], dig[0])
        temp = t_fine / 5120.0
        humid = cls.compensate_humid(t_fine, values[1], dig[1])
        pressure = cls.compensate_pressure(t_fine, values[2], dig[2])
        return (temp, humid, pressure)

    @classmethod
    def compensate_humid(cls, t_fine, raw_humid, dig):
        var_h = t_fine - 76800.0
        if var_h != 0:
                var_h = (raw_humid - (dig[3] * 64.0 + dig[4] / 16384.0 * var_h)) * (dig[1] / 65536.0 * (1.0 + dig[5] / 67108864.0 * var_h * (1.0 + dig[2] / 67108864.0 * var_h)))
        else:
                return 0
        var_h = var_h * (1.0 - dig[0] * var_h / 524288.0)
        if var_h > 100.0:
                var_h = 100.0
        elif var_h < 0.0:
                var_h = 0.0
        return var_h

    @classmethod
    def compensate_pressure(cls, t_fine, raw_pressure, dig):
        pressure = 0.0

        v1 = (t_fine / 2.0) - 64000.0
        v2 = (((v1 / 4.0) * (v1 / 4.0)) / 2048) * dig[5]
        v2 = v2 + ((v1 * dig[4]) * 2.0)
        v2 = (v2 / 4.0) + (dig[3] * 65536.0)
        v1 = (((dig[2] * (((v1 / 4.0) * (v1 / 4.0)) / 8192)) / 8)  + ((dig[1] * v1) / 2.0)) / 262144
        v1 = ((32768 + v1) * dig[0]) / 32768

        if v1 == 0:
            return 0
        pressure = ((1048576 - raw_pressure) - (v2 / 4096)) * 3125
        if pressure < 0x80000000:
            pressure = (pressure * 2.0) / v1
        else:
            pressure = (pressure / v1) * 2
        v1 = (dig[8] * (((pressure / 8.0) * (pressure / 8.0)) / 8192.0)) / 4096
        v2 = ((pressure / 4.0) * dig[7]) / 8192.0
        return pressure + ((v1 + v2 + dig[6]) / 16.0)

    def setup(self):
        osrs_t = 1 # Temperature oversampling x 1
        osrs_p = 1 # Pressure oversampling x 1
        osrs_h = 1 # Humidity oversampling x 1
        mode   = 3 # Normal mode
        t_sb   = 5 # Tstandby 1000ms
        filter = 0 # Filter off
        spi3w_en = 0 # 3-wire SPI Disable

        ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | mode
        config_reg    = (t_sb << 5) | (filter << 2) | spi3w_en
        ctrl_hum_reg  = osrs_h

        self.write_reg(0xF2, ctrl_hum_reg)
        self.write_reg(0xF4, ctrl_meas_reg)
        self.write_reg(0xF5, config_reg)

    def read_data(self):
        data = []
        for i in range (0xF7, 0xF7 + 8):
            data.append(self.bus.read_byte_data(self.i2c_address, i))
        pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        hum_raw  = (data[6] << 8) | data[7]

        return (temp_raw, hum_raw, pres_raw)

    def fetch(self):
        t, h, p = self.compensate(self.read_data(), self.get_calib_param())
        return (t, h, p / 100)
