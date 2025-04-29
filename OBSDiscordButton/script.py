import tkinter as tk
from obsws_python import ReqClient
from datetime import datetime
import os
from pynput import keyboard
import threading
import json
import sys


# Windows taskbar icon fix
if sys.platform.startswith('win'):
    import ctypes


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller .exe """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class OBSTimestampLogger:
    def __init__(self, root):
        self.root = root
        self.root.title("Discord Moments Logger")
        self.root.iconbitmap(resource_path("thatstheone.ico"))
        # Set taskbar icon on Windows
        if sys.platform.startswith('win'):
            myappid = 'mycompany.discordmomentstracker.1.0'  # Arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)



        self.hotkey_label = tk.Label(
            root,
            text="Current Hotkey: [Loading...]",  # Temporary placeholder
            font=("Arial", 14),
            bg="#f0f2f5"
        )
        self.hotkey_label.pack(pady=5)

        self.timestamps = []
        self.hotkey_listener = None
        self.root.configure(bg="#f0f2f5")


        base_name = f"ObsTimeStamps{datetime.now().month}-{datetime.now().day}-{datetime.now().year % 100}"
        counter = 0
        filename = f"{base_name}.txt"
        while os.path.exists(filename):
            counter += 1
            filename = f"{base_name} ({counter}).txt"
        self.filename = filename

        try:
            self.client = ReqClient(host="localhost", port=4455, password="JimBob123")
            self.status_label_text = "Connected to OBS WebSocket."
            print("[INFO] Connected to OBS.")
        except Exception as e:
            self.client = None
            self.status_label_text = "OBS not connected. Start OBS and try again."
            print(f"[ERROR] Could not connect to OBS: {e}")

        self.title_label = tk.Label(root, text="Discord Moments Tracker", font=("Arial", 20, "bold"))
        self.title_label.pack(pady=10)

        self.button_frame = tk.Frame(root)
        self.button_frame.pack(pady=20)

        self.mark_button = tk.Button(
            self.button_frame,
            text="Mark Funny Moment",
            command=self.mark_timestamp,
            bg="#007BFF",
            fg="white",
            font=("Arial", 16),
            width=25,
            height=2
        )
        self.mark_button.pack(pady=10)

        self.change_hotkey_button = tk.Button(
            self.button_frame,
            text="Change Hotkey",
            command=self.open_hotkey_window,
            bg="#6c757d",
            fg="white",
            font=("Arial", 14),
            width=25,
            height=2
        )
        self.change_hotkey_button.pack(pady=10)

        self.save_exit_button = tk.Button(
            self.button_frame,
            text="Save & Exit",
            command=self.save_and_exit,
            bg="#28a745",
            fg="white",
            font=("Arial", 14),
            width=25,
            height=2
        )
        self.save_exit_button.pack(pady=10)

        self.status_label = tk.Label(
            root,
            text=self.status_label_text,
            font=("Arial", 12),
            bg="#f8f9fa",
            relief="sunken",
            bd=2,
            width=50,
            anchor="center"
        )
        self.status_label.pack(pady=15)
        self.root.after(1000, self.update_status)
        self.load_hotkey()
        self.start_hotkey_listener()




    def get_obs_timecode(self):
        try:
            status = self.client.get_record_status()
            if status.output_active:
                duration_ms = status.output_duration
                seconds = duration_ms // 1000
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                return f"{hours:02}:{minutes:02}:{seconds:02}"
            else:
                return None
        except Exception as e:
            print(f"[ERROR] {e}")
            return None

    def mark_timestamp(self):
        timecode = self.get_obs_timecode()
        if timecode:
            self.timestamps.append(timecode)
            self.status_label.config(text=f"Marked: {timecode}")
            print(f"[LOG] Timestamp marked: {timecode}")
        else:
            self.status_label.config(text="OBS is not recording.")

    def update_status(self):
        timecode = self.get_obs_timecode()
        if timecode:
            self.status_label.config(text=f"Recording... {timecode}")
        else:
            self.status_label.config(text="OBS is not recording.")
        self.root.after(1000, self.update_status)

    def save_timestamps(self):
        with open(self.filename, "w") as f:
            for ts in self.timestamps:
                f.write(ts + "\n")
        print(f"[INFO] Saved timestamps to {self.filename}")

    def save_and_exit(self):
        self.save_timestamps()
        self.root.destroy()

    def load_hotkey(self):
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.hotkey = config.get('hotkey', 'f12')
                print(f"[INFO] Hotkey loaded: {self.hotkey}")
        except Exception as e:
            print(f"[ERROR] Could not load config.json: {e}")
            self.hotkey = 'f12'

        # NEW: Update hotkey display
        if hasattr(self, 'hotkey_label'):
            self.hotkey_label.config(text=f"Current Hotkey: {self.hotkey.upper()}")

    def start_hotkey_listener(self):
        # If a previous listener exists, stop it
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            print("[INFO] Old hotkey listener stopped.")

        def on_press(key):
            try:
                if hasattr(key, 'char'):
                    pressed_key = key.char
                else:
                    pressed_key = key.name  # For special keys like 'f12', 'esc', etc.

                if pressed_key.lower() == self.hotkey.lower():
                    print(f"[HOTKEY] {pressed_key} pressed! Marking timestamp.")
                    self.mark_timestamp()
            except AttributeError:
                pass

        # Create and start new listener
        self.hotkey_listener = keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()
        print("[INFO] New hotkey listener started.")

    def open_hotkey_window(self):
        hotkey_window = tk.Toplevel(self.root)
        hotkey_window.title("Set New Hotkey")

        label = tk.Label(hotkey_window, text="Press any key to set as new hotkey...", font=("Arial", 14))
        label.pack(pady=20)

        def on_key_press(key):
            try:
                if hasattr(key, 'char') and key.char:
                    pressed_key = key.char
                else:
                    pressed_key = key.name

                if pressed_key:
                    self.hotkey = pressed_key.lower()
                    self.save_hotkey_to_config()
                    self.restart_hotkey_listener()
                    hotkey_window.destroy()
                    self.status_label.config(text=f"New hotkey set: {self.hotkey}")
                    print(f"[INFO] New hotkey saved: {self.hotkey}")
            except Exception as e:
                print(f"[ERROR] Key press handling failed: {e}")
            finally:
                return False  # Stop listener after first key

        # Start a temporary listener to capture the next key press
        listener = keyboard.Listener(on_press=on_key_press)
        listener.start()

        def save_new_hotkey():
            new_hotkey = hotkey_entry.get().strip()
            if new_hotkey:
                self.hotkey = new_hotkey
                self.save_hotkey_to_config()
                self.restart_hotkey_listener()
                hotkey_window.destroy()
                self.status_label.config(text=f"New hotkey set: {self.hotkey}")
                print(f"[INFO] New hotkey saved: {self.hotkey}")

        save_button = tk.Button(hotkey_window, text="Save Hotkey", command=save_new_hotkey)
        save_button.pack(pady=10)

    def save_hotkey_to_config(self):
        try:
            with open('config.json', 'w') as f:
                json.dump({"hotkey": self.hotkey}, f)
            print("[INFO] Hotkey saved to config.json")
        except Exception as e:
            print(f"[ERROR] Failed to save hotkey: {e}")

    def restart_hotkey_listener(self):
        # Just start a new listener. Old listener is a daemon and will die when the app closes.
        self.start_hotkey_listener()





if __name__ == "__main__":
    root = tk.Tk()
    app = OBSTimestampLogger(root)
    root.mainloop()
