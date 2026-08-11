import json
import logging
from datetime import datetime

import pytz
import requests

from plugins.base_plugin.base_plugin import BasePlugin
from utils.http_client import get_http_session


logger = logging.getLogger(__name__)

API_BASE_URL = "https://menus.healthepro.com/api"
ORGANIZATION_ID = 99
REQUEST_TIMEOUT = 30


class SchoolMenu(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["style_settings"] = True
        return template_params

    def get_settings_data(self, resource, params):
        if resource == "schools":
            return self.get_schools()
        if resource == "menus":
            try:
                school_id = self._required_id(params.get("school_id"), "School")
            except RuntimeError as e:
                raise ValueError(str(e)) from e
            return self.get_menus(school_id)
        raise ValueError(f"Unsupported settings resource: {resource}")

    def generate_image(self, settings, device_config):
        school_id = self._required_id(settings.get("schoolId"), "School")
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
        day_menu = self.get_day_menu(menu_id, today)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        template_params = {
            "school_name": school_name,
            "menu_name": menu_name,
            "date": today.strftime("%A, %B %d"),
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

    def get_schools(self):
        data = self._get_api_data(
            f"/organizations/{ORGANIZATION_ID}/sites/list"
        )
        return [
            {"id": school["id"], "name": school["name"]}
            for school in data
            if school.get("id") and school.get("name")
        ]

    def get_menus(self, school_id):
        data = self._get_api_data(
            f"/organizations/{ORGANIZATION_ID}/sites/{school_id}/menus/"
        )
        return [
            {
                "id": menu["id"],
                "name": menu.get("public_name") or menu.get("name"),
            }
            for menu in data
            if menu.get("id") and (menu.get("public_name") or menu.get("name"))
        ]

    def get_day_menu(self, menu_id, day):
        data = self._get_api_data(
            f"/organizations/{ORGANIZATION_ID}/menus/{menu_id}"
            f"/year/{day.year}/month/{day.month}/date_overwrites"
        )
        entry = next((item for item in data if item.get("day") == day.isoformat()), None)
        if not entry:
            return {"sections": [], "message": "No menu is published for today."}

        current_setting = self._parse_setting(entry.get("setting"))
        if current_setting.get("days_off"):
            return {"sections": [], "message": "No school today."}

        display_items = current_setting.get("current_display") or []
        if not display_items:
            original_setting = self._parse_setting(entry.get("setting_original"))
            display_items = original_setting.get("current_display") or []

        sections = self._build_sections(display_items)
        if not sections:
            return {"sections": [], "message": "No menu is published for today."}
        return {"sections": sections, "message": ""}

    def _get_api_data(self, path):
        try:
            response = get_http_session().get(
                f"{API_BASE_URL}{path}", timeout=REQUEST_TIMEOUT
            )
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
    def _build_sections(display_items):
        sections = []
        current_section = None

        for item in display_items:
            name = str(item.get("name", "")).strip()
            item_type = item.get("type")
            if not name:
                continue
            if item_type == "category":
                current_section = {"name": name, "items": []}
                sections.append(current_section)
            elif item_type == "recipe":
                if current_section is None:
                    current_section = {"name": "Menu", "items": []}
                    sections.append(current_section)
                current_section["items"].append(name)

        return [section for section in sections if section["items"]]
