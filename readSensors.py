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
	Buzzer = 5
	
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
		self.shortName = shortName
		self.longName = longName
		self.valueType = valueType
		self.consecutiveFails = 0
		self.lastFloatValue = -1
		self.floatValue = -1

	def getValue(self):
		value = self.lastFloatValue
		if self.hasChanges():			
			self.lastFloatValue = self.floatValue
			value = self.floatValue
		return int(np.round(value / self.precision) * self.precision)

	def hasValue(self):
		return self.floatValue != -1

	def hasChanges(self):
		return self.lastFloatValue == -1 or abs(self.lastFloatValue - self.floatValue) > self.precision

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
		noOutliers = self.reject_outliers(self.values)
		self.floatValue = np.average(noOutliers)

	def addMeasure(self, measure):
		if not isinstance(measure, numbers.Number) or math.isnan(measure):
			self.consecutiveFails += 1
			# failures are quite common. Only report if 2x in a row or more
			if self.consecutiveFails > 1:
				logging.warning("Unable to read %s value #%d: %s.", self.longName, self.consecutiveFails, measure)
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

ports = { # comment out lines below when there's no associated device/sensor
	PortTypes.Sound: 0,  # A port number. Take sound measurements
	PortTypes.Light: 1,  # A port number. Take light measurements
	PortTypes.TemperatureHumidity: 2, # D port number
	PortTypes.Led: 4,    # D port number. Turn on the led on startup and to react to sound/light
	PortTypes.Lcd: 1,    # I2C port numner. Print out values on LCD
	PortTypes.Buzzer: 7, # D port number. If present, buzz when sound level is too high
}

# Params:
# 1- number of readings to take before aggregating to compensate for fluctuations
# 2- precision
# 3, 4- short and long name
# 5- valueType

measures = {
	MeasureTypes.Temperature: SensorReadings(60, 1, "Tmp", "Temperature", "C"),
	MeasureTypes.Humidity: SensorReadings(60, 1, "Hum", "Humidity", "%"),
	MeasureTypes.Sound: SensorReadings(3, 200, "Snd", "Sound", ""),
	MeasureTypes.Light: SensorReadings(3, 100, "Lht", "Light", ""),
} 

tooLow = 16.0           # Too low temp
justRight = 20.0        # OK temp
tooHigh = 23.0          # Too high temp

soundTooHigh = 600	# Buzz if going over this level

refreshPeriod = .5	# How often to refresh measurements, in seconds
# Configuration end


def updateAnalog(value, portType):
	if (ports.has_key(portType)):
		port = ports[portType]
		logging.debug("AnalogWrite %d on port %d", value, port)
		grovepi.analogWrite(port, value)

def updateDigital(value, portType):
	if (ports.has_key(portType)):
		port = ports[portType]
		logging.debug("DigitalWrite %d on port %d", value, port)
		grovepi.digitalWrite(port, value)

def enableOutput(portType):
	if (ports.has_key(portType)):
		port = ports[portType]
		logging.debug("Enabling output port %d", port)
		grovepi.pinMode(port, "OUTPUT")

def updateLed(value):
	updateAnalog(value, PortTypes.Led)

def updateBuzzer(value):
	updateDigital(value, PortTypes.Buzzer)

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

def onValueChanged(measureType, oldValue, newValue):
	logging.debug("Value for %s changed from %d to %d (%f).", readings.longName, oldValue, newValue, readings.floatValue)
	if measureType == MeasureTypes.Light:
		updateLed(newValue / 4)
	if measureType == MeasureTypes.Sound and ports.has_key(PortTypes.Buzzer):
		if newValue > soundTooHigh:
			updateBuzzer(1)
		else:
			updateBuzzer(0)

def initOutputs():
	enableOutput(PortTypes.Led)
	enableOutput(PortTypes.Buzzer)
	# Show that we're ready
	updateLed(255)
	updateBuzzer(1)
	time.sleep(.1)
	updateBuzzer(0)


initOutputs()

out_str = ""
out_lcd = ""

logging.info("Starting sensor readings. Some readings may take a while to register ...")

while True:

	try:
		time.sleep(refreshPeriod)

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
					onValueChanged(measureType, oldValue, newValue)
											
				new_out_str = "%s: %d%s;%s" % (readings.longName, newValue, readings.valueType, new_out_str)
				new_out_lcd = "%s:%d%s %s" % (readings.shortName, newValue, readings.valueType, new_out_lcd)
	
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
		updateBuzzer(0)
		exit()
	except Exception as e:
		logging.exception("Error: %s", e)

