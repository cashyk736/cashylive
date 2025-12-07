import telebot
from telebot import types
from flask import Flask, render_template
from threading import Thread
import json
import os
import time

# 👇 1. TOKEN SETUP
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# 👇 2. APNA RENDER URL YAHAN DALEIN
WEB_APP_URL = "https://cashylive.onrender.com"  # <--- CHANGE THIS

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# --- SETTINGS ---
MIN_WITHDRAW_AMOUNT = 300
MIN_REQUIRED_REFERS = 6

# --- DATABASE SYSTEM ---
DB_FILE = "database.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: return {}
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
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- HELPER FUNCTIONS ---
def ensure_user(user_id, referrer_id=None):
    uid = str(user_id)
    if uid not in users:
        # New User Create
        users[uid] = {
            'balance': 0.0,
            'refers': 0,
            'referrer': referrer_id,
            'total_withdrawn': 0.0,
            'bonus_taken': False,
            'join_date': time.time()
        }
        
        # Referrer Logic
        if referrer_id and str(referrer_id) in users:
            users[str(referrer_id)]['refers'] += 1
            users[str(referrer_id)]['balance'] += 40.0
            save_data(users)
            
            # 👇 FIXED NOTIFICATION LOGIC (HTML MODE) 👇
            try:
                msg = (
                    f"🎉 <b>Someone joined via your referral!</b>\n\n"
                    f"👤 <b>User:</b> User_{user_id}\n"
                    f"💰 <b>You earned:</b> 40 Rs\n"
                    f"💳 <b>Check balance for details!</b>"
                )
                bot.send_message(referrer_id, msg, parse_mode="HTML")
            except Exception as e:
                print(f"Notification Error: {e}")

        save_data(users)
    return users[uid]

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if WEB_APP_URL and WEB_APP_URL.startswith("http"):
        btn1 = types.KeyboardButton(text="Watch Ads 💰", web_app=types.WebAppInfo(WEB_APP_URL))
    else:
        btn1 = types.KeyboardButton(text="Watch Ads 💰 (Link Error)")
    
    markup.row(btn1)
    markup.row(types.KeyboardButton("Balance 💳"), types.KeyboardButton("Bonus 🎁"))
    markup.row(types.KeyboardButton("Refer and Earn 👥"), types.KeyboardButton("Extra ➡️"))
    return markup

# --- RESET COMMAND (TESTING) ---
@bot.message_handler(commands=['reset'])
def reset_user(message):
    uid = str(message.from_user.id)
    if uid in users:
        del users[uid]
        save_data(users)
        bot.reply_to(message, "🗑 **Data Deleted!**\nAb aap wapis Referral Link se join karke test kar sakte hain.")
    else:
        bot.reply_to(message, "❌ Aapka data pehle se deleted hai.")

# --- COMMANDS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.from_user.id
    args = message.text.split()
    referrer = args[1] if len(args) > 1 and args[1].isdigit() and args[1] != str(uid) else None
    
    ensure_user(uid, referrer)

    text = (
        f"🎉 **Welcome to Cashyads!**\n\n"
        f"💰 **Watch ads** → Earn 3-5 Rs each\n"
        f"👥 **Refer** → Earn 40 Rs + 5% commission\n"
        f"🎁 **Daily bonus:** 5 Rs (once/day)"
    )
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=get_main_menu())

# --- AD REWARD ---
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
        
        text = (
            f"✅ **Ad watched successfully!**\n"
            f"💰 **You earned:** +{reward} Rs\n"
            f"💳 **New balance:** {round(users[uid]['balance'], 1)} Rs"
        )
        bot.reply_to(message, text, parse_mode="Markdown")

# --- REFER AND EARN ---
@bot.message_handler(func=lambda message: message.text == "Refer and Earn 👥")
def refer_earn(message):
    uid = str(message.from_user.id)
    user_data = ensure_user(uid)
    ref_count = user_data['refers']
    
    bot_name = bot.get_me().username
    link = f"https://t.me/{bot_name}?start={uid}"
    
    text = (
        f"👥 **Your Referral Link:**\n\n"
        f"`{link}`\n\n"
        f"👫 **Referrals:** {ref_count}\n\n"
        f"💰 **Earnings:**\n"
        f"• 40 Rs per referral\n"
        f"• 5% commission on their ad earnings\n\n"
        f"📱 Click to share!"
    )
    
    markup = types.InlineKeyboardMarkup()
    share_url = f"https://t.me/share/url?url={link}&text=Join%20this%20bot%20to%20earn%20money%20daily!%20%F0%9F%92%B0"
    markup.add(types.InlineKeyboardButton("📨 Share Link", url=share_url))
    
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

# --- WITHDRAWAL SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "Balance 💳")
def show_balance(message):
    uid = str(message.from_user.id)
    ensure_user(uid)
    bal = round(users[uid]['balance'], 1)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Withdraw", callback_data="withdraw_menu"))
    
    bot.reply_to(message, f"💳 **Your balance: {bal} Rs**\n\n👇 Ready to withdraw?", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "withdraw_menu")
def withdraw_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💳 Paytm", callback_data="pay_Paytm"),
        types.InlineKeyboardButton("💸 UPI", callback_data="pay_UPI"),
        types.InlineKeyboardButton("🏦 Bank Transfer", callback_data="pay_Bank"),
        types.InlineKeyboardButton("💲 Paypal", callback_data="pay_Paypal"),
        types.InlineKeyboardButton("₿ USDT TRC20", callback_data="pay_USDT"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="close_menu")
    )
    bot.edit_message_text("💳 **Choose Payment Method:**\nSelect your preferred withdrawal method below:", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def ask_payment_details(call):
    method = call.data.split("_")[1]
    uid = str(call.from_user.id)
    user_data = users[uid]
    bal = round(user_data['balance'], 1)
    refers = user_data['refers']

    if bal < MIN_WITHDRAW_AMOUNT or refers < MIN_REQUIRED_REFERS:
        error_text = (
            f"❌ **Cannot Withdraw!**\n\n"
            f"💳 **Method Selected:** {method}\n\n"
            f"**Why you can't withdraw:**\n"
            f"Min {MIN_WITHDRAW_AMOUNT} Rs. Current: {bal}\n\n"
            f"💡 **Requirements:**\n"
            f"• Minimum balance: ₹{MIN_WITHDRAW_AMOUNT}\n"
            f"• Minimum referrals: {MIN_REQUIRED_REFERS} (You have: {refers})\n\n"
            f"Keep earning to unlock withdrawals! 💰"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="withdraw_menu"))
        bot.edit_message_text(error_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        return

    msg = bot.edit_message_text(
        f"✅ **Enter Your {method} details:**\n\n"
        f"💰 Amount: ₹{bal}\n"
        f"👇 Reply with your ID/Number:",
        call.message.chat.id, call.message.message_id, parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, process_withdrawal, method, bal)

def process_withdrawal(message, method, amount):
    uid = str(message.from_user.id)
    users[uid]['balance'] = 0.0
    users[uid]['total_withdrawn'] += amount
    save_data(users)
    bot.reply_to(message, "✅ **Request Submitted!**\nProcessing...")

@bot.callback_query_handler(func=lambda call: call.data == "close_menu")
def close_menu(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

# --- OTHER HANDLERS ---
@bot.message_handler(func=lambda message: message.text == "Extra ➡️")
def show_extra(message):
    uid = str(message.from_user.id)
    total_users = len(users) + 4419
    total_paid = 191269.0
    
    text = (
        f"📊 **Bot Stats:**\n"
        f"👥 **Total Users:** {total_users}\n"
        f"💎 **Total Balance:** ₹{total_paid}\n\n"
        f"📢 **Official Links:**"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💬 Support", url="https://t.me/cashysnapsupportbot"))
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Bonus 🎁")
def daily_bonus(message):
    uid = str(message.from_user.id)
    ensure_user(uid)
    if not users[uid]['bonus_taken']:
        users[uid]['balance'] += 5.0
        users[uid]['bonus_taken'] = True
        save_data(users)
        bot.reply_to(message, "🎉 **Daily Bonus Claimed!**\n+5 Rs added!\n👇 Check balance!", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ **Already claimed today!**\n⏳ Try tomorrow!", parse_mode="Markdown")

# --- RUNNING ---
print("Bot Started...")
keep_alive()
try:
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
except Exception as e:
    print(f"⚠️ Error ignored: {e}")
