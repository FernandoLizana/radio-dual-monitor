import pyaudio
import wave
import datetime
from datetime import date
from tkinter import messagebox
import numpy as np
import math
import struct
import time
import os

audio=pyaudio.PyAudio()
Threshold = 20
SHORT_NORMALIZE = (1.0/32768.0)
chunk = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
swidth = 2
TIMEOUT_LENGTH = 5
f_name_directory = os.path.join(os.path.dirname(__file__), "recordings")
stream = audio.open(format=FORMAT,channels=CHANNELS,rate=RATE,input=True,output=True,frames_per_buffer=chunk)

def rms(frame):
    count = len(frame) / swidth
    format = "%dh" % (count)
    shorts = struct.unpack(format, frame)

    sum_squares = 0.0
    for sample in shorts:
        n = sample * SHORT_NORMALIZE
        sum_squares += n * n
    rms = math.pow(sum_squares / count, 0.5)
    return rms * 1000

def record():
    print('Ruido detectado, comenzando a grabar')
    rec = []
    current = time.time()
    end = time.time() + TIMEOUT_LENGTH

    while current <= end:

        data = stream.read(chunk,exception_on_overflow = False)
        if rms(data) >= Threshold: end = time.time() + TIMEOUT_LENGTH

        current = time.time()
        rec.append(data)
    write(rec)

def write(recording):
	stream.stop_stream()
	stream.close()
	audio.terminate()
	nombreArchivo=nombreDinamico()
	waveFile = wave.open(nombreArchivo+".wav", 'wb')
	waveFile.setnchannels(CHANNELS)
	waveFile.setsampwidth(audio.get_sample_size(FORMAT))
	waveFile.setframerate(RATE)
	waveFile.writeframes(b''.join(recording))
	waveFile.close()

	wav = wave.open(nombreArchivo+".wav")
	SepararCanales(nombreArchivo+"channel1.wav", wav, 0)
	SepararCanales(nombreArchivo+"channel2.wav", wav, 1)
	messagebox.showinfo(message="Se ha grabado el Audio", title="Audio")


def listen():
	print ("Esperando a escuchar")
	while True:
		input = stream.read(chunk,exception_on_overflow = False)
		rms_val = rms(input)

		if rms_val > Threshold:
			record()



def nombreDinamico():
	now=datetime.datetime.now()
	return str(now.year)+"-"+str(now.month)+"-"+str(now.day)+"-"+str(now.hour)+"-"+str(now.minute)+"-"+str(now.second)
	
def Audio1Canal():
	FORMAT = pyaudio.paInt16
	CHANNELS = 2
	RATE = 44100
	CHUNK = 1024
	RECORD_SECONDS = 25
	audio = pyaudio.PyAudio()

	# start Recording
	stream = audio.open(format=FORMAT, channels=CHANNELS,
	                    rate=RATE, input=True,
	                    frames_per_buffer=CHUNK)
	print ("recording...")
	frames = []

	for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
	    data = stream.read(CHUNK)
	    frames.append(data)
	print ("finished recording")

	# stop Recording
	stream.stop_stream()
	stream.close()
	audio.terminate()
	nombreArchivo=nombreDinamico()
	waveFile = wave.open(nombreArchivo+".wav", 'wb')
	waveFile.setnchannels(CHANNELS)
	waveFile.setsampwidth(audio.get_sample_size(FORMAT))
	waveFile.setframerate(RATE)
	waveFile.writeframes(b''.join(frames))
	waveFile.close()

	wav = wave.open(nombreArchivo+".wav")
	SepararCanales(nombreArchivo+"channel1.wav", wav, 0)
	SepararCanales(nombreArchivo+"channel2.wav", wav, 1)
	messagebox.showinfo(message="Se ha grabado el Audio", title="Audio")

def SepararCanales(fn, wav, channel):
    '''
    Take Wave_read object as an input and save one of its
    channels into a separate .wav file.
    '''
    # Read data
    nch   = wav.getnchannels()
    depth = wav.getsampwidth()
    wav.setpos(0)
    sdata = wav.readframes(wav.getnframes())

    # Extract channel data (24-bit data not supported)
    typ = { 1: np.uint8, 2: np.uint16, 4: np.uint32 }.get(depth)
    if not typ:
        raise ValueError("sample width {} not supported".format(depth))
    if channel >= nch:
        raise ValueError("cannot extract channel {} out of {}".format(channel+1, nch))
    print ("Extracting channel {} out of {} channels, {}-bit depth".format(channel+1, nch, depth*8))
    data = np.fromstring(sdata, dtype=typ)
    ch_data = data[channel::nch]
    outwav = wave.open(fn, 'w')
    outwav.setparams(wav.getparams())
    outwav.setnchannels(1)
    outwav.writeframes(ch_data.tostring())
    outwav.close()
