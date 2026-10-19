import asyncio
import os
from datetime import datetime
from collections import defaultdict, deque

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
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

STATUS_TEXT = os.getenv(
    "STATUS_TEXT",
    "Hozir maktabdaman yoki bandman, shuning uchun avtomatik yordamchi javob beryapti.",
)

CONTACT_INFO = (
    f"Telegram: @Javoh_123 (https://t.me/Javoh_123), Instagram: @javoh1r_3102"
)

SYSTEM_PROMPT = (
    f"Sen {BASE_NAME} ismli o'quvchining shaxsiy Telegram yordamchisisan. "
    f"{BASE_NAME} hozir band: {STATUS_TEXT} "
    f"{BASE_NAME}ning kontakt ma'lumotlari: {CONTACT_INFO}. "
    "Agar odam ijtimoiy tarmoq, Instagram, boshqa aloqa vositasi yoki shunga o'xshash narsani so'rasa "
    "(qanday so'zlar bilan yozishidan qat'i nazar), shu kontakt ma'lumotlarini bemalol ayt. "
    "Odamlar senga {name} nomidan yozishadi, sen uning o'rniga vaqtincha javob berasan. "
    "ENG MUHIM QOIDA: har bir xabarda AVVAL odam nimani so'rayotganini yoki nima kerakligini tushun, "
    "javobingni ANA SHUNGA qarab ber. Agar savol yoki maqsad aniq bo'lmasa, qisqa aniqlashtiruvchi savol ber "
    "(masalan 'Nima kerak edi?', 'Qaysi masalada yordam kerak?'). "
    "'Band/maktabda' ekanini HAR SAFAR, avtomatik ravishda aytma - buni faqat quyidagi hollarda ayt: "
    "- odam javobni darhol kutayotganini bildirsa (masalan 'tezroq javob ber', qo'ng'iroq so'rasa), "
    "- yoki savolga to'liq javob berish uchun albatta o'zi bilan gaplashish kerak bo'lsa. "
    "Oddiy savollarga (masalan tabriklash, umumiy savol, kichik so'rov) iloji boricha o'zing mazmunli javob ber, "
    "shart bo'lmasa 'band/maktabda' iborasini qo'shma. "
    "Javoblar qisqa (1-3 gap), tabiiy, do'stona, o'zbek tilida bo'lsin, har safar bir xil gapni takrorlama. "
    "Hech qachon parol, kod, SESSION_STRING yoki shaxsiy maxfiy ma'lumot berma. "
    "Suhbat tarixini hisobga olib javob ber, oldin so'ralgan narsani qaytadan so'rama."
)

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Har bir suhbat uchun oxirgi 10 ta xabarni saqlaymiz (xotirada, qayta ishga tushsa tozalanadi)
history = defaultdict(lambda: deque(maxlen=10))


async def ai_reply(chat_id: int, sender_name: str, user_text: str) -> str:
    if not GROQ_API_KEY:
        return STATUS_TEXT

    history[chat_id].append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": SYSTEM_PROMPT.replace("{name}", BASE_NAME)}]
    messages.extend(history[chat_id])

    try:
        import httpx
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.8,
                    "reasoning_effort": "low",
                },
            )
            print("Groq status:", resp.status_code, flush=True)
            print("Groq javob matni:", resp.text[:800], flush=True)
            data = resp.json()
            if resp.status_code != 200 or "choices" not in data:
                return STATUS_TEXT
            msg = data["choices"][0]["message"]
            reply = (msg.get("content") or "").strip()
            if not reply:
                # Ba'zan javob 'reasoning' ichida qolib ketadi yoki bo'sh chiqadi
                reply = (msg.get("reasoning") or "").strip()[:300] or STATUS_TEXT
            history[chat_id].append({"role": "assistant", "content": reply})
            return reply
    except Exception as e:
        print("AI xato:", repr(e), flush=True)
        return STATUS_TEXT


@client.on(events.NewMessage(incoming=True))
async def xabar_handler(event):
    if not event.is_private:
        return

    text = event.raw_text.strip()
    if not text or not text.startswith("/"):
        return  # faqat "/" bilan boshlangan xabarlarga javob beriladi

    low = text.lower()

    # Tayyor buyruqlar (AI chaqirmasdan tezkor javob)
    if low in ("/start", "/salom"):
        await event.reply(f"Salom! {STATUS_TEXT}")
        return
    if low == "/vaqt":
        now = datetime.now(TZ).strftime("%H:%M")
        await event.reply(f"Hozirgi vaqt: {now}")
        return
    if low in ("/instagram", "/insta", "/ig"):
        await event.reply("Instagram: @javoh1r_3102")
        return
    if low == "/yordam":
        await event.reply(
            "Buyruqlar:\n/salom - salomlashish\n/vaqt - joriy vaqt\n/instagram - Instagram havolam\n"
            "Boshqa har qanday xabarga avtomatik yordamchi javob beradi."
        )
        return

    sender = await event.get_sender()
    sender_name = getattr(sender, "first_name", None) or "Noma'lum"
    reply = await ai_reply(event.chat_id, sender_name, text)
    await event.reply(reply)


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
                print("Soat xato:", repr(e), flush=True)
        await asyncio.sleep(20)


async def main():
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("SESSION_STRING yaroqsiz. gen_session.py ni qayta ishga tushiring.")
    print("Bot ishga tushdi", flush=True)
    asyncio.create_task(clock_loop())
    await client.run_until_disconnected()


asyncio.run(main())
