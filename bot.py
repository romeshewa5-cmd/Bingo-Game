import logging, json, os, asyncio, threading
from flask import Flask, request, Response, send_from_directory
from telegram import (
    Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters
)
from database import Database

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config (set these in Render → Environment) ────────────────────────────────
BOT_TOKEN       = os.environ.get("BOT_TOKEN",       "8388233934:AAHosCkcQgogC9x92pGQ6_AjYTuRFogHlDY")
WEBAPP_URL      = os.environ.get("WEBAPP_URL",      "https://github.com/romeshewa5-cmd/Bingo-Game/tree/main/webapp")
ADMIN_ID        = int(os.environ.get("ADMIN_ID",    "0"))
TELEBIRR_NUMBER = os.environ.get("TELEBIRR_NUMBER", "0926710936")
CBE_NUMBER      = os.environ.get("CBE_NUMBER",      "1000132035605")
WEBHOOK_URL     = os.environ.get("WEBHOOK_URL",     "https://fast-bingo-5ipb.onrender.com")
PORT            = int(os.environ.get("PORT",        10000))

db  = Database()
app = Flask(__name__)

# Conversation states
DEPOSIT_AMOUNT, DEPOSIT_METHOD, DEPOSIT_CONFIRM = range(3)
WITHDRAW_AMOUNT, WITHDRAW_PHONE                 = range(3, 5)
TRANSFER_USER,  TRANSFER_AMOUNT                 = range(5, 7)

# ── Flask routes ──────────────────────────────────────────────────────────────
# ── Flask routes ──────────────────────────────────────────────────────────────
@app.get("/")
def index():
    # This delivers your main HTML file when the app opens
    return send_from_directory(".", "index.html")

@app.get("/<path:path>")
def serve_static(path):
    # This ensures your CSS, JS, or image assets load properly
    return send_from_directory(".", path)

@app.get("/health")
def health():
    return Response("OK", status=200)

# ── Keyboards ─────────────────────────────────────────────────────────────────
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎮 Play Now", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("💰 Check Balance"), KeyboardButton("💳 Deposit")],
        [KeyboardButton("📤 Withdraw"),       KeyboardButton("🔄 Transfer")],
        [KeyboardButton("📋 Transactions"),   KeyboardButton("ℹ️ Instructions")],
        [KeyboardButton("📞 Contact Us")],
    ], resize_keyboard=True)

# ── Handlers ──────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.register_user(u.id, u.username or "", u.first_name or "User")
    bal = db.get_balance(u.id)
    await update.message.reply_text(
        f"🎮 *Welcome to Bingo Bot!*\n\nHello {u.first_name}! Play bingo and start winning today! 🎉\n\n💰 Balance: *{bal:.2f} ETB*\n\nTap *Play Now* to open the game:",
        parse_mode="Markdown", reply_markup=main_kb())

async def register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.register_user(u.id, u.username or "", u.first_name or "User")
    await update.message.reply_text(
        f"✅ *Registered!*\n\nName: {u.first_name}\nID: `{u.id}`\n\nUse /deposit to add funds!",
        parse_mode="Markdown", reply_markup=main_kb())

async def check_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    bal = db.get_balance(update.effective_user.id)
    await update.message.reply_text(f"💰 *Your Balance*\n\nAvailable: *{bal:.2f} ETB*", parse_mode="Markdown")

async def play(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tap to open the game! 🎮",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Open Game", web_app=WebAppInfo(url=WEBAPP_URL))]]))

# DEPOSIT
async def deposit_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💳 *Deposit Funds*\n\nEnter amount *(minimum 50 ETB)*:",
        parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True))
    return DEPOSIT_AMOUNT

async def deposit_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    if t == "❌ Cancel":
        await update.message.reply_text("Cancelled.", reply_markup=main_kb())
        return ConversationHandler.END
    try:
        amt = float(t)
        if amt < 50:
            await update.message.reply_text("❌ Minimum is 50 ETB. Try again:")
            return DEPOSIT_AMOUNT
        ctx.user_data["dep_amt"] = amt
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number:")
        return DEPOSIT_AMOUNT
    await update.message.reply_text(
        f"Choose payment method for *{amt:.1f} ETB*:", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 TeleBirr", callback_data="dep_telebirr")],
            [InlineKeyboardButton("🏦 CBE Birr",  callback_data="dep_cbe")],
            [InlineKeyboardButton("❌ Cancel",     callback_data="dep_cancel")],
        ]))
    return DEPOSIT_METHOD

async def deposit_method(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "dep_cancel":
        await q.edit_message_text("Cancelled."); return ConversationHandler.END
    amt = ctx.user_data.get("dep_amt", 0)
    method, acct = ("TeleBirr", TELEBIRR_NUMBER) if q.data == "dep_telebirr" else ("CBE Birr", CBE_NUMBER)
    ctx.user_data["dep_method"] = method
    await q.edit_message_text(
        f"💰 *Manual Deposit — {method}*\n\n💳 Amount: *{amt:.1f} ETB*\n🏦 Account: `{acct}`\n\n"
        f"*Steps:*\n1. Send *{amt:.1f} ETB* to the account above via {method}\n"
        f"2. You receive a confirmation SMS\n3. Copy that SMS and paste it here\n\n"
        f"⚠️ Only {method} → our {method} account\n\nPaste your SMS now:",
        parse_mode="Markdown")
    return DEPOSIT_CONFIRM

async def deposit_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    sms = update.message.text.strip()
    amt = ctx.user_data.get("dep_amt", 0)
    method = ctx.user_data.get("dep_method", "")
    dep_id = db.create_pending_deposit(u.id, amt, method, sms)
    try:
        await ctx.bot.send_message(ADMIN_ID,
            f"🔔 *New Deposit Request*\n\nUser: {u.first_name} (@{u.username})\nID: `{u.id}`\n"
            f"Amount: *{amt:.2f} ETB*\nMethod: {method}\nRef: `{dep_id}`\n\nSMS:\n`{sms}`\n\n"
            f"✅ `/approve {dep_id}`\n❌ `/reject {dep_id}`", parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Admin notify failed: {e}")
    await update.message.reply_text(
        f"✅ *Request received!*\n\nAmount: *{amt:.2f} ETB*\nStatus: ⏳ Pending\n\nWill be credited after verification.",
        parse_mode="Markdown", reply_markup=main_kb())
    return ConversationHandler.END

async def approve_deposit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not ctx.args: await update.message.reply_text("Usage: /approve <id>"); return
    dep = db.get_deposit(int(ctx.args[0]))
    if not dep: await update.message.reply_text("❌ Not found."); return
    db.approve_deposit(dep["id"]); db.credit_balance(dep["user_id"], dep["amount"])
    bal = db.get_balance(dep["user_id"])
    await ctx.bot.send_message(dep["user_id"],
        f"✅ *Deposit Approved!*\n\nAmount: *{dep['amount']:.2f} ETB*\nNew Balance: *{bal:.2f} ETB*\n\nEnjoy! 🎮",
        parse_mode="Markdown")
    await update.message.reply_text(f"✅ Approved #{dep['id']} — {dep['amount']} ETB credited.")

async def reject_deposit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not ctx.args: await update.message.reply_text("Usage: /reject <id>"); return
    dep = db.get_deposit(int(ctx.args[0]))
    if not dep: await update.message.reply_text("❌ Not found."); return
    db.reject_deposit(dep["id"])
    await ctx.bot.send_message(dep["user_id"],
        f"❌ *Deposit Rejected*\n\nAmount: *{dep['amount']:.2f} ETB*\n\nContact /contact", parse_mode="Markdown")
    await update.message.reply_text(f"❌ Rejected #{dep['id']}.")

async def pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    deps = db.get_pending_deposits()
    if not deps: await update.message.reply_text("No pending deposits."); return
    text = "📋 *Pending Deposits*\n\n"
    for d in deps:
        text += f"ID `{d['id']}` — {d['amount']} ETB — {d['method']} — user `{d['user_id']}`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# WITHDRAW
async def withdraw_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    bal = db.get_balance(update.effective_user.id)
    await update.message.reply_text(
        f"📤 *Withdraw*\n\nAvailable: *{bal:.2f} ETB*\nMinimum: 100 ETB\n\nEnter amount:",
        parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True))
    return WITHDRAW_AMOUNT

async def withdraw_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    if t == "❌ Cancel":
        await update.message.reply_text("Cancelled.", reply_markup=main_kb()); return ConversationHandler.END
    bal = db.get_balance(update.effective_user.id)
    try:
        amt = float(t)
        if amt < 100: await update.message.reply_text("❌ Minimum 100 ETB:"); return WITHDRAW_AMOUNT
        if amt > bal: await update.message.reply_text(f"❌ Not enough ({bal:.2f} ETB):"); return WITHDRAW_AMOUNT
        ctx.user_data["wd_amt"] = amt
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number:"); return WITHDRAW_AMOUNT
    await update.message.reply_text("Enter your TeleBirr phone number:")
    return WITHDRAW_PHONE

async def withdraw_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user; phone = update.message.text.strip(); amt = ctx.user_data.get("wd_amt", 0)
    db.debit_balance(u.id, amt, "Withdrawal"); db.create_pending_withdrawal(u.id, amt, phone)
    try:
        await ctx.bot.send_message(ADMIN_ID,
            f"🔔 *Withdrawal*\n\nUser: {u.first_name} (@{u.username})\nID: `{u.id}`\nAmount: *{amt:.2f} ETB*\nPhone: `{phone}`",
            parse_mode="Markdown")
    except Exception: pass
    await update.message.reply_text(
        f"✅ *Withdrawal Submitted!*\n\nAmount: *{amt:.2f} ETB*\nPhone: {phone}\n\nProcessed within 1–2 hours.",
        parse_mode="Markdown", reply_markup=main_kb())
    return ConversationHandler.END

# TRANSFER
async def transfer_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 *Transfer*\n\nEnter recipient username or Telegram ID:",
        parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True))
    return TRANSFER_USER

async def transfer_user_step(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    if t == "❌ Cancel":
        await update.message.reply_text("Cancelled.", reply_markup=main_kb()); return ConversationHandler.END
    rec = db.find_user(t.lstrip("@"))
    if not rec: await update.message.reply_text("❌ User not found:"); return TRANSFER_USER
    if rec["telegram_id"] == update.effective_user.id:
        await update.message.reply_text("❌ Can't transfer to yourself."); return TRANSFER_USER
    ctx.user_data["tr_to"] = rec
    await update.message.reply_text(f"Recipient: *{rec['name']}*\n\nEnter amount:", parse_mode="Markdown")
    return TRANSFER_AMOUNT

async def transfer_amount_step(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user; rec = ctx.user_data.get("tr_to"); bal = db.get_balance(u.id)
    try:
        amt = float(update.message.text.strip())
        if amt <= 0 or amt > bal:
            await update.message.reply_text(f"❌ Invalid. Balance: {bal:.2f} ETB:"); return TRANSFER_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number:"); return TRANSFER_AMOUNT
    db.debit_balance(u.id, amt, f"Transfer to {rec['name']}")
    db.credit_balance(rec["telegram_id"], amt, f"Transfer from {u.first_name}")
    await update.message.reply_text(
        f"✅ *Sent {amt:.2f} ETB* to {rec['name']}\nNew Balance: *{db.get_balance(u.id):.2f} ETB*",
        parse_mode="Markdown", reply_markup=main_kb())
    try:
        await ctx.bot.send_message(rec["telegram_id"], f"💰 You received *{amt:.2f} ETB* from {u.first_name}!", parse_mode="Markdown")
    except Exception: pass
    return ConversationHandler.END

async def transactions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txns = db.get_transactions(update.effective_user.id, 10)
    if not txns: await update.message.reply_text("No transactions yet."); return
    text = "📋 *Last 10 Transactions*\n\n"
    for t in txns:
        text += f"{'⬆️' if t['type']=='credit' else '⬇️'} *{t['amount']:.2f} ETB* — {t['description']}\n`{t['created_at'][:16]}`\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def instructions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How to Play Bingo*\n\n1️⃣ Deposit funds\n2️⃣ Tap *Play Now*\n3️⃣ Choose bet & tap Join\n"
        "4️⃣ Pick your card (Cartela)\n5️⃣ Numbers called every 8 seconds\n6️⃣ Mark matching numbers\n"
        "7️⃣ Complete a line → tap *BINGO!*\n\n🏆 Prize = Bet × Players\n🎁 BONUS games = extra prizes!",
        parse_mode="Markdown")

async def contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📞 *Contact Support*\n\nTelegram: @YourSupportUsername\nPhone: +251 9XX XXX XXX\n\nHours: 8AM–10PM daily",
        parse_mode="Markdown")

async def handle_webapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
    except Exception: return
    u = update.effective_user; action = data.get("action")
    if action == "join_game":
        bet = float(data.get("bet", 0)); card = int(data.get("card", 0))
        bal = db.get_balance(u.id)
        if bal < bet:
            await update.message.reply_text(f"❌ Need *{bet:.2f} ETB*, you have *{bal:.2f} ETB*. Use /deposit.", parse_mode="Markdown"); return
        db.debit_balance(u.id, bet, f"Game bet {bet} ETB — Card #{card}")
        db.record_game_entry(u.id, bet, card)
        await update.message.reply_text(
            f"✅ *Game Joined!*\n\nBet: *{bet:.2f} ETB* | Card: #{card}\nBalance: *{db.get_balance(u.id):.2f} ETB*\n\nGood luck! 🍀",
            parse_mode="Markdown")
    elif action == "bingo_claim":
        await update.message.reply_text("🎉 Bingo claim received! Verifying…")
        try:
            await ctx.bot.send_message(ADMIN_ID,
                f"🎯 *Bingo Claim!*\nUser: {u.first_name} (@{u.username})\nID: `{u.id}`\nData: `{json.dumps(data)}`",
                parse_mode="Markdown")
        except Exception: pass

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mapping = {
        "💰 Check Balance": check_balance, "💳 Deposit": deposit_start,
        "📤 Withdraw": withdraw_start,     "🔄 Transfer": transfer_start,
        "📋 Transactions": transactions,   "ℹ️ Instructions": instructions,
        "📞 Contact Us": contact,
    }
    fn = mapping.get(update.message.text)
    if fn: return await fn(update, ctx)

# ── Build PTB ─────────────────────────────────────────────────────────────────
def build_ptb():
    application = Application.builder().token(BOT_TOKEN).build()
    dep_conv = ConversationHandler(
        entry_points=[CommandHandler("deposit", deposit_start)],
        states={
            DEPOSIT_AMOUNT : [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)],
            DEPOSIT_METHOD : [CallbackQueryHandler(deposit_method, pattern="^dep_")],
            DEPOSIT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_confirm)],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)], allow_reentry=True)
    wd_conv = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw_start)],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)],
            WITHDRAW_PHONE : [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_phone)],
        }, fallbacks=[], allow_reentry=True)
    tr_conv = ConversationHandler(
        entry_points=[CommandHandler("transfer", transfer_start)],
        states={
            TRANSFER_USER  : [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_user_step)],
            TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_amount_step)],
        }, fallbacks=[], allow_reentry=True)
    for cmd, fn in [("start",start),("register",register),("check_balance",check_balance),
                    ("play",play),("transaction",transactions),("instruction",instructions),
                    ("contact",contact),("approve",approve_deposit),("reject",reject_deposit),("pending",pending)]:
        application.add_handler(CommandHandler(cmd, fn))
    application.add_handler(dep_conv); application.add_handler(wd_conv); application.add_handler(tr_conv)
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application

# ── Start background loop + PTB ───────────────────────────────────────────────
bot_loop = asyncio.new_event_loop()
threading.Thread(target=lambda: (asyncio.set_event_loop(bot_loop), bot_loop.run_forever()), daemon=True).start()

ptb = build_ptb()

async def _init():
    await ptb.initialize(); await ptb.start()
    wh = f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"
    await ptb.bot.set_webhook(url=wh)
    logger.info(f"✅ Webhook set → {wh}")

asyncio.run_coroutine_threadsafe(_init(), bot_loop).result(timeout=30)
logger.info("🎮 Bingo Bot running in webhook mode")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
