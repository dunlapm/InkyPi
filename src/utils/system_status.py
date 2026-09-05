import os
import socket
import subprocess
import time
from pathlib import Path

import psutil
from PIL import Image, ImageDraw

from utils.app_utils import get_font, get_ip_address, get_wifi_name


WATCHDOG_STATE_DIR = Path("/var/lib/inkypi-network-watchdog")


def generate_system_status_image(device_config, current_dt):
    dimensions = device_config.get_resolution()
    if device_config.get_config("orientation") == "vertical":
        dimensions = dimensions[::-1]

    width, height = dimensions
    image = Image.new("RGB", dimensions, "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font("Jost", int(min(width, height) * 0.11), "bold")
    label_font = get_font("Jost", int(min(width, height) * 0.04), "bold")
    value_font = get_font("Jost", int(min(width, height) * 0.04))

    draw.text((width * 0.05, height * 0.07), "InkyPi Status", fill="black", font=title_font)
    draw.line(
        (width * 0.05, height * 0.22, width * 0.95, height * 0.22),
        fill="black",
        width=max(2, int(height * 0.008)),
    )

    values = [
        ("Host", socket.gethostname()),
        ("Wi-Fi association", _safe_value(get_wifi_name) or "Disconnected"),
        ("Assigned IP", _safe_value(get_ip_address) or "Unavailable"),
        ("Gateway", _gateway_status()),
        ("DNS lookup", _connection_status("menus.healthepro.com", 443)),
        ("Internet", _connection_status("1.1.1.1", 443)),
        ("Network restart", _state_age("last-network-restart", "Never")),
        ("Current outage", _state_age("outage-start", "None", include_ago=False)),
        ("Oldest data", _oldest_cache_age(device_config)),
        ("Time", current_dt.strftime("%A %I:%M %p").lstrip("0")),
        ("NTP synced", _ntp_status()),
        ("Uptime", _format_uptime()),
        ("CPU temp", _cpu_temperature()),
        ("Disk free", f"{psutil.disk_usage('/').free / (1024 ** 3):.1f} GB"),
    ]

    columns = 2
    rows = (len(values) + columns - 1) // columns
    cell_width = width * 0.45
    row_height = height * 0.1
    for index, (label, value) in enumerate(values):
        column = index // rows
        row = index % rows
        x = width * 0.05 + column * cell_width
        y = height * 0.25 + row * row_height
        draw.text((x, y), label, fill="black", font=label_font)
        draw.text(
            (x, y + height * 0.052),
            str(value),
            fill="black",
            font=value_font,
        )

    return image


def _safe_value(callback):
    try:
        return callback()
    except (OSError, subprocess.SubprocessError):
        return None


def _ntp_status():
    try:
        result = subprocess.run(
            ["timedatectl", "show", "--property=NTPSynchronized", "--value"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        return "Yes" if result.stdout.strip() == "yes" else "No"
    except (OSError, subprocess.SubprocessError):
        return "Unknown"


def _format_uptime():
    seconds = max(0, int(time.time() - psutil.boot_time()))
    days, remainder = divmod(seconds, 86400)
    hours, _ = divmod(remainder, 3600)
    return f"{days}d {hours}h"


def _cpu_temperature():
    temperatures = psutil.sensors_temperatures()
    for sensor_name in ("cpu_thermal", "coretemp"):
        readings = temperatures.get(sensor_name)
        if readings:
            return f"{readings[0].current:.0f} C"
    return "Unavailable"


def _gateway_status():
    gateway = _default_gateway()
    if not gateway:
        return "Unavailable"
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", gateway],
            capture_output=True,
            timeout=2,
            check=False,
        )
        return f"OK ({gateway})" if result.returncode == 0 else "Unreachable"
    except (OSError, subprocess.SubprocessError):
        return "Unknown"


def _default_gateway():
    try:
        with open("/proc/net/route", encoding="ascii") as routes:
            for route in routes:
                fields = route.split()
                if len(fields) > 2 and fields[1] == "00000000":
                    raw = bytes.fromhex(fields[2])
                    return socket.inet_ntoa(raw[::-1])
    except (OSError, ValueError):
        return None
    return None


def _connection_status(host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            return "OK"
    except socket.gaierror:
        return "DNS failed"
    except OSError:
        return "Unreachable"


def _oldest_cache_age(device_config):
    image_dir = Path(device_config.plugin_image_dir)
    cache_times = [
        image.stat().st_mtime
        for image in image_dir.glob("*.png")
        if image.is_file()
    ]
    if not cache_times:
        return "No cached data"

    seconds = max(0, int(time.time() - min(cache_times)))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours}h ago"
    if hours:
        return f"{hours}h {minutes}m ago"
    return f"{minutes}m ago"


def _state_age(filename, missing_value, include_ago=True):
    state_file = WATCHDOG_STATE_DIR / filename
    try:
        timestamp = int(state_file.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return missing_value
    duration = _format_duration(max(0, int(time.time()) - timestamp))
    return f"{duration} ago" if include_ago else duration


def _format_duration(seconds):
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
