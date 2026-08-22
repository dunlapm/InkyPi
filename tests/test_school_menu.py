import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.plugins.school_menu.school_menu import SchoolMenu


@pytest.fixture
def plugin():
    return SchoolMenu({"id": "school_menu"})


def make_entry(day, current_display, original_display=None, days_off=None):
    setting = json.dumps(
        {
            "current_display": current_display,
            "days_off": days_off or [],
        }
    )
    original = json.dumps(
        {
            "current_display": original_display or [],
            "days_off": [],
        }
    )
    return {
        "day": day.isoformat(),
        "setting": setting,
        "setting_original": original,
    }


def test_get_day_menu_builds_sections(plugin):
    day = date(2026, 8, 10)
    entry = make_entry(
        day,
        [
            {"type": "category", "name": "Entree"},
            {"type": "recipe", "name": "Cheese Pizza"},
            {"type": "category", "name": "Fruit"},
            {"type": "recipe", "name": "Apple Slices"},
        ],
    )

    with patch.object(plugin, "_get_api_data", return_value=[entry]):
        result = plugin.get_day_menu(99, 123, day)

    assert result["message"] == ""
    assert result["sections"] == [
        {"name": "Entree", "items": ["Cheese Pizza"]},
        {"name": "Fruit", "items": ["Apple Slices"]},
    ]


def test_get_day_menu_falls_back_to_original_setting(plugin):
    day = date(2026, 8, 10)
    entry = make_entry(
        day,
        [],
        [
            {"type": "category", "name": "Entree"},
            {"type": "recipe", "name": "Chicken Sandwich"},
        ],
    )

    with patch.object(plugin, "_get_api_data", return_value=[entry]):
        result = plugin.get_day_menu(99, 123, day)

    assert result["sections"][0]["items"] == ["Chicken Sandwich"]


def test_get_day_menu_handles_day_off(plugin):
    day = date(2026, 8, 10)
    entry = make_entry(day, [], days_off={"description": "Labor Day"})

    with patch.object(plugin, "_get_api_data", return_value=[entry]):
        result = plugin.get_day_menu(99, 123, day)

    assert result == {"sections": [], "message": "Labor Day"}


def test_get_day_menu_handles_missing_date(plugin):
    with patch.object(plugin, "_get_api_data", return_value=[]):
        result = plugin.get_day_menu(99, 123, date(2026, 8, 10))

    assert result == {
        "sections": [],
        "message": "No menu is published for today.",
    }


def test_get_menus_prefers_public_name(plugin):
    with patch.object(
        plugin,
        "_get_api_data",
        return_value=[
            {"id": 1, "name": "Internal", "public_name": "Lunch"},
            {"id": 2, "name": "Breakfast", "public_name": None},
        ],
    ) as get_api_data:
        menus = plugin.get_menus(99, 744)

    assert menus == [
        {"id": 1, "name": "Lunch"},
        {"id": 2, "name": "Breakfast"},
    ]
    get_api_data.assert_called_once_with(
        "/organizations/99/sites/744/menus/"
    )


def test_get_organizations_flattens_state_groups(plugin):
    with patch.object(
        plugin,
        "_get_api_data",
        return_value=[
            {
                "name": "Washington",
                "organizations": [
                    {"id": 99, "name": "Bellevue School District", "state": "Washington"}
                ],
            }
        ],
    ):
        organizations = plugin.get_organizations()

    assert organizations == [
        {
            "id": 99,
            "name": "Bellevue School District",
            "state": "Washington",
        }
    ]


def test_settings_data_rejects_invalid_school(plugin):
    with pytest.raises(ValueError, match="School is required"):
        plugin.get_settings_data(
            "menus", {"organization_id": "99", "school_id": "not-a-number"}
        )


def test_settings_data_requires_district(plugin):
    with pytest.raises(ValueError, match="School district is required"):
        plugin.get_settings_data("schools", {})


def test_api_failure_has_user_friendly_error(plugin):
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("network details")

    with patch(
        "src.plugins.school_menu.school_menu.get_http_session"
    ) as get_session:
        get_session.return_value.get.return_value = response
        with pytest.raises(RuntimeError, match="Unable to retrieve"):
            plugin._get_api_data("/test")


def test_unpublished_month_is_empty(plugin):
    response = MagicMock(status_code=400)

    with patch(
        "src.plugins.school_menu.school_menu.get_http_session"
    ) as get_session:
        get_session.return_value.get.return_value = response
        result = plugin._get_api_data("/test", empty_on_statuses=(400, 404))

    assert result == []
    response.raise_for_status.assert_not_called()
