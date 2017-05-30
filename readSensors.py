import time
import decimal
import grovepi
import math

from grovepi import *
from grove_rgb_lcd import *

sound_sensor = 0        # port A0
light_sensor = 1        # port A1
temperature_sensor = 2  # port D2
led = 4                 # port D3

lastTemp = 0.1          # initialize a floating point temp variable
lastHum = 0.1           # initialize a floating Point humidity variable
lastLight = 0.1
lastSound = 0.1

tooLow = 16.0           # Too low temp
justRight = 20.0        # OK temp
tooHigh = 23.0          # Too high temp

grovepi.pinMode(led,"OUTPUT")
grovepi.analogWrite(led,255)  #turn led to max to show readiness

def calcColorAdj(variance):     # Calc the adjustment value of the background color
    "Because there is 6 degrees mapping to 255 values, 42.5 is the factor for 12 degree spread"
    factor = 42.5;
    adj = abs(int(factor * variance));
    if adj > 255:
        adj = 255;
    return adj;


def calcBG(ftemp):
    "This calculates the color value for the background"
    variance = ftemp - justRight;   # Calculate the variance
    adj = calcColorAdj(variance);   # Scale it to 8 bit int
    bgList = [0,0,0]               # initialize the color array
    if(variance < 0):
        bgR = 0;                    # too cold, no red
        bgB = adj;                  # green and blue slide equally with adj
        bgG = 255 - adj;

    elif(variance == 0):             # perfect, all on green
        bgR = 0;
        bgB = 0;
        bgG = 255;

    elif(variance > 0):             #too hot - no blue
        bgB = 0;
        bgR = adj;                  # Red and Green slide equally with Adj
        bgG = 255 - adj;

    bgList = [bgR,bgG,bgB]          #build list of color values to return
    return bgList;

while True:

    # Error handling in case of problems communicating with the GrovePi
    try:
    	time.sleep(1)

        light = grovepi.analogRead(light_sensor) / 10
        sound = grovepi.analogRead(sound_sensor)
        [t,h]=[0,0]
        [t,h] = grovepi.dht(temperature_sensor,0)

        grovepi.analogWrite(led,light*2)

	if (h != lastHum) or (t != lastTemp) or (sound != lastSound) or (light != lastLight):
        	out_str ="Temperature:%d C; Humidity:%d %%; Light:%d; Sound:%d" %(t,h,light,sound)
	        print (out_str)

                bgList = calcBG(t)           # Calculate background colors

                setRGB(bgList[0],bgList[1],bgList[2])   # parse our list into the color settings

        	out_str ="Tmp:%d Hum:%d\nLght:%d Snd:%d" %(t,h,light,sound)
		setText(out_str)
	lastHum = h
	lastTemp = t
	lastSound = sound
	lastLight = light

    except IOError:
        print("IO Error")
    except KeyboardInterrupt:
	print("EXITNG")
        setRGB(0,0,0)  
        grovepi.analogWrite(led,0)
        exit()
    except Exception as e:
        print("Error: {}".format(e))

