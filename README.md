# ZEUS

Zero Effort Universal Sidekick — a local agent with Groq reasoning, tool use, and a frameless PySide6 GUI.

## Setup

```powershell
cd C:\Users\
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Put Groq key in `.env`.

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
| `[[SEE_SCREEN]]` | Screenshot + identify objects (local YOLOv8n) |
| `[[SEE_WEBCAM]]` | Webcam frame + identify objects / faces |
| `[[IDENTIFY_IMAGE: path]]` | Identify objects in an image file |

Vision runs fully offline after the first start (downloads a ~13MB YOLOv8n ONNX model into `models/`). It recognizes 80 everyday COCO classes plus Haar face counts — no paid vision API.

Memory and recent chat are stored in `zeus_memory.json` and `zeus_history.json` (gitignored).
