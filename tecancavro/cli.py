import argparse
import logging
import sys

from tecancavro.models import XCaliburD
from tecancavro.transport import TecanAPISerial

PRIMING_VOLUME = 5000

# Configure client logger (logs to file)
logger = logging.getLogger("tecancavro_cli")

# Create handlers
file_handler = logging.FileHandler("/home/pi/logs/tecancavro_cli.log")
file_handler.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)

# Set formatter for both handlers
file_formatter = logging.Formatter(
    fmt="%(asctime)s - %(name)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
stream_formatter = logging.Formatter(fmt="%(name)s - [%(levelname)s] - %(message)s")
file_handler.setFormatter(file_formatter)
stream_handler.setFormatter(stream_formatter)


def get_options():
    description = "CLI tool to run XCalibur functions"
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-f",
        "--function",
        action="store",
        required=True,
        help="Desired XCaliburD function to run",
        choices=["FIND", "PRIME", "TEST", "INIT"],
    )

    parser.add_argument(
        "-p",
        "--serial_port",
        action="store",
        required=False,
        help="Name of the serial port used for RS485 communication with pumps",
    )

    parser.add_argument(
        "-a",
        "--pump_addresses",
        action="store",
        required=False,
        nargs="*",
        type=lambda s: int(s),
        help="List of pump addresses to apply that will receive entered XCaliburD function. Defaults to 0",
        default=0,
    )

    return parser.parse_args(), parser


if __name__ == "__main__":
    options, parser = get_options()
    function = options.function

    if function != "FIND" and not options.serial_port:
        logger.error(
            f"Serial port input not found - required to run entered XCaliburD function: {function}"
        )
        sys.exit(2)

    if function == "FIND":
        while True:
            check_input = input(
                "Make sure XCaliburD pumps are properly connected to the RS485 bus, power is on, and bus USB is plugged in. Press Enter to continue"
            )
            if check_input:
                break

        found_serial_port = TecanAPISerial.findSerialPumps()
        logger.info(
            f"Found XCaliburD pump(s) on the following port: {found_serial_port}"
        )
    if function in ["PRIME", "TEST"]:
        logger.info(
            "Establishing serial connection to XCaliburD pump(s). Please wait..."
        )
        xcalibur_pumps: dict[int, XCaliburD] = {}
        for pump_address in options.pump_addresses:
            tecan_api_serial = TecanAPISerial(pump_address, options.serial_port)
            xcalibur_pumps[pump_address] = XCaliburD(
                num_ports=3, com_link=tecan_api_serial
            )
            xcalibur_pumps[pump_address].init()

        if function == "PRIME":
            for address, pump in xcalibur_pumps.items():
                while True:
                    logger.info(f"Begining PRIME for pump address: {address}")
                    pump.primePort(in_port=3, out_port=1, volume_ul=PRIMING_VOLUME)
                    prime_input = input("Run another priming cycle? (y/n)")
                    if prime_input == "n":
                        break
