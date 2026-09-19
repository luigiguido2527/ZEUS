# ZEUS

Zero Effort Universal Sidekick — a modular, exhibition-ready PySide6 agentic desktop system with a liquid-glass HUD and OpenRouter-backed Nemotron reasoning.

## Project structure

```text
.
├── agent.py
├── config.py
├── memory.py
├── requirements.txt
├── tools/
│   ├── __init__.py
│   ├── research_tools.py
│   └── system_tools.py
├── zeus.py
├── zeus-gui.py
├── web_server.py
├── web/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── zeus_memory.json
├── zeus_history.json
└── .env.example
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set values such as:

```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b
EXHIBITION_DEADLINE=2026-10-05
```

## Run

```powershell
python zeus-gui.py
python zeus.py
# Browser cockpit (local HTTP bridge)
python web_server.py
```

Then open http://127.0.0.1:8765. The web cockpit is a standard-library HTTP
frontend that delegates chat turns to the same `ZeusAgent`; it does not replace
or change the existing PySide6 or terminal entry points.

The dashboard includes responsive sidebar navigation, safe client-side Markdown
rendering, tool activity, conversation history, read-only runtime settings,
CPU/memory/disk telemetry, document uploads (10 MB limit), browser camera
preview, and browser speech-recognition controls where supported. Uploads are
kept in the local `web_uploads/` directory and extracted through the existing
`READ_FILE` pipeline. No WebSocket or third-party frontend dependency is needed.
Camera and microphone permissions are controlled by the browser; media is not
sent to the bridge by the MVP.

## Agent loop

ZEUS can chain tool tags such as `[[GET_SYSTEM_STATUS]]` and `[[SEARCH_WEB: AI trends]]` inside a single reply. The dashboard shows a brief action state before rendering the result.

The `[[READ_FILE: path]]` tool extracts text from plain-text files, Word `.docx`,
PDF `.pdf`, Excel `.xlsx`/`.xlsm`, and PowerPoint `.pptx` documents. Large files
are truncated before being sent to the model.

The GUI sidebar's `UPLOAD FILE` button queues one supported document for the next
text or voice command. The extracted content is sent with that request.

`DEMO MODE` runs a guided exhibition walkthrough in the chat, covering reasoning,
tools, document analysis, voice, camera vision, gesture tracking, desktop-control
safety, and permission prompts. It does not access devices or files automatically.

ZEUS asks for confirmation before executing model-requested tools such as file
reads, directory listings, web searches, and system-status checks. Open the
`CAMERA` panel and enable its `GESTURES` toggle to see live hand landmarks over
the webcam feed. The camera window also includes an opt-in `DESKTOP CONTROL`
mode with an emergency stop and an on-screen gesture guide. Desktop actions are
limited to cursor movement, click, navigation, scrolling, media control, volume,
and screenshots.

## UI notes

- Liquid glass framing
- Deep obsidian background
- Webcam + chat dashboard
- Sidebar health metrics, countdown timer, and live tool status
- Markdown table rendering with electric cyan borders
