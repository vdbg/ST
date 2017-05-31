#!/usr/bin/python

import time
import decimal
import grovepi
import math
import numbers

from grovepi import *
from grove_rgb_lcd import *
# from enum import Enum

import numpy as np

class PortTypes: #(Enum):
	Sound = 0
	Light = 1
	TemperatureHumidity = 2
	Led = 3
	
class MeasureTypes:# (Enum):
	Sound = 0
	Light = 1
	Temperature = 2
	Humidity = 3	

# Configuration start

readings = 11 # Must be an odd number. Since readings fluctuate a lot, we need to take the median


ports = { # comment out lines below if there's no associated device/sensor
#	PortTypes.Sound: 0, # A port number
	PortTypes.Light: 1, # A port number 
	PortTypes.TemperatureHumidity: 2, # D port number
	PortTypes.Led: 4, # D port number. If present, we turn on the led
}

tooLow = 16.0           # Too low temp
justRight = 20.0        # OK temp
tooHigh = 23.0          # Too high temp

# Configuration end

values = {}
counts = {}
medians = {}

def updateLed(value):
	if (ports.has_key(PortTypes.Led)):
		grovepi.analogWrite(led,ports[PortTypes.Led])

def calcColorAdj(variance):   # Calc the adjustment value of the background color
    "Because there is 6 degrees mapping to 255 values, 42.5 is the factor for 12 degree spread"
    factor = 42.5
    adj = abs(int(factor * variance))
    if adj > 255:
        adj = 255
    return adj


def calcBG(ftemp):
    "This calculates the color value for the background"
    variance = ftemp - justRight   # Calculate the variance
    adj = calcColorAdj(variance)   # Scale it to 8 bit int
    bgList = [0,0,0]               # initialize the color array
    if(variance < 0):
        bgR = 0                    # too cold, no red
        bgB = adj                  # green and blue slide equally with adj
        bgG = 255 - adj

    elif(variance == 0):             # perfect, all on green
        bgR = 0
        bgB = 0
        bgG = 255

    elif(variance > 0):             #too hot - no blue
        bgB = 0
        bgR = adj                  # Red and Green slide equally with Adj
        bgG = 255 - adj

    bgList = [bgR,bgG,bgB]          #build list of color values to return
    return bgList

if (ports.has_key(PortTypes.Led)):
	led = ports[PortTypes.Led]
	grovepi.pinMode(led,"OUTPUT")
	grovepi.analogWrite(led, 255)  # turn led to max to show readiness

def addMeasure(measureType, measure, factor):
	if not isinstance(measure, numbers.Number) or math.isnan(measure):
		print("ERROR: unable to read {} value.".format(measureType))
		return

	if not values.has_key(measureType):
		values[measureType] = np.zeros(readings)
		counts[measureType] = 0

#	print("UPDATING ", measureType, " to value ", measure)
	
	values[measureType][counts[measureType] % readings] = measure / factor
	counts[measureType] += 1

def getAnalog(measureType, portNumber, factor):
	ret = grovepi.analogRead(portNumber)
	addMeasure(measureType, ret, factor)

def getTemperatureHumidity(portNumber):
	[temperature,humidity] = [0,0]
	[temperature,humidity] = grovepi.dht(portNumber, 0)
	addMeasure(MeasureTypes.Temperature, temperature, 1)
	addMeasure(MeasureTypes.Humidity, humidity, 1)

while True:

	try:
		time.sleep(1)

		for portType, portNumber in ports.items():
			if (portType == PortTypes.Sound):
				getAnalog(MeasureTypes.Sound, portNumber, 10)
			elif (portType == PortTypes.Light):
				getAnalog(MeasureTypes.Light, portNumber, 10)
			elif portType == PortTypes.TemperatureHumidity:
				getTemperatureHumidity(portNumber)
	
		for measureType, measures in values.items():
			print("VALUES for %d are %s" %(measureType, measures))
			if counts[measureType] < readings:
				continue # Not enough values yet
			oldMedian = -1
			if (medians.has_key(measureType)):
				oldMedian = medians[measureType]
			newMedian = np.median(measures)
			if (oldMedian != newMedian):
				print("Median for %d changed from %d to %d." % (measureType, oldMedian, newMedian))
			medians[measureType] = newMedian


#	updateLed(light * 2)

#	if (humidity != lastHum) or (temperature != lastTemp) or (sound != lastSound) or (light != lastLight):
#        	out_str ="Temperature:%d C; Humidity:%d %%; Light:%d; Sound:%d" %(temperature,humidity,light,sound)
#	        print (out_str)

#                bgList = calcBG(temperature)           # Calculate background colors

#                setRGB(bgList[0],bgList[1],bgList[2])   # parse our list into the color settings

#        	out_str ="Tmp:%d Hum:%d\nLght:%d Snd:%d" %(temperature,humidity,light,sound)
#		setText(out_str)

	except IOError:
		print("IO Error")
	except KeyboardInterrupt:
		print("EXITNG")
		setRGB(0,0,0)  
		updateLed(0)
		exit()
	except Exception as e:
		print("Error: {}".format(e))

