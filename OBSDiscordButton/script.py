import sys
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pynput import keyboard
from obsws_python import ReqClient

# Windows taskbar icon fix
if sys.platform.startswith("win"):
    import ctypes

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CFG_PATH = "config/config.json"
DEFAULT_CFG = {
    "host": "localhost",
    "port": 4455,
    "password": "JimBob123",
    "hotkey": "f12",
    "save_dir": "",
    "geometry": "",
    "silent_close": False,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resource_path(relative_path: str) -> str:
    """Return the absolute path to a bundled resource (PyInstaller-aware)."""
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative_path)


def load_config() -> dict:
    cfg = DEFAULT_CFG.copy()
    try:
        if os.path.exists(CFG_PATH):
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
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
        self.root.title("Discord Moments Logger")
        self.root.configure(bg="#f0f2f5")

        # Icon
        try:
            self.root.iconbitmap(resource_path("thatstheone.ico"))
        except Exception:
            pass

        # Windows taskbar app ID
        if sys.platform.startswith("win"):
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "mycompany.discordmomentstracker.1.0"
                )
            except Exception:
                pass

        # Config & geometry
        self.cfg = load_config()
        if self.cfg.get("geometry"):
            try:
                self.root.geometry(self.cfg["geometry"])
            except Exception:
                pass

        # State
        self.timestamps: list[str] = []
        self.hotkey_listener: keyboard.Listener | None = None
        self.was_recording = False
        self._obs_status = "Connecting to OBS..."

        # OBS connection (non-blocking)
        self.client: ReqClient | None = None
        self._connect_obs()

        # Session filename (determined once per recording session)
        self.filename = self._next_filename()

        # Build UI
        self._build_ui()

        # Start background tasks
        self.root.after(500, self._poll_obs)
        self._start_hotkey_listener()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # OBS connection
    # ------------------------------------------------------------------

    def _connect_obs(self) -> None:
        """Attempt to connect to OBS in a background thread so the UI doesn't block."""
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

        self.main_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(self.main_tab, text="Main")

        self.settings_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(self.settings_tab, text="Settings")

        self._build_main_tab()
        self._build_settings_tab()

    def _build_main_tab(self) -> None:
        tab = self.main_tab

        self.hotkey_label = tk.Label(
            tab,
            text=f"Current Hotkey: {self.cfg.get('hotkey', 'F12').upper()}",
            font=("Arial", 14),
            bg="#f0f2f5",
        )
        self.hotkey_label.pack(pady=5)

        tk.Label(tab, text="Discord Moments Tracker", font=("Arial", 20, "bold"), bg="#f0f2f5").pack(pady=10)

        btn_frame = tk.Frame(tab, bg="#f0f2f5")
        btn_frame.pack(pady=20)

        btn_cfg = {"font": ("Arial", 16), "width": 25, "height": 2, "fg": "white"}

        tk.Button(
            btn_frame, text="Mark Funny Moment", command=self._mark_timestamp,
            bg="#007BFF", **btn_cfg
        ).pack(pady=10)

        tk.Button(
            btn_frame, text="Change Hotkey", command=self._open_hotkey_window,
            bg="#6c757d", **{**btn_cfg, "font": ("Arial", 14)}
        ).pack(pady=10)

        tk.Button(
            btn_frame, text="Save & Exit", command=self._save_and_exit,
            bg="#28a745", **{**btn_cfg, "font": ("Arial", 14)}
        ).pack(pady=10)

        self.status_label = tk.Label(
            tab,
            text=self._obs_status,
            font=("Arial", 12),
            bg="#f8f9fa",
            relief="sunken", bd=2,
            width=50, anchor="center",
        )
        self.status_label.pack(pady=15)

    def _build_settings_tab(self) -> None:
        tab = self.settings_tab
        pad = {"padx": 8, "pady": 6}

        labels = ["OBS Host", "OBS Port", "Password", "Save Folder"]
        for i, text in enumerate(labels):
            tk.Label(tab, text=text, bg="#f0f2f5").grid(row=i, column=0, sticky="e", **pad)

        self.host_var         = tk.StringVar(value=self.cfg.get("host", "localhost"))
        self.port_var         = tk.StringVar(value=str(self.cfg.get("port", 4455)))
        self.pw_var           = tk.StringVar(value=self.cfg.get("password", ""))
        self.save_dir_var     = tk.StringVar(value=self.cfg.get("save_dir", ""))
        self.silent_close_var = tk.BooleanVar(value=self.cfg.get("silent_close", False))

        tk.Entry(tab, textvariable=self.host_var, width=28).grid(row=0, column=1, **pad)
        tk.Entry(tab, textvariable=self.port_var, width=28).grid(row=1, column=1, **pad)
        tk.Entry(tab, textvariable=self.pw_var, show="*", width=28).grid(row=2, column=1, **pad)

        # Save folder row with browse button
        folder_row = tk.Frame(tab, bg="#f0f2f5")
        folder_row.grid(row=3, column=1, sticky="we", **pad)
        tk.Entry(folder_row, textvariable=self.save_dir_var, width=22).pack(side="left")
        tk.Button(folder_row, text="Browse", command=self._pick_dir).pack(side="left", padx=6)

        # Silent close checkbox
        tk.Checkbutton(
            tab,
            text="X button saves & quits without prompt",
            variable=self.silent_close_var,
            bg="#f0f2f5",
        ).grid(row=4, column=0, columnspan=2, pady=4)

        tk.Button(
            tab, text="Save Settings", command=self._save_settings,
            bg="#28a745", fg="white"
        ).grid(row=5, column=0, columnspan=2, pady=10)

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
        """Return HH:MM:SS of current recording position, or None if not recording."""
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

        # Update status bar
        if timecode:
            self.status_label.config(text=f"Recording... {timecode}")
        elif self.client:
            self.status_label.config(text="OBS is not recording.")
        else:
            self.status_label.config(text=self._obs_status)

        # Edge: recording stopped → autosave
        if self.was_recording and not recording_now:
            self._autosave_and_reset()

        # Edge: recording started → prepare a fresh filename
        if not self.was_recording and recording_now:
            self.filename = self._next_filename()

        self.was_recording = recording_now
        self.root.after(500, self._poll_obs)

    # ------------------------------------------------------------------
    # Timestamp actions
    # ------------------------------------------------------------------

    def _mark_timestamp(self) -> None:
        tc = self._get_timecode()
        if tc:
            self.timestamps.append(tc)
            self.status_label.config(text=f"Marked: {tc}")
            print(f"[LOG] Timestamp marked: {tc}")
        else:
            self.status_label.config(text="OBS is not recording.")

    # ------------------------------------------------------------------
    # File saving
    # ------------------------------------------------------------------

    def _base_dir(self) -> str:
        return self.cfg.get("save_dir") or os.getcwd()

    def _next_filename(self) -> str:
        now = datetime.now()
        base = f"ObsTimeStamps{now.month}-{now.day}-{now.year % 100}"
        base_dir = self._base_dir()
        path = os.path.join(base_dir, f"{base}.txt")
        counter = 0
        while os.path.exists(path):
            counter += 1
            path = os.path.join(base_dir, f"{base} ({counter}).txt")
        return path

    def _save_timestamps(self) -> None:
        if not self.timestamps:
            print("[INFO] No timestamps to save.")
            return
        os.makedirs(self._base_dir(), exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write("\n".join(self.timestamps) + "\n")
        print(f"[INFO] Saved {len(self.timestamps)} timestamp(s) to {self.filename}")

    def _autosave_and_reset(self) -> None:
        self._save_timestamps()
        self.timestamps.clear()
        self.filename = self._next_filename()
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
                    self.hotkey_label.config(text=f"Current Hotkey: {self.cfg['hotkey'].upper()}")
                    self._start_hotkey_listener()
                    self.status_label.config(text=f"New hotkey set: {self.cfg['hotkey'].upper()}")
                    win.destroy()
            except Exception as e:
                print(f"[ERROR] Key press handling failed: {e}")
            return False  # stop listener after first key

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
        """Stop listeners, optionally save, persist geometry, and destroy the window."""
        self._stop_hotkey_listener()
        if save:
            self._save_timestamps()
        self._persist_geometry()
        self.root.destroy()

    def _save_and_exit(self) -> None:
        self._quit(save=True)

    def _on_close(self) -> None:
        """Called when the user clicks the window's X button."""
        if self.cfg.get("silent_close", False):
            self._quit(save=True)
            return

        answer = messagebox.askyesnocancel("Quit", "Save timestamps before quitting?")
        if answer is None:
            return  # Cancel — do nothing
        self._quit(save=answer)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = OBSTimestampLogger(root)
    root.mainloop()
