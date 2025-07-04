"""
transport.py

Contains transport layer subclasses of the `TecanAPI` class, which provides
Tecan OEM API frame handling. All subclasses expose instance method `sendRcv`,
which sends a command string (`cmd`) and returns a dictionary containing the
`status_byte` and `data` in the response frame. Current subclasses include:

`TecanAPISerial` : Provides serial encapsulation of TecanAPI frame handling.
                  Can facilitate communication with multiple Tecan devices
                  on the same RS-232 port (i.e., daisy-chaining) by sharing
                  a single serial port instance.

"""

import glob
import sys
import time
import uuid

import serial

from .tecanapi import TecanAPI, TecanAPITimeout


# From http://stackoverflow.com/questions/12090503/
#      listing-available-com-ports-with-python
def listSerialPorts():
    """Lists serial ports

    :raises EnvironmentError:
        On unsupported or unknown platforms
    :returns:
        A list of available serial ports
    """
    if sys.platform.startswith("win"):
        ports: list[str] = ["COM" + str(i + 1) for i in range(256)]

    elif sys.platform.startswith("linux") or sys.platform.startswith("cygwin"):
        # this is to exclude your current terminal "/dev/tty"
        ports: list[str] = glob.glob("/dev/tty[A-Za-z]*")

    elif sys.platform.startswith("darwin"):
        ports: list[str] = glob.glob("/dev/tty.*")

    else:
        raise EnvironmentError("Unsupported platform")

    result: list[str] = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


class TecanAPISerial(TecanAPI):
    """
    Wraps the TecanAPI class to provide serial communication encapsulation
    and management for the Tecan OEM API. Maps devices to a state-monitored
    dictionary, `ser_mapping`, which allows multiple Tecan devices to
    share a serial port (provided that the serial params are the same).
    """

    ser_mapping: dict = {}

    @classmethod
    def findSerialPumps(
        cls,
        tecan_addrs: list[int] = [0],
        ser_baud: int = 9600,
        ser_timeout: float = 0.2,
        max_attempts: int = 2,
    ):
        """Find any enumerated syringe pumps on the local com / serial ports.

        Returns list of (<ser_port>, <pump_config>, <pump_firmware_version>)
        tuples.
        """
        found_devices: list = []
        for port_path in listSerialPorts():
            for addr in tecan_addrs:
                try:
                    p: TecanAPISerial = cls(
                        addr, port_path, ser_baud, ser_timeout, max_attempts
                    )
                    config = p.sendRcv("?76")["data"]
                    fw_version = p.sendRcv("&")["data"]
                    found_devices.append((port_path, config, fw_version))
                except OSError as e:
                    if e.errno != 16:  # Resource busy
                        raise
                except TecanAPITimeout:
                    pass
        return found_devices

    def __init__(
        self, tecan_addr, ser_port, ser_baud=9600, ser_timeout=0.1, max_attempts=5
    ):
        super(TecanAPISerial, self).__init__(tecan_addr)

        self.id_ = str(uuid.uuid4())
        self.ser_port = ser_port
        self.ser_info = {
            "baud": ser_baud,
            "timeout": ser_timeout,
            "max_attempts": max_attempts,
        }
        self._registerSer()

    def sendRcv(self, cmd: str):
        attempt_num: int = 0
        while attempt_num < self.ser_info["max_attempts"]:
            try:
                attempt_num += 1
                if attempt_num == 1:
                    frame_out: bytearray = self.emitFrame(cmd)
                else:
                    frame_out: bytearray = self.emitRepeat()
                self._sendFrame(frame_out)
                frame_in = self._receiveFrame()
                if frame_in:
                    return frame_in
                time.sleep(0.05 * attempt_num)
            except serial.SerialException:
                time.sleep(0.2)
        raise (
            TecanAPITimeout(
                "Tecan serial communication exceeded max attempts [{0}]".format(
                    self.ser_info["max_attempts"]
                )
            )
        )

    def _sendFrame(self, frame: bytearray):
        self._ser.write(frame)

    def _receiveFrame(self):
        raw_data: bytes = b""
        raw_byte = self._ser.read()
        while raw_byte != b"":
            raw_data += raw_byte
            raw_byte = self._ser.read()
        return self.parseFrame(raw_data)

    def _registerSer(self):
        """
        Checks to see if another TecanAPISerial instance has registered the
        same serial port in `ser_mapping`. If there is a conflict, checks to
        see if the parameters match, and if they do, shares the connection.
        Otherwise it raises a `serial.SerialException`.
        """
        reg = TecanAPISerial.ser_mapping
        port = self.ser_port
        if self.ser_port not in reg:
            reg[port] = {}
            reg[port]["info"] = {k: v for k, v in self.ser_info.items()}
            reg[port]["_ser"] = serial.Serial(
                port=port,
                baudrate=reg[port]["info"]["baud"],
                timeout=reg[port]["info"]["timeout"],
            )
            reg[port]["_devices"] = [self.id_]
        else:
            if len(set(self.ser_info.items()) & set(reg[port]["info"].items())) != 3:
                raise serial.SerialException(
                    "TecanAPISerial conflict: another device is already registered to {0} with different parameters".format(
                        port
                    )
                )
            else:
                reg[port]["_devices"].append(self.id_)
        self._ser = reg[port]["_ser"]

    def __del__(self):
        """
        Cleanup serial port registration on delete
        """
        port_reg = TecanAPISerial.ser_mapping[self.ser_port]
        try:
            dev_list = port_reg["_devices"]
            ind = dev_list.index(self.id_)
            del dev_list[ind]
            if len(dev_list) == 0:
                port_reg["_ser"].close()
                del port_reg, TecanAPISerial.ser_mapping[self.ser_port]
        except KeyError:
            pass
