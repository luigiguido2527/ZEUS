import os
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

MODEL_ID = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
OPENROUTER_MODEL = MODEL_ID
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "ZEUS")
OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "4096"))
TTS_RATE = int(os.getenv("ZEUS_TTS_RATE", "155"))
API_KEY = OPENROUTER_API_KEY

deadline_value = os.getenv("EXHIBITION_DEADLINE")
if deadline_value:
    EXHIBITION_DEADLINE = datetime.strptime(deadline_value, "%Y-%m-%d")
else:
    EXHIBITION_DEADLINE = datetime.now() + timedelta(days=12)

MEMORY_PATH = ROOT / "zeus_memory.json"
HISTORY_PATH = ROOT / "zeus_history.json"
HISTORY_LIMIT = 20
