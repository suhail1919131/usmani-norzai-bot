import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from bot import create_application

app = Flask(__name__)

application = create_application()
_initialized = False


async def process_telegram_update(data):
    global _initialized

    if not _initialized:
        await application.initialize()
        _initialized = True

    update = Update.de_json(data, application.bot)
    await application.process_update(update)


@app.route("/", methods=["GET"])
def home():
    return "🏦 Usmani Norzai Bot is running!"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "ok": False,
            "error": "No JSON data"
        }), 400

    try:
        asyncio.run(process_telegram_update(data))

        return jsonify({"ok": True})

    except Exception as error:
        print("Webhook error:", repr(error), flush=True)

        return jsonify({
            "ok": False,
            "error": str(error)
        }), 500
