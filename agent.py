"""
Savunma Sanayii Haber Ajani — v2.0 (Semantik Filtre)
=====================================================
Calisma mantigi:
  1. 15 elite savunma sitesini Google News RSS ile tara (son 48 saat)
    2. Her haber icin Gemini embedding modeli ile anlam vektoru uret
  3. Daha once gonderilenlerle cosine similarity karsilastir
  4. Esik altindaysa (gercekten yeni ve farkli) → Gemini ile Turkce ozet
  5. Telegram'a gonder, embedding'i kaydet

Anahtar kelime filtresi YOKTUR. Icerik benzerligine gore filtreleme yapilir.
"""

import os
import json
import math
import time
import requests
import xml.etree.ElementTree as ET
from google import genai
from google.genai import types
from google.api_core.exceptions import ResourceExhausted
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Yapilandirma
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID     = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY       = os.environ["GEMINI_API_KEY"]

MEMORY_FILE          = Path("sent_embeddings.json")  # semantik hafiza dosyasi
USE_SEMANTIC_FILTER  = False  # v2.1: URL bazli kesin deduplikasyon aktif
SIMILARITY_THRESHOLD = 0.85   # 0.0-1.0; dusurursen daha az haber, yukseltirsen daha fazla
MEMORY_TTL_HOURS     = 48     # bu sureden eski kayitlar silinir
MAX_MEMORY_SIZE      = 300    # dosyada tutulacak maksimum kayit sayisi
MAX_ARTICLES_PER_RUN = 40     # tek turda islenecek maksimum haber sayisi
EMBEDDING_SLEEP      = 4      # embedding istekleri arasi bekleme (saniye)
SUMMARY_SLEEP        = 20     # ozetleme istekleri arasi bekleme (saniye)
EMBEDDING_MODELS     = [
    "models/gemini-embedding-001",
    "models/gemini-embedding-2-preview",
]  # Kullanilabilirlik durumuna gore fallback sirasi

# Takip edilen 15 elite savunma sitesi
DEFENSE_SITES = [
    "janes.com",
    "defensenews.com",
    "breakingdefense.com",
    "twz.com",
    "navalnews.com",
    "ukdefencejournal.org.uk",
    "opex360.com",
    "defence24.com",
    "edrmagazine.eu",
    "esut.de",
    "thediplomat.com",
    "scmp.com",
    "idrw.org",
    "israeldefense.co.il",
    "tass.com",
]

# Google News RSS icin site gruplari (URL uzunluk limiti nedeniyle ucere bolundu)
SITE_GROUPS = [
    DEFENSE_SITES[0:5],
    DEFENSE_SITES[5:10],
    DEFENSE_SITES[10:15],
]


# ---------------------------------------------------------------------------
# Hafiza: Embedding kaydet / yukle
# ---------------------------------------------------------------------------

def load_memory() -> list[dict]:
    """
    Kayitli embedding'leri yukler ve MEMORY_TTL_HOURS'tan eski olanlari atar.
    Her kayit: { "url": str, "embedding": list[float], "timestamp": str (ISO) }
    """
    if not MEMORY_FILE.exists():
        return []

    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        records = data.get("embeddings", [])
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MEMORY_TTL_HOURS)
    fresh = []
    for r in records:
        try:
            ts = datetime.fromisoformat(r["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts > cutoff:
                fresh.append(r)
        except Exception:
            pass  # bozuk kayitlari sil

    print(f"[Hafiza] {len(records)} kayitten {len(fresh)} tanesi taze (son {MEMORY_TTL_HOURS} saat).")
    return fresh


def save_memory(records: list[dict]) -> None:
    trimmed = records[-MAX_MEMORY_SIZE:]
    MEMORY_FILE.write_text(
        json.dumps({"embeddings": trimmed}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[Hafiza] {len(trimmed)} kayit kaydedildi.")


def build_sent_urls(records: list[dict]) -> set[str]:
    return {r.get("url", "") for r in records if r.get("url")}


def append_sent_articles_to_memory(memory: list[dict], sent_articles: list[dict]) -> list[dict]:
    updated      = list(memory)
    existing_urls = build_sent_urls(updated)

    for article in sent_articles:
        url = article.get("url", "")
        if not url or url in existing_urls:
            continue

        updated.append(
            {
                "url":       url,
                "embedding": article.get("_embedding", []),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        existing_urls.add(url)

    return updated


# ---------------------------------------------------------------------------
# Cosine Similarity
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def is_duplicate(embedding: list[float], memory: list[dict]) -> tuple[bool, float]:
    """
    Verilen embedding hafizadaki herhangi bir kayitle SIMILARITY_THRESHOLD
    uzerinde benzerlik gosteriyorsa (True, max_score) doner.
    """
    max_score = 0.0
    for record in memory:
        score = cosine_similarity(embedding, record["embedding"])
        if score > max_score:
            max_score = score
        if score >= SIMILARITY_THRESHOLD:
            return True, score
    return False, max_score


# ---------------------------------------------------------------------------
# Embedding uretici
# ---------------------------------------------------------------------------

def get_embedding(text: str, retries: int = 2) -> list[float] | None:
    """
    Gemini embedding modeli ile semantik vektor uretir.
    Kota asiminda EMBEDDING_SLEEP * 8 saniye bekleyip yeniden dener.
    """
    for attempt in range(retries + 1):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            for model_name in EMBEDDING_MODELS:
                try:
                    result = client.models.embed_content(
                        model=model_name,
                        contents=text,
                        config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
                    )
                    return result.embeddings[0].values
                except Exception as inner_e:
                    msg = str(inner_e)
                    # Model not found durumunda sonraki embedding modelini dene.
                    if "NOT_FOUND" in msg or "not found" in msg.lower():
                        print(f"[Embedding] Model desteklenmiyor: {model_name}, fallback deneniyor...")
                        continue
                    raise
        except ResourceExhausted:
            wait = EMBEDDING_SLEEP * 8
            print(f"[Embedding] 429 Kota asimi, {wait}s bekleniyor... (deneme {attempt+1})")
            time.sleep(wait)
        except Exception as e:
            print(f"[Embedding] Hata: {e}")
            return None
    return None


# ---------------------------------------------------------------------------
# Haber toplama: Google News RSS
# ---------------------------------------------------------------------------

def fetch_rss_group(sites: list[str]) -> list[dict]:
    """
    Verilen site listesi icin Google News RSS'ten son 48 saatin haberlerini ceker.
    """
    site_query = " OR ".join(f"site:{s}" for s in sites)
    query      = f"({site_query}) when:2d"
    encoded    = requests.utils.quote(query)
    url        = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"

    try:
        resp = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DefenseBot/2.0)"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        print(f"[RSS] Grup cekilemedi: {e}")
        return []

    results = []
    for item in root.findall(".//item")[:10]:
        title = item.findtext("title", "").strip()
        link  = item.findtext("link", "").strip()
        desc  = item.findtext("description", "").strip()
        if link:
            results.append({"title": title, "url": link, "snippet": desc})
    return results


def collect_articles() -> list[dict]:
    """Tum site gruplarini tara, URL bazli tekrarlari ele, toplu liste dondur."""
    all_articles = []
    seen_urls    = set()

    for i, group in enumerate(SITE_GROUPS):
        print(f"[RSS] Grup {i+1}/{len(SITE_GROUPS)} taraniyor...")
        articles = fetch_rss_group(group)
        for a in articles:
            url = a.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_articles.append(a)
        time.sleep(2)  # RSS istekleri arasi nezaket beklemesi

    print(f"[Toplama] {len(all_articles)} benzersiz haber bulundu.")
    return all_articles


# ---------------------------------------------------------------------------
# Semantik filtre
# ---------------------------------------------------------------------------

def filter_unique(articles: list[dict], memory: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Her makaleyi embed eder, hafizayla karsilastirir.
      - Benzer (duplicate) → atar
      - Farkli (unique)    → kabul eder, ayni tur icinde de duplicate kontrolu yapilir

    Doner: (kabul_edilenler, guncellenmis_memory)
    """
    unique   = []
    live_mem = list(memory)

    for i, article in enumerate(articles):
        title   = article.get("title", "")
        snippet = article.get("snippet", "")
        text    = f"{title}. {snippet}"[:500]

        print(f"[Filtre] ({i+1}/{len(articles)}) '{title[:55]}'")

        embedding = get_embedding(text)
        if embedding is None:
            print("  → Embedding alinamadi, atlaniyor.")
            time.sleep(EMBEDDING_SLEEP)
            continue

        duplicate, score = is_duplicate(embedding, live_mem)

        if duplicate:
            print(f"  → Benzer haber (skor {score:.3f}), atlaniyor.")
        else:
            print(f"  → Yeni ve farkli (max skor {score:.3f}), kabul edildi.")
            unique.append({**article, "_embedding": embedding})
            live_mem.append({
                "url":       article.get("url", ""),
                "embedding": embedding,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        time.sleep(EMBEDDING_SLEEP)

    print(f"[Filtre] {len(articles)} haberden {len(unique)} benzersiz secildi.")
    return unique, live_mem


# ---------------------------------------------------------------------------
# Gemini ile Turkce ozet
# ---------------------------------------------------------------------------

def summarize_articles(articles: list[dict]) -> list[dict]:
    """
    Her makaleyi Gemini'ye gondererek Turkce 2-3 cumlelik ozet uretir.
    Anahtar kelime filtresi yoktur; kabul edilen tum haberler ozetlenir.
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    summaries = []

    for i, article in enumerate(articles):
        title   = article.get("title", "")
        url     = article.get("url", "")
        snippet = str(article.get("snippet", ""))[:400]

        prompt = f"""Asagidaki savunma sanayii haberini oku.
2-3 cumlelik, sade ve net Turkce bir ozet yaz.
Onem derecesini YUKSEK / ORTA / DUSUK olarak belirle.
YALNIZCA JSON dondur, baska hicbir sey yazma.

{{
  "title": "{title}",
  "url": "{url}",
  "summary": "<2-3 cumle Turkce ozet>",
  "priority": "YUKSEK|ORTA|DUSUK"
}}

Haber:
Baslik : {title}
Icerik : {snippet}
"""
        retries = 2
        for attempt in range(retries + 1):
            try:
                print(f"[Ozet] ({i+1}/{len(articles)}) '{title[:50]}'")
                resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                raw  = resp.text.strip()

                # Kod blogu temizligi
                if "```" in raw:
                    parts = raw.split("```")
                    raw = parts[1] if len(parts) >= 3 else raw
                    if raw.lower().startswith("json"):
                        raw = raw[4:]
                raw = raw.strip()

                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "summary" in parsed:
                    parsed["title"] = title
                    parsed["url"]   = url
                    summaries.append(parsed)
                    break # Basarili, donguden cik
                else:
                    print("  → Beklenmedik JSON yapisi, atlaniyor.")
                    break

            except ResourceExhausted:
                wait = 120
                if attempt < retries:
                    print(f"  → 429 Kota asimi, {wait}s bekleniyor... (deneme {attempt+1})")
                    time.sleep(wait)
                else:
                    print("  → 429 Kota asimi, deneme hakki bitti. Atlaniyor.")
            except json.JSONDecodeError:
                print("  → JSON parse hatasi, atlaniyor.")
                break
            except Exception as e:
                print(f"  → Beklenmedik hata: {e}")
                break

        time.sleep(SUMMARY_SLEEP)

    print(f"[Ozet] {len(summaries)} haber ozetlendi.")
    return summaries


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id":                  TELEGRAM_CHAT_ID,
                "text":                     text,
                "parse_mode":               "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[Telegram] Uyari: HTTP {resp.status_code} - {resp.text}")
            return False
        return True
    except Exception as e:
        print(f"[Telegram] Gonderim hatasi: {e}")
        return False


def build_message(articles: list[dict], slot: str) -> str:
    now    = datetime.now().strftime("%d.%m.%Y %H:%M")
    header = (
        f"🛡️ <b>SAVUNMA HABERLERİ</b>\n"
        f"📅 {now} · {slot}\n"
        f"{'─' * 28}\n\n"
    )

    if not articles:
        return header + "✅ Yeni ve farkli haber bulunamadi."
    blocks    = []

    for a in articles:
        block    = (
            f"• <b>{a.get('title', 'Basliksiz')}</b>\n"
            f"🔗 <a href='{a.get('url', '#')}'>Habere git</a>"
        )
        blocks.append(block)

    return header + "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Ana fonksiyon
# ---------------------------------------------------------------------------

def run_agent(slot: str = "Manuel") -> None:
    print(f"\n{'='*55}")
    print(f"[{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}] Ajan basladi — {slot}")
    print(f"{'='*55}")


    # 1. Semantik hafizayi yukle
    memory = load_memory()
    sent_urls = build_sent_urls(memory)
    print(f"[Hafiza] URL hafizasi: {len(sent_urls)} kayit.")

    # 2. Haberleri topla
    articles = collect_articles()
    if not articles:
        print("[Ajan] Hic haber bulunamadi, cikiliyor.")
        return

    # 3. URL bazli kesin deduplikasyon (embedding'den once)
    candidate_articles = []
    for article in articles[:MAX_ARTICLES_PER_RUN]:
        url = article.get("url", "")
        if not url:
            continue
        if url in sent_urls:
            print(f"[Filtre][URL] Daha once gonderildi, atlaniyor: {url}")
            continue
        candidate_articles.append(article)

    if not candidate_articles:
        send_telegram(
            f"🛡️ <b>SAVUNMA HABERLERİ</b>\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')} · {slot}\n\n"
            f"✅ Yeni ve farkli haber bulunamadi, tum icerikler daha once iletildi."
        )
        save_memory(memory)
        return

    if USE_SEMANTIC_FILTER:
        unique_articles, _ = filter_unique(candidate_articles, memory)
    else:
        unique_articles = candidate_articles

    # 4. Ozetleme olmadan dogrudan baslik + link gonder
    news_to_send = unique_articles[:30]
    sent_articles = []

    # 5. 5'er 5'er Telegram'a gonder
    for i in range(0, len(news_to_send), 5):
        chunk = news_to_send[i : i + 5]
        msg   = build_message(chunk, slot)
        sent_ok = send_telegram(msg)
        if sent_ok:
            sent_articles.extend(chunk)
        if i + 5 < len(news_to_send):
            time.sleep(2)

    # 6. Hafizayi kaydet
    updated_memory = append_sent_articles_to_memory(memory, sent_articles)
    save_memory(updated_memory)

    print(f"\n[Ajan] Tamamlandi. {len(news_to_send)} haber baslik+link olarak iletildi.")
    print(f"{'='*55}\n")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_agent(slot="Manuel Test")
