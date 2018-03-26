# last edit date: 2016/09/24
# author: Forec
# LICENSE
# Copyright (c) 2015-2017, Forec <forec@bupt.edu.cn>

# Permission to use, copy, modify, and/or distribute this code for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.

# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from socket import * # socket interface: https://docs.python.org/3.6/library/socket.html
import threading # threading of client and server connections: https://docs.python.org/3/library/threading.html
import pyaudio # play and record audio: http://people.csail.mit.edu/hubert/pyaudio/docs/
import wave # interface with WAV audio format: https://docs.python.org/3.6/library/wave.html
import sys # interact with interpreter: https://docs.python.org/3.6/library/sys.html
import zlib # data compression and decompression: https://docs.python.org/3.6/library/zlib.html
import struct # conversion between python and C stuctures: https://docs.python.org/3.6/library/struct.html
import pickle # converts objects to bytes and vice versa: https://docs.python.org/3/library/pickle.html
import time # used for waiting: https://docs.python.org/3.6/library/time.html
import numpy as np
import argparse

CHUNK = 1024 # byte size
FORMAT = pyaudio.paInt16 #16 bit value
CHANNELS = 1 # single channel
RATE = 48000 #audio digitized at 48 ksps
RECORD_SECONDS = .5 # 500 ms: used to change kbps: <10

class Audio_Server(threading.Thread):
    # on initialization
    def __init__(self, port, version) : 
        threading.Thread.__init__(self) # super init of Thread
        self.setDaemon(True) # sets to be a dameon thread, ends on program close: https://stackoverflow.com/questions/190010/daemon-threads-explanation
        self.ADDR = ('', port) # set ADDR to the port, don't care about own IP
        if version == 4: # IPV4 or IPV6
            self.sock = socket(AF_INET ,SOCK_STREAM) # (family, socket type)
        else:
            self.sock = socket(AF_INET6 ,SOCK_STREAM) # (family, socket type)
        self.p = pyaudio.PyAudio() # instantiate PyAudio
        self.stream = None # set to nothing initially
    # on deletion
    def __del__(self):
        self.sock.close() # close the socket
        if self.stream is not None: # stream set to something
            self.stream.stop_stream() # stop the stream
            self.stream.close() # close the stream
        self.p.terminate() # end the PyAudio
    # thread activity starts
    def run(self):
        print("AUDIO VOIP server started...") # display initial start message
        self.sock.bind(self.ADDR) # binds the socket to the address
        self.sock.listen(1) # accepts only one connection
        conn, addr = self.sock.accept() # waits for the client to connect, returns connection 
        print("remote AUDIO VOIP client success connected...") # once client connected
        data = "".encode("utf-8") # use utf-8 encoding for data: https://en.wikipedia.org/wiki/UTF-8
        payload_size = struct.calcsize("L") # calculate size of unsigned long for size
        # opens the audio stream
        self.stream = self.p.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  output=True,
                                  frames_per_buffer = CHUNK
                                  )
        # receive data, using a simple buffer to handle jitter
        while True: # run forever
            while len(data) < payload_size: # while not overflowing
                data += conn.recv(136) # add received bytes to data, bufsize=81920
            packed_size = data[:payload_size] # get everything before overflow
            data = data[payload_size:] # set to the overflow bytes
            msg_size = struct.unpack("L", packed_size)[0] # first element of unpacked data
            while len(data) < msg_size: # if overflowed data less than size of msg
                data += conn.recv(136) # add received bytes to data, bufsize=81920
            zframe_data = data[:msg_size] # set to everything in overflowed data up to size of msg
            data = data[msg_size:] # set data to overflow of the overflowed data
            print(time.time())
            frame_data=zlib.decompress(zframe_data) # decompress data
            frames = pickle.loads(frame_data) # de-serializing of data
            for frame in frames: # loops through all of the frames
                self.stream.write(frame, CHUNK) # blocks until all frames have been played

class Audio_Client(threading.Thread):
    # on initialization
    def __init__(self ,ip, port, version):
        threading.Thread.__init__(self) # super init of Thread
        self.setDaemon(True) # sets to be a dameon thread, ends on program close
        self.ADDR = (ip, port) # set ADDR to the ip and port
        if version == 4: # IPV4 or IPV6
            self.sock = socket(AF_INET, SOCK_STREAM) # (family, socket type)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM) # (family, socket type)
        self.p = pyaudio.PyAudio() # instantiate PyAudio
        self.stream = None # set to nothing initially
        print("AUDIO VOIP client started...") # display initial start message
    # on deletion
    def __del__(self) :
        self.sock.close() # close the socket
        if self.stream is not None: # stream set to something
            self.stream.stop_stream() # stop the stream
            self.stream.close() # close the stream
        self.p.terminate() # end the PyAudio
    # thread activity starts
    def run(self):
        # continue trying to connect to server
        while True:
            try:
                self.sock.connect(self.ADDR) # attempt to connect
                break # if successful break
            except:
                time.sleep(3) # if not successful try again in 3 secs
                continue
        print("AUDIO VOIP client connected...") # once success connects to server
        # opens the audio stream
        self.stream = self.p.open(format=FORMAT, 
                             channels=CHANNELS,
                             rate=RATE,
                             input=True,
                             frames_per_buffer=CHUNK)
        while self.stream.is_active(): # while the stream is still active
            frames = []
            # between: 5k - 15k
            for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)): #<10 kbps
                data = self.stream.read(CHUNK) # blocks until all frames have been recorded
                frames.append(data) # adds to end of data 
                senddata = pickle.dumps(frames) # serializes frames
                print("normal: " + str(len(senddata)))
                print(time.time())
                zdata = zlib.compress(senddata,zlib.Z_BEST_COMPRESSION) #compress data: 20-50% compression
                print("compressed: " + str(len(zdata)))
            try:
                self.sock.sendall(struct.pack("L", len(zdata)) + zdata) # sends data to server
            except:
                break



parser = argparse.ArgumentParser()
parser.add_argument('--host', type=str, default='127.0.0.1') #repalce with other person's IP
parser.add_argument('--port', type=int, default=10087)
parser.add_argument('--noself', type=bool, default=False)
parser.add_argument('--level', type=int, default=1)
parser.add_argument('-v', '--version', type=int, default=4)

args = parser.parse_args()

IP = args.host # get IP
PORT = args.port # get port
VERSION = args.version
SHOWME = not args.noself
LEVEL = args.level

if __name__ == '__main__':
    aclient = Audio_Client(IP, PORT+1, VERSION) # client
    aserver = Audio_Server(PORT+1, VERSION) # server
    aclient.start() # start client
    aserver.start() # start server
    while True:
        time.sleep(1)
        # is alive tests if thread is connected (still alive)
        if not aserver.isAlive() or not aclient.isAlive(): # either disconnected
            print("Audio connection lost...")
            sys.exit(0)
