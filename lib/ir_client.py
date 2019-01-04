import time
import pigpio

class IRClient:
    @classmethod
    def carrier(cls, gpio, frequency, micros):
        """
        Generate carrier square wave.
        """
        wf = []
        cycle = 1000.0 / frequency
        cycles = int(round(micros / cycle))
        on = int(round(cycle / 2.0))
        sofar = 0
        for c in range(cycles):
            target = int(round((c + 1) * cycle))
            sofar += on
            off = target - sofar
            sofar += off
            wf.append(pigpio.pulse(1 << gpio, 0, on))
            wf.append(pigpio.pulse(0, 1 << gpio, off))
        return wf

    @classmethod
    def send(cls, code, pin, freq):
        pi = pigpio.pi() # Connect to Pi.
        pi.set_mode(pin, pigpio.OUTPUT) # IR TX connected to this GPIO.
        pi.wave_add_new()

        marks_wid = {}
        spaces_wid = {}

        wave = [0] * len(code)

        for i in range(0, len(code)):
            ci = code[i]
            if i & 1: # Space
                if ci not in spaces_wid:
                    pi.wave_add_generic([pigpio.pulse(0, 0, ci)])
                    spaces_wid[ci] = pi.wave_create()
                wave[i] = spaces_wid[ci]
            else: # Mark
                if ci not in marks_wid:
                    wf = cls.carrier(pin, freq, ci)
                    pi.wave_add_generic(wf)
                    marks_wid[ci] = pi.wave_create()
                wave[i] = marks_wid[ci]

        pi.wave_chain(wave)

        while pi.wave_tx_busy():
            time.sleep(0.002)

        for i in marks_wid:
            pi.wave_delete(marks_wid[i])

        for i in spaces_wid:
            pi.wave_delete(spaces_wid[i])

        pi.stop() # Disconnect from Pi.
