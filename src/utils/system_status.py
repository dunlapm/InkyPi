import os
import socket
import subprocess
import time

import psutil
from PIL import Image, ImageDraw

from utils.app_utils import get_font, get_ip_address, get_wifi_name


def generate_system_status_image(device_config, current_dt):
    dimensions = device_config.get_resolution()
    if device_config.get_config("orientation") == "vertical":
        dimensions = dimensions[::-1]

    width, height = dimensions
    image = Image.new("RGB", dimensions, "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font("Jost", int(min(width, height) * 0.11), "bold")
    label_font = get_font("Jost", int(min(width, height) * 0.048), "bold")
    value_font = get_font("Jost", int(min(width, height) * 0.048))

    draw.text((width * 0.05, height * 0.07), "InkyPi Status", fill="black", font=title_font)
    draw.line(
        (width * 0.05, height * 0.22, width * 0.95, height * 0.22),
        fill="black",
        width=max(2, int(height * 0.008)),
    )

    values = [
        ("Host", socket.gethostname()),
        ("IP address", _safe_value(get_ip_address)),
        ("Wi-Fi", _safe_value(get_wifi_name) or "Not connected"),
        ("Time", current_dt.strftime("%A %I:%M %p").lstrip("0")),
        ("NTP synced", _ntp_status()),
        ("Uptime", _format_uptime()),
        ("CPU temp", _cpu_temperature()),
        ("Disk free", f"{psutil.disk_usage('/').free / (1024 ** 3):.1f} GB"),
    ]

    columns = 2
    rows = (len(values) + columns - 1) // columns
    cell_width = width * 0.45
    row_height = height * 0.17
    for index, (label, value) in enumerate(values):
        column = index // rows
        row = index % rows
        x = width * 0.05 + column * cell_width
        y = height * 0.27 + row * row_height
        draw.text((x, y), label, fill="black", font=label_font)
        draw.text(
            (x, y + height * 0.065),
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
