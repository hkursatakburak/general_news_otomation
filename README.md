# 🛡️ Savunma Sanayii Haber Ajanı v2.0

![Defense Agent Banner](file:///Users/hamzakursatakburak/.gemini/antigravity/brain/c4366152-785a-4dc4-9eb2-88e10986e0c9/defense_agent_banner_1774053339023.png)

<p align="center">
  <img src="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHJqZ3R6Z3R6Z3R6Z3R6Z3R6Z3R6Z3R6Z3R6Z3R6Z3R6Z3R6Z3Amb3A9cw/3o7TKMGpxNfGZfS8qQ/giphy.gif" width="600" alt="AI Processing GIF">
</p>

> **Yapay Zeka Destekli, Semantik Filtrelemeli Otomatik Savunma Haberleri Takip Sistemi**

Bu proje, dünya çapındaki 15 seçkin savunma sanayii haber sitesini anlık olarak takip eder, Google News RSS üzerinden verileri çeker ve **Gemini AI** kullanarak haberlerin içeriğini analiz eder. Sadece "yeni ve gerçekten farklı" olan haberleri seçerek Telegram üzerinden size ulaştırır.

---

## ✨ Öne Çıkan Özellikler

- 🧠 **Semantik Filtreleme:** Sadece anahtar kelime değil, haberin *anlamını* anlar. Gemini Embedding modelleri ile cosine similarity karşılaştırması yaparak benzer haberleri eler.
- ⚡ **Gemini 2.0 Entegrasyonu:** Haber özetlerini en güncel Gemini modelleri ile hazırlar.
- 📱 **Telegram Bildirimleri:** Önemli haberleri anında cebinize ulaştırır.
- 🕒 **Otomatik Planlayıcı:** `scheduler.py` ile sistemi 7/24 otomatik çalışacak şekilde yapılandırabilirsiniz.
- 💾 **Akıllı Hafıza:** Gönderilen haberleri `sent_embeddings.json` dosyasında saklayarak 48 saat boyunca mükerrer gönderimleri engeller.

---

## 🚀 Çalışma Mantığı

![Logic Flow](file:///Users/hamzakursatakburak/.gemini/antigravity/brain/c4366152-785a-4dc4-9eb2-88e10986e0c9/defense_agent_logic_flow_1774053355568.png)

1. **Toplama:** 15 elite savunma sitesinden RSS beslemeleri çekilir.
2. **Analiz:** Her haber için Gemini Embedding üretilir.
3. **Karşılaştırma:** Mevcut hafızadaki haberlerle benzerlik skoru hesaplanır.
4. **Filtreleme:** Benzerlik eşiği (default: 0.85) altındaysa haber "yeni" kabul edilir.
5. **Gönderim:** Seçilen haberler Telegram kanalına/botuna iletilir.

---

## 🛠️ Kurulum

### 1. Gereksinimler
Sistemde Python 3.8+ yüklü olmalıdır.

```bash
pip install -r requirements.txt
```

### 2. Yapılandırma
`.env` dosyanızı oluşturun ve aşağıdaki bilgileri doldurun:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
GEMINI_API_KEY=your_gemini_api_key
```

### 3. Telegram Chat ID Bulma
Eğer Chat ID'nizi bilmiyorsanız yardımcı aracı kullanabilirsiniz:
```bash
python3 setup_telegram.py
```

---

## 🚦 Kullanım

Sistemi manuel olarak tetiklemek için:
```bash
python3 agent.py
```

Sistemi otomatik bir takvimde (7/24) çalıştırmak için:
```bash
python3 scheduler.py
```

---

## 📦 Teknoloji Yığını

- **Dil:** Python
- **AI:** Google Gemini (Generative AI & Embeddings)
- **Veri:** Requests & XML ETre
- **Zamanlama:** Schedule Library
- **Bildirim:** Telegram Bot API

---

## 📄 Lisans
Bu proje özel kullanım için geliştirilmiştir.

---
<p align="center">
  <i>Developed with ❤️ for Defense Intelligence</i>
</p>
