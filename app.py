from flask import Flask, render_template, request, redirect, session, Response, jsonify
import cv2
from ultralytics import YOLO
import os
import time
import subprocess
import numpy as np
import base64
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

app = Flask(__name__)
app.secret_key = "weapon_secret_2024"

UPLOAD_FOLDER = "static/uploads"
RESULT_FOLDER = "static/results"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

import os
import urllib.request
from ultralytics import YOLO

MODEL_PATH = "model/yolo_v8m_best(65).pt"
MODEL_URL = os.getenv("MODEL_URL")

if not os.path.exists(MODEL_PATH):
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    print("Downloading model weights from Hugging Face...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Model downloaded successfully.")

model = YOLO(MODEL_PATH)

EMAIL_SENDER    = "your_gmail@gmail.com"
EMAIL_PASSWORD  = "your_app_password_here"
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587

users = {
    "sai@gmail.com":      {"password": "1234",  "username": "Sai"},
    "mani@gmail.com":     {"password": "5678",  "username": "Mani"},
    "guest@weapondetection": {"password": "guest", "username": "Guest"},
}

detection_logs      = []
user_alerts         = {}
live_alert_cooldown = {}


def _passes_threshold(label, conf_pct):
    label_lower = label.lower()
    if any(w in label_lower for w in ["gun", "pistol", "rifle", "firearm", "weapon", "handgun", "revolver", "shotgun"]):
        return conf_pct >= 60
    elif any(w in label_lower for w in ["knife", "blade", "sword", "dagger", "machete"]):
        return conf_pct >= 60
    else:
        return conf_pct >= 60


def _draw_box(frame, box, label, conf_pct):
    label_lower = label.lower()
    x1, y1, x2, y2 = map(int, box.xyxy[0])
    color = (0, 0, 255) if any(w in label_lower for w in
                                ["gun", "pistol", "rifle", "firearm", "weapon", "handgun", "revolver", "shotgun"]) \
            else (0, 165, 255)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(frame, f"{label} {conf_pct}%",
                (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def send_email_async(to_email, subject, html_body):
    """
    Send email in a background thread so Flask doesn't block.
    Sends to the ACTUAL user email passed in — which is always session['email'].
    Guest emails are skipped.
    """
    if not to_email or to_email == "guest@weapondetection.ai":
        return  # No emails for guest

    def _send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"WeaponDetection <{EMAIL_SENDER}>"
            msg["To"]      = to_email          # ✅ Sends to the logged-in user's email
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
            print(f"[EMAIL] ✅ Sent to {to_email} — {subject}")
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to send to {to_email}: {e}")

    threading.Thread(target=_send, daemon=True).start()


def build_email_html(title, emoji, color, message, detail=""):
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;
                border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
      <div style="background:{color};padding:28px 32px;text-align:center;">
        <div style="font-size:3rem;">{emoji}</div>
        <h1 style="color:#fff;font-size:1.3rem;margin:10px 0 0;
                   letter-spacing:2px;text-transform:uppercase;">{title}</h1>
      </div>
      <div style="padding:28px 32px;background:#fff;">
        <p style="font-size:1rem;color:#1a1a2e;line-height:1.7;">{message}</p>
        {f'<p style="margin-top:14px;font-size:0.88rem;color:#6b7280;">{detail}</p>' if detail else ''}
        <hr style="margin:24px 0;border:none;border-top:1px solid #e2e8f0;">
        <p style="font-size:0.78rem;color:#9ca3af;text-align:center;">
          WeaponDetection · Automated Security Alert · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </p>
      </div>
    </div>
    """


def push_alert(email, message, alert_type="warning"):
    if email not in user_alerts:
        user_alerts[email] = []
    user_alerts[email].append({
        "message":    message,
        "type":       alert_type,
        "time":       datetime.now().strftime("%H:%M:%S"),
        "play_sound": alert_type == "danger"   # ✅ Frontend uses this to trigger sound
    })


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"].strip().lower()
        password = request.form["password"]

        if email in users and users[email]["password"] == password:
            session["user"]  = users[email]["username"]
            session["email"] = email             # ✅ Store actual email in session
            push_alert(email,
                       f"✅ Welcome back, {users[email]['username']}! You are now logged in.",
                       "success")
            send_email_async(
                email,                           # ✅ Email goes to THIS user's address
                "✅ WeaponDetection — Login Successful",
                build_email_html(
                    "Login Successful", "🛡️", "#1a73e8",
                    f"Hello <strong>{users[email]['username']}</strong>, you have successfully logged in to WeaponDetection.",
                    f"Login time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            )
            return redirect("/dashboard")

        return render_template("index.html", error="❌ Invalid email or password.")
    return render_template("index.html")


@app.route("/guest_login")
def guest_login():
    session["user"]  = "Guest"
    session["email"] = "guest@weapondetection.ai"
    push_alert("guest@weapondetection.ai",
               "👤 You are browsing as Guest. Email alerts are disabled.",
               "info")
    return redirect("/dashboard")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email    = request.form["email"].strip().lower()
        password = request.form["password"]

        if email in users:
            return render_template("register.html", error="⚠️ Email already registered.")
        if not username:
            return render_template("register.html", error="⚠️ Username cannot be empty.")

        users[email] = {"password": password, "username": username}
        send_email_async(
            email,                               # ✅ Welcome email to the new user's email
            "🎉 WeaponDetection — Account Created",
            build_email_html(
                "Account Created!", "🎉", "#1e8e3e",
                f"Hello <strong>{username}</strong>, your WeaponDetection account has been created successfully!",
                "You can now log in using your email and password."
            )
        )
        return render_template("register.html",
                               success="✅ Registered! Check your email, then login.")
    return render_template("register.html")


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    message = ""
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        if email in users:
            send_email_async(
                email,
                "🔑 WeaponDetection — Password Recovery",
                build_email_html(
                    "Password Recovery", "🔑", "#f59e0b",
                    f"Hello <strong>{users[email]['username']}</strong>, your password is: "
                    f"<strong style='font-size:1.2rem;color:#1a73e8;'>{users[email]['password']}</strong>",
                    "If you did not request this, please ignore this email."
                )
            )
            message = f"✅ Password sent to {email}"
        else:
            message = "❌ Email not found."
    return render_template("forgot.html", message=message)


@app.route("/logout")
def logout():
    session.pop("user",  None)
    session.pop("email", None)
    return redirect("/")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html", user=session["user"], email=session.get("email",""))


@app.route("/about")
def about():
    if "user" not in session:
        return redirect("/")
    return render_template("about.html", user=session["user"])


@app.route("/logs")
def logs():
    if "user" not in session:
        return redirect("/")
    return render_template("logs.html", user=session["user"], logs=detection_logs)


@app.route("/get_alerts")
def get_alerts():
    if "email" not in session:
        return jsonify([])
    email  = session["email"]
    alerts = user_alerts.get(email, [])
    user_alerts[email] = []
    return jsonify(alerts)


@app.route("/process_frame", methods=["POST"])
def process_frame():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json()
    if not data or "frame" not in data:
        return jsonify({"error": "no frame"}), 400

    img_data  = data["frame"].split(",")[1]
    img_bytes = base64.b64decode(img_data)
    np_arr    = np.frombuffer(img_bytes, np.uint8)
    frame     = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"error": "decode failed"}), 400

    results         = model(frame, verbose=False)
    detections      = []
    annotated_frame = frame.copy()

    for r in results:
        for box in r.boxes:
            cls_id   = int(box.cls[0])
            label    = model.names[cls_id]
            conf     = float(box.conf[0])
            conf_pct = round(conf * 100, 1)

            if not _passes_threshold(label, conf_pct):
                continue

            detections.append({"label": label, "confidence": conf_pct})
            _draw_box(annotated_frame, box, label, conf_pct)

    frame = annotated_frame

    if detections:
        email  = session.get("email", "")
        labels = ", ".join(set(d["label"] for d in detections))
        now    = time.time()

        push_alert(email,
                   f"🚨 LIVE THREAT DETECTED: {labels} spotted on camera!",
                   "danger")   # ✅ play_sound=True added in push_alert for danger type

        last_sent = live_alert_cooldown.get(email, 0)
        if now - last_sent > 30:
            live_alert_cooldown[email] = now
            send_email_async(
                email,          # ✅ Always sends to the session user's actual email
                "🚨 WeaponDetection — LIVE THREAT DETECTED",
                build_email_html(
                    "Live Threat Detected!", "🚨", "#e53935",
                    f"Hello <strong>{session['user']}</strong>, a weapon was detected on your <strong>live camera feed</strong>.",
                    f"Detected: <strong>{labels}</strong> — Please review the camera immediately."
                )
            )

    _, buffer     = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    processed_b64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")

    return jsonify({
        "processed_frame": processed_b64,
        "detections":      detections,
        "play_sound":      len(detections) > 0
    })


@app.route("/detect_file", methods=["POST"])
def detect_file():
    if "user" not in session:
        return redirect("/")

    file     = request.files["file"]
    filename = file.filename
    ext      = filename.rsplit(".", 1)[-1].lower()
    email    = session.get("email", "")
    username = session["user"]

    if ext in ["jpg", "jpeg", "png", "bmp", "webp"]:
        orig_filename = f"orig_{int(time.time())}_{filename}"
        path          = os.path.join(UPLOAD_FOLDER, orig_filename)
        file.save(path)

        img     = cv2.imread(path)
        results = model(img)

        detections    = []
        annotated_img = img.copy()

        for r in results:
            for box in r.boxes:
                cls_id   = int(box.cls[0])
                label    = model.names[cls_id]
                conf     = float(box.conf[0])
                conf_pct = round(conf * 100, 1)

                if not _passes_threshold(label, conf_pct):
                    continue

                detections.append({"label": label, "confidence": conf_pct})
                _draw_box(annotated_img, box, label, conf_pct)

        img = annotated_img

        result_filename = f"result_{int(time.time())}.jpg"
        cv2.imwrite(os.path.join(RESULT_FOLDER, result_filename), img)

        if detections:
            labels = ", ".join(set(d["label"] for d in detections))
            push_alert(email,
                       f"🚨 IMAGE SCAN: Weapon detected — {labels} in '{filename}'!",
                       "danger")
            send_email_async(
                email,          #
                "🚨 WeaponDetection — Weapon Detected in Image",
                build_email_html(
                    "Weapon Detected!", "🚨", "#e53935",
                    f"Hello <strong>{username}</strong>, a weapon was detected in the uploaded image "
                    f"<strong>{filename}</strong>.",
                    f"Detected objects: <strong>{labels}</strong>"
                )
            )
        else:
            push_alert(email,
                       f"✅ IMAGE SCAN: No threats found in '{filename}'.",
                       "success")
            send_email_async(
                email,
                "✅ WeaponDetection — Image Scan Clear",
                build_email_html(
                    "Scan Clear", "✅", "#1e8e3e",
                    f"Hello <strong>{username}</strong>, your image scan of "
                    f"<strong>{filename}</strong> found no threats.",
                )
            )

        detection_logs.insert(0, {
            "time":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user":       username,
            "email":      email,
            "file":       filename,
            "type":       "image",
            "detections": detections
        })

        return render_template("dashboard.html",
                               user=username,
                               email=email,
                               image=f"results/{result_filename}",
                               original_image=f"uploads/{orig_filename}",
                               detections=detections,
                               file_type="image",
                               play_sound="true" if detections else "false")

    elif ext in ["mp4", "avi", "mov", "mkv", "webm"]:
        orig_filename = f"orig_{int(time.time())}_{filename}"
        path          = os.path.join(UPLOAD_FOLDER, orig_filename)
        file.save(path)

        raw_output   = os.path.join(RESULT_FOLDER, f"raw_{int(time.time())}.avi")
        final_output = os.path.join(RESULT_FOLDER, f"result_{int(time.time())}.mp4")

        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(raw_output, cv2.VideoWriter_fourcc(*'XVID'), fps, (w, h))

        all_detections = {}

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results         = model(frame)
            annotated_frame = frame.copy()

            for r in results:
                for box in r.boxes:
                    cls_id   = int(box.cls[0])
                    label    = model.names[cls_id]
                    conf     = float(box.conf[0])
                    conf_pct = round(conf * 100, 1)

                    if not _passes_threshold(label, conf_pct):
                        continue

                    all_detections[label] = all_detections.get(label, 0) + 1
                    _draw_box(annotated_frame, box, label, conf_pct)

            out.write(annotated_frame)

        cap.release()
        out.release()

        subprocess.run([
            "ffmpeg", "-y", "-i", raw_output,
            "-vcodec", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", final_output
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if os.path.exists(raw_output):
            os.remove(raw_output)

        orig_final = os.path.join(UPLOAD_FOLDER, f"web_{int(time.time())}.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-i", path,
            "-vcodec", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", orig_final
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        detections = [{"label": k, "count": v} for k, v in all_detections.items()]

        if detections:
            labels = ", ".join(all_detections.keys())
            push_alert(email,
                       f"🚨 VIDEO SCAN: Weapons detected — {labels} in '{filename}'!",
                       "danger")
            send_email_async(
                email,          # ✅ Sends to user's own email
                "🚨 WeaponDetection — Weapon Detected in Video",
                build_email_html(
                    "Weapon Detected in Video!", "🎬", "#e53935",
                    f"Hello <strong>{username}</strong>, weapons were detected in the uploaded video "
                    f"<strong>{filename}</strong>.",
                    f"Detected objects: <strong>{labels}</strong>"
                )
            )
        else:
            push_alert(email,
                       f"✅ VIDEO SCAN: No threats found in '{filename}'.",
                       "success")
            send_email_async(
                email,
                "✅ WeaponDetection  — Video Scan Clear",
                build_email_html(
                    "Video Scan Clear", "✅", "#1e8e3e",
                    f"Hello <strong>{username}</strong>, your video scan of "
                    f"<strong>{filename}</strong> found no threats.",
                )
            )

        detection_logs.insert(0, {
            "time":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user":       username,
            "email":      email,
            "file":       filename,
            "type":       "video",
            "detections": detections
        })

        return render_template("dashboard.html",
                               user=username,
                               email=email,
                               original_video=orig_final.replace("static/", ""),
                               result_video=final_output.replace("static/", ""),
                               detections=detections,
                               file_type="video",
                               play_sound="true" if detections else "false")

    return render_template("dashboard.html", user=session["user"],
                           email=session.get("email",""),
                           error="❌ Unsupported file type.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
