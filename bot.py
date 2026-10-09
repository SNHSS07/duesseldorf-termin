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
            print("Telegram yaniti:", res.status_code)
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
                    const cookieElements = document.querySelectorAll('div[class*="cookie"], div[id*="cookie"], .modal-backdrop');
                    cookieElements.forEach(el => el.remove());
                    const btns = Array.from(document.querySelectorAll('button, a'));
                    const accept = btns.find(b => b.textContent && b.textContent.includes('Akzeptieren'));
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

            # 4. 'sonstige Staaten' satırındaki mavi '+' butonuna fiziksel tıkla
            print("3. Adim: 'sonstige Staaten' '+' butonuna basiliyor...")
            # İlgili satırı bulup içindeki son tıklanabilir butonu/linki tetikle
            target_row = page.locator("div, tr").filter(has_text="sonstige Staaten").last
            # Mavi artı butonu bu satırın içindeki '+' içeren veya ekle sınıfı olan son elemandır
            plus_btn = target_row.locator("a, button, span, div").filter(has_text="+").last
            plus_btn.click(force=True)
            page.wait_for_timeout(2000)

            # 5. Açılan 'Hinweis' modal penceresindeki 'OK' butonuna bas
            print("4. Adim: Pop-up 'OK' butonuna basiliyor...")
            ok_btn = page.locator("button:has-text('OK'), a:has-text('OK')").first
            if ok_btn.is_visible():
                ok_btn.click(force=True)
                page.wait_for_timeout(1500)

            # 6. Schritt 2 altındaki ilk 'Weiter' butonuna bas
            print("5. Adim: 1. Weiter butonuna basiliyor...")
            weiter_1 = page.locator("#WeiterButton, input[value='Weiter'], button:has-text('Weiter')").first
            weiter_1.click(force=True)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 7. Schritt 3: İkinci 'Weiter' butonuna bas
            print("6. Adim: 2. Weiter butonuna basiliyor...")
            weiter_2 = page.locator("#WeiterButton, input[value='Weiter'], button:has-text('Weiter')").first
            weiter_2.click(force=True)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(4000)

            # 8. Schritt 4: Ekran görüntüsünü al
            screenshot_path = "ekran_kaniti.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print("7. Adim: Ekran goruntusu kaydedildi.")

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
                    print("Saat basi kanit fotografi gonderiliyor...")
                    caption = "ℹ️ Saat Başı Durum Raporu:\nTarama aktif, şu an boş randevu yok (Schritt 4 kanıtı ektedir)."
                    send_telegram_photo(caption, screenshot_path)
                else:
                    print(f"5 dakikalık periyodik kontrol tamamlandi (Dakika: {current_minute}). Bos yer yok.")

        except Exception as e:
            print(f"Hata detayi: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
