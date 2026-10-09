import os
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_photo(caption, image_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        with open(image_path, "rb") as img:
            files = {"photo": img}
            data = {"chat_id": CHAT_ID, "caption": caption}
            res = requests.post(url, data=data, files=files, timeout=30)
            print("Telegram cevabi:", res.status_code)
    except Exception as e:
        print(f"Gorsel gonderme hatasi: {e}")

def run():
    print("Düsseldorf randevu botu baslatiliyor...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 1000}
        )
        page = context.new_page()

        try:
            # 1. Ana sayfaya git
            page.goto("https://termine.duesseldorf.de/", timeout=60000)
            page.wait_for_timeout(3000)

            # Çerez engelini kaldır
            page.evaluate("""
                () => {
                    const cookies = document.querySelectorAll('div[class*="cookie"], div[id*="cookie"], .modal-backdrop');
                    cookies.forEach(el => el.remove());
                    const accept = Array.from(document.querySelectorAll('button, a')).find(b => b.innerText && b.innerText.includes('Akzeptieren'));
                    if (accept) accept.click();
                }
            """)
            page.wait_for_timeout(1000)

            # 2. Schritt 1: Fahrerlaubnisbehörde seç
            print("1. Adim: Fahrerlaubnisbehörde seciliyor...")
            page.locator("text=Fahrerlaubnisbehörde").first.click(force=True)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2500)

            # 3. Schritt 2: Akordiyon başlığını aç
            print("2. Adim: Akordiyon basligi aciliyor...")
            page.locator("text=Umschreibung ausländische Fahrerlaubnis / Dienstfahrerlaubnis").first.click(force=True)
            page.wait_for_timeout(1500)

            # 4. 'sonstige Staaten' satırını bul ve o satırdaki mavi '+' butonuna FİZİKSEL tıkla
            print("3. Adim: 'sonstige Staaten' satirindaki buton tiklaniyor...")
            # Satırı buluyoruz
            target_row = page.locator("tr, div").filter(has_text="Umschreibung ausländischer Führerschein (sonstige Staaten)").last
            
            # Bu satırın içindeki tüm buton benzeri elemanlardan SONUNCUSU (sağdaki mavi + butonu)
            plus_btn = target_row.locator("button, a, input[type='button'], div[role='button']").last
            plus_btn.scroll_into_view_if_needed()
            plus_btn.click(force=True)
            print("Butona basildi.")
            page.wait_for_timeout(2000)

            # 5. Açılan 'Hinweis' modalındaki 'OK' butonuna bas
            print("4. Adim: Modal OK butonu bekleniyor...")
            ok_btn = page.locator("button:has-text('OK'), a:has-text('OK')").first
            ok_btn.wait_for(state="visible", timeout=5000)
            ok_btn.click(force=True)
            print("Modal OK tiklandi.")
            page.wait_for_timeout(1500)

            # 6. Schritt 2 altındaki ilk 'Weiter' butonuna tıkla
            print("5. Adim: 1. Weiter tiklaniyor...")
            weiter_1 = page.locator("#WeiterButton, input[value='Weiter'], button:has-text('Weiter')").first
            weiter_1.wait_for(state="visible", timeout=5000)
            weiter_1.click(force=True)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 7. Schritt 3 (Standortauswahl): İkinci 'Weiter' butonuna tıkla
            print("6. Adim: 2. Weiter tiklaniyor...")
            weiter_2 = page.locator("#WeiterButton, input[value='Weiter'], button:has-text('Weiter')").first
            weiter_2.wait_for(state="visible", timeout=5000)
            weiter_2.click(force=True)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(4000)

            # 8. Schritt 4: Ekran görüntüsünü al
            screenshot_path = "ekran_kaniti.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print("7. Adim: Schritt 4 ekran goruntusu alindi.")

            # 9. Randevu kontrolü
            body_text = page.locator("body").inner_text().lower()
            no_termin = "keine zeiten verfügbar" in body_text or "keine freien termine" in body_text
            slots = page.locator("a.ekol-suggest-button, .suggest-cell a, .calendar-day.available, td.buchbar a")

            if not no_termin and slots.count() > 0:
                print("Randevu yakalandi!")
                caption = "🚨 DÜSSELDORF RANDEVU ALARMI! 🚨\nEhliyet için randevu açıldı! Hemen girin:\nhttps://termine.duesseldorf.de"
                send_telegram_photo(caption, screenshot_path)
            else:
                current_minute = datetime.utcnow().minute
                event_name = os.environ.get("GITHUB_EVENT_NAME", "")

                if current_minute <= 7 or event_name == "workflow_dispatch":
                    print("Saat basi raporu gonderiliyor...")
                    caption = "ℹ️ Saat Başı Durum Raporu:\nTarama aktif, şu an boş randevu yok (Schritt 4 kanıtı ektedir)."
                    send_telegram_photo(caption, screenshot_path)
                else:
                    print(f"5 dakikalık sessiz kontrol tamamlandi (Dakika: {current_minute}). Boş yer yok.")

        except Exception as e:
            print(f"Hata detayi: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
