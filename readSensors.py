#!/usr/bin/python

import datetime
import time
import decimal
import grovepi
import math
import numbers
import logging

from grovepi import *
from grove_rgb_lcd import *
# from enum import Enum

import numpy as np # in case of error, run: 'apt-get install python-numpy' or 'pip install numpy'

class PortTypes: #(Enum):
	Sound = 0
	Light = 1
	TemperatureHumidity = 2
	Led = 3
	Lcd = 4
	
class MeasureTypes:# (Enum):
	Sound = 0
	Light = 1
	Temperature = 2
	Humidity = 3	

class SensorReadings:

	def __init__(self, readings, precision, shortName, longName, valueType):
		self.values = []
		self.counts = 0
		self.readings = readings
		self.precision = precision
		self.value = -1
		self.shortName = shortName
		self.longName = longName
		self.valueType = valueType
		self.consecutiveFails = 0

	def getValue(self):
		return self.value

	def hasValue(self):
		return self.value != -1

	def reject_outliers(self, data, m = 2.):
		if len(data) < 5:
			return data
		data = np.array(data)
		ret = data[abs(data - np.mean(data)) <= m * np.std(data)]
		if len(data) != len(ret):
			logging.debug("Removed outliers; from %s to %s", data, ret)
		return ret
	
	def computeValue(self):
		if (self.counts < self.readings):
			return
		self.value = np.round(np.average(self.reject_outliers(self.values)) / self.precision) * self.precision

	def addMeasure(self, measure):
		if not isinstance(measure, numbers.Number) or math.isnan(measure):
			self.consecutiveFails += 1
			# failures are quite common. Only report if 2x in a row or more
			if self.consecutiveFails > 1:
				logging.warning("Unable to read %s value #%d: %s.", self.longName, self.consecutiveFail, measure)
			return

		self.consecutiveFails = 0
		if (self.counts < self.readings):
			self.values.append(measure)
		else:
			self.values[self.counts % self.readings] = measure
		self.counts += 1


# Configuration start

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(asctime)s:%(message)s')

isPro = 0 # Set to 1 is it's a GrovePi Pro DHT; 0 otherwise

ports = { # comment out lines below if there's no associated device/sensor
#	PortTypes.Sound: 0, # A port number
	PortTypes.Light: 1, # A port number 
	PortTypes.TemperatureHumidity: 2, # D port number
	PortTypes.Led: 4, # D port number. If present, we turn on the led
	PortTypes.Lcd: 1, # I2C port numner. If present, we print out values on LCD
}

# Params:
# 1- number of readings to take before aggregating to compensate for fluctuations
# 2- precision
# 3, 4- short and long name
# 5- valueType

measures = {
	MeasureTypes.Temperature: SensorReadings(60, 1, "Tmp", "Temperature", "C"),
	MeasureTypes.Humidity: SensorReadings(60, 1, "Hum", "Humidity", "%"),
	MeasureTypes.Sound: SensorReadings(3, 100, "Snd", "Sound", ""),
	MeasureTypes.Light: SensorReadings(3, 100.0, "Lht", "Light", ""),
} 

tooLow = 16.0           # Too low temp
justRight = 20.0        # OK temp
tooHigh = 23.0          # Too high temp

# Configuration end


def updateLed(value):
	if (ports.has_key(PortTypes.Led)):
		grovepi.analogWrite(led, ports[PortTypes.Led])


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

def getAnalog(measureType, portNumber):
	ret = grovepi.analogRead(portNumber)
	measures[measureType].addMeasure(ret)

def getTemperatureHumidity(portNumber):
	[temperature,humidity] = [0,0]
	[temperature,humidity] = grovepi.dht(portNumber, isPro)
	measures[MeasureTypes.Temperature].addMeasure(temperature)
	measures[MeasureTypes.Humidity].addMeasure(humidity)

def setLcd(text, rgb):
	if not ports.has_key(PortTypes.Lcd):
		return
	setRGB(rgb[0], rgb[1], rgb[2])
	setText(text)

out_str = ""
out_lcd = ""

logging.info("Starting sensor readings. Some readings may take a while to register ...")

while True:

	try:
		time.sleep(1)

		for portType, portNumber in ports.items():
			if (portType == PortTypes.Sound):
				getAnalog(MeasureTypes.Sound, portNumber)
			elif (portType == PortTypes.Light):
				getAnalog(MeasureTypes.Light, portNumber)
			elif portType == PortTypes.TemperatureHumidity:
				getTemperatureHumidity(portNumber)

		new_out_str = ""
		new_out_lcd = ""
	
		for measureType, readings in measures.items():
			oldValue = readings.getValue()
			readings.computeValue()
			if readings.hasValue():
				newValue = readings.getValue()
				if (oldValue != newValue):
					logging.debug("Value for %s changed from %d to %d: %s.", readings.longName, oldValue, newValue, readings.reject_outliers(readings.values))
				new_out_str = "%s: %d%s %s" % (readings.longName, newValue, readings.valueType, new_out_str)
				new_out_lcd = "%s:%d%s %s" % (readings.shortName, newValue, readings.valueType, new_out_lcd)
	
		if measures[MeasureTypes.Light].hasValue():
			updateLed(measures[MeasureTypes.Light].getValue() / 4)

		if new_out_str != out_str:
			out_str = new_out_str
			logging.info(out_str)

		if ports.has_key(PortTypes.Lcd) and new_out_lcd != out_lcd:
			out_lcd = new_out_lcd
			rgb = (0,0,0)
			if measures[MeasureTypes.Temperature].hasValue():
		                rgb = calcBG(measures[MeasureTypes.Temperature].getValue())
			setLcd(out_lcd, rgb)
	except IOError:
		logging.error("IO Error")
	except KeyboardInterrupt:
		logging.critical("EXITING")
		setLcd(" " * 32, (0,0,0))
		updateLed(0)
		exit()
	except Exception as e:
		logging.exception("Error: %s", e)

