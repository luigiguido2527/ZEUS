import customtkinter as ctk
from groq import Groq
import threading
import os
import datetime

# --- BRAIN CONFIG ---
API_KEY = "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"
MODEL_ID = "openai/gpt-oss-120b"
ZEUS_PROMPT = "You are ZEUS. Give sharp, formatted answers. Use bullet points and clear headers."
messages = [{"role": "system", "content": ZEUS_PROMPT}]

client = Groq(api_key=API_KEY) if API_KEY else None

# --- UI COLORS ---
COLOR_BG = "#0A0A0A"            # Deep Space Black
COLOR_PANEL = "#121212"         # Chat panel
COLOR_HEADER = "#111318"        # Header bar
COLOR_TEXT_USER = "#00D4FF"     # Lightning Blue
COLOR_TEXT_ZEUS = "#FFD700"     # Electric Gold
COLOR_TEXT_META = "#5A5A5A"     # Timestamps / dividers
COLOR_ACCENT = "#1B4F72"        # Power Blue
COLOR_ACCENT_HOVER = "#24689A"
COLOR_ONLINE = "#00FF41"
COLOR_BUSY = "#FFBB00"
COLOR_ERROR = "#FF4444"

# --- FONT SETTINGS ---
FONT_BOX = ("Consolas", 14)
FONT_UI = ("Consolas", 12, "bold")
FONT_HEADER = ("Consolas", 18, "bold")
FONT_META = ("Consolas", 10)

ctk.set_appearance_mode("dark")


class ZeusApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ZEUS SYSTEM v1.0")
        self.geometry("720x820")
        self.minsize(500, 500)
        self.configure(fg_color=COLOR_BG)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._thinking_job = None
        self._pulse_job = None
        self._thinking_frame = 0
        self._thinking_states = ["●○○", "○●○", "○○●", "○●○"]

        # --- HEADER BAR ---
        self.header = ctk.CTkFrame(self, fg_color=COLOR_HEADER, corner_radius=0, height=64)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)
        self.header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header, text="⚡ ZEUS", text_color="#FFFFFF", font=FONT_HEADER
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=25, pady=15)

        self.status_label = ctk.CTkLabel(
            self.header, text="● CORE ONLINE", text_color=COLOR_ONLINE, font=FONT_META
        )
        self.status_label.grid(row=0, column=1, sticky="e", padx=25, pady=15)

        # --- CHAT DISPLAY ---
        self.chat_display = ctk.CTkTextbox(
            self,
            state="disabled",
            corner_radius=15,
            border_width=1,
            border_color="#222222",
            fg_color=COLOR_PANEL,
            text_color="#FFFFFF",
            font=FONT_BOX,
            padx=20,
            pady=20,
        )
        self.chat_display.grid(row=1, column=0, padx=25, pady=(20, 10), sticky="nsew")

        self.chat_display.tag_config("user_tag", foreground=COLOR_TEXT_USER)
        self.chat_display.tag_config("zeus_tag", foreground=COLOR_TEXT_ZEUS)
        self.chat_display.tag_config("line_tag", foreground="#333333")
        self.chat_display.tag_config("meta_tag", foreground=COLOR_TEXT_META)
        self.chat_display.tag_config("error_tag", foreground=COLOR_ERROR)

        # --- INPUT AREA ---
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=25, pady=(10, 25), sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.user_input = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Enter command..." if client else "Set GROQ_API_KEY to begin...",
            height=50,
            corner_radius=12,
            fg_color="#1A1A1A",
            border_color="#333333",
            font=FONT_BOX,
        )
        self.user_input.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.user_input.bind("<Return>", lambda e: self.send_message())

        self.send_button = ctk.CTkButton(
            self.input_frame,
            text="EXE ➜",
            width=90,
            height=50,
            corner_radius=12,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            font=FONT_UI,
            command=self.send_message,
        )
        self.send_button.grid(row=0, column=1)

        if not client:
            self.append_system_error(
                "GROQ_API_KEY environment variable not found.\n"
                "Set it in your terminal, then restart ZEUS."
            )
            self.user_input.configure(state="disabled")
            self.send_button.configure(state="disabled")
        else:
            self._start_online_pulse()

        # Optional: drop a zeus_icon.ico next to this script to brand the window/taskbar
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zeus_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

    # ---------- helpers ----------

    def _timestamp(self):
        return datetime.datetime.now().strftime("%H:%M:%S")

    def append_chat(self, sender, text):
        self.chat_display.configure(state="normal")
        ts = self._timestamp()

        if sender == "You":
            self.chat_display.insert("end", f"\n🧑 ── USER · {ts} ──────────────────\n", "line_tag")
            self.chat_display.insert("end", f"{text}\n", "user_tag")
            self.chat_display.configure(state="disabled")
            self.chat_display.see("end")
        elif sender == "ZEUS":
            self.chat_display.insert("end", f"\n⚡ ── ZEUS · {ts} ──────────────────\n", "line_tag")
            self.chat_display.configure(state="disabled")
            self.chat_display.see("end")
            self._typewriter_reveal(text)

    def _typewriter_reveal(self, full_text, index=0, chunk_size=2):
        # Reveals ZEUS's response a few characters at a time for a "live typing" feel
        self.chat_display.configure(state="normal")
        end = min(index + chunk_size, len(full_text))
        self.chat_display.insert("end", full_text[index:end], "zeus_tag")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

        if end < len(full_text):
            self.after(12, lambda: self._typewriter_reveal(full_text, end, chunk_size))
        else:
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", "\n", "zeus_tag")
            self.chat_display.configure(state="disabled")

    def append_system_error(self, text):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"\n[SYSTEM] {text}\n", "error_tag")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def _start_thinking_animation(self):
        if self._pulse_job is not None:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None
        self._thinking_frame = 0
        self._animate_thinking()

    def _animate_thinking(self):
        dots = self._thinking_states[self._thinking_frame % len(self._thinking_states)]
        self.status_label.configure(text=f"{dots} PROCESSING", text_color=COLOR_BUSY)
        self._thinking_frame += 1
        self._thinking_job = self.after(350, self._animate_thinking)

    def _stop_thinking_animation(self):
        if self._thinking_job is not None:
            self.after_cancel(self._thinking_job)
            self._thinking_job = None
        self._start_online_pulse()

    def _start_online_pulse(self, bright=True):
        # Idle state gently pulses between full and dim green instead of sitting static
        color = COLOR_ONLINE if bright else "#0B4D18"
        self.status_label.configure(text="● CORE ONLINE", text_color=color)
        if self._thinking_job is None:  # only keep pulsing while not actively "thinking"
            self._pulse_job = self.after(900, lambda: self._start_online_pulse(not bright))

    # ---------- core actions ----------

    def send_message(self):
        user_text = self.user_input.get().strip()
        if not user_text or not client:
            return

        self.append_chat("You", user_text)
        self.user_input.delete(0, "end")
        self.send_button.configure(state="disabled", text="...")
        self._start_thinking_animation()

        thread = threading.Thread(target=self.get_ai_response, args=(user_text,), daemon=True)
        thread.start()

    def get_ai_response(self, text):
        global messages
        messages.append({"role": "user", "content": text})
        try:
            completion = client.chat.completions.create(model=MODEL_ID, messages=messages)
            response = completion.choices[0].message.content
            messages.append({"role": "assistant", "content": response})
            self.after(0, self._on_response_success, response)
        except Exception as e:
            self.after(0, self._on_response_error, str(e))

    def _on_response_success(self, response):
        self.append_chat("ZEUS", response)
        self._finish_turn()

    def _on_response_error(self, error_text):
        self.append_system_error(f"REQUEST FAILED: {error_text}")
        self._finish_turn()

    def _finish_turn(self):
        self._stop_thinking_animation()
        self.send_button.configure(state="normal", text="EXE ➜")


if __name__ == "__main__":
    app = ZeusApp()
    app.mainloop()