import os
import time
import threading
import logging
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config ---
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
THRESHOLD = int(os.environ.get("EVENT_THRESHOLD", "100"))
WINDOW_SECONDS = int(os.environ.get("WINDOW_SECONDS", "1"))
COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "60"))

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# --- State ---
event_timestamps: list[float] = []
lock = threading.Lock()
last_alert_time: float = 0


def send_telegram(message: str):
    """Send a message via Telegram bot."""
    try:
        resp = requests.post(TELEGRAM_API, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        if not resp.ok:
            logger.error("Telegram API error: %s", resp.text)
    except Exception:
        logger.exception("Failed to send Telegram message")


def check_threshold():
    """Check if event count exceeds threshold within the time window."""
    global last_alert_time
    now = time.time()

    with lock:
        # Remove events outside the window
        cutoff = now - WINDOW_SECONDS
        event_timestamps[:] = [t for t in event_timestamps if t > cutoff]
        count = len(event_timestamps)

    if count >= THRESHOLD and (now - last_alert_time) > COOLDOWN_SECONDS:
        last_alert_time = now
        message = (
            f"<b>Exceptionless Alert</b>\n\n"
            f"Son <b>{WINDOW_SECONDS}</b> saniyede <b>{count}</b> event alindi!\n"
            f"Esik degeri: {THRESHOLD}\n"
            f"Zaman: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_telegram(message)
        logger.warning("ALERT: %d events in %ds window — Telegram sent", count, WINDOW_SECONDS)


@app.route("/webhook", methods=["POST"])
def webhook():
    """Receive Exceptionless webhook events."""
    now = time.time()

    with lock:
        event_timestamps.append(now)

    check_threshold()
    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    with lock:
        cutoff = time.time() - WINDOW_SECONDS
        recent = sum(1 for t in event_timestamps if t > cutoff)
    return jsonify({
        "status": "healthy",
        "events_in_window": recent,
        "threshold": THRESHOLD,
        "window_seconds": WINDOW_SECONDS,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
