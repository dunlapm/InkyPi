import time
import warnings
from types import MethodType


AC073TC1A_DRIVER_MODULE = "inky.inky_ac073tc1a"
SPI_CHUNK_SIZE = 4096
BUSY_ASSERTION_GRACE_SECONDS = 0.1
BUSY_POLL_SECONDS = 0.01


def _ac073tc1a_spi_write(display, dc, values):
    from gpiod.line import Value

    display._gpio.set_value(display.cs_pin, Value.INACTIVE)
    display._gpio.set_value(
        display.dc_pin,
        Value.ACTIVE if dc else Value.INACTIVE,
    )

    if isinstance(values, str):
        values = [ord(character) for character in values]

    try:
        display._spi_bus.xfer3(values)
    except AttributeError:
        for offset in range(0, len(values), SPI_CHUNK_SIZE):
            display._spi_bus.xfer(
                values[offset:offset + SPI_CHUNK_SIZE]
            )

    display._gpio.set_value(display.cs_pin, Value.ACTIVE)


def _ac073tc1a_busy_wait(display, timeout=40.0):
    from gpiod.line import Value

    deadline = time.monotonic() + timeout
    assertion_deadline = min(
        deadline,
        time.monotonic() + BUSY_ASSERTION_GRACE_SECONDS,
    )

    while (
        display._gpio.get_value(display.busy_pin) == Value.ACTIVE
        and time.monotonic() < assertion_deadline
    ):
        time.sleep(BUSY_POLL_SECONDS)

    if display._gpio.get_value(display.busy_pin) == Value.ACTIVE:
        remaining = max(0, deadline - time.monotonic())
        warnings.warn(
            f"Busy Wait: Held high. Waiting for {remaining:0.2f}s"
        )
        time.sleep(remaining)
        return

    while (
        display._gpio.get_value(display.busy_pin) != Value.ACTIVE
        and time.monotonic() < deadline
    ):
        time.sleep(BUSY_POLL_SECONDS)

    if display._gpio.get_value(display.busy_pin) != Value.ACTIVE:
        warnings.warn(f"Busy Wait: Timed out after {timeout:0.2f}s")


def optimize_ac073tc1a_driver(display):
    if type(display).__module__ != AC073TC1A_DRIVER_MODULE:
        return False

    display._spi_write = MethodType(_ac073tc1a_spi_write, display)
    display._busy_wait = MethodType(_ac073tc1a_busy_wait, display)
    return True
