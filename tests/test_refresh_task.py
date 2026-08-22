from datetime import datetime
from unittest.mock import MagicMock

import pytest
from PIL import Image

from src.refresh_task import PlaylistRefresh, RefreshTask


@pytest.mark.parametrize(
    "current,interval,expected",
    [
        (datetime(2026, 8, 10, 12, 15, 0), 3600, 2700),
        (datetime(2026, 8, 10, 12, 59, 30), 3600, 30),
        (datetime(2026, 8, 10, 12, 0, 50), 3600, 3550),
        (datetime(2026, 8, 10, 12, 2, 30), 300, 150),
        (datetime(2026, 8, 10, 12, 0, 0), 3600, 3600),
    ],
)
def test_seconds_until_next_interval(current, interval, expected):
    assert RefreshTask._seconds_until_next_interval(current, interval) == expected


def test_seconds_until_next_interval_handles_nonpositive_interval():
    current = datetime(2026, 8, 10, 12, 0, 0, 500000)

    assert RefreshTask._seconds_until_next_interval(current, 0) == 0.5


def test_playlist_navigation_uses_cached_image(tmp_path):
    cached_image = Image.new("RGB", (2, 2), "red")
    cached_image.save(tmp_path / "weather_weather.png")
    plugin_instance = MagicMock()
    plugin_instance.plugin_id = "weather"
    plugin_instance.name = "weather"
    plugin_instance.get_image_path.return_value = "weather_weather.png"
    device_config = MagicMock(plugin_image_dir=str(tmp_path))
    plugin = MagicMock()
    refresh = PlaylistRefresh(
        MagicMock(name="Default"),
        plugin_instance,
        use_cached=True,
    )

    image = refresh.execute(plugin, device_config, datetime(2026, 8, 21))

    assert image.getpixel((0, 0)) == (255, 0, 0)
    plugin.generate_image.assert_not_called()
    plugin_instance.should_refresh.assert_not_called()
