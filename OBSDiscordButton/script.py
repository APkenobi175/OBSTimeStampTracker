import sys
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from dataclasses import dataclass
from pynput import keyboard
from obsws_python import ReqClient

from pathlib import Path
from platformdirs import user_config_dir, user_data_dir

import re


if sys.platform.startswith("win"):
    import ctypes

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


APP_NAME = "OBSSessions"
APP_AUTHOR = "RoxmaStudiosLLC"

CFG_PATH = Path(user_config_dir(APP_NAME, APP_AUTHOR)) / "config.json"
DEFAULT_CFG = {
    "host": "localhost",
    "port": 4455,
    "password": "JimBob123",
    "hotkey": "f12",
    "save_dir": "",
    "geometry": "",
    "silent_close": True,
}

ACCENT    = "#007BFF"
DANGER    = "#dc3545"
SUCCESS   = "#28a745"
MUTED     = "#6c757d"
BG        = "#f0f2f5"
BG_CARD   = "#ffffff"
BG_STATUS = "#f8f9fa"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Timestamp:
    timecode: str
    comment: str = ""

    def to_dict(self) -> dict:
        return {"timestamp": self.timecode, "comment": self.comment}

    @staticmethod
    def from_dict(d: dict) -> "Timestamp":
        return Timestamp(timecode=d.get("timestamp", ""), comment=d.get("comment", ""))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resource_path(relative_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative_path)


def load_config() -> dict:
    cfg = DEFAULT_CFG.copy()
    changed = False

    if CFG_PATH.exists():
        try:
            with CFG_PATH.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update(loaded)
            else:
                # corrupt format
                changed = True
        except Exception:
            # unreadable/corrupt -> rewrite with defaults
            changed = True
    else:
        changed = True

    # Default save location once (and ensure it exists)
    if not (cfg.get("save_dir") or "").strip():
        sessions_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR)) / "Sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        cfg["save_dir"] = str(sessions_dir)
        changed = True

    if changed:
        save_config(cfg)

    return cfg


def save_config(cfg: dict) -> None:
    try:
        CFG_PATH.parent.mkdir(parents=True, exist_ok=True)

        with CFG_PATH.open("w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    except Exception as e:
        print(f"[WARN] Failed to save config: {e}")


def format_seconds(total_seconds: int) -> str:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02}:{m:02}:{s:02}"


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class OBSTimestampLogger:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("OBS Sessions")
        self.root.configure(bg=BG)

        try:
            self.root.iconbitmap(resource_path("assets/thatstheone.ico"))
        except Exception:
            pass

        if sys.platform.startswith("win"):
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "RoxmaStudiosLLC.OBSSessions"
                )
            except Exception:
                pass

        self.cfg = load_config()
        if self.cfg.get("geometry"):
            try:
                self.root.geometry(self.cfg["geometry"])
            except Exception:
                pass

        # State
        self.timestamps: list[Timestamp] = []
        self.hotkey_listener: keyboard.Listener | None = None
        self.was_recording = False
        self._obs_status = "Connecting to OBS..."
        self.client: ReqClient | None = None
        self._live_scroll_frame: tk.Frame | None = None

        self._connect_obs()
        self.filename = self._next_filename()
        self._build_ui()

        self.root.after(500, self._poll_obs)
        self._start_hotkey_listener()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # OBS connection
    # ------------------------------------------------------------------

    def _connect_obs(self) -> None:
        def attempt():
            try:
                self.client = ReqClient(
                    host=self.cfg["host"],
                    port=int(self.cfg["port"]),
                    password=self.cfg["password"],
                )
                self._obs_status = "Connected to OBS WebSocket."
                print("[INFO] Connected to OBS.")
            except Exception as e:
                self.client = None
                self._obs_status = "OBS not connected. Start OBS and try again."
                print(f"[ERROR] Could not connect to OBS: {e}")

        threading.Thread(target=attempt, daemon=True).start()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)

        self.main_tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.main_tab, text="Main")

        self.timestamps_tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.timestamps_tab, text="Timestamps")

        self.viewer_tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.viewer_tab, text="History")

        self.settings_tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.settings_tab, text="Settings")

        self._build_main_tab()
        self._build_timestamps_tab()
        self._build_viewer_tab()
        self._build_settings_tab()

        # Refresh history when that tab is clicked
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_main_tab(self) -> None:
        tab = self.main_tab

        # Subtle header: hotkey left, counter right
        header = tk.Frame(tab, bg=BG)
        header.pack(fill="x", padx=12, pady=(8, 0))

        self.hotkey_label = tk.Label(
            header,
            text=f"Hotkey: {self.cfg.get('hotkey', 'F12').upper()}",
            font=("Arial", 10), bg=BG, fg=MUTED,
        )
        self.hotkey_label.pack(side="left")

        self.counter_label = tk.Label(
            header,
            text="0 marked",
            font=("Arial", 10, "bold"),
            bg=ACCENT, fg="white",
            padx=8, pady=2,
        )
        self.counter_label.pack(side="right")

        # Smaller, lighter title
        tk.Label(
            tab, text="OBS Sessions",
            font=("Arial", 15, "bold"), bg=BG, fg="#333",
        ).pack(pady=(8, 12))

        # Comment box
        comment_frame = tk.Frame(tab, bg=BG)
        comment_frame.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(
            comment_frame, text="Comment (optional)",
            font=("Arial", 9), bg=BG, fg=MUTED,
        ).pack(anchor="w")

        self.comment_var = tk.StringVar()
        self.comment_entry = tk.Entry(
            comment_frame, textvariable=self.comment_var,
            font=("Arial", 11), relief="solid", bd=1,
        )
        self.comment_entry.pack(fill="x", ipady=5)
        self.comment_entry.bind("<Return>", lambda e: self._mark_timestamp())

        # Mark button — the hero, nothing else competing with it
        tk.Button(
            tab, text="Mark Funny Moment",
            command=self._mark_timestamp,
            bg=ACCENT, fg="white",
            font=("Arial", 15, "bold"),
            relief="flat", cursor="hand2",
            activebackground="#0069d9", activeforeground="white",
        ).pack(fill="x", padx=16, pady=(0, 16), ipady=12)

        # Save / Save & Exit row
        save_row = tk.Frame(tab, bg=BG)
        save_row.pack(fill="x", padx=16)

        tk.Button(
            save_row, text="Save & Start Fresh",
            command=self._autosave_and_reset,
            bg=MUTED, fg="white",
            font=("Arial", 11),
            relief="flat", cursor="hand2",
            activebackground="#5a6268", activeforeground="white",
        ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 4))

        tk.Button(
            save_row, text="Save & Exit",
            command=self._save_and_exit,
            bg=SUCCESS, fg="white",
            font=("Arial", 11),
            relief="flat", cursor="hand2",
            activebackground="#218838", activeforeground="white",
        ).pack(side="left", fill="x", expand=True, ipady=6)

        # Status bar
        self.status_label = tk.Label(
            tab, text=self._obs_status,
            font=("Arial", 9), bg=BG_STATUS, fg="#555",
            relief="sunken", bd=1, anchor="center",
        )
        self.status_label.pack(fill="x", padx=12, pady=10, ipady=4)

    def _build_timestamps_tab(self) -> None:
        tab = self.timestamps_tab

        # Toolbar
        toolbar = tk.Frame(tab, bg=BG)
        toolbar.pack(fill="x", padx=10, pady=(8, 4))

        tk.Label(toolbar, text="Current Session", font=("Arial", 11, "bold"), bg=BG).pack(side="left")

        tk.Button(
            toolbar, text="Copy To Clipboard",
            command=self._copy_to_clipboard,
            bg=MUTED, fg="white", font=("Arial", 9),
            relief="flat", cursor="hand2", padx=8, pady=2,
        ).pack(side="right")

        # Scrollable list
        container = tk.Frame(tab, bg=BG)
        container.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self._ts_canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self._ts_canvas.yview)
        self._live_scroll_frame = tk.Frame(self._ts_canvas, bg=BG)

        self._live_scroll_frame.bind(
            "<Configure>",
            lambda e: self._ts_canvas.configure(scrollregion=self._ts_canvas.bbox("all"))
        )

        self._ts_canvas.create_window((0, 0), window=self._live_scroll_frame, anchor="nw")
        self._ts_canvas.configure(yscrollcommand=scrollbar.set)

        # Keep inner frame width in sync with canvas width
        self._ts_canvas.bind(
            "<Configure>",
            lambda e: self._ts_canvas.itemconfig("all", width=e.width)
        )

        scrollbar.pack(side="right", fill="y")
        self._ts_canvas.pack(side="left", fill="both", expand=True)

        # Bind mousewheel — Windows/macOS and Linux
        self._ts_canvas.bind("<Enter>", self._bind_mousewheel)
        self._ts_canvas.bind("<Leave>", self._unbind_mousewheel)

        self._refresh_timestamps_tab()

    def _build_viewer_tab(self) -> None:
        tab = self.viewer_tab

        # Header
        header = tk.Frame(tab, bg=BG)
        header.pack(fill="x", padx=10, pady=(8, 4))

        tk.Label(header, text="Past Recording Sessions", font=("Arial", 11, "bold"), bg=BG).pack(side="left")

        tk.Button(
            header, text="Refresh",
            command=self._refresh_viewer_sessions,
            bg=MUTED, fg="white", font=("Arial", 9),
            relief="flat", cursor="hand2", padx=8, pady=2,
        ).pack(side="right")

        # Split: session list on left, detail on right
        pane = tk.Frame(tab, bg=BG)
        pane.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        # --- Left: session list ---
        left = tk.Frame(pane, bg=BG, width=160)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="Sessions", font=("Arial", 9), bg=BG, fg=MUTED).pack(anchor="w", padx=4, pady=(0, 2))

        list_frame = tk.Frame(left, bg=BG)
        list_frame.pack(fill="both", expand=True)

        self._session_listbox = tk.Listbox(
            list_frame,
            font=("Arial", 9),
            relief="solid", bd=1,
            selectbackground=ACCENT,
            selectforeground="white",
            activestyle="none",
            bg=BG_CARD,
        )
        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self._session_listbox.yview)
        self._session_listbox.configure(yscrollcommand=list_scroll.set)
        list_scroll.pack(side="right", fill="y")
        self._session_listbox.pack(side="left", fill="both", expand=True)
        self._session_listbox.bind("<<ListboxSelect>>", self._on_session_select)

        # Divider
        tk.Frame(pane, bg="#d0d3d8", width=1).pack(side="left", fill="y", padx=(6, 6))

        # --- Right: detail view ---
        right = tk.Frame(pane, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        self._viewer_header_label = tk.Label(
            right, text="Select a session to view",
            font=("Arial", 10), bg=BG, fg=MUTED, anchor="w",
        )
        self._viewer_header_label.pack(fill="x", padx=4, pady=(0, 4))

        detail_container = tk.Frame(right, bg=BG)
        detail_container.pack(fill="both", expand=True)

        self._viewer_canvas = tk.Canvas(detail_container, bg=BG, highlightthickness=0)
        viewer_scroll = ttk.Scrollbar(detail_container, orient="vertical", command=self._viewer_canvas.yview)
        self._viewer_scroll_frame = tk.Frame(self._viewer_canvas, bg=BG)

        self._viewer_scroll_frame.bind(
            "<Configure>",
            lambda e: self._viewer_canvas.configure(scrollregion=self._viewer_canvas.bbox("all"))
        )
        self._viewer_canvas.create_window((0, 0), window=self._viewer_scroll_frame, anchor="nw")
        self._viewer_canvas.configure(yscrollcommand=viewer_scroll.set)
        self._viewer_canvas.bind(
            "<Configure>",
            lambda e: self._viewer_canvas.itemconfig("all", width=e.width)
        )

        viewer_scroll.pack(side="right", fill="y")
        self._viewer_canvas.pack(side="left", fill="both", expand=True)

        self._viewer_canvas.bind("<Enter>", self._bind_viewer_mousewheel)
        self._viewer_canvas.bind("<Leave>", self._unbind_viewer_mousewheel)

        # Track loaded session files: filename -> list[Timestamp]
        self._session_files: list[str] = []

    def _on_tab_changed(self, event=None) -> None:
        selected = self.notebook.index(self.notebook.select())
        viewer_index = self.notebook.index(self.viewer_tab)
        if selected == viewer_index:
            self._refresh_viewer_sessions()

    def _refresh_viewer_sessions(self) -> None:
        base_dir = self._base_dir()
        self._session_listbox.delete(0, tk.END)
        self._session_files = []

        try:
            pattern = re.compile(r"^\d{1,2}-\d{1,2}-\d{2}\(Session\d+\)\.json$", re.IGNORECASE)

            files = sorted(
                [f for f in os.listdir(base_dir) if pattern.match(f)],
                reverse=True,
            )
        except Exception:
            files = []

        if not files:
            self._session_listbox.insert(tk.END, "(no sessions found)")
            self._viewer_header_label.config(text=f"No sessions in: {base_dir}")
            return

        for f in files:
            self._session_files.append(os.path.join(base_dir, f))
            # Strip extension for display
            self._session_listbox.insert(tk.END, f[:-5])

    def _on_session_select(self, event=None) -> None:
        selection = self._session_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self._session_files):
            return

        filepath = self._session_files[index]
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            timestamps = [Timestamp.from_dict(d) for d in data]
        except Exception as e:
            messagebox.showerror("Error", f"Could not load file:\n{e}")
            return

        # Parse date from filename e.g. ObsTimeStamps2-28-26
        name = os.path.basename(filepath)[:-5]  # strip .json
        self._viewer_header_label.config(
            text=f"{name}  ·  {len(timestamps)} timestamp(s)"
        )
        self._render_viewer(timestamps)

    def _render_viewer(self, timestamps: list) -> None:
        for widget in self._viewer_scroll_frame.winfo_children():
            widget.destroy()

        if not timestamps:
            tk.Label(
                self._viewer_scroll_frame,
                text="No timestamps in this session.",
                bg=BG, fg=MUTED, font=("Arial", 10),
            ).pack(pady=20)
            return

        for ts in timestamps:
            row = tk.Frame(self._viewer_scroll_frame, bg=BG_CARD, bd=1, relief="solid")
            row.pack(fill="x", pady=2, padx=2)

            tk.Label(
                row, text=ts.timecode,
                font=("Arial", 11, "bold"), bg=BG_CARD, fg=ACCENT, width=9,
            ).pack(side="left", padx=8, pady=6)

            tk.Label(
                row,
                text=ts.comment if ts.comment else "(no comment)",
                font=("Arial", 10), bg=BG_CARD,
                fg="#333" if ts.comment else MUTED,
                anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=4)

    def _bind_viewer_mousewheel(self, event=None) -> None:
        self._viewer_canvas.bind_all("<MouseWheel>", self._on_viewer_mousewheel)
        self._viewer_canvas.bind_all("<Button-4>", self._on_viewer_mousewheel)
        self._viewer_canvas.bind_all("<Button-5>", self._on_viewer_mousewheel)

    def _unbind_viewer_mousewheel(self, event=None) -> None:
        self._viewer_canvas.unbind_all("<MouseWheel>")
        self._viewer_canvas.unbind_all("<Button-4>")
        self._viewer_canvas.unbind_all("<Button-5>")

    def _on_viewer_mousewheel(self, event) -> None:
        if event.num == 4:
            self._viewer_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._viewer_canvas.yview_scroll(1, "units")
        else:
            self._viewer_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_settings_tab(self) -> None:
        tab = self.settings_tab
        pad = {"padx": 10, "pady": 6}

        for i, text in enumerate(["OBS Host", "OBS Port", "Password", "Save Folder"]):
            tk.Label(tab, text=text, bg=BG, font=("Arial", 10)).grid(row=i, column=0, sticky="e", **pad)

        self.host_var         = tk.StringVar(value=self.cfg.get("host", "localhost"))
        self.port_var         = tk.StringVar(value=str(self.cfg.get("port", 4455)))
        self.pw_var           = tk.StringVar(value=self.cfg.get("password", ""))
        self.save_dir_var     = tk.StringVar(value=self.cfg.get("save_dir", ""))
        self.silent_close_var = tk.BooleanVar(value=self.cfg.get("silent_close", False))

        tk.Entry(tab, textvariable=self.host_var, width=26).grid(row=0, column=1, **pad)
        tk.Entry(tab, textvariable=self.port_var, width=26).grid(row=1, column=1, **pad)
        tk.Entry(tab, textvariable=self.pw_var, show="*", width=26).grid(row=2, column=1, **pad)

        folder_row = tk.Frame(tab, bg=BG)
        folder_row.grid(row=3, column=1, sticky="we", **pad)
        tk.Entry(folder_row, textvariable=self.save_dir_var, width=20).pack(side="left")
        tk.Button(folder_row, text="Browse", command=self._pick_dir).pack(side="left", padx=6)

        tk.Checkbutton(
            tab, text="X button saves & quits without prompt",
            variable=self.silent_close_var, bg=BG, font=("Arial", 10),
        ).grid(row=4, column=0, columnspan=2, pady=4, sticky="w", padx=10)

        tk.Button(
            tab, text="Change Hotkey", command=self._open_hotkey_window,
            bg=MUTED, fg="white", relief="flat", cursor="hand2",
        ).grid(row=5, column=0, columnspan=2, pady=(4, 2), ipadx=10, ipady=4)

        tk.Button(
            tab, text="Save Settings", command=self._save_settings,
            bg=SUCCESS, fg="white", relief="flat", cursor="hand2",
        ).grid(row=6, column=0, columnspan=2, pady=(2, 10), ipadx=10, ipady=4)

    # ------------------------------------------------------------------
    # Settings actions
    # ------------------------------------------------------------------

    def _pick_dir(self) -> None:
        d = filedialog.askdirectory()
        if d:
            self.save_dir_var.set(d)

    def _save_settings(self) -> None:
        self.cfg["host"]         = self.host_var.get().strip() or "localhost"
        self.cfg["password"]     = self.pw_var.get()
        self.cfg["save_dir"]     = self.save_dir_var.get().strip()
        self.cfg["silent_close"] = self.silent_close_var.get()

        try:
            self.cfg["port"] = int(self.port_var.get().strip())
        except ValueError:
            self.cfg["port"] = 4455

        save_config(self.cfg)
        self.filename = self._next_filename()
        self._obs_status = "Connecting to OBS..."
        self.status_label.config(text=self._obs_status)
        self._connect_obs()
        messagebox.showinfo("Settings", "Settings saved.")

    # ------------------------------------------------------------------
    # OBS helpers
    # ------------------------------------------------------------------

    def _is_recording(self) -> bool:
        if not self.client:
            return False
        try:
            return bool(self.client.get_record_status().output_active)
        except Exception:
            return False

    def _get_timecode(self) -> str | None:
        if not self.client:
            return None
        try:
            status = self.client.get_record_status()
            if not status.output_active:
                return None
            return format_seconds(status.output_duration // 1000)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    def _poll_obs(self) -> None:
        recording_now = self._is_recording()
        timecode = self._get_timecode()

        if timecode:
            self.status_label.config(text=f"● Recording  {timecode}")
        elif self.client:
            self.status_label.config(text="Not recording")
        else:
            self.status_label.config(text=self._obs_status)

        if self.was_recording and not recording_now:
            self._autosave_and_reset()

        if not self.was_recording and recording_now:
            self.filename = self._next_filename()

        self.was_recording = recording_now
        self.root.after(500, self._poll_obs)

    # ------------------------------------------------------------------
    # Timestamp actions
    # ------------------------------------------------------------------

    def _mark_timestamp(self) -> None:
        tc = self._get_timecode()
        if not tc:
            self.status_label.config(text="OBS is not recording.")
            return

        comment = self.comment_var.get().strip()
        self.timestamps.append(Timestamp(timecode=tc, comment=comment))

        self.comment_var.set("")
        self.comment_entry.focus_set()
        self._update_counter()
        self._refresh_timestamps_tab()

        label = f"Marked: {tc}" + (f'  —  "{comment}"' if comment else "")
        self.status_label.config(text=label)
        print(f"[LOG] {label}")

    def _update_counter(self) -> None:
        n = len(self.timestamps)
        self.counter_label.config(text=f"{n} marked")

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self) -> None:
        if not self.timestamps:
            self.status_label.config(text="No timestamps to copy.")
            return
        lines = [
            ts.timecode + (f"  —  {ts.comment}" if ts.comment else "")
            for ts in self.timestamps
        ]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.status_label.config(text=f"Copied {len(self.timestamps)} timestamp(s) to clipboard.")

    # ------------------------------------------------------------------
    # Timestamps tab
    # ------------------------------------------------------------------

    def _bind_mousewheel(self, event=None) -> None:
        self._ts_canvas.bind_all("<MouseWheel>", self._on_mousewheel)        # Windows/macOS
        self._ts_canvas.bind_all("<Button-4>", self._on_mousewheel)          # Linux scroll up
        self._ts_canvas.bind_all("<Button-5>", self._on_mousewheel)          # Linux scroll down

    def _unbind_mousewheel(self, event=None) -> None:
        self._ts_canvas.unbind_all("<MouseWheel>")
        self._ts_canvas.unbind_all("<Button-4>")
        self._ts_canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event) -> None:
        if event.num == 4:
            self._ts_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._ts_canvas.yview_scroll(1, "units")
        else:
            self._ts_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _refresh_timestamps_tab(self) -> None:
        if not self._live_scroll_frame:
            return

        for widget in self._live_scroll_frame.winfo_children():
            widget.destroy()

        if not self.timestamps:
            tk.Label(
                self._live_scroll_frame,
                text="No timestamps yet — start recording and hit your hotkey.",
                bg=BG, fg=MUTED, font=("Arial", 10), wraplength=340,
            ).pack(pady=30)
            return

        for i, ts in enumerate(self.timestamps):
            self._build_timestamp_row(i, ts)

    def _build_timestamp_row(self, index: int, ts: Timestamp) -> None:
        row = tk.Frame(self._live_scroll_frame, bg=BG_CARD, bd=1, relief="solid")
        row.pack(fill="x", pady=2, padx=4)

        tk.Label(
            row, text=ts.timecode,
            font=("Arial", 11, "bold"), bg=BG_CARD, fg=ACCENT, width=9,
        ).pack(side="left", padx=8, pady=6)

        comment_var = tk.StringVar(value=ts.comment)

        comment_label = tk.Label(
            row,
            text=ts.comment or "(no comment)",
            font=("Arial", 10), bg=BG_CARD,
            fg="#333" if ts.comment else MUTED,
            anchor="w",
        )
        comment_label.pack(side="left", fill="x", expand=True, padx=4)

        comment_entry = tk.Entry(row, textvariable=comment_var, font=("Arial", 10), relief="solid", bd=1)

        def start_edit(lbl=comment_label, ent=comment_entry):
            lbl.pack_forget()
            ent.pack(side="left", fill="x", expand=True, padx=4, pady=5)
            ent.focus_set()
            ent.select_range(0, tk.END)

        def save_edit(i=index, lbl=comment_label, ent=comment_entry, var=comment_var):
            new_comment = var.get().strip()
            self.timestamps[i].comment = new_comment
            lbl.config(
                text=new_comment or "(no comment)",
                fg="#333" if new_comment else MUTED,
            )
            ent.pack_forget()
            lbl.pack(side="left", fill="x", expand=True, padx=4)

        comment_entry.bind("<Return>", lambda e: save_edit())
        comment_entry.bind("<Escape>", lambda e: save_edit())

        btn_frame = tk.Frame(row, bg=BG_CARD)
        btn_frame.pack(side="right", padx=6)

        tk.Button(
            btn_frame, text="Edit", command=start_edit,
            bg=ACCENT, fg="white", font=("Arial", 8),
            width=4, relief="flat", cursor="hand2",
        ).pack(side="left", padx=2)

        tk.Button(
            btn_frame, text="✕",
            command=lambda i=index: self._delete_timestamp(i),
            bg=DANGER, fg="white", font=("Arial", 8),
            width=2, relief="flat", cursor="hand2",
        ).pack(side="left", padx=2)

    def _delete_timestamp(self, index: int) -> None:
        if 0 <= index < len(self.timestamps):
            removed = self.timestamps.pop(index)
            print(f"[LOG] Deleted: {removed.timecode}")
            self._update_counter()
            self._refresh_timestamps_tab()

    # ------------------------------------------------------------------
    # File saving
    # ------------------------------------------------------------------

    def _base_dir(self) -> str:
        d = (self.cfg.get("save_dir") or "").strip()
        if not d:
            d = str(Path(user_data_dir(APP_NAME, APP_AUTHOR)))
            Path(d).mkdir(parents=True, exist_ok=True)
            self.cfg["save_dir"] = d
            save_config(self.cfg)
        return d

    def _next_filename(self) -> str:
        now = datetime.now()
        date = f"{now.month}-{now.day}-{now.year % 100}"
        base_dir = self._base_dir()
        session = 1
        while True:
            path = os.path.join(base_dir, f"{date}(Session{session}).json")
            if not os.path.exists(path):
                return path
            session += 1

    def _save_timestamps(self) -> None:
        if not self.timestamps:
            print("[INFO] No timestamps to save.")
            return
        os.makedirs(self._base_dir(), exist_ok=True)
        data = [ts.to_dict() for ts in self.timestamps]
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[INFO] Saved {len(self.timestamps)} timestamp(s) to {self.filename}")

    def _autosave_and_reset(self) -> None:
        self._save_timestamps()
        self.timestamps.clear()
        self._update_counter()
        self.filename = self._next_filename()
        self._refresh_timestamps_tab()
        print("[INFO] Ready for next session.")

    # ------------------------------------------------------------------
    # Hotkey management
    # ------------------------------------------------------------------

    def _stop_hotkey_listener(self) -> None:
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None

    def _start_hotkey_listener(self) -> None:
        self._stop_hotkey_listener()
        target = self.cfg.get("hotkey", "f12").lower()

        def on_press(key):
            try:
                pressed = key.char if hasattr(key, "char") and key.char else key.name
                if pressed and pressed.lower() == target:
                    self._mark_timestamp()
            except AttributeError:
                pass

        self.hotkey_listener = keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()
        print("[INFO] Hotkey listener started.")

    def _open_hotkey_window(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Set New Hotkey")
        tk.Label(win, text="Press any key to set as new hotkey...", font=("Arial", 14)).pack(pady=20)

        def on_key_press(key):
            try:
                pressed = key.char if hasattr(key, "char") and key.char else key.name
                if pressed:
                    self.cfg["hotkey"] = pressed.lower()
                    save_config(self.cfg)
                    self.hotkey_label.config(text=f"Hotkey: {self.cfg['hotkey'].upper()}")
                    self._start_hotkey_listener()
                    self.status_label.config(text=f"Hotkey set: {self.cfg['hotkey'].upper()}")
                    win.destroy()
            except Exception as e:
                print(f"[ERROR] Key press handling failed: {e}")
            return False

        keyboard.Listener(on_press=on_key_press).start()

    # ------------------------------------------------------------------
    # Exit handling
    # ------------------------------------------------------------------

    def _persist_geometry(self) -> None:
        try:
            self.cfg["geometry"] = self.root.winfo_geometry()
            save_config(self.cfg)
        except Exception:
            pass

    def _quit(self, save: bool = True) -> None:
        self._stop_hotkey_listener()
        if save:
            self._save_timestamps()
        self._persist_geometry()
        self.root.destroy()

    def _save_and_exit(self) -> None:
        self._quit(save=True)

    def _on_close(self) -> None:
        if self.cfg.get("silent_close", False):
            self._quit(save=True)
            return
        answer = messagebox.askyesnocancel("Quit", "Save timestamps before quitting?")
        if answer is None:
            return
        self._quit(save=answer)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = OBSTimestampLogger(root)
    root.mainloop()
