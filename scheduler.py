"""
Zamanlayıcı: agent.py'yi 09:00, 15:00 ve 22:00'de otomatik çalıştırır.
Sürekli çalışır durumda kalmalıdır.
Çalıştır: python3 scheduler.py
"""

import schedule
import time
import os
from agent import run_agent
from datetime import datetime

def job_morning():
    print(f"[{datetime.now()}] Sabah raporu başlıyor...")
    run_agent(slot="Sabah 09:00")

def job_afternoon():
    print(f"[{datetime.now()}] Öğleden sonra raporu başlıyor...")
    run_agent(slot="Öğleden Sonra 15:00")

def job_evening():
    print(f"[{datetime.now()}] Akşam raporu başlıyor...")
    run_agent(slot="Akşam 22:00")

# Görev zamanlarını ayarla
# Not: Railway sunucusu UTC kullanıyorsa saatleri ona göre ayarlamanız gerekebilir.
# Türkiye saati (UTC+3) için Railway'de TZ=Europe/Istanbul değişkenini eklemeyi unutmayın.
schedule.every().day.at("09:00").do(job_morning)
schedule.every().day.at("15:00").do(job_afternoon)
schedule.every().day.at("22:00").do(job_evening)

print("⏰ Zamanlayıcı başlatıldı. Haber botu çevrimiçi.")
print("   → Beklenen çalışma saatleri: 09:00, 15:00, 22:00")
print("   (Durdurmak için Ctrl+C)\n")

# İlk çalıştırma (Opsiyonel: Başlatıldığında hemen bir kontrol yapması için)
# run_agent(slot="Sistem Başlangıcı")

while True:
    schedule.run_pending()
    time.sleep(60) # Her dakika kontrol et
