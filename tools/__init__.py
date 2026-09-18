from .research_tools import search_web
from .system_tools import get_system_status, get_time, list_files, read_file
from .vision_tools import identify_image, see_screen, see_webcam

TOOLS = {
    "GET_TIME": get_time,
    "GET_SYSTEM_STATUS": get_system_status,
    "LIST_FILES": list_files,
    "READ_FILE": read_file,
    "SEARCH_WEB": search_web,
    "SEE_SCREEN": see_screen,
    "SEE_WEBCAM": see_webcam,
    "IDENTIFY_IMAGE": identify_image,
}

__all__ = ["TOOLS"]
