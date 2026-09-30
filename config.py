# =====================================================================
# CONFIG
# =====================================================================
import os

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID_PREMATCH')

MIN_SCORE = int(os.getenv('MIN_SCORE', '8'))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '3600'))
HOURS_BEFORE = int(os.getenv('HOURS_BEFORE', '24'))

if not BOT_TOKEN or not CHAT_ID:
    print("❌ BOT_TOKEN или CHAT_ID_PREMATCH не заданы", flush=True)
    exit(1)

# Лиги (названия как в Understat)
LEAGUES = {
    "АПЛ": {
        "understat": "АПЛ",
        "1xlite_id": 88637,
    },
    "Бундеслига": {
        "understat": "Бундеслига",
        "1xlite_id": 96463,
    },
    "Ла Лига": {
        "understat": "Ла Лига",
        "1xlite_id": 127733,
    },
    "Серия А": {
        "understat": "Серия А",
        "1xlite_id": 110163,
    },
    "Лига 1": {
        "understat": "Лига 1",
        "1xlite_id": 12821,
    },
    "РПЛ": {
        "understat": "РПЛ",
        "1xlite_id": 225733,
    },
}

BASE_URL = "https://1xlite-7936.pro"
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Referer": f"{BASE_URL}/ru/live",
    "Origin": BASE_URL,
    "x-requested-with": "XMLHttpRequest",
    "x-app-n": "__BETTING_APP__",
    "x-svc-source": "__BETTING_APP__",
}