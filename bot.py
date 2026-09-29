import logging
import re
import requests

from bs4 import BeautifulSoup

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)


# =========================================================
# تنظیمات
# =========================================================

BOT_TOKEN = "8858827620:AAFgMrCM-1SySWCEaZfatVzy-M08YAE1z0Y"

TGJU_URL = "https://www.tgju.org/currency"

TIMEOUT = 15


# =========================================================
# لاگ
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# مراحل تبدیل ارز
# =========================================================

CONVERT_FROM = 1
CONVERT_TO = 2
CONVERT_AMOUNT = 3


# =========================================================
# مراحل محاسبه دستی
# =========================================================

MANUAL_EURO = 10
MANUAL_DOLLAR = 11
MANUAL_TOMAN = 12
MANUAL_COMMISSION = 13


# =========================================================
# ابزارها
# =========================================================

def normalize_digits(text):
    """تبدیل اعداد فارسی و عربی به انگلیسی"""

    if not text:
        return ""

    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )

    return str(text).translate(translation)


def clean_number(text):
    """تبدیل متن عددی به float"""

    text = normalize_digits(text)

    text = (
        text.replace(",", "")
        .replace("٬", "")
        .replace("٫", ".")
        .replace(" ", "")
    )

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def format_number(number):
    """نمایش عدد با جداکننده هزارگان"""

    if number is None:
        return "-"

    if isinstance(number, float) and number.is_integer():
        number = int(number)

    if isinstance(number, int):
        return f"{number:,}"

    return f"{number:,.2f}"


def get_html(url):
    """گرفتن صفحه سایت"""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/142.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    return response.text


# =========================================================
# دریافت نرخ TGJU
# =========================================================

def get_tgju_rates():

    try:

        html = get_html(TGJU_URL)

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        dollar = None
        euro = None
        afn = None

        dollar_time = None
        euro_time = None
        afn_time = None

        # تمام جدول‌ها
        tables = soup.find_all("table")

        for table in tables:

            rows = table.find_all("tr")

            for row in rows:

                cells = row.find_all(
                    ["td", "th"],
                    recursive=False,
                )

                if len(cells) < 2:
                    continue

                cell_texts = []

                for cell in cells:

                    text = cell.get_text(
                        " ",
                        strip=True,
                    )

                    text = normalize_digits(text)

                    cell_texts.append(text)

                if len(cell_texts) < 2:
                    continue

                title = cell_texts[0].strip()

                # فقط ردیف‌های مورد نظر
                if title not in [
                    "دلار",
                    "یورو",
                    "افغانی",
                ]:
                    continue

                price_text = cell_texts[1]

                # پیدا کردن اولین عدد داخل سلول قیمت
                price_match = re.search(
                    r"\d[\d,٬]*",
                    price_text,
                )

                if not price_match:
                    continue

                price_string = price_match.group(0)

                price_string = (
                    price_string
                    .replace(",", "")
                    .replace("٬", "")
                )

                try:
                    price = int(price_string)
                except ValueError:
                    continue

                row_time = None

                # پیدا کردن ساعت
                for text in cell_texts:

                    time_match = re.search(
                        r"\d{1,2}:\d{2}:\d{2}",
                        text,
                    )

                    if time_match:
                        row_time = time_match.group(0)
                        break

                if title == "دلار":

                    dollar = price
                    dollar_time = row_time

                elif title == "یورو":

                    euro = price
                    euro_time = row_time

                elif title == "افغانی":

                    afn = price
                    afn_time = row_time

        logger.info(
            "TGJU -> USD=%s EUR=%s AFN=%s",
            dollar,
            euro,
            afn,
        )

        return {
            "USD": dollar,
            "EUR": euro,
            "AFN": afn,
            "USD_TIME": dollar_time,
            "EUR_TIME": euro_time,
            "AFN_TIME": afn_time,
        }

    except Exception as error:

        logger.error(
            "TGJU ERROR: %s",
            error,
        )

        return {
            "USD": None,
            "EUR": None,
            "AFN": None,
            "USD_TIME": None,
            "EUR_TIME": None,
            "AFN_TIME": None,
        }


# =========================================================
# منوی اصلی
# =========================================================

def main_keyboard():

    keyboard = [

        [
            InlineKeyboardButton(
                "🏦 نرخ بازار",
                callback_data="market",
            )
        ],

        [
            InlineKeyboardButton(
                "💱 تبدیل ارز",
                callback_data="convert",
            )
        ],

        [
            InlineKeyboardButton(
                "🧮 محاسبه دستی",
                callback_data="manual",
            )
        ],

    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# منوی برگشت
# =========================================================

def back_keyboard():

    keyboard = [

        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="home",
            )
        ]

    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# شروع ربات
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🏦 صرافی عثمانی نورزایی\n"
        "💱 نرخ و محاسبه ارز\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "لطفاً یکی از گزینه‌ها را انتخاب کنید 👇\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    if update.message:

        await update.message.reply_text(
            text,
            reply_markup=main_keyboard(),
        )

    elif update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=main_keyboard(),
        )


# =========================================================
# منوی اصلی از دکمه
# =========================================================

async def home(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🏦 صرافی هرات\n"
        "💱 نرخ و محاسبه ارز\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "لطفاً یکی از گزینه‌ها را انتخاب کنید 👇\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    await query.edit_message_text(
        text,
        reply_markup=main_keyboard(),
    )


# =========================================================
# نرخ بازار
# =========================================================

async def market(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    await query.edit_message_text(
        "⏳ در حال دریافت آخرین نرخ بازار...",
    )

    rates = get_tgju_rates()

    dollar_irr = rates["USD"]
    euro_irr = rates["EUR"]

    if dollar_irr is None or euro_irr is None:

        text = (
            "❌ دریافت نرخ بازار موفق نشد.\n\n"
            "لطفاً چند لحظه بعد دوباره امتحان کنید."
        )

        await query.edit_message_text(
            text,
            reply_markup=back_keyboard(),
        )

        return

    # TGJU نرخ را ریال ایران می‌دهد
    dollar_toman = dollar_irr / 10
    euro_toman = euro_irr / 10

    # یورو به دالر
    euro_usd = euro_irr / dollar_irr

    dollar_time = rates["USD_TIME"] or "-"
    euro_time = rates["EUR_TIME"] or "-"

    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🏦 نرخ بازار\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🇺🇸 1 دالر ≈ "
        f"{format_number(dollar_toman)} تومان\n"

        f"🇪🇺 1 یورو ≈ "
        f"{euro_usd:.4f} دالر\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📡 منبع: TGJU\n"
        f"🕐 نرخ دالر: {dollar_time}\n"
        f"🕐 نرخ یورو: {euro_time}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    await query.edit_message_text(
        text,
        reply_markup=back_keyboard(),
    )


# =========================================================
# منوی تبدیل ارز
# =========================================================

def conversion_from_keyboard():

    keyboard = [

        [
            InlineKeyboardButton(
                "🇺🇸 دالر",
                callback_data="from_USD",
            ),
            InlineKeyboardButton(
                "🇪🇺 یورو",
                callback_data="from_EUR",
            ),
        ],

        [
            InlineKeyboardButton(
                "🇦🇫 افغانی",
                callback_data="from_AFN",
            ),
            InlineKeyboardButton(
                "🇮🇷 تومان",
                callback_data="from_IRR",
            ),
        ],

        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="home",
            )
        ],

    ]

    return InlineKeyboardMarkup(keyboard)


def conversion_to_keyboard():

    keyboard = [

        [
            InlineKeyboardButton(
                "🇺🇸 دالر",
                callback_data="to_USD",
            ),
            InlineKeyboardButton(
                "🇪🇺 یورو",
                callback_data="to_EUR",
            ),
        ],

        [
            InlineKeyboardButton(
                "🇦🇫 افغانی",
                callback_data="to_AFN",
            ),
            InlineKeyboardButton(
                "🇮🇷 تومان",
                callback_data="to_IRR",
            ),
        ],

        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="home",
            )
        ],

    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# شروع تبدیل
# =========================================================

async def convert_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    context.user_data.pop("source", None)
    context.user_data.pop("destination", None)

    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "💱 تبدیل ارز\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "ارزی که می‌خواهید تبدیل کنید را انتخاب کنید 👇"
    )

    await query.edit_message_text(
        text,
        reply_markup=conversion_from_keyboard(),
    )

    return CONVERT_FROM


# =========================================================
# انتخاب ارز اول و دوم
# =========================================================

async def conversion_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    data = query.data

    if data.startswith("from_"):

        source = data.replace(
            "from_",
            "",
        )

        context.user_data["source"] = source

        names = {
            "USD": "🇺🇸 دالر",
            "EUR": "🇪🇺 یورو",
            "AFN": "🇦🇫 افغانی",
            "IRR": "🇮🇷 تومان",
        }

        source_name = names.get(
            source,
            source,
        )

        text = (
            "━━━━━━━━━━━━━━━━━━\n"
            "💱 تبدیل ارز\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"ارز مبدا: {source_name}\n\n"
            "حالا ارز مقصد را انتخاب کنید 👇"
        )

        await query.edit_message_text(
            text,
            reply_markup=conversion_to_keyboard(),
        )

        return CONVERT_TO

    if data.startswith("to_"):

        destination = data.replace(
            "to_",
            "",
        )

        source = context.user_data.get(
            "source"
        )

        if not source:

            await query.edit_message_text(
                "❌ خطا. لطفاً دوباره شروع کنید.",
                reply_markup=back_keyboard(),
            )

            return ConversationHandler.END

        if source == destination:

            await query.answer(
                "ارز مبدا و مقصد نباید یکسان باشد.",
                show_alert=True,
            )

            return CONVERT_TO

        context.user_data["destination"] = destination

        names = {
            "USD": "🇺🇸 دالر",
            "EUR": "🇪🇺 یورو",
            "AFN": "🇦🇫 افغانی",
            "IRR": "🇮🇷 تومان",
        }

        source_name = names.get(
            source,
            source,
        )

        destination_name = names.get(
            destination,
            destination,
        )

        text = (
            "━━━━━━━━━━━━━━━━━━\n"
            "💱 تبدیل ارز\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"مبدا: {source_name}\n"
            f"مقصد: {destination_name}\n\n"
            "🔢 لطفاً مقدار را وارد کنید:"
        )

        await query.edit_message_text(
            text
        )

        return CONVERT_AMOUNT

    return CONVERT_FROM


# =========================================================
# محاسبه تبدیل
# =========================================================

async def convert_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = update.message.text.strip()

    amount = clean_number(text)

    if amount is None or amount <= 0:

        await update.message.reply_text(
            "❌ لطفاً یک عدد معتبر وارد کنید.\n\n"
            "مثلاً:\n"
            "100\n"
            "250.5\n"
            "100000"
        )

        return CONVERT_AMOUNT

    source = context.user_data.get("source")
    destination = context.user_data.get("destination")

    if not source or not destination:

        await update.message.reply_text(
            "❌ اطلاعات تبدیل پیدا نشد.\n"
            "لطفاً دوباره از منوی اصلی شروع کنید.",
            reply_markup=back_keyboard(),
        )

        return ConversationHandler.END

    # دریافت نرخ
    rates = get_tgju_rates()

    usd_irr = rates["USD"]
    eur_irr = rates["EUR"]

    # برای تبدیل‌های ایران
    usd_toman = (
        usd_irr / 10
        if usd_irr
        else None
    )

    eur_toman = (
        eur_irr / 10
        if eur_irr
        else None
    )

    result = None
    rate_text = ""

    # -----------------------------------------
    # USD -> IRR
    # -----------------------------------------

    if source == "USD" and destination == "IRR":

        if not usd_toman:

            result = None

        else:

            result = amount * usd_toman

            rate_text = (
                f"1 دالر = {format_number(usd_toman)} تومان"
            )

    # -----------------------------------------
    # IRR -> USD
    # -----------------------------------------

    elif source == "IRR" and destination == "USD":

        if not usd_toman:

            result = None

        else:

            result = amount / usd_toman

            rate_text = (
                f"1 دالر = {format_number(usd_toman)} تومان"
            )

    # -----------------------------------------
    # EUR -> IRR
    # -----------------------------------------

    elif source == "EUR" and destination == "IRR":

        if not eur_toman:

            result = None

        else:

            result = amount * eur_toman

            rate_text = (
                f"1 یورو = {format_number(eur_toman)} تومان"
            )

    # -----------------------------------------
    # IRR -> EUR
    # -----------------------------------------

    elif source == "IRR" and destination == "EUR":

        if not eur_toman:

            result = None

        else:

            result = amount / eur_toman

            rate_text = (
                f"1 یورو = {format_number(eur_toman)} تومان"
            )

    # -----------------------------------------
    # EUR -> USD
    # -----------------------------------------

    elif source == "EUR" and destination == "USD":

        if not usd_irr or not eur_irr:

            result = None

        else:

            rate = eur_irr / usd_irr

            result = amount * rate

            rate_text = (
                f"1 یورو = {rate:.4f} دالر"
            )

    # -----------------------------------------
    # USD -> EUR
    # -----------------------------------------

    elif source == "USD" and destination == "EUR":

        if not usd_irr or not eur_irr:

            result = None

        else:

            rate = usd_irr / eur_irr

            result = amount * rate

            rate_text = (
                f"1 دالر = {rate:.4f} یورو"
            )

    # -----------------------------------------
    # AFN
    # -----------------------------------------

    elif source == "AFN" or destination == "AFN":

        await update.message.reply_text(
            "⚠️ نرخ زنده افغانی هنوز به منبع معتبر "
            "بازار هرات وصل نشده است.\n\n"
            "بخش افغانی را بعداً به نرخ واقعی بازار "
            "هرات وصل می‌کنیم.",
            reply_markup=back_keyboard(),
        )

        return ConversationHandler.END

    else:

        result = None

    if result is None:

        await update.message.reply_text(
            "❌ نرخ مورد نیاز فعلاً دریافت نشد.\n"
            "لطفاً دوباره امتحان کنید.",
            reply_markup=back_keyboard(),
        )

        return ConversationHandler.END

    names = {
        "USD": "🇺🇸 دالر",
        "EUR": "🇪🇺 یورو",
        "AFN": "🇦🇫 افغانی",
        "IRR": "🇮🇷 تومان",
    }

    source_name = names.get(
        source,
        source,
    )

    destination_name = names.get(
        destination,
        destination,
    )

    usd_time = rates["USD_TIME"] or "-"
    eur_time = rates["EUR_TIME"] or "-"

    result_text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "💱 نتیجه تبدیل\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🔹 مقدار: {format_number(amount)}\n"
        f"🔹 از: {source_name}\n"
        f"🔹 به: {destination_name}\n\n"
        f"💰 نتیجه:\n"
        f"{format_number(result)}\n\n"
        f"📊 {rate_text}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📡 منبع: TGJU\n"
        f"🕐 دالر: {usd_time}\n"
        f"🕐 یورو: {eur_time}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    keyboard = [

        [
            InlineKeyboardButton(
                "🔄 تبدیل جدید",
                callback_data="convert",
            )
        ],

        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="home",
            )
        ],

    ]

    await update.message.reply_text(
        result_text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )

    return ConversationHandler.END


# =========================================================
# محاسبه دستی
# =========================================================

async def manual_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🧮 محاسبه دستی\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ نرخ یورو به افغانی را وارد کنید.\n\n"
        "مثال: 74"
    )

    await query.edit_message_text(
        text
    )

    return MANUAL_EURO


async def manual_euro(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    value = clean_number(
        update.message.text
    )

    if value is None or value <= 0:

        await update.message.reply_text(
            "❌ یک عدد معتبر وارد کنید.\n"
            "مثال: 74"
        )

        return MANUAL_EURO

    context.user_data["manual_euro"] = value

    await update.message.reply_text(
        "2️⃣ حالا نرخ دالر به افغانی را وارد کنید.\n\n"
        "مثال: 65"
    )

    return MANUAL_DOLLAR


async def manual_dollar(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    value = clean_number(
        update.message.text
    )

    if value is None or value <= 0:

        await update.message.reply_text(
            "❌ یک عدد معتبر وارد کنید.\n"
            "مثال: 65"
        )

        return MANUAL_DOLLAR

    context.user_data["manual_dollar"] = value

    await update.message.reply_text(
        "3️⃣ حالا مقدار تومان را وارد کنید.\n\n"
        "مثال: 100000"
    )

    return MANUAL_TOMAN


async def manual_toman(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    value = clean_number(
        update.message.text
    )

    if value is None or value <= 0:

        await update.message.reply_text(
            "❌ یک مقدار معتبر وارد کنید.\n"
            "مثال: 100000"
        )

        return MANUAL_TOMAN

    context.user_data["manual_toman"] = value

    await update.message.reply_text(
        "4️⃣ درصد کمیسیون را وارد کنید.\n\n"
        "مثال: 3"
    )

    return MANUAL_COMMISSION


async def manual_commission(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    commission = clean_number(
        update.message.text
    )

    if commission is None or commission < 0:

        await update.message.reply_text(
            "❌ درصد کمیسیون معتبر وارد کنید.\n"
            "مثال: 3"
        )

        return MANUAL_COMMISSION

    euro = context.user_data.get(
        "manual_euro"
    )

    dollar = context.user_data.get(
        "manual_dollar"
    )

    toman = context.user_data.get(
        "manual_toman"
    )

    if not euro or not dollar or toman is None:

        await update.message.reply_text(
            "❌ اطلاعات محاسبه کامل نیست.",
            reply_markup=back_keyboard(),
        )

        return ConversationHandler.END

    # نسبت یورو به دالر
    euro_to_dollar = euro / dollar

    # تبدیل تومان بر اساس نسبت
    converted = toman * euro_to_dollar

    # کمیسیون
    commission_amount = (
        converted * commission / 100
    )

    # مبلغ نهایی
    final_amount = (
        converted - commission_amount
    )

    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🧮 نتیجه محاسبه دستی\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🇪🇺 نرخ یورو: {format_number(euro)} افغانی\n"
        f"🇺🇸 نرخ دالر: {format_number(dollar)} افغانی\n\n"

        f"📊 نسبت یورو/دالر: "
        f"{euro_to_dollar:.4f}\n\n"

        f"💵 تومان: {format_number(toman)}\n\n"

        f"💰 قبل از کمیسیون:\n"
        f"{format_number(converted)} تومان\n\n"

        f"📉 کمیسیون {commission:g}%:\n"
        f"{format_number(commission_amount)} تومان\n\n"

        f"✅ مبلغ نهایی:\n"
        f"{format_number(final_amount)} تومان\n"

        "━━━━━━━━━━━━━━━━━━"
    )

    keyboard = [

        [
            InlineKeyboardButton(
                "🔄 محاسبه جدید",
                callback_data="manual",
            )
        ],

        [
            InlineKeyboardButton(
                "🏠 منوی اصلی",
                callback_data="home",
            )
        ],

    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )

    return ConversationHandler.END


# =========================================================
# لغو
# =========================================================

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "❌ عملیات لغو شد.",
        reply_markup=main_keyboard(),
    )

    return ConversationHandler.END


# =========================================================
# اجرای ربات
# =========================================================

def main():

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(False)
        .build()
    )

    # -----------------------------
    # تبدیل ارز
    # -----------------------------

    convert_conversation = ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                convert_start,
                pattern="^convert$",
            )
        ],

        states={

            CONVERT_FROM: [
                CallbackQueryHandler(
                    conversion_callback,
                    pattern="^from_",
                )
            ],

            CONVERT_TO: [
                CallbackQueryHandler(
                    conversion_callback,
                    pattern="^to_",
                )
            ],

            CONVERT_AMOUNT: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    convert_amount,
                )
            ],

        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel,
            )
        ],

        allow_reentry=True,
    )

    # -----------------------------
    # محاسبه دستی
    # -----------------------------

    manual_conversation = ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                manual_start,
                pattern="^manual$",
            )
        ],

        states={

            MANUAL_EURO: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    manual_euro,
                )
            ],

            MANUAL_DOLLAR: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    manual_dollar,
                )
            ],

            MANUAL_TOMAN: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    manual_toman,
                )
            ],

            MANUAL_COMMISSION: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    manual_commission,
                )
            ],

        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel,
            )
        ],

        allow_reentry=True,
    )

    # -----------------------------
    # Handlerها
    # -----------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            market,
            pattern="^market$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            home,
            pattern="^home$",
        )
    )

    application.add_handler(
        convert_conversation
    )

    application.add_handler(
        manual_conversation
    )

    print()
    print("======================================")
    print("🤖 Bot is running...")
    print("======================================")
    print()

    application.run_polling()


# =========================================================
# شروع
# =========================================================

if __name__ == "__main__":
    main()