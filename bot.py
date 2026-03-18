import asyncio
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI
import google.generativeai as genai

# ================= 🔐 KEYS =================
TELEGRAM_TOKEN = "8281549367:AAGdiMosdtc5naBe9ohOqsp0LitmmeX6OVc"
OPENAI_API_KEY = "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"
GEMINI_API_KEY = "AIzaSyDYH56baqfawUdgz1gnoB5cZNT1RCWTw7c"

# ================= 🤖 SETUP =================
client = OpenAI(api_key=OPENAI_API_KEY)

genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-pro")

# ================= 💾 DATABASE =================
conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS chats (
    user_id INTEGER,
    role TEXT,
    message TEXT
)
""")

def save_message(user_id, role, message):
    cursor.execute("INSERT INTO chats VALUES (?, ?, ?)", (user_id, role, message))
    conn.commit()

def get_history(user_id):
    cursor.execute("SELECT role, message FROM chats WHERE user_id=?", (user_id,))
    return [{"role": r, "content": m} for r, m in cursor.fetchall()]

# ================= 🧠 STATE =================
user_modes = {}        # gpt / gemini / auto
user_personality = {}  # coder / hacker / friendly

# ================= 🎭 PERSONALITIES =================
def get_system_prompt(mode):
    prompts = {
        "coder": "You are a professional coding assistant. Give clean, efficient code.",
        "hacker": "You are a cybersecurity expert. Think like a penetration tester.",
        "friendly": "You are a helpful and friendly AI assistant."
    }
    return prompts.get(mode, prompts["friendly"])

# ================= 🤖 AI FUNCTIONS =================

def ask_gpt(user_id, text):
    try:
        history = get_history(user_id)
        personality = user_personality.get(user_id, "friendly")

        messages = [{"role": "system", "content": get_system_prompt(personality)}]
        messages += history[-10:]  # last 10 messages
        messages.append({"role": "user", "content": text})

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=messages
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"GPT Error: {e}"


def ask_gemini(user_id, text):
    try:
        chat = gemini_model.start_chat(history=[])
        response = chat.send_message(text)
        return response.text
    except Exception as e:
        return f"Gemini Error: {e}"


def smart_ai(user_id, text):
    mode = user_modes.get(user_id, "auto")

    if mode == "gpt":
        return ask_gpt(user_id, text)
    elif mode == "gemini":
        return ask_gemini(user_id, text)
    else:
        # AUTO MODE (smart routing)
        if "code" in text.lower() or "python" in text.lower():
            return ask_gpt(user_id, text)
        else:
            return ask_gemini(user_id, text)

# ================= 🖼️ IMAGE =================
def generate_image(prompt):
    try:
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )
        return result.data[0].url
    except Exception as e:
        return f"Image Error: {e}"

# ================= 🚀 COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 ULTRA REVERSE AI ONLINE\n\n"
        "Commands:\n"
        "/mode gpt | gemini | auto\n"
        "/personality coder | hacker | friendly\n"
        "/image prompt\n"
        "/reset\n\n"
        "Just send a message to chat!"
    )


async def mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: /mode gpt OR gemini OR auto")
        return

    m = context.args[0].lower()

    if m in ["gpt", "gemini", "auto"]:
        user_modes[user_id] = m
        await update.message.reply_text(f"✅ Mode set to {m}")
    else:
        await update.message.reply_text("❌ Invalid mode")


async def personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: /personality coder|hacker|friendly")
        return

    p = context.args[0].lower()

    if p in ["coder", "hacker", "friendly"]:
        user_personality[user_id] = p
        await update.message.reply_text(f"🎭 Personality set to {p}")
    else:
        await update.message.reply_text("❌ Invalid personality")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cursor.execute("DELETE FROM chats WHERE user_id=?", (user_id,))
    conn.commit()

    await update.message.reply_text("🧠 Memory cleared!")


async def image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args).strip()

    if not prompt:
        await update.message.reply_text("Usage: /image prompt")
        return

    await update.message.reply_text("🎨 Generating image...")

    img = await asyncio.to_thread(generate_image, prompt)

    await update.message.reply_text(img)

# ================= 💬 CHAT =================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    save_message(user_id, "user", text)

    await update.message.reply_text("🤖 Thinking...")

    reply = await asyncio.to_thread(smart_ai, user_id, text)

    save_message(user_id, "assistant", reply)

    await update.message.reply_text(reply)

# ================= ▶️ RUN =================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("mode", mode))
app.add_handler(CommandHandler("personality", personality))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CommandHandler("image", image))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🔥 ULTRA PRO REVERSE AI RUNNING...")

app.run_polling()