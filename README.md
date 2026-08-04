# WeaponDetection AI

A Flask-based web application for real-time weapon detection using a custom-trained YOLOv8m model. Supports live camera feed monitoring, image scanning, and video file analysis, with user accounts and email alerts.

## Features

- 🔐 User registration, login, and guest access
- 📹 Live camera feed detection (browser webcam → server-side YOLO inference)
- 🖼️ Image upload and scanning
- 🎬 Video upload and scanning (re-encoded with ffmpeg for browser playback)
- 📧 Email alerts on login, registration, password recovery, and threat detection
- 📋 Detection history / session logs
- 🔊 In-browser sound alerts on live threat detection

## Project Structure

```
weapon-detection/
├── app.py
├── requirements.txt
├── .env
├── models/
│   └── yolo_v8m_best(65).pt
├── templates/
│   ├── index.html
│   ├── register.html
│   ├── forgot.html
│   ├── dashboard.html
│   ├── about.html
│   └── logs.html
└── static/
    ├── styles.css
    ├── uploads/
    └── results/
```

## Prerequisites

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/) installed and available on your system PATH (used for video re-encoding)
  - Windows: `winget install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- A trained YOLOv8 weapon detection model file (`.pt`)

## Setup

### 1. Clone / place the project

Make sure your folder matches the structure above, with the `.pt` model file placed inside `models/`.

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
flask
ultralytics
opencv-python
python-dotenv
```

### 4. Configure environment variables

Create a `.env` file in the project root (never commit this file):

```
FLASK_SECRET_KEY=replace_with_a_random_secret
EMAIL_SENDER=your_gmail@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
```

> Use a Gmail **App Password**, not your real Gmail password, for `EMAIL_PASSWORD`. Generate one from your Google Account → Security → App Passwords (requires 2-Step Verification enabled).

In `app.py`, load these instead of hardcoding:

```python
from dotenv import load_dotenv
import os

load_dotenv()
app.secret_key = os.getenv("FLASK_SECRET_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
```

### 5. Set the model path

Update the model loading line in `app.py` to point to your local model file:

```python
model = YOLO("models/yolo_v8m_best(65).pt")
```

## Running the App

```bash
python app.py
```

The app will be available at:

```
http://127.0.0.1:5000
```

To access it from another device on the same network (e.g. testing camera on your phone), use your machine's LAN IP instead, since the app runs with `host="0.0.0.0"`:

```
http://<your-local-ip>:5000
```

## Default Test Accounts

These are seeded in-memory (reset on every restart, since there's no database):

| Email | Password |
|---|---|
| sai@gmail.com | 1234 |
| mani@gmail.com | 5678 |
| guest@weapondetection | guest |

You can also register a new account from the app's Register page.

## Notes & Limitations

- **In-memory storage**: users, logs, and alerts are stored in Python dicts/lists and reset every time the app restarts. For persistence, add a database (SQLite/PostgreSQL).
- **Detection threshold**: all classes currently use a 60% confidence threshold (`_passes_threshold` in `app.py`); adjust per class if needed.
- **Secrets**: rotate the `FLASK_SECRET_KEY` and email app password before deploying anywhere beyond local testing, and make sure `.env` is in `.gitignore`.
- **CSS not loading?** Make sure `static/` sits directly next to `app.py` (not nested inside `templates/`), and hard-refresh the browser (`Ctrl+Shift+R` / `Cmd+Shift+R`) to bypass caching.
- **Video processing** can be slow on CPU-only machines since every frame runs through YOLO inference.

## Tech Stack

- Flask (web framework)
- Ultralytics YOLOv8 (object detection)
- OpenCV (image/video processing)
- Vanilla JS (webcam capture, live inference polling, alerts)