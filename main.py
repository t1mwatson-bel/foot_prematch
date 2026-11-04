import time
import threading
from curl_cffi import requests
import web

def test_sofascore():
    print("🧪 ТЕСТ SOFASCORE", flush=True)
    url = "https://www.sofascore.com/api/v1/sport/football/scheduled-events/2026-11-04"
    headers = {
        "Accept": "*/*",
        "Accept-Language": "ru,en;q=0.9",
        "Referer": "https://www.sofascore.com/",
        "x-requested-with": "5a80a2",
    }
    try:
        r = requests.get(url, headers=headers, impersonate="chrome", timeout=15)
        print(f"🔎 HTTP: {r.status_code}", flush=True)
        if r.status_code == 200:
            data = r.json()
            events = data.get("events", [])
            print(f"✅ Найдено матчей: {len(events)}", flush=True)
            for ev in events[:5]:
                home = ev.get("homeTeam", {}).get("name", "?")
                away = ev.get("awayTeam", {}).get("name", "?")
                print(f"   {home} — {away}", flush=True)
        else:
            print(f"❌ Ошибка: {r.text[:300]}", flush=True)
    except Exception as e:
        print(f"❌ Исключение: {e}", flush=True)

def run_web():
    try:
        web.app.run(host="0.0.0.0", port=3000, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"❌ Ошибка запуска сайта: {e}", flush=True)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    test_sofascore()
    print("💤 Тест завершен. Спим 5 минут...", flush=True)
    while True:
        time.sleep(300)
