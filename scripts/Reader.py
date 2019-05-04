#!/usr/bin/env python2
# This alternative Reader.py script was meant to cover not only USB readers but more.
# It can be used to replace Reader.py if you have readers such as
# MFRC522 or RDM6300.
# Please use the github issue threads to share bugs and improvements
# or create pull requests.

import os.path
import sys
import serial
import string
import RPi.GPIO as GPIO
import rfidiot

from evdev import InputDevice, categorize, ecodes, list_devices
#import MFRC522
import pirc522


def get_devices():
    devices = [InputDevice(fn) for fn in list_devices()]
    devices.append(NonUsbDevice('MFRC522'))
    devices.append(NonUsbDevice('RDM6300'))
    # The following code is from RFIDIOt's multiselect.py
    try:
        card = rfidiot.card
    except:
        return devices

    args = rfidiot.args

    card.info('Searching for pcscd-compatible readers')

    # force card type if specified
    if len(args) == 1:
        if not card.settagtype(args[0]):
            print 'Could not set tag type'
            return devices
    else:
        card.settagtype(card.ALL)
    devices.append(NonUsbDevice('PCSCD'))
    return devices


class NonUsbDevice(object):
    name = None

    def __init__(self, name):
        self.name = name


class UsbReader(object):
    def __init__(self, device):
        self.keys = "X^1234567890XXXXqwertzuiopXXXXasdfghjklXXXXXyxcvbnmXXXXXXXXXXXXXXXXXXXXXXX"
        self.dev = device

    def readCard(self):
        from select import select
        stri = ''
        key = ''
        while key != 'KEY_ENTER':
            select([self.dev], [], [])
            for event in self.dev.read():
                if event.type == 1 and event.value == 1:
                    stri += self.keys[event.code]
                    key = ecodes.KEY[event.code]
        return stri[:-1]

class PcscdReader(object):
    def __init__(self):
        self.card= rfidiot.card
        args = rfidiot.args
        self.card.settagtype(self.card.ALL)

    def readCard(self):
        while True:
            if self.card.select('A') or self.card.select('B'):
                return self.card.uid

        return None

class Mfrc522Reader(object):
    def __init__(self):
        self.device = pirc522.RFID()

    def readCard(self):
        # Scan for cards
        self.device.wait_for_tag()
        (error, tag_type) = self.device.request()

        if not error:
            print "Card detected."
            # Perform anti-collision detection to find card uid
            (error, uid) = self.device.anticoll()
            if not error:
                return ''.join((str(x) for x in uid))

        print "No Device ID found."
        return None

    @staticmethod
    def cleanup():
        GPIO.cleanup()


class Rdm6300Reader:
    def __init__(self):
        device = '/dev/ttyS0'
        baudrate = 9600
        ser_timeout = 0.1
        self.last_card_id = ''
        try:
            self.rfid_serial = serial.Serial(device, baudrate, timeout=ser_timeout)
        except serial.SerialException as e:
            print(e)
            exit(1)

    def readCard(self):
        byte_card_id = b''

        try:
            while True:
                try:
                    read_byte = self.rfid_serial.read()

                    if read_byte == b'\x02':    # start byte
                        while read_byte != b'\x03':     # end bye
                            read_byte = self.rfid_serial.read()
                            byte_card_id += read_byte

                        card_id = byte_card_id.decode('utf-8')
                        byte_card_id = ''
                        card_id = ''.join(x for x in card_id if x in string.printable)

                        # Only return UUIDs with correct length
                        if len(card_id) == 12 and card_id != self.last_card_id:
                            self.last_card_id = card_id
                            self.rfid_serial.reset_input_buffer()
                            return self.last_card_id

                        else:   # wrong UUID length or already send that UUID last time
                            self.rfid_serial.reset_input_buffer()

                except ValueError as ve:
                    print(ve)

        except serial.SerialException as se:
            print(se)

    def cleanup(self):
        self.rfid_serial.close()


class Reader(object):
    def __init__(self):
        path = os.path.dirname(os.path.realpath(__file__))
        if not os.path.isfile(path + '/deviceName.txt'):
            sys.exit('Please run RegisterDevice.py first')
        else:
            with open(path + '/deviceName.txt', 'r') as f:
                device_name = f.read()

            if device_name == 'MFRC522':
                self.reader = Mfrc522Reader()
            elif device_name == 'RDM6300':
                self.reader = Rdm6300Reader()
            elif device_name == 'PCSCD':
                self.reader = PcscdReader()
            else:
                try:
                    device = [device for device in get_devices() if device.name == device_name][0]
                    self.reader = UsbReader(device)
                except IndexError:
                    sys.exit('Could not find the device %s.\n Make sure it is connected' % device_name)
