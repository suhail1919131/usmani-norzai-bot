import asyncio
import threading

from flask import Flask, request, jsonify
from telegram import Update
from bot import create_application


app = Flask(__name__)

application = create_application()

_initialized = False
_init_lock = None

# یک Event Loop دائمی برای این نمونه Vercel
event_loop = asyncio.new_event_loop()


def run_event_loop():
    asyncio.set_event_loop(event_loop)
    event_loop.run_forever()


loop_thread = threading.Thread(
    target=run_event_loop,
    daemon=True
)

loop_thread.start()


async def process_telegram_update(data):
    global _initialized, _init_lock

    if _init_lock is None:
        _init_lock = asyncio.Lock()

    async with _init_lock:
        if not _initialized:
            await application.initialize()
            _initialized = True

    update = Update.de_json(
        data,
        application.bot
    )

    await application.process_update(update)


@app.route("/", methods=["GET"])
def home():
    return "🏦 Usmani Norzai Bot is running!"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok"
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "ok": False,
            "error": "No JSON data"
        }), 400

    try:
        future = asyncio.run_coroutine_threadsafe(
            process_telegram_update(data),
            event_loop
        )

        future.result(timeout=30)

        return jsonify({
            "ok": True
        })

    except Exception as error:
        print(
            "Webhook error:",
            repr(error),
            flush=True
        )

        return jsonify({
            "ok": False,
            "error": str(error)
        }), 500
