# OBS Time Stamp Tracker

## Table of Contents:
- [Description](#description)
- [ChangeLog](#changelog)
- [Downloads](#downloads)
- [Set up Instructions](#set-up-instructions)


## Changelog
**Most Recent Version: 1.0**
##### What's New?
- Application created

## Description
Track OBS Time Stamps While Recording

Run the application with OBS already open to get started

There are two ways to mark an time stamp:
1. Click the "Mark Funny Moment"
2. Press the hotkey on the keyboard. 
>[!NOTE]
>The default hotkey is F12

You can change the hotkey for marking time stamps by pressing the "Change Hotkey" Button

After your OBS recording session is done click "Save & Exit"

A text file will be generated in the same folder as the .exe file that contains all your time stamps
## Downloads
#### Windows:
Version 1.0 - Download [Here](https://www.mediafire.com/file/x7oqkeqvetzbkcf/OBSTimeTracker.exe/file)
#### Linux
No Official Support
#### MAC
No Official Support


## Set up Instructions
**Step 0:**
[Install](https://www.mediafire.com/file/x7oqkeqvetzbkcf/OBSTimeTracker.exe/file) OBS Time Tracker

**Step 1:**

Create a folder anywhere on your PC called whatever you want, mine is called Time Stamps

**Step 2:**

Place the OBSTimeTracker.exe file in there

**Step 3:**

Open OBS
Install OBS [Here](https://obsproject.com/download)

**Step 4:**

In the ribbon in OBS click on "Tools" and click on "websocket server settings"

**Step 5:**

Check the enable WebSocket Server box

**Step 6:**

Make sure your port is set to 4455

**Step 7:**

Set the server password to "JimBob123"
> [!NOTE]
> The Password is hard coded in so this must be your password for the script to work

This gives the program access to your OBS

**Step 8:**

Run the .exe file, ensure that it says that its connected to OBS

**Step 9:**

When you start recording it should display the time stamp of your current recording

**Step 10:** 

Click on Mark Funny Moment and it will save all your funny moments to a .txt file. The .txt file will not show up until:

1- **You click "Save and exit"** 

>[!WARNING]
>You must click save and exit to get your .txt file, if you don't you'll lose your time stamps

**Step 11:**
Your .txt document will be saved in the same folder as the .exe file, and it will be named "ObsTimeStamps(todaysdate). If you have multiple documents with the same date it will just create the same .txt file but with a (1),(2),(3) at the end