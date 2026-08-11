from unittest.mock import Mock

from src.button_controller import ButtonController
from src.model import Playlist


def test_button_controller_coalesces_pending_actions():
    controller = ButtonController(Mock())

    assert controller.submit_action("next") is True
    assert controller.submit_action("refresh") is False
    assert controller.action_queue.get_nowait() == "next"


def test_playlist_relative_navigation_wraps():
    playlist = Playlist(
        "Default",
        "00:00",
        "24:00",
        [
            {
                "plugin_id": "weather",
                "name": "Weather",
                "plugin_settings": {},
                "refresh": {"interval": 3600},
            },
            {
                "plugin_id": "clock",
                "name": "Clock",
                "plugin_settings": {},
                "refresh": {"interval": 60},
            },
        ],
    )

    assert playlist.get_current_plugin().name == "Weather"
    assert playlist.get_previous_plugin().name == "Clock"
    assert playlist.get_next_plugin().name == "Weather"


def test_previous_selects_last_plugin_when_nothing_selected():
    playlist = Playlist(
        "Default",
        "00:00",
        "24:00",
        [
            {
                "plugin_id": "weather",
                "name": "Weather",
                "plugin_settings": {},
                "refresh": {"interval": 3600},
            },
            {
                "plugin_id": "clock",
                "name": "Clock",
                "plugin_settings": {},
                "refresh": {"interval": 60},
            },
        ],
    )

    assert playlist.get_previous_plugin().name == "Clock"
