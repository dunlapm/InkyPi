import json
import logging
from datetime import date, datetime

import pytz
import requests

from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session


logger = logging.getLogger(__name__)

API_BASE_URL = "https://menus.healthepro.com/api"
LEGACY_ORGANIZATION_ID = 99
REQUEST_TIMEOUT = 30
NEXT_MENU_LOOKAHEAD_MONTHS = 2
HIDDEN_SECTION_NAMES = {"milk", "misc", "misc."}


class SchoolMenu(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["style_settings"] = True
        return template_params

    def get_settings_data(self, resource, params):
        if resource == "organizations":
            return self.get_organizations()
        if resource == "schools":
            organization_id = self._settings_id(
                params.get("organization_id"), "School district"
            )
            return self.get_schools(organization_id)
        if resource == "menus":
            organization_id = self._settings_id(
                params.get("organization_id"), "School district"
            )
            school_id = self._settings_id(params.get("school_id"), "School")
            return self.get_menus(organization_id, school_id)
        raise ValueError(f"Unsupported settings resource: {resource}")

    def generate_image(self, settings, device_config):
        organization_id = self._required_id(
            settings.get("organizationId", LEGACY_ORGANIZATION_ID),
            "School district",
        )
        self._required_id(settings.get("schoolId"), "School")
        menu_id = self._required_id(settings.get("menuId"), "Menu")
        school_name = settings.get("schoolName", "").strip()
        menu_name = settings.get("menuName", "").strip()
        if not school_name or not menu_name:
            raise RuntimeError("School and menu names are required.")

        timezone_name = device_config.get_config(
            "timezone", default="America/New_York"
        )
        try:
            timezone = pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError as e:
            raise RuntimeError(f"Invalid device timezone: {timezone_name}") from e

        today = datetime.now(timezone).date()
        day_menu = self.get_menu_for_display(organization_id, menu_id, today)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        template_params = {
            "school_name": school_name,
            "menu_name": menu_name,
            "date": (
                f"{day_menu['day']:%A, %B} {day_menu['day'].day}"
            ),
            "is_upcoming": day_menu["is_upcoming"],
            "sections": day_menu["sections"],
            "message": day_menu["message"],
            "plugin_settings": settings,
        }
        image = self.render_image(
            dimensions, "school_menu.html", "school_menu.css", template_params
        )
        if not image:
            raise RuntimeError("Failed to render the school menu.")
        return image

    def get_organizations(self):
        state_groups = self._get_api_data("/organizations")
        organizations = []
        for state_group in state_groups:
            state_name = state_group.get("name", "")
            for organization in state_group.get("organizations", []):
                if organization.get("id") and organization.get("name"):
                    organizations.append({
                        "id": organization["id"],
                        "name": organization["name"],
                        "state": organization.get("state") or state_name,
                    })
        return organizations

    def get_schools(self, organization_id):
        data = self._get_api_data(
            f"/organizations/{organization_id}/sites/list"
        )
        return [
            {"id": school["id"], "name": school["name"]}
            for school in data
            if school.get("id") and school.get("name")
        ]

    def get_menus(self, organization_id, school_id):
        data = self._get_api_data(
            f"/organizations/{organization_id}/sites/{school_id}/menus/"
        )
        return [
            {
                "id": menu["id"],
                "name": menu.get("public_name") or menu.get("name"),
            }
            for menu in data
            if menu.get("id") and (menu.get("public_name") or menu.get("name"))
        ]

    def get_day_menu(self, organization_id, menu_id, day):
        entries = self._get_api_data(
            f"/organizations/{organization_id}/menus/{menu_id}"
            f"/year/{day.year}/month/{day.month}/date_overwrites",
            empty_on_statuses=(400, 404),
        )
        entry = next(
            (item for item in entries if item.get("day") == day.isoformat()),
            None,
        )
        if not entry:
            return {"sections": [], "message": "No menu is published for today."}
        return self._menu_from_entry(entry)

    def get_menu_for_display(self, organization_id, menu_id, day):
        fallback = None

        for month_start in self._month_starts(day, NEXT_MENU_LOOKAHEAD_MONTHS + 1):
            entries = self._get_api_data(
                f"/organizations/{organization_id}/menus/{menu_id}"
                f"/year/{month_start.year}/month/{month_start.month}/date_overwrites",
                empty_on_statuses=(400, 404),
            )

            if month_start.year == day.year and month_start.month == day.month:
                entry = next(
                    (item for item in entries if item.get("day") == day.isoformat()),
                    None,
                )
                fallback = (
                    self._menu_from_entry(entry)
                    if entry
                    else {
                        "sections": [],
                        "message": "No menu is published for today.",
                    }
                )
                if fallback["sections"]:
                    return {
                        **fallback,
                        "day": day,
                        "is_upcoming": False,
                    }

            future_entries = sorted(
                (
                    (entry_day, entry)
                    for entry in entries
                    if (entry_day := self._entry_day(entry)) and entry_day > day
                ),
                key=lambda item: item[0],
            )
            for entry_day, entry in future_entries:
                menu = self._menu_from_entry(entry)
                if menu["sections"]:
                    return {
                        **menu,
                        "day": entry_day,
                        "is_upcoming": True,
                    }

        fallback = fallback or {
            "sections": [],
            "message": "No upcoming menu is published.",
        }
        return {**fallback, "day": day, "is_upcoming": False}

    def _menu_from_entry(self, entry):
        current_setting = self._parse_setting(entry.get("setting"))
        if current_setting.get("days_off"):
            return {
                "sections": [],
                "message": self._day_off_message(current_setting["days_off"]),
            }

        display_items = current_setting.get("current_display") or []
        if not display_items:
            original_setting = self._parse_setting(entry.get("setting_original"))
            display_items = original_setting.get("current_display") or []

        sections = self._build_sections(display_items)
        if not sections:
            return {"sections": [], "message": "No menu is published for today."}
        return {"sections": sections, "message": ""}

    @staticmethod
    def _entry_day(entry):
        try:
            return date.fromisoformat(entry.get("day", ""))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _month_starts(day, count):
        month_index = day.year * 12 + day.month - 1
        return [
            date((month_index + offset) // 12, (month_index + offset) % 12 + 1, 1)
            for offset in range(count)
        ]

    def _get_api_data(self, path, empty_on_statuses=()):
        try:
            response = get_http_session().get(
                f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT
            )
            if response.status_code in empty_on_statuses:
                return []
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning("Health-e Pro request failed for %s: %s", path, e)
            raise RuntimeError("Unable to retrieve My School Menus data.") from e

        if not isinstance(payload, dict):
            raise RuntimeError("My School Menus returned an unexpected response.")
        data = payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError("My School Menus returned an unexpected response.")
        return data

    @staticmethod
    def _required_id(value, label):
        try:
            parsed = int(value)
        except (TypeError, ValueError) as e:
            raise RuntimeError(f"{label} is required.") from e
        if parsed <= 0:
            raise RuntimeError(f"{label} is required.")
        return parsed

    @classmethod
    def _settings_id(cls, value, label):
        try:
            return cls._required_id(value, label)
        except RuntimeError as e:
            raise ValueError(str(e)) from e

    @staticmethod
    def _parse_setting(value):
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _day_off_message(days_off):
        if isinstance(days_off, dict):
            days_off = [days_off]
        for day_off in days_off:
            if isinstance(day_off, dict):
                description = str(day_off.get("description", "")).strip()
                if description:
                    return description
        return "No school today."

    @staticmethod
    def _build_sections(display_items):
        sections = []
        current_section = None
        skip_recipes = False

        for item in display_items:
            name = str(item.get("name", "")).strip()
            item_type = item.get("type")
            if not name:
                continue
            if item_type == "category":
                skip_recipes = name.casefold() in HIDDEN_SECTION_NAMES
                if skip_recipes:
                    current_section = None
                    continue
                current_section = {"name": name, "items": []}
                sections.append(current_section)
            elif item_type == "recipe":
                if skip_recipes:
                    continue
                if current_section is None:
                    current_section = {"name": "Menu", "items": []}
                    sections.append(current_section)
                current_section["items"].append(name)

        return [section for section in sections if section["items"]]
