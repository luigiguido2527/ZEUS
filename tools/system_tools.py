import datetime
import os
import platform

import psutil

MAX_LIST_ENTRIES = 80
MAX_READ_CHARS = 80_000


def get_time():
    now = datetime.datetime.now().strftime("%I:%M %p")
    return f"The current time is {now}."


def get_system_status():
    cpu = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory().percent
    if platform.system() == "Windows":
        root = os.path.splitdrive(os.getcwd())[0] + "\\"
    else:
        root = "/"
    disk = psutil.disk_usage(root).percent
    return (
        f"ZEUS System Health: OS: {platform.system()} | "
        f"CPU: {cpu}% | RAM: {ram}% | Disk: {disk}%"
    )


def list_files(directory="."):
    try:
        path = (directory or ".").strip() or "."
        names = os.listdir(path)
        extra = ""
        if len(names) > MAX_LIST_ENTRIES:
            extra = f" ... (+{len(names) - MAX_LIST_ENTRIES} more)"
            names = names[:MAX_LIST_ENTRIES]
        return f"Files in '{path}': " + ", ".join(names) + extra
    except Exception as e:
        return f"Error accessing path: {e}"


def read_file(filepath):
    try:
        path = filepath.strip()
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(MAX_READ_CHARS + 1)
        if len(text) > MAX_READ_CHARS:
            text = text[:MAX_READ_CHARS] + "\n... [truncated]"
        return f"Content of {path}:\n{text}"
    except Exception as e:
        return f"Error reading file: {e}"
