"""
Telegram kurulumunu test eder ve Chat ID'nizi bulmanıza yardımcı olur.
Çalıştır: python3 setup_telegram.py
"""

import os
import requests
from dotenv import load_dotenv

# .env dosyasından token'ı yükle (varsa)
load_dotenv()
env_token = os.getenv("TELEGRAM_BOT_TOKEN")

if env_token and "buraya" not in env_token:
    TOKEN = env_token
    print(f"✅ .env dosyasındaki token kullanılıyor: {TOKEN[:10]}...")
else:
    TOKEN = input("Telegram Bot Token'ınızı girin: ").strip()

print("\n1. Telegram'da botunuzu açın ve herhangi bir mesaj (örnek: 'merhaba') gönderin.")
input("   Gönderdikten sonra Enter'a basın...")

try:
    resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates").json()
    updates = resp.get("result", [])

    if not updates:
        print("\n⚠️  Güncelleme bulunamadı. Botunuza bir mesaj gönderdiniz mi?")
        print("   Not: Yeni bir mesaj yazıp tekrar deneyin.")
    else:
        # En son mesajdan chat ID al
        # Not: message veya edited_message olabilir
        last_item = updates[-1]
        msg_key = "message" if "message" in last_item else "edited_message"
        
        if msg_key in last_item:
            chat = last_item[msg_key]["chat"]
            chat_id = chat["id"]
            name = chat.get("first_name", "") + " " + chat.get("last_name", "")
            print(f"\n✅ Chat ID bulundu: {chat_id}")
            print(f"   İsim: {name.strip()}")
            print(f"\n.env dosyanıza şunu ekleyin:")
            print(f"   TELEGRAM_CHAT_ID={chat_id}")
        else:
            print("\n⚠️  Mesaj yapısı anlaşılamadı.")

except Exception as e:
    print(f"\n❌ Bir hata oluştu: {e}")
