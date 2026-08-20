import sys

from groq import Groq
from PySide6.QtCore import Qt, QObject, QThread, Signal, Slot, QRectF, QTimer
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QLinearGradient,
    QPen,
    QFont,
    QGuiApplication,
)
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
)

from agent import ZeusAgent
from config import API_KEY


def ui_font(size: int = 11, bold: bool = False) -> QFont:
    font = QFont("Consolas", size)
    if font.family() != "Consolas":
        font = QFont("Roboto", size)
    if bold:
        font.setBold(True)
    return font


class AgentWorker(QObject):
    tool_started = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, agent: ZeusAgent):
        super().__init__()
        self.agent = agent

    @Slot(str)
    def run_turn(self, user_text: str):
        try:
            result = self.agent.run_turn(user_text, on_tool=self.tool_started.emit)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


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


class ZeusWindow(QWidget):
    request_turn = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._agent_thread = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.glass = GlassFrame()
        root.addWidget(self.glass)

        shadow = QGraphicsDropShadowEffect(self.glass)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.glass.setGraphicsEffect(shadow)

        inner = QVBoxLayout(self.glass)
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
        ib.addWidget(self.entry)
        ib.addWidget(self.send)

        inner.addWidget(header)
        inner.addWidget(self.scroll, 1)
        inner.addWidget(input_bar)
        self._fit_to_screen()
        self._setup_worker()

    def _fit_to_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        width = min(640, int(geo.width() * 0.46))
        height = min(700, int(geo.height() * 0.86))
        width = max(460, width)
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
            self.add_bubble(
                "Set GROQ_API_KEY in a .env file (see .env.example), then restart ZEUS.",
                "zeus",
            )
            return

        self._agent_thread = QThread(self)
        self.worker = AgentWorker(ZeusAgent(Groq(api_key=API_KEY)))
        self.worker.moveToThread(self._agent_thread)
        self.request_turn.connect(self.worker.run_turn)
        self.worker.tool_started.connect(self.on_tool)
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

    def send_message(self):
        text = self.entry.text().strip()
        if not text or not self.send.isEnabled() or self._agent_thread is None:
            return
        self.entry.clear()
        self.add_bubble(text, "user")
        self.send.setDisabled(True)
        self.set_status("● REASONING", "#FFBB00")
        self.request_turn.emit(text)

    @Slot(str)
    def on_tool(self, name: str):
        self.set_status(f"● TOOL  {name}", "#FFD700")

    @Slot(str)
    def on_reply(self, text: str):
        self.add_bubble(text, "zeus")
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
        if self._agent_thread is not None:
            self._agent_thread.quit()
            self._agent_thread.wait(1500)
        super().closeEvent(event)


if __name__ == "__main__":
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setFont(ui_font(11))
    window = ZeusWindow()
    window.show()
    sys.exit(app.exec())
