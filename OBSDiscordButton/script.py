import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from obsws_python import ReqClient
from datetime import datetime
import os
from pynput import keyboard
import json
import sys

# Windows taskbar icon fix
if sys.platform.startswith('win'):
    import ctypes

CFG_PATH = "config.json"
DEFAULT_CFG = {
    "host": "localhost",
    "port": 4455,
    "password": "JimBob123",
    "hotkey": "f12",
    "save_dir": "",
    "geometry": ""
}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_config():
    cfg = DEFAULT_CFG.copy()
    try:
        if os.path.exists(CFG_PATH):
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    return cfg

def save_config(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[WARN] failed to save config: {e}")

class OBSTimestampLogger:
    def __init__(self, root):
        self.root = root
        self.root.title("Discord Moments Logger")
        try:
            self.root.iconbitmap(resource_path("thatstheone.ico"))
        except Exception:
            pass

        if sys.platform.startswith('win'):
            try:
                myappid = 'mycompany.discordmomentstracker.1.0'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        self.cfg = load_config()
        if self.cfg.get("geometry"):
            try:
                self.root.geometry(self.cfg["geometry"])
            except Exception:
                pass

        self.timestamps = []                   # list[str] like "HH:MM:SS"
        self.hotkey_listener = None
        self.root.configure(bg="#f0f2f5")

        # connect OBS
        try:
            self.client = ReqClient(
                host=self.cfg["host"],
                port=int(self.cfg["port"]),
                password=self.cfg["password"]
            )
            self.status_label_text = "Connected to OBS WebSocket."
            print("[INFO] Connected to OBS.")
        except Exception as e:
            self.client = None
            self.status_label_text = "OBS not connected. Start OBS and try again."
            print(f"[ERROR] Could not connect to OBS: {e}")

        # --- filename/session + edge detection ---
        self.filename = self._next_filename()
        self.was_recording = False  # remember last state to detect stop/start edges

        # ---------- TABS ----------
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)

        # Main tab (keep your original look)
        self.main_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(self.main_tab, text="Main")

        # Settings tab
        self.settings_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(self.settings_tab, text="Settings")

        # ---------- MAIN UI ----------
        self.hotkey_label = tk.Label(
            self.main_tab,
            text=f"Current Hotkey: {self.cfg.get('hotkey', 'F12').upper()}",
            font=("Arial", 14),
            bg="#f0f2f5"
        )
        self.hotkey_label.pack(pady=5)

        self.title_label = tk.Label(self.main_tab, text="Discord Moments Tracker", font=("Arial", 20, "bold"), bg="#f0f2f5")
        self.title_label.pack(pady=10)

        self.button_frame = tk.Frame(self.main_tab, bg="#f0f2f5")
        self.button_frame.pack(pady=20)

        self.mark_button = tk.Button(
            self.button_frame,
            text="Mark Funny Moment",
            command=self.mark_timestamp,
            bg="#007BFF", fg="white",
            font=("Arial", 16), width=25, height=2
        )
        self.mark_button.pack(pady=10)

        self.change_hotkey_button = tk.Button(
            self.button_frame,
            text="Change Hotkey",
            command=self.open_hotkey_window,
            bg="#6c757d", fg="white",
            font=("Arial", 14), width=25, height=2
        )
        self.change_hotkey_button.pack(pady=10)

        self.save_exit_button = tk.Button(
            self.button_frame,
            text="Save & Exit",
            command=self.save_and_exit,
            bg="#28a745", fg="white",
            font=("Arial", 14), width=25, height=2
        )
        self.save_exit_button.pack(pady=10)

        self.status_label = tk.Label(
            self.main_tab,
            text=self.status_label_text,
            font=("Arial", 12),
            bg="#f8f9fa",
            relief="sunken", bd=2,
            width=50, anchor="center"
        )
        self.status_label.pack(pady=15)

        # ---------- SETTINGS UI ----------
        self._build_settings_ui()

        # timers / listeners
        self.root.after(500, self._poll_obs)  # handles autosave-on-stop + new-session-on-start
        self.start_hotkey_listener()

        # intercept window close (the X)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ----- Settings tab -----
    def _build_settings_ui(self):
        pad = {'padx': 8, 'pady': 6}

        tk.Label(self.settings_tab, text="OBS Host", bg="#f0f2f5").grid(row=0, column=0, sticky="e", **pad)
        tk.Label(self.settings_tab, text="OBS Port", bg="#f0f2f5").grid(row=1, column=0, sticky="e", **pad)
        tk.Label(self.settings_tab, text="Password", bg="#f0f2f5").grid(row=2, column=0, sticky="e", **pad)
        tk.Label(self.settings_tab, text="Save Folder", bg="#f0f2f5").grid(row=3, column=0, sticky="e", **pad)

        self.host_var = tk.StringVar(value=self.cfg.get("host", "localhost"))
        self.port_var = tk.StringVar(value=str(self.cfg.get("port", 4455)))
        self.pw_var   = tk.StringVar(value=self.cfg.get("password", ""))
        self.save_dir_var = tk.StringVar(value=self.cfg.get("save_dir", ""))

        tk.Entry(self.settings_tab, textvariable=self.host_var, width=28).grid(row=0, column=1, **pad)
        tk.Entry(self.settings_tab, textvariable=self.port_var, width=28).grid(row=1, column=1, **pad)
        tk.Entry(self.settings_tab, textvariable=self.pw_var, show="*", width=28).grid(row=2, column=1, **pad)

        row = tk.Frame(self.settings_tab, bg="#f0f2f5")
        row.grid(row=3, column=1, sticky="we", **pad)
        tk.Entry(row, textvariable=self.save_dir_var, width=22).pack(side="left")
        tk.Button(row, text="Browse", command=self._pick_dir).pack(side="left", padx=6)

        tk.Button(self.settings_tab, text="Save Settings", command=self._save_settings, bg="#28a745", fg="white").grid(row=4, column=0, columnspan=2, pady=10)

    def _pick_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.save_dir_var.set(d)

    def _save_settings(self):
        self.cfg["host"] = self.host_var.get().strip() or "localhost"
        try:
            self.cfg["port"] = int(self.port_var.get().strip())
        except ValueError:
            self.cfg["port"] = 4455
        self.cfg["password"] = self.pw_var.get()
        self.cfg["save_dir"] = self.save_dir_var.get().strip()
        save_config(self.cfg)

        # reconnect
        try:
            self.client = ReqClient(
                host=self.cfg["host"],
                port=self.cfg["port"],
                password=self.cfg["password"]
            )
            self.status_label_text = "Connected to OBS WebSocket."
        except Exception as e:
            self.client = None
            self.status_label_text = "OBS not connected. Start OBS and try again."
            print(f"[ERROR] Could not connect to OBS: {e}")

        self.status_label.config(text=self.status_label_text)
        messagebox.showinfo("Settings", "Settings saved.")

    # ----- OBS helpers -----
    def _is_recording(self):
        if not self.client:
            return False
        try:
            return bool(self.client.get_record_status().output_active)
        except Exception:
            return False

    def _get_timecode(self):
        if not self.client:
            return None
        try:
            st = self.client.get_record_status()
            if not st.output_active:
                return None
            seconds = (st.output_duration // 1000)
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h:02}:{m:02}:{s:02}"
        except Exception:
            return None

    # ----- polling loop: updates status + handles stop/start edges -----
    def _poll_obs(self):
        rec_now = self._is_recording()

        # status text
        tc = self._get_timecode()
        if tc:
            self.status_label.config(text=f"Recording... {tc}")
        else:
            self.status_label.config(text="OBS is not recording.")

        # STOP edge: was True -> now False  ==> autosave & prep new file
        if self.was_recording and not rec_now:
            self._autosave_and_reset()

        # START edge: was False -> now True  ==> fresh file for new session
        if not self.was_recording and rec_now:
            # don’t wipe if user manually saved already; we just make sure a fresh filename is ready
            self.filename = self._next_filename()

        self.was_recording = rec_now
        self.root.after(500, self._poll_obs)

    # ----- UI actions -----
    def mark_timestamp(self):
        tc = self._get_timecode()
        if tc:
            self.timestamps.append(tc)
            self.status_label.config(text=f"Marked: {tc}")
            print(f"[LOG] Timestamp marked: {tc}")
        else:
            self.status_label.config(text="OBS is not recording.")

    # ----- saving -----
    def _base_dir(self):
        return self.cfg.get("save_dir") or os.getcwd()

    def _next_filename(self):
        base_dir = self._base_dir()
        base_name = f"ObsTimeStamps{datetime.now().month}-{datetime.now().day}-{datetime.now().year % 100}"
        counter = 0
        filename = os.path.join(base_dir, f"{base_name}.txt")
        while os.path.exists(filename):
            counter += 1
            filename = os.path.join(base_dir, f"{base_name} ({counter}).txt")
        return filename

    def save_timestamps(self):
        if not self.timestamps:
            print("[INFO] No timestamps; not writing a file.")
            return
        # ensure directory exists
        os.makedirs(self._base_dir(), exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as f:
            for ts in self.timestamps:
                f.write(ts + "\n")
        print(f"[INFO] Saved timestamps to {self.filename}")

    def _autosave_and_reset(self):
        # save only if we have data
        if self.timestamps:
            self.save_timestamps()
        # prepare for next recording session
        self.timestamps.clear()
        self.filename = self._next_filename()
        print("[INFO] Ready for next session.")

    def save_and_exit(self):
        self.save_timestamps()
        self._persist_geometry()
        self.root.destroy()

    # ----- hotkey -----
    def start_hotkey_listener(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()

        def on_press(key):
            try:
                if hasattr(key, 'char') and key.char:
                    pressed_key = key.char
                else:
                    pressed_key = key.name
                if pressed_key and pressed_key.lower() == self.cfg.get('hotkey', 'f12').lower():
                    self.mark_timestamp()
            except AttributeError:
                pass

        self.hotkey_listener = keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()
        print("[INFO] Hotkey listener started.")

    def open_hotkey_window(self):
        win = tk.Toplevel(self.root)
        win.title("Set New Hotkey")
        tk.Label(win, text="Press any key to set as new hotkey...", font=("Arial", 14)).pack(pady=20)

        def on_key_press(key):
            try:
                if hasattr(key, 'char') and key.char:
                    pressed = key.char
                else:
                    pressed = key.name
                if pressed:
                    self.cfg["hotkey"] = pressed.lower()
                    save_config(self.cfg)
                    self.hotkey_label.config(text=f"Current Hotkey: {self.cfg['hotkey'].upper()}")
                    self.start_hotkey_listener()
                    win.destroy()
                    self.status_label.config(text=f"New hotkey set: {self.cfg['hotkey']}")
            except Exception as e:
                print(f"[ERROR] Key press handling failed: {e}")
            finally:
                return False

        listener = keyboard.Listener(on_press=on_key_press)
        listener.start()

    # ----- window close (the X) -----
    def on_close(self):
        answer = messagebox.askyesnocancel("Save and quit?", "Save and quit?")
        if answer is None:
            return
        if answer:
            self.save_timestamps()
        self._persist_geometry()
        self.root.destroy()

    def _persist_geometry(self):
        try:
            self.cfg["geometry"] = self.root.winfo_geometry()
            save_config(self.cfg)
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = OBSTimestampLogger(root)
    root.mainloop()
