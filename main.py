import telebot
from telebot import types
from flask import Flask, render_template, request
from threading import Thread
import json
import os
import time

# 👇 1. TOKEN: Ye ab Environment (Render) se aayega
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# 👇 2. WEB APP URL: (Aapka Render Link)
# Agar ye link galat ho, to ise change kar lena
WEB_APP_URL = "https://cashylive.onrender.com"

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# --- SETTINGS ---
MIN_WITHDRAW_AMOUNT = 300
MIN_REQUIRED_REFERS = 7

# --- DATABASE ---
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

# --- SERVER ---
@app.route('/')
def home():
    return render_template('index.html')

def run_web():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- FUNCTIONS ---
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

# --- BOT COMMANDS ---
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

@bot.message_handler(content_types=['web_app_data'])
def web_app_data_handler(message):
    if message.web_app_data.data == "AD_WATCHED_SUCCESS":
        uid = str(message.from_user.id)
        ensure_user(uid)
        
        reward = 4.2
        users[uid]['balance'] += reward
        
        ref_id = users[uid].get('referrer')
        if ref_id and str(ref_id) in users:
            users[str(ref_id)]['balance'] += (reward * 0.05)
            
        save_data(users)
        bal = round(users[uid]['balance'], 2)
        
        bot.reply_to(message, f"✅ **Ad watched!**\n💰 +4.2 Rs\n💳 Balance: {bal} Rs", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💳 Balance")
def show_balance(message):
    uid = str(message.from_user.id)
    bal = round(users[uid]['balance'], 2)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Withdraw", callback_data="withdraw_menu"))
    bot.reply_to(message, f"💳 **Balance:** {bal} Rs", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "withdraw_menu")
def withdraw_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💳 Paytm", callback_data="pay_Paytm"),
        types.InlineKeyboardButton("💸 UPI", callback_data="pay_UPI"),
        types.InlineKeyboardButton("💲 USDT TRC20", callback_data="pay_USDT"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="close_menu")
    )
    bot.edit_message_text("💳 **Choose Method:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def ask_payment_details(call):
    method = call.data.split("_")[1]
    uid = str(call.from_user.id)
    user_data = users[uid]
    bal = user_data['balance']
    refers = user_data['refers']
    
    if bal < MIN_WITHDRAW_AMOUNT or refers < MIN_REQUIRED_REFERS:
        error_text = (
            f"❌ **Cannot Withdraw!**\n"
            f"Min Balance: ₹{MIN_WITHDRAW_AMOUNT} (You: {round(bal,1)})\n"
            f"Min Refers: {MIN_REQUIRED_REFERS} (You: {refers})"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="withdraw_menu"))
        bot.edit_message_text(error_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        return

    msg = bot.edit_message_text(f"👇 Reply with your {method} ID:", call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(msg, process_withdrawal, method, bal)

def process_withdrawal(message, method, amount):
    uid = str(message.from_user.id)
    users[uid]['balance'] = 0.0
    users[uid]['total_withdrawn'] += amount
    save_data(users)
    bot.reply_to(message, "✅ **Withdrawal Request Sent!**")

@bot.callback_query_handler(func=lambda call: call.data == "close_menu")
def close_menu(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda message: message.text == "➡️ Extra")
def show_extra(message):
    uid = str(message.from_user.id)
    u = users[uid]
    text = f"👤 **Stats:**\n💰 Bal: {round(u['balance'], 2)}\n👥 Ref: {u['refers']}\n💸 W/D: {u['total_withdrawn']}"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "👥 Refer & Earn")
def refer_earn(message):
    uid = str(message.from_user.id)
    bot_name = bot.get_me().username
    link = f"https://t.me/{bot_name}?start={uid}"
    bot.reply_to(message, f"👥 **Link:**\n`{link}`\n\nEarn ₹40 per refer!", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🎁 Daily Bonus")
def daily_bonus(message):
    uid = str(message.from_user.id)
    if not users[uid]['bonus_taken']:
        users[uid]['balance'] += 5.0
        users[uid]['bonus_taken'] = True
        save_data(users)
        bot.reply_to(message, "✅ +₹5 Bonus!")
    else:
        bot.reply_to(message, "❌ Come back tomorrow.")

keep_alive()
bot.infinity_polling()
