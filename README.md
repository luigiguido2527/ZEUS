# ZEUS

Zero Effort Universal Sidekick — a local agent with Groq reasoning, tool use, and a frameless PySide6 GUI.

## Setup

```powershell
cd C:\Users\shour\Documents\GitHub\ZEUS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Put your Groq key in `.env` as `GROQ_API_KEY`. Never commit that file.

If a key was previously hardcoded in this repo, rotate it in the Groq dashboard.

## Run

```powershell
python zeus-gui.py    # glass UI
python zeus.py        # terminal
python model-finder.py
```

## Tools

The same agent loop powers CLI and GUI:

| Tag | Action |
| --- | --- |
| `[[GET_TIME]]` | Local clock |
| `[[GET_SYSTEM_STATUS]]` | CPU / RAM / disk |
| `[[LIST_FILES: path]]` | Directory listing |
| `[[READ_FILE: path]]` | Text file (size-capped) |
| `[[SEARCH_WEB: query]]` | Web search |

Memory and recent chat are stored in `zeus_memory.json` and `zeus_history.json` (gitignored).
