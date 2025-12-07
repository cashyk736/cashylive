import telebot
from telebot import types
from flask import Flask, render_template
from threading import Thread
import json
import os
import time

# 👇 RENDER ENVIRONMENT VARIABLE SE TOKEN LEGA 👇
# (Make sure Render me 'API_TOKEN' naam se variable set ho)
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# 👇 APNA REPLIT/RENDER WEB URL (Agar WebApp button use kar rahe hain) 👇
# Agar Render ka URL hai to wo yahan dalein
WEB_APP_URL = "https://your-render-app-url.onrender.com" 

if not API_TOKEN:
    print("Error: API_TOKEN not found in environment variables!")

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# --- SETTINGS ---
MIN_WITHDRAW_AMOUNT = 300
MIN_REQUIRED_REFERS = 7

# --- DATABASE SYSTEM ---
DB_FILE = "database.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

users = load_data()

# --- WEB SERVER (REQUIRED FOR RENDER TO KEEP RUNNING) ---
@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    # Render ka default port uthayega ya fir 10000 use karega
    port = int(os.environ.get('PORT', 10000))
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
        # Referral Commission Logic
        if referrer_id and str(referrer_id) in users:
            users[str(referrer_id)]['refers'] += 1
            users[str(referrer_id)]['balance'] += 40.0
            save_data(users)
            try:
                bot.send_message(referrer_id, f"🎉 **New Referral!**\nUser {user_id} joined via your link.\n💰 You earned +40 Rs!")
            except:
                pass
        save_data(users)
    return users[uid]

# 👇 BUTTON LAYOUT (CASHYADS STYLE) 👇
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # Row 1: Watch Ads
    # Note: Agar WebApp URL set nahi hai to ye button kaam nahi karega
    web_app_info = types.WebAppInfo(WEB_APP_URL) if WEB_APP_URL else None
    if web_app_info:
        btn1 = types.KeyboardButton(text="Watch Ads 💰", web_app=web_app_info)
    else:
        btn1 = types.KeyboardButton(text="Watch Ads 💰") # Fallback without WebApp

    # Row 2: Balance | Bonus
    btn2 = types.KeyboardButton("Balance 💳")
    btn3 = types.KeyboardButton("Bonus 🎁")
    
    # Row 3: Refer | Extra
    btn4 = types.KeyboardButton("Refer and Earn 👥")
    btn5 = types.KeyboardButton("Extra ➡️")
    
    markup.row(btn1)
    markup.row(btn2, btn3)
    markup.row(btn4, btn5)
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
        f"🎉 **Welcome to Cashyads!**\n\n"
        f"💰 **Watch ads** → Earn 3-5 Rs each\n"
        f"👥 **Refer** → Earn 40 Rs + 5% commission\n"
        f"🎁 **Daily bonus:** 5 Rs (once/day)"
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

        bal = round(users[uid]['balance'], 1)
        text = (
            f"✅ **Ad watched successfully!**\n"
            f"💰 **You earned:** +{reward} Rs\n"
            f"💳 **New balance:** {bal} Rs"
        )
        bot.reply_to(message, text, parse_mode="Markdown")

# --- WITHDRAWAL SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "Balance 💳")
def show_balance(message):
    uid = str(message.from_user.id)
    bal = round(users[uid]['balance'], 1)

    text = (
        f"💳 **Your balance: {bal} Rs**\n\n"
        f"👇 Ready to withdraw?"
    )
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
    bot.edit_message_text("💳 **Choose Payment Method:**", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def ask_payment_details(call):
    method = call.data.split("_")[1]
    uid = str(call.from_user.id)
    user_data = users[uid]
    bal = user_data['balance']
    refers = user_data['refers']

    if bal < MIN_WITHDRAW_AMOUNT or refers < MIN_REQUIRED_REFERS:
        error_text = (
            f"❌ **Cannot Withdraw!**\n\n"
            f"⚠️ **Requirements:**\n"
            f"• Balance: ₹{MIN_WITHDRAW_AMOUNT}\n"
            f"• Refers: {MIN_REQUIRED_REFERS} (You have: {refers})"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="withdraw_menu"))
        bot.edit_message_text(error_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        return

    msg = bot.edit_message_text(
        f"Enter your {method} details:",
        call.message.chat.id, call.message.message_id
    )
    bot.register_next_step_handler(msg, process_withdrawal, method, bal)

def process_withdrawal(message, method, amount):
    uid = str(message.from_user.id)
    users[uid]['balance'] = 0.0
    users[uid]['total_withdrawn'] += amount
    save_data(users)
    bot.reply_to(message, "✅ **Request Submitted!**\nAdmin will process it shortly.")

@bot.callback_query_handler(func=lambda call: call.data == "close_menu")
def close_menu(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

# --- OTHER HANDLERS ---
@bot.message_handler(func=lambda message: message.text == "Extra ➡️")
def show_extra(message):
    uid = str(message.from_user.id)
    total_users = len(users) + 531 
    total_paid = 29285.7 

    text = (
        f"📊 **Bot Stats:**\n"
        f"👥 **Total Users:** {total_users}\n"
        f"💎 **Total Balance:** ₹{total_paid}\n\n"
        f"📢 **Official Links:**"
    )
    
    markup = types.InlineKeyboardMarkup()
    # 👇 UPDATED SUPPORT BUTTON LINK 👇
    markup.add(types.InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel_here"))
    markup.add(types.InlineKeyboardButton("💬 Support", url="https://t.me/cashysnapsupportbot"))
    
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Refer and Earn 👥")
def refer_earn(message):
    uid = str(message.from_user.id)
    bot_name = bot.get_me().username
    link = f"https://t.me/{bot_name}?start={uid}"

    text = (
        f"👥 **Your Referral Link:**\n\n"
        f"`{link}`\n\n"
        f"👫 **Referrals:** {users[uid]['refers']}\n\n"
        f"💰 **Earnings:**\n"
        f"• 40 Rs per referral\n"
        f"• 5% commission on their ad earnings\n\n"
        f"📱 Click to share!"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📩 Share Link", url=f"https://t.me/share/url?url={link}&text=Join%20and%20Earn%20Money!"))
    
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Bonus 🎁")
def daily_bonus(message):
    uid = str(message.from_user.id)
    if not users[uid]['bonus_taken']:
        users[uid]['balance'] += 5.0
        users[uid]['bonus_taken'] = True
        save_data(users)
        
        text = (
            f"🎉 **Daily Bonus Claimed!**\n"
            f"+5 Rs added!\n"
            f"👇 Check balance!"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        text = (
            f"❌ **Already claimed today!**\n"
            f"⏳ Try tomorrow!"
        )
        bot.reply_to(message, text, parse_mode="Markdown")

print("Bot is Running on Render...")
keep_alive()
bot.infinity_polling()
