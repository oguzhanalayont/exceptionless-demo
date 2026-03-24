import os
import time
import html
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
ERROR_THRESHOLD = int(os.environ.get("ERROR_THRESHOLD", "10"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))
COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "60"))
ELASTICSEARCH_URL = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

last_total_alert: float = 0
alerted_stacks: dict[str, float] = {}  # stack_id -> last alert time


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


def get_total_count() -> int:
    """Get total event count in the polling window."""
    try:
        query = {
            "query": {
                "range": {
                    "date": {"gte": f"now-{POLL_INTERVAL}s", "lte": "now"}
                }
            }
        }
        resp = requests.get(
            f"{ELASTICSEARCH_URL}/prod-events-v1-*/_count",
            json=query, timeout=10,
        )
        if resp.ok:
            return int(resp.json().get("count", 0))
        logger.error("ES count error %s: %s", resp.status_code, resp.text)
        return 0
    except Exception:
        logger.exception("Failed to query ES count")
        return 0


def get_top_errors() -> list[dict]:
    """Get errors grouped by stack_id with count and details."""
    try:
        query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"range": {"date": {"gte": f"now-{POLL_INTERVAL}s", "lte": "now"}}}
                    ]
                }
            },
            "aggs": {
                "by_stack": {
                    "terms": {
                        "field": "stack_id",
                        "min_doc_count": ERROR_THRESHOLD,
                        "size": 10,
                        "order": {"_count": "desc"}
                    },
                    "aggs": {
                        "sample": {
                            "top_hits": {
                                "size": 1,
                                "_source": ["message", "type", "tags",
                                            "data.@error.message",
                                            "data.@error.type",
                                            "data.@error.stack_trace.file_name",
                                            "data.@error.stack_trace.line_number",
                                            "data.@error.stack_trace.name"]
                            }
                        }
                    }
                }
            }
        }
        resp = requests.post(
            f"{ELASTICSEARCH_URL}/prod-events-v1-*/_search",
            json=query, timeout=10,
        )
        if not resp.ok:
            logger.error("ES agg error %s: %s", resp.status_code, resp.text)
            return []

        buckets = resp.json().get("aggregations", {}).get("by_stack", {}).get("buckets", [])
        results = []
        for bucket in buckets:
            stack_id = bucket["key"]
            count = bucket["doc_count"]
            hit = bucket["sample"]["hits"]["hits"][0]["_source"]
            results.append({
                "stack_id": stack_id,
                "count": count,
                "message": hit.get("message", "N/A"),
                "type": hit.get("type", "N/A"),
                "tags": hit.get("tags", []),
                "error_type": (hit.get("data", {}).get("@error", {}).get("type", "")),
                "stack_trace": hit.get("data", {}).get("@error", {}).get("stack_trace", []),
            })
        return results
    except Exception:
        logger.exception("Failed to query ES aggregation")
        return []


def format_error_message(error: dict) -> str:
    """Format a single error for Telegram notification."""
    msg = html.escape(error['message'])
    etype = html.escape(error['type'])

    lines = [
        f"<b>Tekrarlayan Hata Alarmi</b>",
        f"",
        f"<b>Hata:</b> {msg}",
        f"<b>Tip:</b> {etype}",
        f"<b>Tekrar:</b> Son {POLL_INTERVAL}s icinde <b>{error['count']}</b> kez",
        f"<b>Esik:</b> {ERROR_THRESHOLD}",
    ]

    if error["tags"]:
        tags = ', '.join(html.escape(t) for t in error['tags'])
        lines.append(f"<b>Etiketler:</b> {tags}")

    # Add first stack trace entry if available
    traces = error.get("stack_trace", [])
    if traces:
        t = traces[0]
        file_name = html.escape(t.get("file_name", ""))
        line_num = t.get("line_number", "")
        method = html.escape(t.get("name", ""))
        if file_name:
            lines.append(f"<b>Konum:</b> {file_name}:{line_num} → {method}")

    lines.append(f"<b>Zaman:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)


def poll_loop():
    """Periodically check event counts via Elasticsearch."""
    global last_total_alert
    logger.info(
        "Polling started: every %ds | total threshold=%d | error threshold=%d | cooldown=%ds",
        POLL_INTERVAL, THRESHOLD, ERROR_THRESHOLD, COOLDOWN_SECONDS
    )

    while True:
        time.sleep(POLL_INTERVAL)
        now = time.time()

        # 1) Total event threshold check
        total = get_total_count()
        rate = total / POLL_INTERVAL if POLL_INTERVAL > 0 else total
        logger.info("Poll: %d total events in last %ds (%.1f/s)", total, POLL_INTERVAL, rate)

        if total >= THRESHOLD and (now - last_total_alert) > COOLDOWN_SECONDS:
            last_total_alert = now
            send_telegram(
                f"<b>Exceptionless Alert</b>\n\n"
                f"Son <b>{POLL_INTERVAL}</b> saniyede <b>{total}</b> event algilandi!\n"
                f"Hiz: <b>{rate:.1f}</b> event/saniye\n"
                f"Esik degeri: {THRESHOLD} / {POLL_INTERVAL}s\n"
                f"Zaman: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # 2) Per-error threshold check
        top_errors = get_top_errors()
        for error in top_errors:
            sid = error["stack_id"]
            last_alerted = alerted_stacks.get(sid, 0)
            if (now - last_alerted) > COOLDOWN_SECONDS:
                alerted_stacks[sid] = now
                send_telegram(format_error_message(error))

        # Cleanup old stack cooldowns
        alerted_stacks.update({
            k: v for k, v in alerted_stacks.items()
            if (now - v) < COOLDOWN_SECONDS * 10
        })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "poll_interval": POLL_INTERVAL,
        "total_threshold": THRESHOLD,
        "error_threshold": ERROR_THRESHOLD,
        "cooldown": COOLDOWN_SECONDS,
        "tracked_stacks": len(alerted_stacks),
    })


# Start polling thread when app loads
poll_thread = threading.Thread(target=poll_loop, daemon=True)
poll_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
