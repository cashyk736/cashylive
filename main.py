import telebot
from telebot import types
from flask import Flask, request
from threading import Thread
import json
import os
import time

# 👇 1. TOKEN SETUP (Render Environment se lega)
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# 👇 2. APNA RENDER URL YAHAN PASTE KAREIN (ZAROORI HAI!) 👇
# Example: "https://cashylive.onrender.com"
WEB_APP_URL = "https://cashylive.onrender.com"  # <--- YAHAN CHANGE KAREIN

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# --- AD PAGE HTML (Isse 'Not Found' error nahi aayega) ---
AD_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Watch Ad</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body { font-family: sans-serif; text-align: center; padding: 20px; background-color: #f0f0f0; display: flex; flex-direction: column; justify-content: center; height: 100vh; margin: 0; }
.btn { background-color: #2ea650; color: white; padding: 15px 30px; border: none; border-radius: 10px; font-size: 18px; cursor: pointer; display: none; margin-top: 20px; }
.loader { border: 5px solid #f3f3f3; border-top: 5px solid #3498db; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 0 auto; }
h2 { color: #333; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
</style>
</head>
<body>
    <div id="loading">
        <div class="loader"></div>
        <h2>⏳ Loading Ad...</h2>
        <p>Please wait 3 seconds</p>
    </div>
    
    <div id="content" style="display:none;">
        <h1>🎉 Ad Watched!</h1>
        <p>Click below to claim reward.</p>
        <button id="claimBtn" class="btn" onclick="claimReward()">✅ Claim ₹4.2</button>
    </div>

<script>
    // 3 Second ka fake timer
    setTimeout(() => {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('content').style.display = 'block';
        document.getElementById('claimBtn').style.display = 'inline-block';
    }, 3000);

    function claimReward() {
        Telegram.WebApp.sendData("AD_WATCHED_SUCCESS");
    }
</script>
</body>
</html>
"""

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

# --- WEB SERVER (Ye 'Watch Ads' page dikhayega) ---
@app.route('/')
def home():
    return AD_PAGE_HTML

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
                bot.send_message(referrer_id, f"🎉 **New Referral!**\nUser {user_id} joined via your link.\n💰 You earned +40 Rs!")
            except: pass
        save_data(users)
    return users[uid]

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # WebApp URL check
    if WEB_APP_URL.startswith("http"):
        btn1 = types.KeyboardButton(text="Watch Ads 💰", web_app=types.WebAppInfo(WEB_APP_URL))
    else:
        btn1 = types.KeyboardButton(text="Watch Ads 💰 (Setup Error)")
    
    markup.row(btn1)
    markup.row(types.KeyboardButton("Balance 💳"), types.KeyboardButton("Bonus 🎁"))
    markup.row(types.KeyboardButton("Refer and Earn 👥"), types.KeyboardButton("Extra ➡️"))
    return markup

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

@bot.message_handler(content_types=['web_app_data'])
def web_app_data_handler(message):
    if message.web_app_data.data == "AD_WATCHED_SUCCESS":
        uid = str(message.from_user.id)
        ensure_user(uid)
        
        # Reward Logic
        reward = 4.2
        users[uid]['balance'] += reward
        
        # Commission
        ref_id = users[uid].get('referrer')
        if ref_id and str(ref_id) in users:
            users[str(ref_id)]['balance'] += (reward * 0.05)
        
        save_data(users)
        
        text = (
            f"✅ **Ad watched successfully!**\n"
            f"💰 **You earned:** +{reward} Rs\n"
            f"💳 **New balance:** {round(users[uid]['balance'], 1)} Rs"
        )
        bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "Extra ➡️")
def show_extra(message):
    uid = str(message.from_user.id)
    total_users = len(users) + 533
    total_paid = 29285.7
    
    text = (
        f"📊 **Bot Stats:**\n"
        f"👥 **Total Users:** {total_users}\n"
        f"💎 **Total Balance:** ₹{total_paid}\n\n"
        f"📢 **Official Links:**"
    )
    
    # 👇 SIRF SUPPORT BUTTON RAHEGA (Channel button hata diya)
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
        types.InlineKeyboardButton("💲 USDT TRC20", callback_data="pay_USDT"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="close_menu")
    )
    bot.edit_message_text("💳 **Choose Payment Method:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "close_menu")
def close_menu(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda message: message.text == "Refer and Earn 👥")
def refer_earn(message):
    uid = str(message.from_user.id)
    bot_name = bot.get_me().username
    link = f"https://t.me/{bot_name}?start={uid}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📩 Share Link", url=f"https://t.me/share/url?url={link}&text=Join%20Now!"))
    
    text = (f"👥 **Your Referral Link:**\n`{link}`\n\n💰 **Earnings:**\n• 40 Rs per referral")
    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)

# --- RUNNING ---
print("Bot Started...")
keep_alive()
bot.remove_webhook() # Purana conflict hatane ke liye
bot.infinity_polling()
