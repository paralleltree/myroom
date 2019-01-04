from .utils import flatten

class IRConverter:
    def __init__(self, leader_pulse, space_pulse, mark_pulse):
        self._leader_pulse = leader_pulse
        self._space_pulse = space_pulse
        self._mark_pulse = mark_pulse

    @property
    def leader_pulse(self):
        return self._leader_pulse

    @property
    def space_pulse(self):
        return self._space_pulse

    @property
    def mark_pulse(self):
        return self._mark_pulse

    def pulse(self, bit, T):
        return [T * t for t in (self.mark_pulse if bit else self.space_pulse)]

    def decode_frames(self, pulses, T):
        periods = [int(float(t) / T + 0.5) for t in pulses]
        data = []
        i = 0
        while True:
            # Detect Leader
            while i + 1 < len(periods) and periods[i] != self.leader_pulse[0]:
                i += 2
            if i + 1 >= len(periods):
                break
            # Validate Leader
            if periods[i + 1] != self.leader_pulse[1]:
                i += 2
                next
            i += 2
            # Convert Bit Sequence
            seq = []
            while i + 1 < len(periods):
                if periods[i : i + 2] == self.space_pulse:
                    seq.append(False)
                elif periods[i : i + 2] == self.mark_pulse:
                    seq.append(True)
                else:
                    i += 2
                    break
                i += 2
            data.append(seq)
        return data

    def encode_frame(self, frame, T):
        payload = flatten([self.pulse(b, T) for b in frame])
        return [T * t for t in self.leader_pulse] + payload + [T]
