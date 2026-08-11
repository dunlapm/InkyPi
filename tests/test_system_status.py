from datetime import datetime
from unittest.mock import MagicMock, patch

from src.refresh_task import SystemStatusRefresh
from src.utils.system_status import generate_system_status_image


def test_generate_system_status_image():
    config = MagicMock()
    config.get_resolution.return_value = [800, 480]
    config.get_config.return_value = "horizontal"

    with (
        patch("src.utils.system_status.get_ip_address", return_value="192.168.1.103"),
        patch("src.utils.system_status.get_wifi_name", return_value="Home Wi-Fi"),
        patch("src.utils.system_status._ntp_status", return_value="Yes"),
        patch("src.utils.system_status._format_uptime", return_value="2d 3h"),
        patch("src.utils.system_status._cpu_temperature", return_value="42 C"),
        patch("src.utils.system_status.psutil.disk_usage") as disk_usage,
    ):
        disk_usage.return_value.free = 10 * 1024 ** 3
        image = generate_system_status_image(
            config, datetime(2026, 8, 11, 9, 30)
        )

    assert image.size == (800, 480)
    assert image.mode == "RGB"


def test_system_status_is_transient_and_does_not_require_plugin():
    refresh = SystemStatusRefresh()

    assert refresh.requires_plugin() is False
    assert refresh.updates_schedule() is False
