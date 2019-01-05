#!/usr/bin/env python

# irrp.py
# IR Record and Playback
# 2015-12-21
# Public Domain

# irrpcli.py
# 2019-01-02
# Modified by Paralleltree

"""
A utility to record and then playback IR remote control codes.

To record use

./irrpcli.py -r -g4

where

-r record
-g the GPIO connected to the IR receiver

To playback use

cat pulse | ./irrp.py -p -g17

where

-p playback
-g the GPIO connected to the IR transmitter

OPTIONS

-r record
-p playback
-g GPIO (receiver for record, transmitter for playback)

RECORD

--glitch     ignore edges shorter than glitch microseconds, default 100 us
--post       expect post milliseconds of silence after code, default 15 ms
--pre        expect pre milliseconds of silence before code, default 200 ms
--short      reject codes with less than short pulses, default 10
--tolerance  consider pulses the same if within tolerance percent, default 15
--no-confirm don't require a code to be repeated during record

TRANSMIT

--freq       IR carrier frequency, default 38 kHz
--gap        gap in milliseconds between transmitted codes, default 100 ms
"""

import os
import sys
import time
import argparse

import pigpio # http://abyz.co.uk/rpi/pigpio/python.html
from lib.ir_client import IRClient

p = argparse.ArgumentParser()

g = p.add_mutually_exclusive_group(required=True)
g.add_argument("-p", "--play",   help="play keys",   action="store_true")
g.add_argument("-r", "--record", help="record keys", action="store_true")

p.add_argument("-g", "--gpio", help="GPIO for RX/TX", required=True, type=int)

p.add_argument("--freq",      help="frequency kHz",   type=float, default=38.0)

p.add_argument("--gap",       help="key gap ms",        type=int, default=100)
p.add_argument("--glitch",    help="glitch us",         type=int, default=100)
p.add_argument("--post",      help="postamble ms",      type=int, default=15)
p.add_argument("--pre",       help="preamble ms",       type=int, default=200)
p.add_argument("--short",     help="short code length", type=int, default=10)
p.add_argument("--tolerance", help="tolerance percent", type=int, default=15)

p.add_argument("-v", "--verbose", help="Be verbose",     action="store_true")
p.add_argument("--no-confirm", help="No confirm needed", action="store_true")

args = p.parse_args()

GPIO       = args.gpio
GLITCH     = args.glitch
PRE_MS     = args.pre
POST_MS    = args.post
FREQ       = args.freq
VERBOSE    = args.verbose
SHORT      = args.short
GAP_MS     = args.gap
NO_CONFIRM = args.no_confirm
TOLERANCE  = args.tolerance

POST_US    = POST_MS * 1000
PRE_US     = PRE_MS  * 1000
GAP_S      = GAP_MS  / 1000.0
CONFIRM    = not NO_CONFIRM
TOLER_MIN =  (100 - TOLERANCE) / 100.0
TOLER_MAX =  (100 + TOLERANCE) / 100.0

last_tick = 0
in_code = False
code = []
fetching_code = False

def normalise(c):
   """
   Typically a code will be made up of two or three distinct
   marks (carrier) and spaces (no carrier) of different lengths.

   Because of transmission and reception errors those pulses
   which should all be x micros long will have a variance around x.

   This function identifies the distinct pulses and takes the
   average of the lengths making up each distinct pulse.  Marks
   and spaces are processed separately.

   This makes the eventual generation of waves much more efficient.

   Input

     M    S   M   S   M   S   M    S   M    S   M
   9000 4500 600 540 620 560 590 1660 620 1690 615

   Distinct marks

   9000                average 9000
   600 620 590 620 615 average  609

   Distinct spaces

   4500                average 4500
   540 560             average  550
   1660 1690           average 1675

   Output

     M    S   M   S   M   S   M    S   M    S   M
   9000 4500 609 550 609 550 609 1675 609 1675 609
   """
   if VERBOSE:
      print("before normalise", c)
   entries = len(c)
   p = [0]*entries # Set all entries not processed.
   for i in range(entries):
      if not p[i]: # Not processed?
         v = c[i]
         tot = v
         similar = 1.0

         # Find all pulses with similar lengths to the start pulse.
         for j in range(i+2, entries, 2):
            if not p[j]: # Unprocessed.
               if (c[j]*TOLER_MIN) < v < (c[j]*TOLER_MAX): # Similar.
                  tot = tot + c[j]
                  similar += 1.0

         # Calculate the average pulse length.
         newv = round(tot / similar, 2)
         c[i] = newv

         # Set all similar pulses to the average value.
         for j in range(i+2, entries, 2):
            if not p[j]: # Unprocessed.
               if (c[j]*TOLER_MIN) < v < (c[j]*TOLER_MAX): # Similar.
                  c[j] = newv
                  p[j] = 1

   if VERBOSE:
      print("after normalise", c)

def compare(p1, p2):
   """
   Check that both recodings correspond in pulse length to within
   TOLERANCE%.  If they do average the two recordings pulse lengths.

   Input

        M    S   M   S   M   S   M    S   M    S   M
   1: 9000 4500 600 560 600 560 600 1700 600 1700 600
   2: 9020 4570 590 550 590 550 590 1640 590 1640 590

   Output

   A: 9010 4535 595 555 595 555 595 1670 595 1670 595
   """
   if len(p1) != len(p2):
      return False

   for i in range(len(p1)):
      v = p1[i] / p2[i]
      if (v < TOLER_MIN) or (v > TOLER_MAX):
         return False

   for i in range(len(p1)):
       p1[i] = int(round((p1[i]+p2[i])/2.0))

   if VERBOSE:
      print("after compare", p1)

   return True

def tidy_mark_space(record, base):

   ms = {}

   # Find all the unique marks (base=0) or spaces (base=1)
   # and count the number of times they appear,

   for i in range(base, len(record), 2):
      if record[i] in ms:
         ms[record[i]] += 1
      else:
         ms[record[i]] = 1

   if VERBOSE:
      print("t_m_s A", ms)

   v = None

   for plen in sorted(ms):

      # Now go through in order, shortest first, and collapse
      # pulses which are the same within a tolerance to the
      # same value.  The value is the weighted average of the
      # occurences.
      #
      # E.g. 500x20 550x30 600x30  1000x10 1100x10  1700x5 1750x5
      #
      # becomes 556(x80) 1050(x20) 1725(x10)
      #
      if v == None:
         e = [plen]
         v = plen
         tot = plen * ms[plen]
         similar = ms[plen]

      elif plen < (v*TOLER_MAX):
         e.append(plen)
         tot += (plen * ms[plen])
         similar += ms[plen]

      else:
         v = int(round(tot/float(similar)))
         # set all previous to v
         for i in e:
            ms[i] = v
         e = [plen]
         v = plen
         tot = plen * ms[plen]
         similar = ms[plen]

   v = int(round(tot/float(similar)))
   # set all previous to v
   for i in e:
      ms[i] = v

   if VERBOSE:
      print("t_m_s B", ms)

   for i in range(base, len(record), 2):
      record[i] = ms[record[i]]

def tidy(record):

   tidy_mark_space(record, 0) # Marks.

   tidy_mark_space(record, 1) # Spaces.

def end_of_code():
   global code, fetching_code
   if len(code) > SHORT:
      normalise(code)
      fetching_code = False
   else:
      code = []
      print("Short code, probably a repeat, try again")

def cbf(gpio, level, tick):

   global last_tick, in_code, code, fetching_code

   if level != pigpio.TIMEOUT:

      edge = pigpio.tickDiff(last_tick, tick)
      last_tick = tick

      if fetching_code:

         if (edge > PRE_US) and (not in_code): # Start of a code.
            in_code = True
            pi.set_watchdog(GPIO, POST_MS) # Start watchdog.

         elif (edge > POST_US) and in_code: # End of a code.
            in_code = False
            pi.set_watchdog(GPIO, 0) # Cancel watchdog.
            end_of_code()

         elif in_code:
            code.append(edge)

   else:
      pi.set_watchdog(GPIO, 0) # Cancel watchdog.
      if in_code:
         in_code = False
         end_of_code()

pi = pigpio.pi() # Connect to Pi.

if not pi.connected:
   exit(0)

if args.record: # Record.

   record = []

   pi.set_mode(GPIO, pigpio.INPUT) # IR RX connected to this GPIO.

   pi.set_glitch_filter(GPIO, GLITCH) # Ignore glitches.

   cb = pi.callback(GPIO, pigpio.EITHER_EDGE, cbf)

   sys.stderr.write('Recording\n')
   sys.stderr.write('Press key for record\n')
   sys.stderr.flush()
   code = [] # global
   fetching_code = True
   while fetching_code:
      time.sleep(0.1)
   sys.stderr.write('Okay\n')
   time.sleep(0.5)

   if CONFIRM:
      press_1 = code[:]
      done = False

      tries = 0
      while not done:
         sys.stderr.write('Press key to confirm\n')
         code = []
         fetching_code = True
         while fetching_code:
            time.sleep(0.1)
         press_2 = code[:]
         the_same = compare(press_1, press_2)
         if the_same:
            done = True
            record = press_1[:]
            sys.stderr.write('Okay\n')
            time.sleep(0.5)
         else:
            tries += 1
            if tries <= 3:
               sys.stderr.write('No match\n')
            else:
               sys.stderr.write('Giving up recording\n')
               done = True
            time.sleep(0.5)
   else: # No confirm.
      record = code[:]

   pi.set_glitch_filter(GPIO, 0) # Cancel glitch filter.
   pi.set_watchdog(GPIO, 0) # Cancel watchdog.

   tidy(record)

   print(*record, sep=' ')

else: # Playback.

   codes = [[int(s) for s in l.split()] for l in sys.stdin.read().splitlines()]

   if VERBOSE:
      print("Playing")

   emit_time = time.time()

   for code in codes:
      emit_time = time.time()

      IRClient.send(code, GPIO, FREQ)

      delay = emit_time - time.time()

      if delay > 0.0:
         time.sleep(delay)

      emit_time = time.time() + GAP_S

pi.stop() # Disconnect from Pi.
