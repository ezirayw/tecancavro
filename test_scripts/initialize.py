from tecancavro.models import XCaliburD
from tecancavro.syringe import SyringeError
from tecancavro.transport import TecanAPISerial

# Args:
#     `com_link` (Object) : instantiated TecanAPI subclass / transport
#                           layer (see transport.py)
#         *Must have a `.sendRcv(cmd)` instance method to send a command
#             string and parse the reponse (see transport.py)
# Kwargs:
#     `num_ports` (int) : number of ports on the distribution valve
#         [default] - 9
#     `syringe_ul` (int) : syringe volume in microliters
#         [default] - 1000
#     `microstep` (bool) : whether or not to operate in microstep mode
#         [default] - False (factory default)
#     `waste_port` (int) : waste port for `extractToWaste`-like
#                          convenience functions
#         [default] - 9 (factory default for init out port)
#     `slope` (int) : slope setting
#         [default] - 14 (factory default)
#     `init_force` (int) : initialization force or speed
#         0 [default] - full plunger force and default speed
#         1 - half plunger force and default speed
#         2 - one third plunger force and default speed
#         10-40 - full force and speed code X
#     `debug` (bool) : turns on debug file, which logs extensive debug
#                      output to 'xcaliburd_debug.log' at
#                      `debug_log_path`
#         [default] - False
#     `debug_log_path` : path to debug log file - only relevant if
#                        `debug` == True.
#         [default] - '' (cwd)


if __name__ == "__main__":
    # find serial pump
    # found_pumps = TecanAPISerial.findSerialPumps()
    # print(found_pumps)

    suck_back_volume = 20

    serial_port = "/dev/tty.usbserial-AG0KB3HZ"
    tecan_api_serial = TecanAPISerial(0, serial_port)
    xcalibur_pump = XCaliburD(num_ports=3, waste_port=3, com_link=tecan_api_serial)

    # initialize pump
    xcalibur_pump.init()
    xcalibur_pump.extract(1, suck_back_volume)
    target_volume = 990
    if target_volume + suck_back_volume > 1000:
        raise Exception("too big of volume")

    # xcalibur_pump.dispense(3, 1000)
    # delay = xcalibur_pump.executeChain()
    # xcalibur_pump.waitReady(delay)

    # send A3000R to change syringe
    # xcalibur_pump.sendRcv("A3000", execute=True)

    # prime pump
    # xcalibur_pump.primePort(1, 2000)
    # calculate steps

    # run a quick extract/dispense sequence
    for sequence in range(5):
        print("yo")
        xcalibur_pump.extract(1, target_volume)
        xcalibur_pump.dispense(3, target_volume + suck_back_volume)
        xcalibur_pump.extract(3, suck_back_volume)
        delay = xcalibur_pump.executeChain()
        xcalibur_pump.waitReady(delay)
