import sys
import argparse
from lib.ir_converter import IRConverter

def datum(bits):
    res = 0
    for b in reversed(bits):
        res = (res << 1) | b
    return res

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

parser = argparse.ArgumentParser()
parser.add_argument('-t', '--periodic_time', type=float, required=True)
parser.add_argument('-v', '--verbose', action='store_true')

args = parser.parse_args()

code = [int(s) for s in sys.stdin.read().split()]
irc = IRConverter(leader_pulse=[8, 4], space_pulse=[1, 1], mark_pulse=[1, 3])
frames = irc.decode_frames(code, args.periodic_time)

for i, frame in enumerate(frames):
    if args.verbose:
        print(f"Frame {i}")
        print(f"Customer Code: {'{:016b}'.format(datum(frame[0:16]))}")
        print(f"Parity: {'{:04b}'.format(datum(frame[16:20]))}")
        print(f"Data00: {'{:04b}'.format(datum(frame[20:24]))}")
        for i in range(int((len(frame) - 24) / 8)):
            print(f"Data{'{:02}'.format(i + 1)}: {'{:08b}'.format(datum(frame[24+i*8:24+i*8+8]))}")
    else:
        header = [datum(d) for d in [frame[0:8], frame[8:16], frame[16:20], frame[20:24]]]
        body = [datum(d) for d in chunks(frame[24:], 8)]
        print(*(header + body), sep=' ')
