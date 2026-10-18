import asyncio
import os
from datetime import datetime

import pytz
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
TZ = pytz.timezone(os.getenv("TIMEZONE", "Asia/Tashkent"))
BASE_NAME = os.getenv("BASE_NAME", "Javohir")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Bot qaysi vaziyatni tushuntirishini shu yerda o'zgartiring
STATUS_TEXT = os.getenv(
    "STATUS_TEXT",
    "Hozir maktabdaman yoki bandman. Bo'sh bo'lsam, tez orada o'zim yozaman.",
)

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


# ---------- AI javob (Groq) ----------
async def ai_reply(user_text: str) -> str:
    if not GROQ_API_KEY:
        return STATUS_TEXT
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"Sen {BASE_NAME} nomidan avtomatik javob beruvchi yordamchisan. "
                                f"Holat: {STATUS_TEXT} "
                                "Qisqa (1-2 gap), samimiy, o'zbek tilida javob yoz. "
                                "Hech qachon shaxsiy ma'lumot (parol, kod, manzil) berma."
                            ),
                        },
                        {"role": "user", "content": user_text},
                    ],
                    "max_tokens": 120,
                    "temperature": 0.7,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("AI xato:", e, flush=True)
        return STATUS_TEXT


# ---------- Buyruqlar (/ bilan boshlangan) ----------
@client.on(events.NewMessage(pattern=r"^/", incoming=True))
async def komanda_handler(event):
    if not event.is_private:
        return
    text = event.raw_text.strip().lower()

    if text in ("/start", "/salom"):
        await event.reply(f"Salom! {STATUS_TEXT}")
    elif text == "/vaqt":
        now = datetime.now(TZ).strftime("%H:%M")
        await event.reply(f"Hozirgi vaqt: {now}")
    elif text == "/instagram":
        await event.reply("Instagram: @javoh1r_3102")
    elif text == "/yordam":
        await event.reply(
            "Buyruqlar:\n/salom - salomlashish\n/vaqt - joriy vaqt\n/instagram - Instagram havolam"
        )
    else:
        reply = await ai_reply(event.raw_text)
        await event.reply(reply)


# ---------- Oddiy xabarlarga AI javob ----------
@client.on(events.NewMessage(incoming=True, pattern=None))
async def xabar_handler(event):
    if not event.is_private:
        return
    if event.raw_text.startswith("/"):
        return  # buyruqlar yuqorida ishlanadi
    reply = await ai_reply(event.raw_text)
    await event.reply(reply)


# ---------- Profilda soat ----------
async def clock_loop():
    last = None
    while True:
        now = datetime.now(TZ).strftime("%H:%M")
        if now != last:
            try:
                await client(UpdateProfileRequest(first_name=f"{BASE_NAME} | {now}"))
                last = now
                print("Yangilandi:", now, flush=True)
            except Exception as e:
                print("Xato:", e, flush=True)
        await asyncio.sleep(20)


async def main():
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("SESSION_STRING yaroqsiz. gen_session.py ni qayta ishga tushiring.")
    print("Bot ishga tushdi", flush=True)
    asyncio.create_task(clock_loop())
    await client.run_until_disconnected()


asyncio.run(main())
