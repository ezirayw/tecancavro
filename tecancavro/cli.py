import argparse
import logging
import sys

from tecancavro.models import XCaliburD
from tecancavro.syringe import SyringeError, SyringeTimeout
from tecancavro.transport import TecanAPISerial

PRIMING_VOLUME = 5000

# Configure client logger (logs to file)
logger = logging.getLogger("tecancavro_cli")
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler("/home/pi/logs/tecancavro_cli.log")
file_handler.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

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
        choices=["FIND", "PRIME", "INIT", "PIPETTE"],
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
        help="List of pump addresses to apply that will receive entered XCaliburD function.",
        default=[0],
    )

    return parser.parse_args(), parser


def get_port(mode: str) -> int:
    while True:
        port_input: int = int(
            input(f"Enter port to {mode} from. Must be either 1, 2, or 3: ")
        )
        if port_input not in [1, 2, 3]:
            logger.warning("Invalid port entered, try again.")
        else:
            return port_input


def pipette(xcalibur_pump: XCaliburD, pipette_volume: int, address: int):
    aspirate_port: int = get_port("aspirate")
    dispense_port: int = get_port("dispense")

    try:
        logger.info(
            f"Pipetting {pipette_volume} uL from port_{aspirate_port} to port_{dispense_port}"
        )
        xcalibur_pump.extract(aspirate_port, pipette_volume)
        xcalibur_pump.dispense(dispense_port, pipette_volume)
        delay = xcalibur_pump.executeChain()
        xcalibur_pump.waitReady(int(delay))
        logger.info("Pipetting complete.")
    except (SyringeTimeout, SyringeError):
        logger.exception(
            f"Pipetting error encountered for XCaliburD pump on address {address}",
            stack_info=True,
        )


def prime(xcalibur_pump: XCaliburD, prime_volume: int, address: int):
    aspirate_port: int = get_port("aspirate")
    dispense_port: int = get_port("dispense")

    try:
        logger.info(
            f"Priming fludic line between port_{aspirate_port} from port_{dispense_port} using {prime_volume} uL"
        )
        pump.primePort(
            in_port=aspirate_port, out_port=dispense_port, volume_ul=prime_volume
        )
        logger.info(f"Priming for XCalibur pump on address {address} complete.")
    except (SyringeTimeout, SyringeError):
        logger.exception(
            f"Pipetting error encountered for XCaliburD pump on address {address}",
            stack_info=True,
        )


if __name__ == "__main__":
    options, parser = get_options()
    function = options.function

    if function != "FIND" and not options.serial_port:
        logger.error(
            f"Serial port input not found - required to run entered XCaliburD function: {function}"
        )
        sys.exit(2)

    if function == "FIND":
        input(
            "Make sure XCaliburD pumps are properly connected to the RS485 bus, power is on, and bus USB is plugged in. Press Enter to continue"
        )

        found_serial_port = TecanAPISerial.findSerialPumps()
        logger.info(
            f"Found XCaliburD pump(s) on the following port: {found_serial_port}"
        )
    if function in ["PRIME", "INIT", "PIPETTE"]:
        logger.info(
            "Establishing serial connection to XCaliburD pump(s). Please wait..."
        )
        xcalibur_pumps: dict[int, XCaliburD] = {}
        for pump_address in options.pump_addresses:
            tecan_api_serial = TecanAPISerial(pump_address, options.serial_port)
            xcalibur_pumps[pump_address] = XCaliburD(
                num_ports=3, com_link=tecan_api_serial
            )
            logger.info(f"Initializing XCaliburD pump on address {pump_address}")
            try:
                xcalibur_pumps[pump_address].init()
            except (SyringeError, SyringeTimeout):
                logger.exception(
                    f"Error encountered trying to initialize XCaliburD pump on address {pump_address}, exiting program...",
                    stack_info=True,
                )
                sys.exit(1)

        if function == "PRIME":
            for address, pump in xcalibur_pumps.items():
                while True:
                    try:
                        prime(pump, PRIMING_VOLUME, address)
                    except (SyringeError, SyringeTimeout):
                        logger.exception(
                            f"Error encountered trying to prime XCaliburD pump on address {address}, moving to next XCalibur pump.",
                            stack_info=True,
                        )
                        break
                    prime_input: str = ""
                    while True:
                        prime_input = input("Run another priming cycle? (y/n)")
                        if prime_input not in ["y", "n"]:
                            logger.warning("Must enter either 'y' or 'n', try again.")
                        else:
                            break
                    if prime_input == "n":
                        break

        if function == "PIPETTE":
            for address, pump in xcalibur_pumps.items():
                volume_input: int = 0
                while True:
                    try:
                        volume_input: int = int(
                            input(
                                f"Enter the volume of fluid to run PIPETTE for XCaliburD on address {address} (uL): "
                            )
                        )
                    except (TypeError, ValueError):
                        logger.warning("Invalid volume value entered, try again.")

                    if volume_input < 0:
                        logger.warning("Volume must be a positive integer, try again.")
                    else:
                        try:
                            pipette(pump, volume_input, address)
                        except (SyringeError, SyringeTimeout):
                            logger.exception(
                                f"Error encountered trying to pipette XCaliburD pump on address {address}, moving to next XCalibur pump.",
                                stack_info=True,
                            )
                            break

                        pipette_input: str = ""
                        while True:
                            pipette_input = input(
                                f"Run another pipette cycle for the pump on address: {address}? (y/n)"
                            )
                            if pipette_input not in ["y", "n"]:
                                logger.warning(
                                    "Must enter either 'y' or 'n', try again."
                                )
                            else:
                                break
                        if pipette_input == "n":
                            break
