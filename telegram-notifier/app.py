import os
import time
import threading
import logging
from flask import Flask, jsonify
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config ---
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
THRESHOLD = int(os.environ.get("EVENT_THRESHOLD", "100"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))
COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "60"))
ELASTICSEARCH_URL = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

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
        else:
            logger.info("Telegram message sent successfully")
    except Exception:
        logger.exception("Failed to send Telegram message")


def get_event_count() -> int:
    """Query Elasticsearch for recent event count."""
    try:
        query = {
            "query": {
                "range": {
                    "date": {
                        "gte": f"now-{POLL_INTERVAL}s",
                        "lte": "now"
                    }
                }
            }
        }

        resp = requests.get(
            f"{ELASTICSEARCH_URL}/events-*/_count",
            json=query,
            timeout=10,
        )
        if resp.ok:
            count = resp.json().get("count", 0)
            return int(count)
        else:
            logger.error("Elasticsearch error %s: %s", resp.status_code, resp.text)
            return 0
    except Exception:
        logger.exception("Failed to query Elasticsearch")
        return 0


def poll_loop():
    """Periodically check event count via Elasticsearch."""
    global last_alert_time
    logger.info(
        "Polling started: checking every %ds, threshold=%d events, cooldown=%ds",
        POLL_INTERVAL, THRESHOLD, COOLDOWN_SECONDS
    )

    while True:
        time.sleep(POLL_INTERVAL)
        count = get_event_count()
        now = time.time()

        rate = count / POLL_INTERVAL if POLL_INTERVAL > 0 else count
        logger.info("Poll result: %d events in last %ds (%.1f/s)", count, POLL_INTERVAL, rate)

        if count >= THRESHOLD and (now - last_alert_time) > COOLDOWN_SECONDS:
            last_alert_time = now
            message = (
                f"<b>Exceptionless Alert</b>\n\n"
                f"Son <b>{POLL_INTERVAL}</b> saniyede <b>{count}</b> event algilandi!\n"
                f"Hiz: <b>{rate:.1f}</b> event/saniye\n"
                f"Esik degeri: {THRESHOLD} / {POLL_INTERVAL}s\n"
                f"Zaman: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_telegram(message)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "poll_interval": POLL_INTERVAL,
        "threshold": THRESHOLD,
        "cooldown": COOLDOWN_SECONDS,
    })


# Start polling thread when app loads
poll_thread = threading.Thread(target=poll_loop, daemon=True)
poll_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
