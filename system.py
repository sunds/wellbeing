"""
The MIT License (MIT)
Copyright © 2020 David Sundstrom

ESP32 functions for ADC and RTC I2C integration and also for relay control
"""

import machine
import math
import ads1x15
import ds3231
import btree
import struct
import time
import json
import array
import os
import micropython
from collections import deque
from time import sleep

micropython.alloc_emergency_exception_buf(100)

# External ADC and RTC boards use the I2C communication bus

class I2C_Bus:
    SCA_Pin = 21
    SCL_Pin = 22
    SCL_Freq =400000
    i2c =None

    def __init__(self):
        if (I2C_Bus.i2c is None):
            I2C_Bus.i2c = machine.I2C(scl=machine.Pin(I2C_Bus.SCL_Pin), sda=machine.Pin(I2C_Bus.SCA_Pin), freq=I2C_Bus.SCL_Freq)
        self.i2c = I2C_Bus.i2c

class A2D(I2C_Bus):
    Alert_Pin = 4
    Factor = 22.438 # determined by manual testing and line fitting
    Addr = 72
    Gain = 2  # 2.048V range
    SampleRate = 1 # 250 samples per second
    ADC_Pin1 = 0
    ADC_Pin2 = 1
    CollectionCounts = micropython.const(240)
    adc = None

    def __init__(self, manager):
        super().__init__()
        self.ads = ads1x15.ADS1015(self.i2c, A2D.Addr, A2D.Gain)
        self.manager = manager
        self.samples = array.array('i', [0 for x in range(A2D.CollectionCounts)])
        self.accumulate_ref = self.accumulate # python magic https://docs.micropython.org/en/latest/reference/isr_rules.html

    def getManager(self):
        return self.manager

    def start(self):
        self.irq_pin = machine.Pin(A2D.Alert_Pin, machine.Pin.IN)
        self.ads.conversion_start(A2D.SampleRate, A2D.ADC_Pin1, A2D.ADC_Pin2)
        self.irq_pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=self.interrupt)
        self.collect_count =0

        # micropython watchdog will reset board if interrupts stop
        self.wdt = machine.WDT(timeout=300000) # 5 minutes

    def stop(self):
        self.irq_pin.irq(handler=None)

    def raw_to_amps(self, raw) -> float:
        return round(raw * A2D.Factor / 1000, 3)

    def accumulate(self, _):

        accumulation = 0

        for s in self.samples:
            accumulation += s * s

        read = math.sqrt(accumulation / A2D.CollectionCounts)
        amps = self.raw_to_amps(read)
        self.manager.read(amps)
        self.collect_count = 0

    # Per https://docs.micropython.org/en/latest/reference/isr_rules.html
    # Interrupt handlers must be short, use only primitive types, and do no allocation
    # However this is NOT true for ESP32 https://forum.micropython.org/viewtopic.php?f=2&t=4304
    # The scheduling onto the python loop is baked in.
    # This will happen on whichever python thread is running at the time. This method will not be
    # preempted by another interrupt so it is "safe" in that regard.
    def interrupt(self, t):
        try:
            self.wdt.feed()
            r = self.ads.alert_read()
            if self.collect_count < A2D.CollectionCounts:
                self.samples[self.collect_count] = r
                self.collect_count += 1

            if (self.collect_count >= A2D.CollectionCounts):
                self.accumulate(None)
        except OSError:
            pass # error reading ADC


class Clock(I2C_Bus):

    rtc = None

    def __init__(self):
        super().__init__()
        if (Clock.rtc is None):
            Clock.rtc = ds3231.DS3231(self.i2c)
        self.rtc = Clock.rtc

    def setDateTime(self, year, month, day, hour, minute, second, weekday):
        t = (year, month, day, hour, minute, second, weekday, 0)
        # YY, MM, DD, hh, mm, ss, wday -1, 0
        Clock.rtc.save_time(t)

    def getTimestamp(self) -> int:
        dt = Clock.rtc.get_time()
        return (int) (time.mktime(dt))

    # YY, MM, DD, hh, mm, ss, wday -1, 0
    def getDateTime(self):
        return Clock.rtc.get_time()

class LogEntry():

    def __init__(self):
        self.count = 0

    def start(self, startTime):
        self.startTime = startTime
        self.count = 0
        self.minAmps = 999999
        self.maxAmps = 0
        self.avgAmps = 0

    def end(self, endTime):
        self.endTime = endTime
        self.avgAmps = 0 if (self.count == 0) else round(self.avgAmps / self.count, 3)
        self.duration = self.endTime - self.startTime

    def value(self, amps):
        self.avgAmps += amps
        self.count += 1
        if (amps > self.maxAmps):
            self.maxAmps =amps
        if (amps < self.minAmps):
            self.minAmps =amps

    def getBinaryKeyForTime(self, t) -> []:
        key = struct.pack("!I", t)
        return key

    def getBinaryKey(self) -> []:
        return self.getBinaryKeyForTime(self.startTime)

    def getBinaryValue(self) -> []:
        value = struct.pack("!IIfff",
                             self.startTime,
                             self.duration,
                             self.minAmps,
                             self.avgAmps,
                             self.maxAmps)
        return value

    def fromBinary(self, b):
        t = struct.unpack("!IIfff", b)
        self.startTime = t[0]
        self.duration = t[1]
        self.minAmps = t[2]
        self.avgAmps = t[3]
        self.maxAmps = t[4]

        self.endTime = self.startTime + self.duration

    def getTupleValue(self):
        """
        YY, MM, DD, hh, mm, ss, wday, duration, min, avg, max
        """
        t = time.localtime(self.startTime)[0:6] # # YY, MM, DD, hh, mm, ss, wday
        return t + (self.duration, self.minAmps, self.avgAmps, self.maxAmps)

class ConfigEntry:

    def __init__(self, bootTime):
        self.maxRuntime = 8 * 60 # max individual runtime in seconds
        self.maxCycles = 360 # max cycles per day
        self.minCurrent = .250 # on threshold in amps
        self.bootTime = bootTime

    def setConfig(self, maxCycles, maxRuntime, minCurrent):
        self.maxCycles = maxCycles
        self.maxRuntime = maxRuntime
        self.minCurrent = minCurrent

    def getConfig(self):
        return json.dumps(self.__dict__)

    def getBinaryKey(self) -> []:
        key = struct.pack("!I", 0)
        return key

    def getBinaryValue(self) -> []:
        value = struct.pack("!IIf",
                            self.maxRuntime,
                            self.maxCycles,
                            self.minCurrent)
        return value

    def fromBinary(self, b):
        t = struct.unpack("!IIf", b)
        self.maxRuntime = t[0]
        self.maxCycles = t[1]
        self.minCurrent = t[2]


class PumpManager():

    RelayPin = 5
    LampPin = 2
    manager = None
    DBFile = "database.bin"

    @classmethod
    def getManager(cls):
        if (cls.manager is None):
            cls.manager = PumpManager()
        return cls.manager

    # Idomatic way to create if not exist a DB file. The 'r' doesn't really mean read-only....
    # See http://docs.micropython.org/en/v1.9.3/pyboard/library/btree.html
    def __init__(self):
        self.adc = A2D(self)
        self.rtc = Clock()
        self.queue = deque((),25)

        try:
            self.dbFile = open(PumpManager.DBFile, "r+b")
        except OSError:
            self.dbFile = open(PumpManager.DBFile, "w+b")

        self.db = btree.open(self.dbFile)

        self.relay =machine.Pin(PumpManager.RelayPin, machine.Pin.OUT)
        self.relay.value(0)
        self.lamp =machine.Pin(PumpManager.LampPin, machine.Pin.OUT)
        self.lamp.value(0)

        self.config = ConfigEntry(self.rtc.getDateTime())
        if (self.config.getBinaryKey() in self.db):
            self.config.fromBinary(self.db[self.config.getBinaryKey()])

        self.on = False
        self.fault = False
        self.logEntry = None
        self.callback = None
        self.adc.start()

    # check for max runtime limit
    def guardRuntime(self, duration):
        if (duration > self.config.maxRuntime):
            self.fault = True
            self.relay.value(1)
            self.lamp.value(1)

    # check for cycles per day limit
    def guardCycles(self, count):
        if (count > self.config.maxCycles):
            self.fault = True
            self.relay.value(1)
            self.lamp.value(1)

    # gets configuration values
    def getConfig(self):
        return self.config.getConfig()

    # sets configuration values into database
    def setConfig(self, maxCycles, maxRuntime, minCurrent):
        self.config.setConfig(maxCycles, maxRuntime, minCurrent)
        self.db[self.config.getBinaryKey()] = self.config.getBinaryValue()
        self.db.flush()

    # register the websocket callback handler
    def setCallback(self, callback):
        self.callback = callback

    # Form the JSON update for websockets
    def statusUpdate(self, amps):
        if (self.on):
            status = "ON"
        elif (self.fault):
            status = "FAULT"
        else:
            status = "OK"

        s = {
            "status": status,
            "amps": amps
        }

        j = json.dumps(s)
        return j

    # log a reading.
    def log(self, amps):
        if (self.callback is not None):
            self.callback(self.statusUpdate(amps))

        if (self.on):
            if (amps <= self.config.minCurrent):
                self.on = False
                self.logEntry.end(self.rtc.getTimestamp())
                self.db[self.logEntry.getBinaryKey()] = self.logEntry.getBinaryValue()
                self.db.flush()

                itemsInLastDay = self.db.keys(self.logEntry.getBinaryKeyForTime(self.logEntry.endTime - 86400))
                self.guardCycles(len(list(itemsInLastDay)))

            else:
                # avoid logging last value if the next value is below threshold. This avoids logging a partial sample.
                if (self.lastValue > 0):
                    self.logEntry.value(self.lastValue)
                self.lastValue = amps
                self.guardRuntime(self.rtc.getTimestamp() - self.logEntry.startTime)

        else:
            if (amps > self.config.minCurrent):
                # Note first value is not logged as it could be a partial sample.
                self.on = True
                self.lastValue = 0
                self.logEntry = LogEntry()
                self.logEntry.start(self.rtc.getTimestamp())

    # get N days worth of logs
    def getLogs(self, days) -> []:
        """
        Each entry: days_ago, YY, MM, DD, hh, mm, ss, duration, min, avg, max
        """
        (year, month, mday, hour, minute, second, weekday, yearday) = self.rtc.getDateTime()
        endOfToday = time.mktime((year, month, mday, 23, 59, 59, weekday, yearday))
        timeBefore = endOfToday - (days * 86400)
        le = LogEntry()
        logs = []
        for rawLog in self.db.values(le.getBinaryKeyForTime(timeBefore)):
            le.fromBinary(rawLog)
            daysBefore = (int) ((le.startTime - endOfToday) / 86400)
            t = (daysBefore,) + le.getTupleValue()
            logs.append(t)
        return logs

    # set fault value
    def setFault(self, fault):
        self.fault = fault
        self.relay.value(1 if fault else 0)
        self.lamp.value(1 if fault else 0)

    # "factory reset"
    # Deletes the database and restarts the ESP32
    def reset(self):
        self.db.close()
        self.dbFile.close()
        os.remove(PumpManager.DBFile)
        machine.reset()

    # Thread safe producer. Interrupt could have happened on any thread. This passes the reading to a thread
    # safe queue to be read on the main thread.
    def read(self, amps):
        self.queue.append(amps)

    # Thread safe consumer. Consumes interrupt readings and processes on the main thread.
    def run(self):
        while True:
            try:
                while not self.queue:
                    sleep(.25)
                amps = self.queue.popleft()
                self.log(amps)
            except KeyboardInterrupt as e:
                self.adc.stop()
                raise e






