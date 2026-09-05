from unittest.mock import patch

from src.utils.app_utils import get_wifi_name


def test_get_wifi_name_uses_active_networkmanager_ssid():
    with patch("src.utils.app_utils.subprocess.run") as run:
        run.return_value.stdout = " :Neighbor\n*:Home Wi-Fi\n"

        assert get_wifi_name() == "Home Wi-Fi"


def test_get_wifi_name_returns_none_without_active_wifi():
    with patch("src.utils.app_utils.subprocess.run") as run:
        run.return_value.stdout = " :Neighbor\n"

        assert get_wifi_name() is None
