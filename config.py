import os
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

MODEL_ID = os.getenv("ZEUS_MODEL", "openai/gpt-oss-120b")
VISION_MODEL = os.getenv("ZEUS_VISION_MODEL", "qwen/qwen3.6-27b")
API_KEY = os.getenv("GROQ_API_KEY", "").strip()
MEMORY_PATH = ROOT / "zeus_memory.json"
HISTORY_PATH = ROOT / "zeus_history.json"
HISTORY_LIMIT = 20
MODELS_DIR = ROOT / "models"
YOLO_ONNX_URL = os.getenv(
    "ZEUS_YOLO_URL",
    "https://huggingface.co/Kalray/yolov8/resolve/main/yolov8n.onnx",
)
