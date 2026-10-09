import os
import requests
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Mesaj iletilemedi: {e}")

def run():
    print("Düsseldorf randevu sayfası kontrol ediliyor...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto("https://termine.duesseldorf.de/suggest", timeout=60000)
            page.wait_for_timeout(4000)
            
            content = page.content().lower()
            
            # Ekranda randevu olmadığını belirten ifadeler
            no_termin_patterns = [
                "keine zeiten verfügbar",
                "keine freien termine",
                "im moment sind leider keine freien termine verfügbar"
            ]
            
            is_empty = any(p in content for p in no_termin_patterns)
            
            if is_empty:
                print("Şu an boş randevu bulunmuyor.")
            else:
                msg = (
                    "🚨 DÜSSELDORF RANDEVU ALARMI! 🚨\n\n"
                    "Ehliyet denkliği için randevu slotu açılmış olabilir!\n\n"
                    "Hemen giriş yapıp kontrol edin:\n"
                    "https://termine.duesseldorf.de"
                )
                print("Randevu bulundu veya durum değişti! Telegram'a gönderiliyor...")
                send_telegram(msg)
                
        except Exception as e:
            print(f"Hata meydana geldi: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
