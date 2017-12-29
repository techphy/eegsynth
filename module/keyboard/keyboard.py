#!/usr/bin/env python

# Keyboard outputs MIDI for the purpose of playing a MIDI keyboard
#
# Keyboard is part of the EEGsynth project (https://github.com/eegsynth/eegsynth)
#
# Copyright (C) 2017 EEGsynth project
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import ConfigParser # this is version 2.x specific, on version 3.x it is called 'configparser' and has a different API
import argparse
import mido
import os
import redis
import sys
import threading
import time

if hasattr(sys, 'frozen'):
    basis = sys.executable
elif sys.argv[0]!='':
    basis = sys.argv[0]
else:
    basis = './'
installed_folder = os.path.split(basis)[0]

# eegsynth/lib contains shared modules
sys.path.insert(0,os.path.join(installed_folder,'../../lib'))
import EEGsynth

# the list of MIDI commands is specific to the implementation for a full-scale keyboard
# see https://newt.phys.unsw.edu.au/jw/notes.html
note_name = ['C0', 'Db0', 'D0', 'Eb0', 'E0', 'F0', 'Gb0', 'G0', 'Ab0', 'A0', 'Bb0', 'B0', 'C1', 'Db1', 'D1', 'Eb1', 'E1', 'F1', 'Gb1', 'G1', 'Ab1', 'A1', 'Bb1', 'B1', 'C2', 'Db2', 'D2', 'Eb2', 'E2', 'F2', 'Gb2', 'G2', 'Ab2', 'A2', 'Bb2', 'B2', 'C3', 'Db3', 'D3', 'Eb3', 'E3', 'F3', 'Gb3', 'G3', 'Ab3', 'A3', 'Bb3', 'B3', 'C4', 'Db4', 'D4', 'Eb4', 'E4', 'F4', 'Gb4', 'G4', 'Ab4', 'A4', 'Bb4', 'B4', 'C5', 'Db5', 'D5', 'Eb5', 'E5', 'F5', 'Gb5', 'G5', 'Ab5', 'A5', 'Bb5', 'B5', 'C6', 'Db6', 'D6', 'Eb6', 'E6', 'F6', 'Gb6', 'G6', 'Ab6', 'A6', 'Bb6', 'B6', 'C7', 'Db7', 'D7', 'Eb7', 'E7', 'F7', 'Gb7', 'G7', 'Ab7', 'A7', 'Bb7', 'B7', 'C8', 'Db8', 'D8', 'Eb8', 'E8', 'F8', 'Gb8', 'G8', 'Ab8', 'A8', 'Bb8', 'B8', 'C9', 'Db9', 'D9', 'Eb9', 'E9', 'F9', 'Gb9', 'G9', 'Ab9', 'A9', 'Bb9', 'B9', 'C10', 'Db10', 'D10', 'Eb10', 'E10', 'F10', 'Gb10', 'G10', 'Ab10', 'A10', 'Bb10', 'B10']
note_code = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143]

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--inifile", default=os.path.join(installed_folder, os.path.splitext(os.path.basename(__file__))[0] + '.ini'), help="optional name of the configuration file")
args = parser.parse_args()

config = ConfigParser.ConfigParser()
config.read(args.inifile)

try:
    r = redis.StrictRedis(host=config.get('redis','hostname'), port=config.getint('redis','port'), db=0)
    response = r.client_list()
except redis.ConnectionError:
    print 'Error: cannot connect to redis server'
    exit()

# combine the patching from the configuration file and Redis
patch = EEGsynth.patch(config, r)
# del config

# this determines how much debugging information gets printed
debug = patch.getint('general','debug')

# this is only for debugging
print('------ INPUT ------')
for port in mido.get_input_names():
  print(port)
print('------ OUTPUT ------')
for port in mido.get_output_names():
  print(port)
print('-------------------------')

mididevice = patch.getstring('midi', 'device')
try:
    inputport  = mido.open_input(mididevice)
    if debug>0:
        print "Connected to MIDI input"
except:
    print "Error: cannot connect to MIDI input"
    exit()

try:
    outputport  = mido.open_output(mididevice)
    if debug>0:
        print "Connected to MIDI output"
except:
    print "Error: cannot connect to MIDI output"
    exit()

try:
    # channel 1-16 in the ini file should be mapped to 0-15
    midichannel = patch.getint('midi', 'channel')-1
except:
    # this happens if it is not specified in the ini file
    # it will be determined on the basis of the first incoming message
    midichannel = None

# the input scale and offset are used to map Redis values to MIDI values
input_scale  = patch.getfloat('input', 'scale', default=127)
input_offset = patch.getfloat('input', 'offset', default=0)
# the output scale and offset are used to map MIDI values to Redis values
output_scale  = patch.getfloat('output', 'scale', default=0.00787401574803149606)
output_offset = patch.getfloat('output', 'offset', default=0)

# this is to prevent two messages from being sent at the same time
lock = threading.Lock()

class TriggerThread(threading.Thread):
    def __init__(self, redischannel, note):
        threading.Thread.__init__(self)
        self.redischannel = redischannel
        self.note = note
        self.running = True
    def stop(self):
        self.running = False
    def run(self):
        pubsub = r.pubsub()
        pubsub.subscribe('KEYBOARD_UNBLOCK')  # this message unblocks the redis listen command
        pubsub.subscribe(self.redischannel)   # this message contains the note
        while self.running:
            for item in pubsub.listen():
                if not self.running or not item['type'] == 'message':
                    break
                if item['channel']==self.redischannel:
                    # map the Redis values to MIDI values
                    val = EEGsynth.rescale(item['data'], slope=input_scale, offset=input_offset)
                    val = EEGsynth.limit(val, 0, 127)
                    val = int(val)
                    if debug>1:
                        print item['channel'], '=', val
                    if midichannel is None:
                        msg = mido.Message('note_on', note=self.note, velocity=val)
                    else:
                        msg = mido.Message('note_on', note=self.note, velocity=val, channel=midichannel)
                    lock.acquire()
                    outputport.send(msg)
                    lock.release()

# each of the notes that can be played is mapped onto a different trigger
trigger = []
for name, code in zip(note_name, note_code):
    if config.has_option('input', name):
        # start the background thread that deals with this note
        this = TriggerThread(patch.getstring('input', name), code)
        trigger.append(this)
        if debug>1:
            print name, 'OK'

# start the thread for each of the notes
for thread in trigger:
    thread.start()

try:
    while True:
        time.sleep(patch.getfloat('general','delay'))

        for msg in inputport.iter_pending():
            if midichannel is None:
                try:
                    # specify the MIDI channel on the basis of the first incoming message
                    midichannel = int(msg.channel)
                except:
                    pass

            if debug>0 and msg.type!='clock':
                print msg

            if hasattr(msg,'note'):
                print(msg)
                if patch.getstring('processing','detect')=='release' and msg.velocity>0:
                    pass
                elif patch.getstring('processing','detect')=='press' and msg.velocity==0:
                    pass
                else:
                    # prefix.note=note
                    key = '{}.note'.format(patch.getstring('output','prefix'))
                    val = msg.note
                    r.set(key, val)         # send it as control value
                    r.publish(key, val)     # send it as trigger
                    # prefix.noteXXX=velocity
                    key = '{}.note{:0>3d}'.format(patch.getstring('output','prefix'), msg.note)
                    val = msg.velocity
                    # map the MIDI values to Redis values
                    val = EEGsynth.rescale(val, slope=output_scale, offset=output_offset)
                    r.set(key, val)         # send it as control value
                    r.publish(key, val)     # send it as trigger
            elif hasattr(msg,'control'):
                # ignore these
                pass
            elif hasattr(msg,'time'):
                # ignore these
                pass

except KeyboardInterrupt:
    print 'Closing threads'
    for thread in trigger:
        thread.stop()
    r.publish('KEYBOARD_UNBLOCK', 1)
    for thread in trigger:
        thread.join()
    sys.exit()
