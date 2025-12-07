import telebot
from telebot import types
from flask import Flask, render_template, request
from threading import Thread
import json
import os
import time

# 👇 1. APNA TOKEN YAHAN DALEIN 👇
API_TOKEN = '# Token ab hum direct nahi likhenge, balki Environment se lenge
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')' 

# 👇 2. APNA REPLIT URL YAHAN DALEIN 👇
WEB_APP_URL = "https://220d7af6-a70b-46c1-afbf-ed6624bf0538-00-14n3p80wqmp44.pike.replit.dev:5000/"

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# --- SETTINGS (Aapke mutabik) ---
MIN_WITHDRAW_AMOUNT = 300  # Kam se kam ₹300
MIN_REQUIRED_REFERS = 7    # Kam se kam 7 log

# --- DATABASE SYSTEM ---
DB_FILE = "database.json"

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

users = load_data()

# --- WEB SERVER ---
@app.route('/')
def home():
    return render_template('index.html')

def run_web():
    def run_web():
        # Render apna port khud deta hai, agar nahi mila to 5000 use karega
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- HELPER FUNCTIONS ---
def ensure_user(user_id, referrer_id=None):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            'balance': 0.0,
            'refers': 0,
            'referrer': referrer_id,
            'total_withdrawn': 0.0,
            'bonus_taken': False,
            'join_date': time.time()
        }
        if referrer_id and str(referrer_id) in users:
            users[str(referrer_id)]['refers'] += 1
            users[str(referrer_id)]['balance'] += 40.0
            save_data(users)
            try:
                bot.send_message(referrer_id, f"🎉 **New Referral!**\nUser {user_id} joined via your link.\n💰 You earned +₹40!")
            except:
                pass
        save_data(users)
    return users[uid]

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    web_app_info = types.WebAppInfo(WEB_APP_URL)
    btn1 = types.KeyboardButton(text="💰 Watch Ads", web_app=web_app_info)
    btn2 = types.KeyboardButton("💳 Balance")
    btn3 = types.KeyboardButton("🎁 Daily Bonus")
    btn4 = types.KeyboardButton("👥 Refer & Earn")
    btn5 = types.KeyboardButton("➡️ Extra")
    markup.add(btn1, btn2, btn3, btn4, btn5)
    return markup

# --- COMMANDS ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    args = message.text.split()
    referrer = None
    if len(args) > 1 and args[1].isdigit():
        referrer = args[1]
        if str(referrer) == str(user_id): referrer = None

    ensure_user(user_id, referrer)

    text = (
        f"👋 **Welcome to CashyAds!**\n\n"
        f"💰 Watch ads → Earn ₹3-5 Rs each\n"
        f"👥 Refer → Earn ₹40 Rs + 5% commission\n"
        f"🎁 Daily bonus: ₹5 Rs (once/day)\n\n"
        f"👇 **Start Earning Now:**"
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_menu())

# --- AD WATCH SUCCESS ---
@bot.message_handler(content_types=['web_app_data'])
def web_app_data_handler(message):
    if message.web_app_data.data == "AD_WATCHED_SUCCESS":
        uid = str(message.from_user.id)
        ensure_user(uid)

        reward = 4.2
        users[uid]['balance'] += reward

        ref_id = users[uid].get('referrer')
        if ref_id and str(ref_id) in users:
            commission = reward * 0.05
            users[str(ref_id)]['balance'] += commission

        save_data(users)

        bal = round(users[uid]['balance'], 2)
        text = (
            f"✅ **Ad watched successfully!**\n"
            f"💰 You earned: +{reward} Rs\n"
            f"💳 New balance: {bal} Rs"
        )
        bot.reply_to(message, text, parse_mode="Markdown")

# --- WITHDRAWAL SYSTEM (Updated Logic) ---
@bot.message_handler(func=lambda message: message.text == "💳 Balance")
def show_balance(message):
    uid = str(message.from_user.id)
    bal = round(users[uid]['balance'], 2)

    text = f"💳 **Your balance:** {bal} Rs\n👇 Ready to withdraw?"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Withdraw", callback_data="withdraw_menu"))
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "withdraw_menu")
def withdraw_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💳 Paytm", callback_data="pay_Paytm"),
        types.InlineKeyboardButton("💸 UPI", callback_data="pay_UPI"),
        types.InlineKeyboardButton("💲 USDT TRC20", callback_data="pay_USDT"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="close_menu")
    )
    bot.edit_message_text("💳 **Choose Payment Method:**\nSelect your preferred withdrawal method below:", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# 👇👇 YE NAYA LOGIC HAI (RESTRICTION WALA) 👇👇
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def ask_payment_details(call):
    method = call.data.split("_")[1]
    uid = str(call.from_user.id)
    user_data = users[uid]

    bal = user_data['balance']
    refers = user_data['refers']

    # Check Conditions (Screenhot jaisa error logic)
    if bal < MIN_WITHDRAW_AMOUNT or refers < MIN_REQUIRED_REFERS:

        error_text = (
            f"❌ **Cannot Withdraw!**\n\n"
            f"💳 **Method Selected:** {method}\n\n"
            f"**Why you can't withdraw:**\n"
            f"Min {MIN_WITHDRAW_AMOUNT} Rs. Current: {round(bal, 1)}\n\n"
            f"💡 **Requirements:**\n"
            f"• Minimum balance: ₹{MIN_WITHDRAW_AMOUNT}\n"
            f"• Minimum referrals: {MIN_REQUIRED_REFERS} (You have: {refers})\n\n"
            f"Keep earning to unlock withdrawals! 💰"
        )

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="withdraw_menu"))

        bot.edit_message_text(error_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        return

    # Agar sab sahi hai, to details mango
    msg = bot.edit_message_text(
        f"₿ **Enter Your {method} Wallet/ID:**\n\n"
        f"💰 Amount: ₹{round(bal, 2)}\n"
        f"💳 Method: {method}\n\n"
        f"Please reply with your {method} details below.\nExample: `abc@upi` or Wallet Address",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, process_withdrawal, method, bal)

def process_withdrawal(message, method, amount):
    uid = str(message.from_user.id)
    wallet_details = message.text

    users[uid]['balance'] = 0.0
    users[uid]['total_withdrawn'] += amount
    save_data(users)

    text = (
        f"✅ **Withdrawal Processed!**\n\n"
        f"💰 Amount: ₹{round(amount, 2)}\n"
        f"💳 Method: {method}\n"
        f"👤 Details: `{wallet_details}`\n\n"
        f"⏳ **Status:** Processing...\n"
        f"📩 Admin will contact within 24h\n\n"
        f"💳 **New Balance:** ₹0.0"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "close_menu")
def close_menu(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

# --- OTHER HANDLERS ---
@bot.message_handler(func=lambda message: message.text == "➡️ Extra")
def show_extra(message):
    uid = str(message.from_user.id)
    u_data = users[uid]
    total_users = len(users) + 3800
    total_paid = sum(u['total_withdrawn'] for u in users.values()) + 157000

    text = (
        f"➡️ **EXTRA INFO**\n\n"
        f"👤 **Your Stats:**\n"
        f"💰 Balance: ₹{round(u_data['balance'], 2)}\n"
        f"👥 Referrals: {u_data['refers']}\n"
        f"💸 Withdrawn: ₹{u_data['total_withdrawn']}\n\n"
        f"📊 **Bot Stats:**\n"
        f"👥 Total Users: {total_users}\n"
        f"💎 Total Paid: ₹{total_paid}\n\n"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "👥 Refer & Earn")
def refer_earn(message):
    uid = str(message.from_user.id)
    bot_name = bot.get_me().username
    link = f"https://t.me/{bot_name}?start={uid}"

    text = (
        f"👥 **Your Referral Link:**\n"
        f"`{link}`\n\n"
        f"👥 Referrals: {users[uid]['refers']}\n\n"
        f"💰 **Earnings:**\n"
        f"• 40 Rs per referral\n"
        f"• 5% commission\n\n"
        f"📱 Click link to copy & share!"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🎁 Daily Bonus")
def daily_bonus(message):
    uid = str(message.from_user.id)
    if not users[uid]['bonus_taken']:
        users[uid]['balance'] += 5.0
        users[uid]['bonus_taken'] = True
        save_data(users)
        bot.reply_to(message, "🎉 **Daily Bonus Claimed!**\n+5 Rs added.")
    else:
        bot.reply_to(message, "❌ **Already claimed today!**\nTry tomorrow.")

print("Bot is Running...")
keep_alive()
bot.infinity_polling()
