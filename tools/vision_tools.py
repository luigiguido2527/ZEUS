"""Capture a view, show it, and identify what is in it."""

from __future__ import annotations

import base64
import time
import urllib.request
from collections import Counter
from pathlib import Path

from config import API_KEY, MODELS_DIR, VISION_MODEL, YOLO_ONNX_URL

COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

INPUT_SIZE = 640
CONF_THRESHOLD = 0.28
IOU_THRESHOLD = 0.45
MODEL_PATH = MODELS_DIR / "yolov8n.onnx"
PREVIEW_PATH = MODELS_DIR / "last_view.jpg"

last_preview_path: str | None = None
_session = None


def consume_preview() -> str | None:
    global last_preview_path
    path = last_preview_path
    last_preview_path = None
    return path


def _deps_error() -> str | None:
    missing = []
    try:
        import cv2  # noqa: F401
    except ImportError:
        missing.append("opencv-python")
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        missing.append("onnxruntime")
    try:
        from PIL import ImageGrab  # noqa: F401
    except ImportError:
        missing.append("pillow")
    if not missing:
        return None
    return (
        "Vision deps missing: "
        + ", ".join(missing)
        + ". Run: pip install opencv-python onnxruntime numpy pillow"
    )


def _ensure_model() -> Path:
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_000_000:
        return MODEL_PATH
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MODEL_PATH.with_suffix(".onnx.part")
    req = urllib.request.Request(
        YOLO_ONNX_URL,
        headers={"User-Agent": "ZEUS-vision/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as out:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        tmp.replace(MODEL_PATH)
    except Exception as e:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Could not download YOLOv8n ({YOLO_ONNX_URL}): {e}"
        ) from e
    return MODEL_PATH


def _session_ort():
    global _session
    if _session is None:
        import onnxruntime as ort

        _ensure_model()
        _session = ort.InferenceSession(
            str(MODEL_PATH), providers=["CPUExecutionProvider"]
        )
    return _session


def _letterbox(bgr, size: int = INPUT_SIZE):
    import cv2
    import numpy as np

    h, w = bgr.shape[:2]
    scale = min(size / h, size / w)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top = (size - nh) // 2
    left = (size - nw) // 2
    canvas[top : top + nh, left : left + nw] = resized
    return canvas, scale, left, top


def _detect(bgr) -> list[dict]:
    import cv2
    import numpy as np

    try:
        session = _session_ort()
    except Exception:
        return []

    blob, scale, pad_x, pad_y = _letterbox(bgr)
    rgb = cv2.cvtColor(blob, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    tensor = np.transpose(rgb, (2, 0, 1))[None, ...]
    inp_name = session.get_inputs()[0].name
    raw = session.run(None, {inp_name: tensor})[0]
    pred = np.squeeze(raw)

    if pred.ndim != 2:
        return []
    if pred.shape[0] < pred.shape[1]:
        pred = pred.T

    cls_scores = pred[:, 4:]
    class_ids = np.argmax(cls_scores, axis=1)
    confs = cls_scores[np.arange(pred.shape[0]), class_ids]
    keep = confs >= CONF_THRESHOLD
    if not np.any(keep):
        return []

    xywh = pred[keep, :4]
    confs = confs[keep]
    class_ids = class_ids[keep]
    boxes = np.column_stack(
        (xywh[:, 0] - xywh[:, 2] / 2, xywh[:, 1] - xywh[:, 3] / 2, xywh[:, 2], xywh[:, 3])
    ).tolist()
    scores = confs.tolist()

    indices = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESHOLD, IOU_THRESHOLD)
    if indices is None or len(indices) == 0:
        return []
    indices = np.array(indices).flatten()

    detections = []
    ih, iw = bgr.shape[:2]
    for i in indices:
        x, y, w, h = boxes[i]
        x1 = int((x - pad_x) / scale)
        y1 = int((y - pad_y) / scale)
        x2 = int((x + w - pad_x) / scale)
        y2 = int((y + h - pad_y) / scale)
        class_id = int(class_ids[i])
        name = COCO_NAMES[class_id] if class_id < len(COCO_NAMES) else "object"
        detections.append(
            {
                "label": name,
                "confidence": float(scores[i]),
                "box": (max(0, x1), max(0, y1), min(iw, x2), min(ih, y2)),
            }
        )
    return detections


def _count_faces(bgr) -> int:
    import cv2

    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    if not cascade_path.exists():
        return 0
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = cv2.CascadeClassifier(str(cascade_path)).detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)
    )
    return len(faces)


def _annotate(bgr, detections: list[dict]):
    import cv2

    out = bgr.copy()
    for det in detections:
        x1, y1, x2, y2 = det["box"]
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 180, 255), 2)
        tag = f"{det['label']} {det['confidence']:.0%}"
        cv2.putText(
            out, tag, (x1, max(18, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 180, 255), 2, cv2.LINE_AA,
        )
    return out


def _save_preview(bgr) -> str:
    import cv2

    global last_preview_path
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("Could not encode preview JPEG.")
    buf.tofile(str(PREVIEW_PATH))
    last_preview_path = str(PREVIEW_PATH)
    return last_preview_path


def _jpeg_for_api(bgr, max_side: int = 1280) -> bytes:
    import cv2

    h, w = bgr.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        bgr = cv2.resize(
            bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
        )
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise RuntimeError("Could not encode vision JPEG.")
    return buf.tobytes()


def _see_with_vlm(jpeg_bytes: bytes) -> str | None:
    if not API_KEY:
        return None
    from groq import Groq

    payload = base64.b64encode(jpeg_bytes).decode("ascii")
    client = Groq(api_key=API_KEY)
    completion = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are ZEUS vision. Describe what is actually visible. "
                            "Identify people, objects, on-screen text, windows, and the scene. "
                            "Be concrete and concise. Do not mention that you are an AI."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{payload}"},
                    },
                ],
            }
        ],
        temperature=0.2,
        max_completion_tokens=700,
    )
    msg = completion.choices[0].message
    text = (msg.content or "").strip()
    if text:
        return text
    reasoning = getattr(msg, "reasoning", None)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return None


def _describe(source: str, bgr) -> str:
    detections = _detect(bgr)
    faces = _count_faces(bgr)
    preview = _annotate(bgr, detections) if detections else bgr
    _save_preview(preview)

    grouped: Counter[str] = Counter()
    best: dict[str, float] = {}
    for det in detections:
        grouped[det["label"]] += 1
        best[det["label"]] = max(best.get(det["label"], 0.0), det["confidence"])

    h, w = bgr.shape[:2]
    lines = [f"--- VISION: {source} ---", f"Resolution: {w}x{h}"]
    try:
        seen = _see_with_vlm(_jpeg_for_api(bgr))
        if seen:
            lines.append("What I see:")
            lines.append(seen)
    except Exception as e:
        lines.append(f"Vision language model failed ({e}). Using local detector only.")

    if grouped:
        lines.append("Local detector:")
        for label, count in grouped.most_common():
            extra = f" x{count}" if count > 1 else ""
            lines.append(f"- {label}{extra} ({best[label]:.0%})")
    if faces:
        lines.append(f"Faces detected: {faces}")
    lines.append(f"Preview saved: {PREVIEW_PATH}")
    return "\n".join(lines)


def _load_image(path: str):
    import cv2
    import numpy as np
    from PIL import Image

    bgr = None
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size:
            bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
    except OSError:
        bgr = None
    if bgr is None:
        with Image.open(path) as im:
            bgr = cv2.cvtColor(np.array(im.convert("RGB")), cv2.COLOR_RGB2BGR)
    return bgr


def _ready() -> str | None:
    return _deps_error()


def see_screen(_arg: str | None = None) -> str:
    """Capture the desktop, save a preview, and identify what is visible."""
    ready = _ready()
    if ready:
        return ready
    try:
        from PIL import ImageGrab
        import cv2
        import numpy as np

        time.sleep(0.4)
        shot = ImageGrab.grab(all_screens=True)
        bgr = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        return _describe("SCREEN", bgr)
    except Exception as e:
        return f"Screen capture failed: {e}"


def see_webcam(camera: str | None = None) -> str:
    """Grab a webcam frame, save a preview, and identify what is in view."""
    ready = _ready()
    if ready:
        return ready
    try:
        import cv2

        raw = (camera or "0").strip() or "0"
        try:
            index = int(raw)
        except ValueError:
            return f"Invalid camera index: {raw!r}. Use 0, 1, ..."

        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            return (
                f"Could not open webcam {index}. Grant camera permission and "
                "close other apps using it."
            )

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        frame = None
        for _ in range(12):
            ok, grabbed = cap.read()
            if ok and grabbed is not None:
                frame = grabbed
            time.sleep(0.04)
        cap.release()
        if frame is None:
            return f"Webcam {index} opened but returned no frame."
        return _describe(f"WEBCAM {index}", frame)
    except Exception as e:
        return f"Webcam capture failed: {e}"


def identify_image(filepath: str | None = None) -> str:
    """Identify objects in an image file and save a labeled preview."""
    ready = _ready()
    if ready:
        return ready
    path = (filepath or "").strip().strip('"')
    if not path:
        return "Provide an image path: [[IDENTIFY_IMAGE: C:\\path\\photo.jpg]]"
    try:
        bgr = _load_image(path)
        return _describe(f"IMAGE {path}", bgr)
    except Exception as e:
        return f"Image identify failed: {e}"
