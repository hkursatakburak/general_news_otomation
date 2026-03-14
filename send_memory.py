"""
Hafizadaki haberleri Telegram'a gonder.
Kullanim: python send_memory.py
"""

import json
import requests
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
MEMORY_FILE        = Path("sent_embeddings.json")


def send_telegram(text: str) -> None:
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id":                  TELEGRAM_CHAT_ID,
            "text":                     text,
            "parse_mode":               "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )


def main():
    if not MEMORY_FILE.exists():
        print("sent_embeddings.json bulunamadi.")
        return

    data    = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    records = data.get("embeddings", [])

    if not records:
        print("Hafizada kayitli haber yok.")
        return

    print(f"{len(records)} kayit bulundu, Telegram'a gonderiliyor...")

    # 20'ser URL'lik mesajlara bol (Telegram 4096 karakter limiti)
    chunk_size = 20
    for chunk_i, i in enumerate(range(0, len(records), chunk_size), start=1):
        chunk = records[i : i + chunk_size]
        lines = [f"📋 <b>Hafiza Raporu ({chunk_i}. Parca — {len(records)} toplam kayit)</b>\n"]

        for j, r in enumerate(chunk, start=i + 1):
            url       = r.get("url", "—")
            timestamp = r.get("timestamp", "")[:16].replace("T", " ")
            lines.append(f"{j}. <a href='{url}'>{url[:60]}...</a>\n    🕐 {timestamp}")

        send_telegram("\n".join(lines))
        print(f"  Parca {chunk_i} gonderildi.")

    print("Tamamlandi.")


if __name__ == "__main__":
    main()
