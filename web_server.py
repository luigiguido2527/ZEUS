"""Local-only HTTP bridge for the ZEUS agent and responsive browser cockpit."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import platform
import threading
import uuid
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psutil

from agent import ZeusAgent, require_api_key
from config import HISTORY_LIMIT, HISTORY_PATH, MODEL_ID, OPENROUTER_BASE_URL, TTS_RATE
from memory import load_json
from tools.system_tools import MAX_READ_CHARS, read_file

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
UPLOAD_ROOT = ROOT / "web_uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class ZeusWebState:
    def __init__(self) -> None:
        self._agent: ZeusAgent | None = None
        self._lock = threading.Lock()
        self.status = "idle"
        self.last_tools: list[str] = []
        self.last_error = ""

    def configured(self) -> bool:
        try:
            require_api_key()
        except RuntimeError:
            return False
        return True

    def turn(self, message: str, attachment: str = "") -> dict[str, Any]:
        message = message.strip()
        if not message:
            raise ValueError("message must not be empty")
        with self._lock:
            if self._agent is None:
                self._agent = ZeusAgent()
            self.status, self.last_error, self.last_tools = "thinking", "", []
            try:
                reply = self._agent.run_turn(
                    message,
                    file_data=attachment[:MAX_READ_CHARS] if attachment else None,
                    on_tool=lambda name: self.last_tools.append(name),
                )
                return {"reply": reply, "tools": self.last_tools}
            except Exception as exc:
                self.last_error = str(exc)
                raise
            finally:
                self.status = "idle"

    def history(self) -> list[dict[str, str]]:
        with self._lock:
            source = self._agent.messages if self._agent else load_json(HISTORY_PATH, [])
            return [
                {"role": item["role"], "content": str(item.get("content", ""))}
                for item in source
                if item["role"] != "system"
            ][-HISTORY_LIMIT:]

    def snapshot(self) -> dict[str, Any]:
        return {"status": self.status, "configured": self.configured(),
                "tools": self.last_tools, "error": self.last_error}


STATE = ZeusWebState()


def metrics() -> dict[str, Any]:
    root = os.path.splitdrive(os.getcwd())[0] + "\\" if platform.system() == "Windows" else "/"
    return {"cpu": psutil.cpu_percent(interval=0.05), "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage(root).percent, "os": platform.system(),
            "python": platform.python_version()}


class ZeusHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def _json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_UPLOAD_BYTES:
            raise ValueError("request is too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/api/health", "/api/state"}:
            self._json({"ok": True, **STATE.snapshot()})
        elif path == "/api/history":
            self._json({"messages": STATE.history()})
        elif path == "/api/metrics":
            self._json(metrics())
        elif path == "/api/settings":
            self._json({"model": MODEL_ID, "base_url": OPENROUTER_BASE_URL,
                        "history_limit": HISTORY_LIMIT, "tts_rate": TTS_RATE,
                        "local_only": True})
        else:
            super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/chat":
                body = self._body()
                self._json(STATE.turn(str(body.get("message", "")), str(body.get("attachment", ""))))
            elif path == "/api/upload":
                self._upload()
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _upload(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("use multipart/form-data")
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_UPLOAD_BYTES:
            raise ValueError("file exceeds 10 MB limit")
        raw = self.rfile.read(length)
        message = BytesParser(policy=default).parsebytes(
            b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + raw
        )
        part = next((p for p in message.walk() if p.get_filename()), None)
        if part is None:
            raise ValueError("no file supplied")
        name = Path(part.get_filename()).name
        target = UPLOAD_ROOT / f"{uuid.uuid4().hex}_{name}"
        UPLOAD_ROOT.mkdir(exist_ok=True)
        target.write_bytes(part.get_payload(decode=True) or b"")
        extracted = read_file(str(target))
        self._json({"name": name, "size": target.stat().st_size,
                    "content": extracted[:MAX_READ_CHARS]})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[web] {self.address_string()} - {format % args}")


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), ZeusHandler)
    print(f"ZEUS web UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ZEUS web UI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the local ZEUS web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run(args.host, args.port)
