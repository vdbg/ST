#!/usr/bin/python27

import time
import math
import numbers
import logging

# To install: 'apt-get install python-numpy' or 'pip install numpy'
import numpy as np
import grovepi
import grove_rgb_lcd as grove_lcd

class PortTypes(object): # pylint: disable=R0903
    Sound = 0
    Light = 1
    TemperatureHumidity = 2
    Led = 3
    Lcd = 4
    Buzzer = 5


class MeasureTypes(object): # pylint: disable=R0903
    Sound = 0
    Light = 1
    Temperature = 2
    Humidity = 3


class SensorReadings(object): # pylint: disable=R0902

    def __init__(self, readings, precision, short_name, long_name, value_type): # pylint: disable=R0913
        self.values = []
        self.counts = 0
        self.readings = readings
        self.precision = precision
        self.short_name = short_name
        self.long_name = long_name
        self.value_type = value_type
        self.consecutive_fails = 0
        self.last_float_value = -1
        self.float_value = -1

    def get_value(self):
        value = self.last_float_value
        if self.has_changes():
            self.last_float_value = self.float_value
            value = self.float_value
        return int(np.round(value / self.precision) * self.precision)

    def has_value(self):
        return self.float_value != -1

    def has_changes(self):
        return self.last_float_value == -1 or \
		       abs(self.last_float_value - self.float_value) > self.precision

    @staticmethod
    def reject_outliers(data):
        if len(data) < 5:
            return data
        data = np.array(data)
        ret = data[abs(data - np.mean(data)) <= 2. * np.std(data)]
        if len(data) != len(ret):
            logging.debug("Removed outliers; from %s to %s", data, ret)
        return ret

    def compute_value(self):
        if self.counts < self.readings:
            return
        ret = SensorReadings.reject_outliers(self.values)
        self.float_value = np.average(ret)

    def add_measure(self, measure):
        if not isinstance(measure, numbers.Number) or math.isnan(measure):
            self.consecutive_fails += 1
            # failures are quite common. Only report if 2x in a row or more
            if self.consecutive_fails > 1:
                logging.warning("Unable to read %s value #%d: %s.",
                                self.long_name, self.consecutive_fails, measure)
            return

        self.consecutive_fails = 0
        if self.counts < self.readings:
            self.values.append(measure)
        else:
            self.values[self.counts % self.readings] = measure
        self.counts += 1


# Configuration start

logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s:%(asctime)s:%(message)s')

IS_GROVE_PRO = 0  # Set to 1 is it's a GrovePi Pro DHT; 0 otherwise

ENABLED_PORTS = {  # comment out lines below when there's no associated device/sensor
    PortTypes.Sound: 0,  # A port number. Take sound measurements
    PortTypes.Light: 1,  # A port number. Take light measurements
    PortTypes.TemperatureHumidity: 2,  # D port number
    PortTypes.Led: 4,    # D port number. Turn on the led on startup and to react to sound/light
    PortTypes.Lcd: 1,    # I2C port numner. Print out values on LCD
    PortTypes.Buzzer: 7,  # D port number. If present, buzz when sound level is too high
}

# Params:
# 1- number of readings to take before aggregating to compensate for fluctuations
# 2- precision
# 3, 4- short and long name
# 5- valueType

MEASURES = {
    MeasureTypes.Temperature: SensorReadings(60, 1, "Tmp", "Temperature", "C"),
    MeasureTypes.Humidity: SensorReadings(60, 1, "Hum", "Humidity", "%"),
    MeasureTypes.Sound: SensorReadings(3, 200, "Snd", "Sound", ""),
    MeasureTypes.Light: SensorReadings(3, 100, "Lht", "Light", ""),
}

GOOD_TEMPERATURE = 20.0

SOUND_TOO_HIGH = 600  # Buzz if going over this level

LOOP_SECONDS = .5  # How often to refresh measurements, in seconds
# Configuration end


def update_analog(value, port_type):
    if ENABLED_PORTS.has_key(port_type):
        port = ENABLED_PORTS[port_type]
        logging.debug("AnalogWrite %d on port %d", value, port)
        grovepi.analogWrite(port, value)


def update_digital(value, port_type):
    if ENABLED_PORTS.has_key(port_type):
        port = ENABLED_PORTS[port_type]
        logging.debug("DigitalWrite %d on port %d", value, port)
        grovepi.digitalWrite(port, value)


def enable_output_port(port_type):
    if ENABLED_PORTS.has_key(port_type):
        port = ENABLED_PORTS[port_type]
        logging.debug("Enabling output port %d", port)
        grovepi.pinMode(port, "OUTPUT")


def update_led(value):
    update_analog(value, PortTypes.Led)


def update_buzzer(value):
    update_digital(value, PortTypes.Buzzer)


def adjust_color(variance):
    """Calc the adjustment value of the background color"""
    # Because there is 6 degrees mapping to 255 values, 42.5 is the factor for 12 degree spread
    factor = 42.5
    adj = abs(int(factor * variance))
    if adj > 255:
        adj = 255
    return adj


def calc_background(ftemp):
    "This calculates the color value for the background"
    variance = ftemp - GOOD_TEMPERATURE   # Calculate the variance
    adj = adjust_color(variance)   # Scale it to 8 bit int
    ret = [0, 0, 0]               # initialize the color array
    if variance < 0:
        red = 0                    # too cold, no red
        blue = adj                  # green and blue slide equally with adj
        green = 255 - adj

    elif variance == 0:             # perfect, all on green
        red = 0
        blue = 0
        green = 255

    elif variance > 0:  # too hot - no blue
        blue = 0
        red = adj                  # Red and Green slide equally with Adj
        green = 255 - adj

    ret = [red, green, blue]  # build list of color values to return
    return ret


def get_analog(measure_type, port_number):
    ret = grovepi.analogRead(port_number)
    MEASURES[measure_type].add_measure(ret)


def get_temperature_humidity(port_number):
    [temperature, humidity] = [0, 0]
    [temperature, humidity] = grovepi.dht(port_number, IS_GROVE_PRO)
    MEASURES[MeasureTypes.Temperature].add_measure(temperature)
    MEASURES[MeasureTypes.Humidity].add_measure(humidity)


def set_lcd(text, rgb):
    if not ENABLED_PORTS.has_key(PortTypes.Lcd):
        return
    grove_lcd.setRGB(rgb[0], rgb[1], rgb[2])
    grove_lcd.setText(text)


def on_value_changed(measure_type, old_value, new_value, readings):
    logging.debug("Value for %s changed from %d to %d (%f).",
                  readings.long_name, old_value, new_value, readings.float_value)
    if measure_type == MeasureTypes.Light:
        update_led(new_value / 4)
    if measure_type == MeasureTypes.Sound and ENABLED_PORTS.has_key(PortTypes.Buzzer):
        if new_value > SOUND_TOO_HIGH:
            update_buzzer(1)
        else:
            update_buzzer(0)

def init_outputs():
    enable_output_port(PortTypes.Led)
    enable_output_port(PortTypes.Buzzer)
    # Show that we're ready
    update_led(255)
    update_buzzer(1)
    time.sleep(.1)
    update_buzzer(0)

def read_all():
    for port_type, port_number in ENABLED_PORTS.items():
        if port_type == PortTypes.Sound:
            get_analog(MeasureTypes.Sound, port_number)
        elif port_type == PortTypes.Light:
            get_analog(MeasureTypes.Light, port_number)
        elif port_type == PortTypes.TemperatureHumidity:
            get_temperature_humidity(port_number)


def main():
    init_outputs()
    out_str = ""
    out_lcd = ""

    logging.info("Starting sensor readings. Some readings may take a while to register ...")

    while True:

        try:
            time.sleep(LOOP_SECONDS)
            read_all()

            new_out_str = ""
            new_out_lcd = ""

            for measure_type, readings in MEASURES.items():
                old_value = readings.get_value()
                readings.compute_value()
                if readings.has_value():
                    new_value = readings.get_value()
                    if old_value != new_value:
                        on_value_changed(measure_type, old_value, new_value, readings)

                    new_out_str = "%s: %d%s;%s" % (
                        readings.long_name, new_value, readings.value_type, new_out_str)
                    new_out_lcd = "%s:%d%s %s" % (
                        readings.short_name, new_value, readings.value_type, new_out_lcd)

            if new_out_str != out_str:
                out_str = new_out_str
                logging.info(out_str)

            if ENABLED_PORTS.has_key(PortTypes.Lcd) and new_out_lcd != out_lcd:
                out_lcd = new_out_lcd
                rgb = (0, 0, 0)
                if MEASURES[MeasureTypes.Temperature].has_value():
                    rgb = calc_background(MEASURES[MeasureTypes.Temperature].get_value())
                set_lcd(out_lcd, rgb)
        except IOError:
            logging.error("IO Error")
        except KeyboardInterrupt:
            logging.critical("EXITING")
            set_lcd(" " * 32, (0, 0, 0))
            update_led(0)
            update_buzzer(0)
            exit()
        except Exception as exception: # pylint: disable=W0703
            logging.exception("Error: %s", exception)

if __name__ == "__main__":
    main()
