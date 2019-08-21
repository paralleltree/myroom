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

        if not pi.connected:
            raise RuntimeError('cannot connect to gpio')

        try:
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

            wave = cls.compress_wave(wave)
            pi.wave_chain(wave)

            while pi.wave_tx_busy():
                time.sleep(0.002)

            for i in marks_wid:
                pi.wave_delete(marks_wid[i])

            for i in spaces_wid:
                pi.wave_delete(spaces_wid[i])

        finally:
            pi.stop() # Disconnect from Pi.

    @classmethod
    def compress_wave(cls, code):
        import collections
        MAX_ENTRY = 600
        MAX_LOOP = 20
        if len(code) < MAX_ENTRY:
            return code

        def ngram(l, n):
            return list(zip(*(l[i:] for i in range(n))))

        # (start, size) => count(continuous)
        dic = {}
        for size in range(2, 8):
            # order by descending
            freqs = collections.Counter(ngram(code, size)).most_common()
            for block, count in freqs:
                if count < 2:
                    break
                block = list(block)
                for i in range(len(code) - size + 1):
                    if code[i:i+size] != block:
                        continue
                    # count continuous blocks
                    for c in range(2, count + 1):
                        if code[i+size*(c-1):i+size*c] == block:
                            dic[(i, size)] = c
                        else:
                            break

        # select compressable blocks
        blocks = [(start, size, count) for (start, size), count in dic.items() if count > 1 and size * count > 6]

        if len(blocks) == 0:
            return code

        # order by efficiency
        blocks = sorted(blocks, key=lambda b: b[1] * b[2], reverse=True)
        # excluding overlaps
        cands = [0]
        for i in range(1, len(blocks)):
            if len(cands) >= MAX_LOOP:
                break
            astart, asize, acount = blocks[i]
            aend = astart + asize * acount - 1
            valid = True
            for j in cands:
                bstart, bsize, bcount = blocks[j]
                bend = bstart + bsize * bcount - 1
                if astart <= bend and aend >= bstart:
                    valid = False
                    break
            if valid:
                cands.append(i)

        # order by starting index
        for start, size, count in sorted([blocks[i] for i in cands], key=lambda b: b[0], reverse=True):
            div, mod = count // 256, count % 256
            code[start:start+size*count] = [255, 0] + code[start:start+size] + [255, 1, mod, div]

        return code
