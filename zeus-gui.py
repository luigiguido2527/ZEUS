import base64
import sys
import threading
import urllib.request
import urllib.error
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QThread, Signal, Slot, QRectF, QTimer
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QLinearGradient,
    QPen,
    QFont,
    QGuiApplication,
    QImage,
    QPixmap,
)
import pyttsx3
import speech_recognition as sr
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QGraphicsDropShadowEffect,
    QDialog,
    QMessageBox,
    QFileDialog,
)
import cv2
import pyautogui

from agent import ZeusAgent
from config import API_KEY, OPENROUTER_MODEL, TTS_RATE
from tools.system_tools import read_file


def ui_font(size: int = 11, bold: bool = False) -> QFont:
    font = QFont("Consolas", size)
    if font.family() != "Consolas":
        font = QFont("Roboto", size)
    if bold:
        font.setBold(True)
    return font


class AgentWorker(QObject):
    tool_started = Signal(str)
    tool_confirmation_requested = Signal(str, str, object)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, agent: ZeusAgent):
        super().__init__()
        self.agent = agent

    @Slot(str, object, object)
    def run_turn(
        self,
        user_text: str,
        image_data: str | None = None,
        file_data: str | None = None,
    ):
        try:
            result = self.agent.run_turn(
                user_text,
                on_tool=self.tool_started.emit,
                approve_tool=self._approve_tool,
                image_data=image_data,
                file_data=file_data,
            )
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))

    def _approve_tool(self, name: str, argument: str | None) -> bool:
        decision = [False]
        completed = threading.Event()
        self.tool_confirmation_requested.emit(name, argument or "", (completed, decision))
        completed.wait()
        return decision[0]


class VoiceWorker(QObject):
    recognized = Signal(str)
    status = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self):
        super().__init__()

    @Slot()
    def listen(self):
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as microphone:
                recognizer.adjust_for_ambient_noise(microphone, duration=0.6)
                self.status.emit("● LISTENING")
                audio = recognizer.listen(microphone, timeout=8, phrase_time_limit=8)
                self.status.emit("● TRANSCRIBING")
                try:
                    text = recognizer.recognize_google(audio).strip()
                except sr.UnknownValueError:
                    text = ""
                except sr.RequestError as exc:
                    self.failed.emit(f"Speech recognition unavailable: {exc}")
                    return
                if text:
                    self.recognized.emit(text)
                else:
                    self.failed.emit("I could not understand that.")
        except sr.WaitTimeoutError:
            self.failed.emit("No speech detected.")
        except (OSError, AttributeError) as exc:
            self.failed.emit(f"Microphone unavailable: {exc}")
        finally:
            self.finished.emit()


class GlassFrame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        radius = 18.0
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, QColor(10, 10, 10, 180))
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(255, 255, 255, int(255 * 0.20)))
        grad.setColorAt(1.0, QColor(255, 255, 255, int(255 * 0.05)))
        painter.strokePath(path, QPen(grad, 1.0))


class HeaderBar(QWidget):
    def __init__(self, window: QWidget):
        super().__init__()
        self._window = window
        self._drag_offset = None
        self.setFixedHeight(44)
        self.setCursor(Qt.SizeAllCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        event.accept()


class Bubble(QFrame):
    def __init__(self, text: str, kind: str):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setFont(ui_font(11))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(label)
        if kind == "user":
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(180, 28, 40, 210),
                        stop:1 rgba(120, 16, 28, 180));
                    border: 1px solid rgba(255, 120, 130, 70);
                    border-radius: 16px;
                    border-top-right-radius: 4px;
                }
                QLabel { color: #FFE8EA; background: transparent; }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(180, 140, 20, 200),
                        stop:1 rgba(90, 70, 10, 170));
                    border: 1px solid rgba(255, 215, 0, 80);
                    border-radius: 16px;
                    border-top-left-radius: 4px;
                }
                QLabel { color: #FFF4C2; background: transparent; }
            """)


class ChatRow(QWidget):
    def __init__(self, text: str, kind: str):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.kind = kind
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 4, 4, 4)
        self.bubble = Bubble(text, kind)
        if kind == "user":
            row.addStretch()
            row.addWidget(self.bubble, 0, Qt.AlignRight)
        else:
            row.addWidget(self.bubble, 0, Qt.AlignLeft)
            row.addStretch()

    def resizeEvent(self, event):
        cap = max(240, int(self.width() * 0.76))
        self.bubble.setMaximumWidth(cap)
        super().resizeEvent(event)


class CameraDialog(QDialog):
    captured = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ZEUS CAMERA")
        self.setModal(False)
        self.resize(520, 420)
        self.capture = cv2.VideoCapture(0)
        self.gesture_enabled = False
        self.hands = None
        self.mp = None
        self.desktop_enabled = False
        self.last_center = None
        self.last_action_at = 0.0
        self.pinch_active = False
        pyautogui.FAILSAFE = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)

        layout = QVBoxLayout(self)
        self.preview = QLabel("Opening webcam...")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(480, 320)
        self.preview.setStyleSheet("background: #080808; color: #D4AF37;")
        layout.addWidget(self.preview)

        self.gesture_status = QLabel("GESTURES OFF")
        self.gesture_status.setStyleSheet("color: #8F9AA8; font-weight: bold;")
        layout.addWidget(self.gesture_status)

        guide = QLabel(
            "<b>GESTURE GUIDE</b><br>"
            "• Point: move cursor<br>"
            "• Pinch: click / release<br>"
            "• Swipe left/right: app or slide navigation<br>"
            "• Swipe up/down: scroll<br>"
            "• Fist: play / pause<br>"
            "• Victory: screenshot<br>"
            "• Open palm: emergency stop<br>"
            "• Thumb up: confirm / volume up<br>"
            "• Thumb down: cancel / volume down<br><br>"
            "<b>SAFETY</b><br>"
            "Tracking only draws landmarks.<br>"
            "Enable DESKTOP CONTROL to act.<br>"
            "Hold gestures briefly to trigger."
        )
        guide.setWordWrap(True)
        guide.setStyleSheet("color: #C9D2DE; font-size: 10px; background: #11151C; padding: 8px;")
        layout.addWidget(guide)

        controls = QHBoxLayout()
        capture_button = QPushButton("CAPTURE PHOTO")
        capture_button.clicked.connect(self._capture_photo)
        self.gesture_button = QPushButton("GESTURES")
        self.gesture_button.setCheckable(True)
        self.gesture_button.toggled.connect(self._toggle_gestures)
        self.desktop_button = QPushButton("DESKTOP CONTROL")
        self.desktop_button.setCheckable(True)
        self.desktop_button.toggled.connect(self._toggle_desktop)
        self.stop_button = QPushButton("EMERGENCY STOP")
        self.stop_button.setStyleSheet("background: #8B1E2D; color: white; font-weight: bold;")
        self.stop_button.clicked.connect(self._emergency_stop)
        close_button = QPushButton("CLOSE")
        close_button.clicked.connect(self.close)
        controls.addWidget(capture_button)
        controls.addWidget(self.gesture_button)
        controls.addWidget(self.desktop_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(close_button)
        layout.addLayout(controls)
        self.timer.start(33)

    def _update_frame(self):
        if not self.capture.isOpened():
            self.preview.setText("Webcam unavailable")
            return
        ok, frame = self.capture.read()
        if not ok:
            return
        if self.gesture_enabled and self.hands is not None:
            rgb_for_tracking = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.hands.detect(
                self.mp.Image(
                    image_format=self.mp.ImageFormat.SRGB,
                    data=rgb_for_tracking,
                )
            )
            gesture, points = self._classify_hand(result)
            self._draw_hand_tracking(frame, result, gesture)
            self._apply_desktop_control(gesture, points)
            if result.hand_landmarks:
                mode = "CONTROL ON" if self.desktop_enabled else "TRACKING ONLY"
                self.gesture_status.setText(f"{mode} — {gesture or 'HAND TRACKED'}")
            else:
                self.gesture_status.setText("GESTURES ON — SHOW YOUR HAND")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888)
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def _toggle_gestures(self, enabled: bool):
        if enabled:
            try:
                import importlib
                import os

                python_install_dir = os.path.dirname(sys.executable)
                original_path = list(sys.path)
                sys.path = [
                    entry for entry in sys.path
                    if os.path.abspath(entry or os.getcwd()) != os.path.abspath(python_install_dir)
                ]
                try:
                    mp = importlib.import_module("mediapipe")
                finally:
                    sys.path = original_path
                model_path = Path.home() / ".zeus" / "hand_landmarker.task"
                if not model_path.exists():
                    model_path.parent.mkdir(parents=True, exist_ok=True)
                    urllib.request.urlretrieve(
                        "https://storage.googleapis.com/mediapipe-models/"
                        "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
                        model_path,
                    )
                options = mp.tasks.vision.HandLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_hands=1,
                    min_hand_detection_confidence=0.7,
                    min_hand_presence_confidence=0.7,
                    min_tracking_confidence=0.7,
                )
                self.hands = mp.tasks.vision.HandLandmarker.create_from_options(options)
                self.mp = mp
                self.gesture_enabled = True
                self.gesture_status.setText("GESTURES ON — SHOW YOUR HAND")
                self.gesture_status.setStyleSheet("color: #00FF41; font-weight: bold;")
            except (ImportError, AttributeError, OSError, urllib.error.URLError) as exc:
                self.gesture_button.setChecked(False)
                self.gesture_status.setText(f"GESTURES UNAVAILABLE: {exc}")
                self.gesture_status.setStyleSheet("color: #FF6666;")
        else:
            self.gesture_enabled = False
            self._emergency_stop()
            if self.hands is not None:
                self.hands.close()
                self.hands = None
            self.gesture_status.setText("GESTURES OFF")
            self.gesture_status.setStyleSheet("color: #8F9AA8; font-weight: bold;")

    def _toggle_desktop(self, enabled: bool):
        if enabled and not self.gesture_enabled:
            self.desktop_button.setChecked(False)
            self.gesture_status.setText("ENABLE GESTURES FIRST")
            return
        self.desktop_enabled = enabled
        self.last_center = None
        self.pinch_active = False
        self.gesture_status.setText("DESKTOP CONTROL ARMED" if enabled else "TRACKING ONLY")

    def _emergency_stop(self):
        self.desktop_enabled = False
        self.desktop_button.setChecked(False)
        self.pinch_active = False
        self.gesture_status.setText("EMERGENCY STOP — CONTROL OFF")
        self.gesture_status.setStyleSheet("color: #FF6666; font-weight: bold;")

    @staticmethod
    def _classify_hand(result):
        if not result.hand_landmarks:
            return None, None
        points = result.hand_landmarks[0]
        fingers = [
            points[8].y < points[6].y,
            points[12].y < points[10].y,
            points[16].y < points[14].y,
            points[20].y < points[18].y,
        ]
        thumb_up = points[4].y < points[3].y and not any(fingers)
        thumb_down = points[4].y > points[3].y and not any(fingers)
        pinch = ((points[4].x - points[8].x) ** 2 + (points[4].y - points[8].y) ** 2) ** 0.5 < 0.07
        if pinch:
            gesture = "PINCH"
        elif thumb_up:
            gesture = "THUMB UP"
        elif thumb_down:
            gesture = "THUMB DOWN"
        elif sum(fingers) == 0:
            gesture = "FIST"
        elif sum(fingers) == 2 and fingers[0] and fingers[1]:
            gesture = "VICTORY"
        elif sum(fingers) >= 4:
            gesture = "OPEN PALM"
        elif fingers[0] and not any(fingers[1:]):
            gesture = "POINT"
        else:
            gesture = None
        center = (points[9].x, points[9].y)
        return gesture, (points, center)

    def _apply_desktop_control(self, gesture, hand_data):
        if not self.desktop_enabled or hand_data is None:
            return
        import time

        points, center = hand_data
        now = time.monotonic()
        if gesture == "OPEN PALM":
            self._emergency_stop()
            return
        try:
            if gesture == "POINT":
                screen_width, screen_height = pyautogui.size()
                pyautogui.moveTo(
                    int((1 - points[8].x) * screen_width),
                    int(points[8].y * screen_height),
                    duration=0.05,
                )
            if gesture == "PINCH" and not self.pinch_active:
                pyautogui.click()
                self.pinch_active = True
            if gesture != "PINCH":
                self.pinch_active = False
            if self.last_center and now - self.last_action_at > 0.8:
                dx = center[0] - self.last_center[0]
                dy = center[1] - self.last_center[1]
                if abs(dx) > 0.18:
                    pyautogui.hotkey("ctrl", "tab" if dx < 0 else "shift", "tab")
                    self.last_action_at = now
                elif abs(dy) > 0.18:
                    pyautogui.scroll(-5 if dy > 0 else 5)
                    self.last_action_at = now
            if now - self.last_action_at > 1.0:
                if gesture == "FIST":
                    pyautogui.press("space")
                    self.last_action_at = now
                elif gesture == "VICTORY":
                    screenshot_path = Path.home() / "Pictures" / "zeus_gesture_screenshot.png"
                    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                    pyautogui.screenshot(str(screenshot_path))
                    self.gesture_status.setText(f"SCREENSHOT SAVED: {screenshot_path.name}")
                    self.last_action_at = now
                elif gesture == "THUMB UP":
                    pyautogui.press("volumeup")
                    self.last_action_at = now
                elif gesture == "THUMB DOWN":
                    pyautogui.press("volumedown")
                    self.last_action_at = now
        except pyautogui.FailSafeException:
            self._emergency_stop()
        except OSError as exc:
            self._emergency_stop()
            self.gesture_status.setText(f"DESKTOP CONTROL ERROR: {exc}")
        self.last_center = center

    @staticmethod
    def _draw_hand_tracking(frame, result, gesture=None):
        if not result.hand_landmarks:
            return
        height, width = frame.shape[:2]
        connections = (
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (5, 9), (9, 10), (10, 11), (11, 12),
            (9, 13), (13, 14), (14, 15), (15, 16),
            (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
        )
        for hand in result.hand_landmarks:
            points = [
                (int(point.x * width), int(point.y * height))
                for point in hand
            ]
            for start, end in connections:
                cv2.line(frame, points[start], points[end], (0, 215, 255), 3)
            for point in points:
                cv2.circle(frame, point, 6, (0, 255, 80), -1)
        if gesture:
            cv2.putText(
                frame,
                gesture,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 215, 255),
                2,
                cv2.LINE_AA,
            )

    def _capture_photo(self):
        if not self.capture.isOpened():
            return
        ok, frame = self.capture.read()
        if not ok:
            return
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if ok:
            data = base64.b64encode(encoded.tobytes()).decode("ascii")
            self.captured.emit(f"data:image/jpeg;base64,{data}")
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        self._emergency_stop()
        if self.hands is not None:
            self.hands.close()
            self.hands = None
        if self.capture.isOpened():
            self.capture.release()
        super().closeEvent(event)


class SidebarPanel(QFrame):
    clear_requested = Signal()
    camera_requested = Signal()
    upload_requested = Signal()
    demo_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedWidth(148)
        self.setStyleSheet("""
            QFrame#Sidebar {
                background: rgba(8, 8, 10, 210);
                border: 1px solid rgba(255,255,255,32);
                border-radius: 14px;
            }
            QLabel { background: transparent; }
            QLabel#SideBrand { color: #D4AF37; font-size: 19px; font-weight: bold; }
            QLabel#SideCaption { color: rgba(255,255,255,125); font-size: 9px; }
            QLabel.SideLabel { color: rgba(255,255,255,145); font-size: 9px; }
            QLabel.SideValue { color: #F5F0DA; font-size: 11px; font-weight: bold; }
            QPushButton {
                background: rgba(255,255,255,24);
                color: #F4F1E7;
                border: 1px solid rgba(255,255,255,48);
                border-radius: 8px;
                padding: 8px 5px;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(201,162,39,175); color: #16120A; }
            QPushButton:pressed { background: #8B1E2D; color: white; }
        """)
        self.setObjectName("Sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        brand = QLabel("ZEUS")
        brand.setObjectName("SideBrand")
        caption = QLabel("UNIVERSAL\nSIDEKICK")
        caption.setObjectName("SideCaption")
        layout.addWidget(brand)
        layout.addWidget(caption)
        layout.addSpacing(12)

        self.core_value = self._add_status(layout, "CORE", "ONLINE")
        self.api_value = self._add_status(layout, "API", "CONNECTED" if API_KEY else "NO KEY")
        self.model_value = self._add_status(layout, "MODEL", "NEMOTRON ULTRA")

        layout.addStretch()

        new_button = QPushButton("NEW CHAT")
        new_button.setCursor(Qt.PointingHandCursor)
        new_button.clicked.connect(self.clear_requested.emit)
        layout.addWidget(new_button)

        camera_button = QPushButton("CAMERA")
        camera_button.setCursor(Qt.PointingHandCursor)
        camera_button.clicked.connect(self.camera_requested.emit)
        layout.addWidget(camera_button)

        upload_button = QPushButton("UPLOAD FILE")
        upload_button.setCursor(Qt.PointingHandCursor)
        upload_button.clicked.connect(self.upload_requested.emit)
        layout.addWidget(upload_button)

        demo_button = QPushButton("DEMO MODE")
        demo_button.setCursor(Qt.PointingHandCursor)
        demo_button.setStyleSheet(
            "QPushButton { background: #8B1E2D; color: white; border: 1px solid #D4AF37; "
            "border-radius: 8px; padding: 8px 5px; font-size: 9px; font-weight: bold; }"
            "QPushButton:hover { background: #C9A227; color: #16120A; }"
        )
        demo_button.clicked.connect(self.demo_requested.emit)
        layout.addWidget(demo_button)

        hint = QLabel("ENTER  SEND\nESC  CLOSE")
        hint.setObjectName("SideCaption")
        layout.addWidget(hint)

    @staticmethod
    def _add_status(layout, title: str, value: str) -> QLabel:
        label = QLabel(title)
        label.setProperty("class", "SideLabel")
        value_label = QLabel(value)
        value_label.setProperty("class", "SideValue")
        layout.addWidget(label)
        layout.addWidget(value_label)
        layout.addSpacing(8)
        return value_label

    def set_status(self, text: str, color: str):
        self.core_value.setText(text.replace("● ", ""))
        self.core_value.setStyleSheet(f"color: {color}; background: transparent; font-size: 11px; font-weight: bold;")

class ZeusWindow(QWidget):
    request_turn = Signal(str, object, object)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._agent_thread = None
        self._voice_thread = None
        self._voice_worker = None
        self._camera_dialog = None
        self._pending_image_data = None
        self._pending_file_data = None
        self._pending_file_name = None
        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._advance_demo)
        self._demo_steps = []
        self._demo_index = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.glass = GlassFrame()
        root.addWidget(self.glass)

        shadow = QGraphicsDropShadowEffect(self.glass)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.glass.setGraphicsEffect(shadow)

        shell = QHBoxLayout(self.glass)
        shell.setContentsMargins(14, 14, 14, 14)
        shell.setSpacing(12)

        self.sidebar = SidebarPanel()
        self.sidebar.clear_requested.connect(self.clear_chat)
        self.sidebar.camera_requested.connect(self.open_camera)
        self.sidebar.upload_requested.connect(self.upload_file)
        self.sidebar.demo_requested.connect(self.start_demo)
        shell.addWidget(self.sidebar)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        shell.addWidget(content, 1)

        inner = QVBoxLayout(content)
        inner.setContentsMargins(22, 20, 22, 20)
        inner.setSpacing(10)

        header = HeaderBar(self)
        h = QHBoxLayout(header)
        h.setContentsMargins(4, 0, 4, 0)

        title = QLabel("ZEUS  ·  Universal Sidekick")
        title.setStyleSheet("color: rgba(255,255,255,220); background: transparent;")
        title.setFont(ui_font(14, bold=True))

        self.status = QLabel("● CORE ONLINE")
        self.status.setStyleSheet("color: #00FF41; background: transparent;")
        self.status.setFont(ui_font(10))

        chrome = """
            QPushButton {
                background: rgba(255,255,255,18);
                color: rgba(255,255,255,180);
                border: 1px solid rgba(255,255,255,30);
                border-radius: 8px;
            }
            QPushButton:hover { background: rgba(255,255,255,40); color: white; }
        """
        min_btn = QPushButton("–")
        min_btn.setFixedSize(28, 28)
        min_btn.setCursor(Qt.PointingHandCursor)
        min_btn.setStyleSheet(chrome)
        min_btn.clicked.connect(self.showMinimized)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            chrome
            + "QPushButton:hover { background: rgba(200,40,50,180); color: white; }"
        )
        close_btn.clicked.connect(self.close)

        h.addWidget(title)
        h.addStretch()
        h.addWidget(self.status)
        h.addSpacing(8)
        h.addWidget(min_btn)
        h.addWidget(close_btn)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 8px; margin: 4px; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,40); border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.chat_host = QWidget()
        self.chat_host.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_host)
        self.chat_layout.addStretch()
        self.scroll.setWidget(self.chat_host)

        input_bar = QFrame()
        input_bar.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,12);
                border: 1px solid rgba(255,255,255,28);
                border-radius: 16px;
            }
        """)
        ib = QHBoxLayout(input_bar)
        ib.setContentsMargins(12, 8, 8, 8)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Command ZEUS…")
        self.entry.setFont(ui_font(12))
        self.entry.setStyleSheet("""
            QLineEdit {
                background: transparent; border: none;
                color: #F2F2F2; selection-background-color: #8B1E2D;
                padding: 8px;
            }
        """)
        self.entry.returnPressed.connect(self.send_message)

        self.send = QPushButton("EXE")
        self.send.setFixedSize(72, 40)
        self.send.setCursor(Qt.PointingHandCursor)
        self.send.setFont(ui_font(11, bold=True))
        self.send.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #8B1E2D, stop:1 #C9A227);
                color: white; border: none; border-radius: 12px;
            }
            QPushButton:hover { background: #D4AF37; color: #111; }
            QPushButton:disabled { background: rgba(255,255,255,20); color: #777; }
        """)
        self.send.clicked.connect(self.send_message)
        self.mic = QPushButton("MIC")
        self.mic.setFixedSize(58, 40)
        self.mic.setCursor(Qt.PointingHandCursor)
        self.mic.setFont(ui_font(10, bold=True))
        self.mic.setToolTip("Press to speak one command")
        self.mic.setStyleSheet("""
            QPushButton {
                background: #263B54;
                color: #F5F0DA;
                border: 1px solid #6D8EB5;
                border-radius: 12px;
            }
            QPushButton:hover { background: #385A7A; }
            QPushButton:pressed { background: #8B1E2D; }
            QPushButton:disabled { background: rgba(255,255,255,20); color: #777; }
        """)
        self.mic.clicked.connect(self.listen_once)
        ib.addWidget(self.entry)
        ib.addWidget(self.mic)
        ib.addWidget(self.send)

        inner.addWidget(header)
        inner.addWidget(self.scroll, 1)
        inner.addWidget(input_bar)
        self._fit_to_screen()
        self._setup_worker()

    def _fit_to_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        width = min(780, int(geo.width() * 0.56))
        height = min(700, int(geo.height() * 0.86))
        width = max(560, width)
        height = max(500, min(height, geo.height() - 16))
        self.setMinimumSize(420, 460)
        self.resize(width, height)
        frame = self.frameGeometry()
        frame.moveCenter(geo.center())
        self.move(frame.topLeft())

    def _setup_worker(self):
        if not API_KEY:
            self.set_status("● NO API KEY", "#FF4444")
            self.entry.setDisabled(True)
            self.send.setDisabled(True)
            self.mic.setDisabled(True)
            self.add_bubble(
                "Set OPENROUTER_API_KEY in a .env file (see .env.example), then restart ZEUS.",
                "zeus",
            )
            return

        self._agent_thread = QThread(self)
        self.sidebar.model_value.setText(OPENROUTER_MODEL.rsplit("/", 1)[-1].upper())
        self.worker = AgentWorker(ZeusAgent())
        self.worker.moveToThread(self._agent_thread)
        self.request_turn.connect(self.worker.run_turn)
        self.worker.tool_started.connect(self.on_tool)
        self.worker.tool_confirmation_requested.connect(self.confirm_tool)
        self.worker.finished.connect(self.on_reply)
        self.worker.failed.connect(self.on_error)
        self._agent_thread.start()

    def add_bubble(self, text: str, kind: str):
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, ChatRow(text, kind))
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_status(self, text: str, color: str):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {color}; background: transparent;")
        self.sidebar.set_status(text, color)

    def clear_chat(self):
        self.stop_demo()
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.add_bubble("Chat cleared. ZEUS is ready.", "zeus")
        self._pending_file_data = None
        self._pending_file_name = None
        self._pending_image_data = None

    def start_demo(self):
        if self._demo_timer.isActive():
            self.stop_demo()
            return
        self.clear_chat()
        self._demo_steps = [
            "EXHIBITION DEMO MODE\n\nZEUS is a multimodal desktop sidekick powered by Nemotron Ultra.",
            "1 / AGENT REASONING\nZEUS understands natural language, plans multi-step work, and explains its actions.",
            "2 / TOOL USE\nZEUS can read files, inspect system health, search the web, and access time data.",
            "3 / DOCUMENT INTELLIGENCE\nUse UPLOAD FILE to analyze Word, PDF, Excel, PowerPoint, and text documents.",
            "4 / VOICE\nPress MIC for one push-to-talk command. ZEUS can answer aloud at a controlled speed.",
            "5 / VISION\nOpen CAMERA to see a live webcam feed and capture a photo for Nemotron analysis.",
            "6 / HAND TRACKING\nInside CAMERA, enable GESTURES to see hand landmarks and the live gesture label.",
            "7 / DESKTOP CONTROL\nDesktop gestures are opt-in, allowlisted, cooldown-protected, and guarded by EMERGENCY STOP.",
            "8 / SAFETY\nZEUS asks permission before tools, file access, camera access, and other sensitive actions.",
            "DEMO READY\n\nTry this now: upload a document, ask ZEUS to summarize it, then use MIC for a follow-up.",
        ]
        self._demo_index = 0
        self.set_status("● DEMO MODE", "#D4AF37")
        self._advance_demo()
        self._demo_timer.start(2600)

    def _advance_demo(self):
        if self._demo_index >= len(self._demo_steps):
            self.stop_demo()
            return
        self.add_bubble(self._demo_steps[self._demo_index], "zeus")
        self._demo_index += 1

    def stop_demo(self):
        if self._demo_timer.isActive():
            self._demo_timer.stop()
        if self.status.text() == "● DEMO MODE":
            self.set_status("● CORE ONLINE", "#00FF41")

    def send_message(self):
        text = self.entry.text().strip()
        if not text or not self.send.isEnabled() or self._agent_thread is None:
            return
        self.entry.clear()
        image_data = self._pending_image_data
        file_data = self._pending_file_data
        file_name = self._pending_file_name
        self._pending_image_data = None
        self._pending_file_data = None
        self._pending_file_name = None
        self._submit_message(text, image_data, file_data, file_name)

    def _submit_message(
        self,
        text: str,
        image_data: str | None = None,
        file_data: str | None = None,
        file_name: str | None = None,
    ):
        attachments = []
        if image_data:
            attachments.append("[PHOTO ATTACHED]")
        if file_data:
            attachments.append(f"[FILE ATTACHED: {file_name}]")
        display_text = f"{text}  {' '.join(attachments)}" if attachments else text
        self.add_bubble(display_text, "user")
        self.send.setDisabled(True)
        self.set_status("● REASONING", "#FFBB00")
        self.request_turn.emit(text, image_data, file_data)

    def upload_file(self):
        answer = QMessageBox.question(
            self,
            "ZEUS FILE PERMISSION",
            "ZEUS wants to open a local file for analysis.\n\nAllow file selection?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Upload a file for ZEUS",
            "",
            (
                "Supported files (*.txt *.md *.py *.json *.csv *.docx *.pdf "
                "*.xlsx *.xlsm *.pptx);;All files (*.*)"
            ),
        )
        if not file_path:
            return
        content = read_file(file_path)
        if content.startswith("Error reading file:"):
            self.add_bubble(f"[FILE] {content}", "zeus")
            self.set_status("● FILE ERROR", "#FF4444")
            return
        self._pending_file_data = content
        self._pending_file_name = file_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        self.entry.setText(f"Analyze {self._pending_file_name}.")
        self.entry.setFocus()
        self.set_status("● FILE READY", "#D4AF37")

    def open_camera(self):
        answer = QMessageBox.question(
            self,
            "ZEUS CAMERA PERMISSION",
            "ZEUS wants to access your webcam.\n\nAllow camera access?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        if self._camera_dialog is not None:
            self._camera_dialog.raise_()
            self._camera_dialog.activateWindow()
            return
        self._camera_dialog = CameraDialog(self)
        self._camera_dialog.captured.connect(self._photo_captured)
        self._camera_dialog.finished.connect(self._camera_closed)
        self._camera_dialog.show()

    @Slot(str)
    def _photo_captured(self, image_data: str):
        self._pending_image_data = image_data
        self.entry.setText("Analyze this photo.")
        self.entry.setFocus()
        self.set_status("● PHOTO READY", "#D4AF37")

    @Slot()
    def _camera_closed(self):
        self._camera_dialog = None

    def listen_once(self):
        if self._voice_thread is not None or self._agent_thread is None:
            return
        self.mic.setDisabled(True)
        self.send.setDisabled(True)
        self._voice_thread = QThread(self)
        self._voice_worker = VoiceWorker()
        self._voice_worker.moveToThread(self._voice_thread)
        self._voice_thread.started.connect(self._voice_worker.listen)
        self._voice_worker.recognized.connect(self._on_voice_text)
        self._voice_worker.status.connect(self._on_voice_status)
        self._voice_worker.failed.connect(self._on_voice_error)
        self._voice_worker.finished.connect(self._voice_thread.quit)
        self._voice_worker.finished.connect(self._voice_worker.deleteLater)
        self._voice_thread.finished.connect(self._voice_thread.deleteLater)
        self._voice_thread.finished.connect(self._voice_stopped)
        self._voice_thread.start()

    @Slot(str)
    def _on_voice_text(self, text: str):
        if self._agent_thread is None:
            return
        self.entry.setText(text)
        file_data = self._pending_file_data
        file_name = self._pending_file_name
        image_data = self._pending_image_data
        self._pending_file_data = None
        self._pending_file_name = None
        self._pending_image_data = None
        self._submit_message(text, image_data, file_data, file_name)

    @Slot(str)
    def _on_voice_status(self, text: str):
        color = "#FFD700" if "TRANSCRIBING" in text else "#00FF41"
        self.set_status(text, color)

    @Slot(str)
    def _on_voice_error(self, message: str):
        self.add_bubble(f"[VOICE] {message}", "zeus")
        self.set_status("● VOICE ERROR", "#FF4444")
        self.mic.setEnabled(True)
        self.send.setEnabled(True)

    @Slot()
    def _voice_stopped(self):
        self._voice_thread = None
        self._voice_worker = None
        self.mic.setEnabled(True)
        if self._agent_thread is not None and self.send.isEnabled():
            self.set_status("● CORE ONLINE", "#00FF41")

    @Slot(str)
    def on_tool(self, name: str):
        self.set_status(f"● TOOL  {name}", "#FFD700")

    @Slot(str, str, object)
    def confirm_tool(self, name: str, argument: str, response):
        completed, decision = response
        descriptions = {
            "READ_FILE": "read the contents of a local file",
            "LIST_FILES": "list files in a local directory",
            "SEARCH_WEB": "search the web",
            "GET_SYSTEM_STATUS": "inspect system health metrics",
            "GET_TIME": "read the current time",
        }
        action = descriptions.get(name, "run a tool")
        detail = f"\nTarget: {argument}" if argument else ""
        answer = QMessageBox.question(
            self,
            "ZEUS TOOL PERMISSION",
            f"ZEUS wants to {action}.{detail}\n\nAllow this action?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        decision[0] = answer == QMessageBox.Yes
        completed.set()

    @Slot(str)
    def on_reply(self, text: str):
        self.add_bubble(text, "zeus")
        self._speak(text)
        self.set_status("● CORE ONLINE", "#00FF41")
        self.send.setEnabled(True)
        self.entry.setFocus()

    @Slot(str)
    def on_error(self, err: str):
        self.add_bubble(f"[SYSTEM] {err}", "zeus")
        self.set_status("● FAULT", "#FF4444")
        self.send.setEnabled(True)
        self.entry.setFocus()

    def closeEvent(self, event):
        self.stop_demo()
        if self._camera_dialog is not None:
            self._camera_dialog.close()
        if self._voice_worker is not None:
            self._voice_worker.deleteLater()
        if self._voice_thread is not None:
            self._voice_thread.quit()
            self._voice_thread.wait(1500)
        if self._agent_thread is not None:
            self._agent_thread.quit()
            self._agent_thread.wait(1500)
        super().closeEvent(event)

    @staticmethod
    def _speak(text: str):
        def speak():
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", TTS_RATE)
                engine.say(text)
                engine.runAndWait()
            except (OSError, RuntimeError):
                pass

        threading.Thread(target=speak, daemon=True).start()


if __name__ == "__main__":
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setFont(ui_font(11))
    window = ZeusWindow()
    window.show()
    sys.exit(app.exec())
