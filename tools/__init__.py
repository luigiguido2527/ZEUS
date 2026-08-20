from .research_tools import search_web
from .system_tools import get_system_status, get_time, list_files, read_file

TOOLS = {
    "GET_TIME": get_time,
    "GET_SYSTEM_STATUS": get_system_status,
    "LIST_FILES": list_files,
    "READ_FILE": read_file,
    "SEARCH_WEB": search_web,
}

__all__ = ["TOOLS"]
