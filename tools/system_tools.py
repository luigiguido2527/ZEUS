import datetime
import os
import platform
import psutil 

def get_time():
    return f"The current time is {datetime.datetime.now().strftime('%I:%M %p')}."

def get_system_status():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    return f"ZEUS System Health: OS: {platform.system()} | CPU: {cpu}% | RAM: {ram}% | Disk: {disk}%"

def list_files(directory="."):
    try:
        path = directory.strip() if directory else "."
        files = os.listdir(path)
        return f"Files in '{path}': " + ", ".join(files)
    except Exception as e:
        return f"Error accessing path: {e}"

# This is the function the error was complaining about!
def read_file(filepath):
    try:
        path = filepath.strip()
        with open(path, "r") as f:
            return f"Content of {path}:\n{f.read()}"
    except Exception as e:
        return f"Error reading file: {e}"