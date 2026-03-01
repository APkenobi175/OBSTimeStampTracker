# Discord Moments Logger

<div align="center">
  <img src="OBSDiscordButton\assets\Screenshot 2026-02-28 191157.png" alt="Main Screen" width="420"/>
  <br/>
  <em>Mark funny moments in real time while OBS records</em>
</div>

---

## Table of Contents
- [Description](#description)
- [Changelog](#changelog)
- [Downloads](#downloads)
- [Set Up Instructions](#set-up-instructions)
- [How To Use](#how-to-use)

---

## Description

**Discord Moments Logger** connects to OBS via WebSocket and lets you mark timestamps during a recording session with optional comments, so you can find your funny moments later without searching through the whole video.

Timestamps are saved as `.json` files and can be browsed directly inside the app from the History tab.

---

## Changelog

### Version 2.0
> Complete rewrite and redesign

##### What's New
- **Comments** — add a note to each timestamp as you mark it
- **Timestamps tab** - view, edit, and delete timestamps for the current session live
- **History tab** - browse all past recording sessions from your save folder, click to view
- **JSON output** - timestamps now save as structured `.json` instead of plain text
- **Smarter filenames** - files are now named `2-28-26(Session1).json`, `2-28-26(Session2).json` etc.
- **Save & Start Fresh** - save your current session and start a new one without exiting
- **Copy to Clipboard** - copy all timestamps for the current session with one click
- **Configurable save folder** - choose where your files are saved from the Settings tab
- **Configurable OBS connection** - set host, port, and password from the Settings tab (no more hardcoded values)
- **Silent close** - option to have the X button save and quit without a prompt
- **Non-blocking startup** - app launches instantly even if OBS isn't running yet, a seperate thread handles the connection in the bacgkround and the status bar will update once connected
- **Auto-save on recording stop** - timestamps are automatically saved when OBS stops recording
- **Counter badge** - live count of timestamps marked this session

---

### Version 1.0
> Initial Release
- Application created
- Basic timestamp marking via button or hotkey
- F12 default hotkey
- Plain text `.txt` output

---

## Downloads

<table>
  <tr>
    <th>Platform</th>
    <th>Version</th>
    <th>Link</th>
  </tr>
  <tr>
    <td> Windows</td>
    <td>2.0</td>
    <td><a href="https://www.mediafire.com/file/z3aczsyjdl3f00u/OBS_Sessions_Setup.exe/file">Download</a></td>
  </tr>
  <tr>
    <td> Windows</td>
    <td>1.0 (legacy)</td>
    <td><a href="https://www.mediafire.com/file/x7oqkeqvetzbkcf/OBSTimeTracker.exe/file">Download</a></td>
  </tr>
  <tr>
    <td> Linux</td>
    <td>—</td>
    <td>No official support</td>
  </tr>
  <tr>
    <td> macOS</td>
    <td>—</td>
    <td>No official support</td>
  </tr>
</table>

---

## Set Up Instructions

### Step 1 — Install OBS
Download and install OBS from [obsproject.com](https://obsproject.com/download) if you haven't already.

### Step 2 — Enable OBS WebSocket

1. Open OBS
2. In the top menu click **Tools → WebSocket Server Settings**
3. Check **Enable WebSocket Server**
4. Set the port to `4455`
5. Set a password, you'll enter this in the app's Settings tab

<div align="center">
  <img src="OBSDiscordButton\assets\Screenshot 2026-02-28 191240.png" alt="Settings Tab" width="420"/>
  <br/>
  <em>Enter your OBS connection details in the Settings tab</em>
</div>

### Step 3 — Configure the App

Open the app and go to the **Settings tab**:

- **OBS Host** - `localhost` (or your Windows IP if running across WSL)
- **OBS Port** - `4455`
- **Password** - whatever you set in OBS WebSocket settings
- **Save Folder** - choose where your session `.json` files will be saved
- Hit **Save Settings**

The status bar at the bottom of the Main tab will confirm you're connected.

> [!NOTE]
> The app will launch even if OBS isn't running. it connects in the background and the status bar will update once connected.

---

## How To Use

<div align="center">
  <img src="OBSDiscordButton\assets\Screenshot 2026-02-28 191157.png" alt="Main Tab" width="420"/>
</div>

### Marking Timestamps

Start a recording in OBS. The status bar will show `● Recording  00:00:00`.

To mark a timestamp:
- Type an optional comment in the **Comment** box, then
- Click **Mark Funny Moment**, or
- Press your hotkey (default: **F12**)

> [!NOTE]
> The comment box clears automatically after each mark. You can also press **Enter** from the comment box to mark without clicking the button.

The counter badge in the top right updates live so you always know how many moments you've marked.

---

### Managing Timestamps

<div align="center">
  <img src="OBSDiscordButton\assets\Screenshot 2026-02-28 191213.png" alt="Timestamps Tab" width="420"/>
  <br/>
  <em>Edit or delete individual timestamps during your session</em>
</div>

Click the **Timestamps tab** to see everything you've marked this session. From here you can:

- **Edit** a comment by clicking the Edit button - press Enter or Escape to save
- **Delete** a timestamp with the X button
- **Copy All** to clipboard with one click

---

### Saving

You have three options:

| Action | What it does |
|---|---|
| **Save & Start Fresh** | Saves current session to a `.json` file and clears the list for a new session |
| **Save & Exit** | Saves and closes the app |
| **Auto-save** | Happens automatically when OBS stops recording |

> [!WARNING]
> If you close the app with the X button and choose **No** at the prompt, your unsaved timestamps will be lost. Enable **"X button saves & quits without prompt"** in Settings to always save on close.

Files are named like this:
```
2-28-26(Session1).json
2-28-26(Session2).json
3-1-26(Session1).json
```

Each file contains structured JSON:
```json
[
  { "timestamp": "00:16:12", "comment": "Kevin said something dumb" },
  { "timestamp": "00:34:55", "comment": "" }
]
```

---

### Viewing Past Sessions

<div align="center">
  <img src="OBSDiscordButton\assets\Screenshot 2026-02-28 191226.png" alt="History Tab" width="420"/>
  <br/>
  <em>Browse and view all past sessions from your save folder</em>
</div>

Click the **History tab** to browse all past sessions saved in your configured folder. Click any session on the left to view its timestamps and comments on the right.

---

### Changing the Hotkey

Go to **Settings → Change Hotkey** and press any key. The new hotkey is saved immediately.
