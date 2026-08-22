import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.display.inky_ac073tc1a_optimization import (
    _ac073tc1a_busy_wait,
    _ac073tc1a_spi_write,
    optimize_ac073tc1a_driver,
)


def test_optimized_spi_uses_bulk_transfer():
    display = MagicMock()
    display.cs_pin = 8
    display.dc_pin = 22

    value = MagicMock()
    with patch.dict(sys.modules, {"gpiod.line": SimpleNamespace(Value=value)}):
        _ac073tc1a_spi_write(display, 1, [1, 2, 3])

    display._spi_bus.xfer3.assert_called_once_with([1, 2, 3])
    display._spi_bus.xfer.assert_not_called()
    display._gpio.set_value.assert_any_call(display.cs_pin, value.INACTIVE)
    display._gpio.set_value.assert_any_call(display.dc_pin, value.ACTIVE)
    display._gpio.set_value.assert_any_call(display.cs_pin, value.ACTIVE)


def test_busy_wait_returns_when_busy_pin_releases():
    display = MagicMock()
    display.busy_pin = 17

    with (
        patch.dict(
            sys.modules,
            {"gpiod.line": SimpleNamespace(Value=(value := MagicMock()))},
        ),
        patch(
            "src.display.inky_ac073tc1a_optimization.time.monotonic",
            side_effect=[0, 0, 0.01, 0.02, 0.03],
        ),
        patch("src.display.inky_ac073tc1a_optimization.time.sleep"),
    ):
        display._gpio.get_value.side_effect = [
            value.ACTIVE,
            value.INACTIVE,
            value.INACTIVE,
            value.ACTIVE,
            value.ACTIVE,
        ]
        _ac073tc1a_busy_wait(display, timeout=45)


def test_optimization_only_applies_to_ac073tc1a():
    supported_type = type("Inky", (), {})
    supported_type.__module__ = "inky.inky_ac073tc1a"
    supported = supported_type()
    unsupported = type("Inky", (), {})()

    assert optimize_ac073tc1a_driver(supported) is True
    assert optimize_ac073tc1a_driver(unsupported) is False
