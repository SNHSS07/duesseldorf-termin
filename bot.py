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

            # Çerez penceresini ve arkasındaki perdeyi doğrudan DOM'dan kaldır
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

            # 2. Schritt 1: Fahrerlaubnisbehörde seçeneğine tıkla
            print("1. Adim: Fahrerlaubnisbehörde tiklaniyor...")
            page.locator("text=Fahrerlaubnisbehörde").first.click(force=True)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2500)

            # Tekrar olası perde/overlay varsa temizle
            page.evaluate("""
                () => {
                    const overlays = document.querySelectorAll('div[class*="cookie"], .modal-backdrop');
                    overlays.forEach(el => el.remove());
                }
            """)

            # 3. Schritt 2: Akordiyon başlığını aç
            print("2. Adim: Akordiyon basligi aciliyor...")
            page.locator("text=Umschreibung ausländische Fahrerlaubnis / Dienstfahrerlaubnis").first.click(force=True)
            page.wait_for_timeout(1500)

            # 4. "sonstige Staaten" satırının yanındaki "+" butonuna tıkla
            print("3. Adim: 'sonstige Staaten' yanindaki '+' butonuna tiklaniyor...")
            page.evaluate("""
                () => {
                    const allElements = Array.from(document.querySelectorAll('*'));
                    const targetText = allElements.find(el => el.children.length === 0 && el.textContent.includes('sonstige Staaten'));
                    if (targetText) {
                        const container = targetText.closest('tr') || targetText.closest('li') || targetText.parentElement.parentElement;
                        const plus = container.querySelector('button, input[type="button"], a, span, .btn');
                        if (plus) plus.click();
                    }
                }
            """)
            page.wait_for_timeout(1500)

            # 5. Açılan "Hinweis" modal penceresindeki "OK" butonuna bas
            print("4. Adim: Hinweis penceresindeki 'OK' butonuna tiklaniyor...")
            ok_btn = page.locator("button:has-text('OK'), a:has-text('OK')").first
            if ok_btn.is_visible():
                ok_btn.click(force=True)
                page.wait_for_timeout(1500)

            # 6. Schritt 2'nin altındaki ilk "Weiter" butonuna tıkla
            print("5. Adim: Ilk 'Weiter' butonuna basiliyor...")
            weiter_1 = page.locator("#WeiterButton, input[value='Weiter'], button:has-text('Weiter')").first
            weiter_1.click(force=True)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 7. Schritt 3 (Standortauswahl): İkinci "Weiter" butonuna tıkla
            print("6. Adim: Ikinci 'Weiter' butonuna basiliyor...")
            weiter_2 = page.locator("#WeiterButton, input[value='Weiter'], button:has-text('Weiter')").first
            weiter_2.click(force=True)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(4000)

            # 8. Schritt 4: Ekran görüntüsünü al
            screenshot_path = "ekran_kaniti.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print("7. Adim: Schritt 4 ekran goruntusu alindi.")

            # 9. Randevu Kontrolü
            body_text = page.locator("body").inner_text().lower()
            no_termin = "keine zeiten verfügbar" in body_text or "keine freien termine" in body_text
            slots = page.locator("a.ekol-suggest-button, .suggest-cell a, .calendar-day.available, td.buchbar a")

            if not no_termin and slots.count() > 0:
                print("Randevu bulundu! Alarm gonderiliyor...")
                caption = "🚨 DÜSSELDORF RANDEVU ALARMI! 🚨\nEhliyet için randevu açıldı! Hemen girin:\nhttps://termine.duesseldorf.de"
                send_telegram_photo(caption, screenshot_path)
            else:
                current_minute = datetime.utcnow().minute
                event_name = os.environ.get("GITHUB_EVENT_NAME", "")

                # Saat başı taramasıysa (0-7 dk) veya elle tetiklendiyse kanıt görselini yolla
                if current_minute <= 7 or event_name == "workflow_dispatch":
                    print("Saat basi kanit fotografi Telegram'a gonderiliyor...")
                    caption = "ℹ️ Saat Başı Durum Raporu:\nTarama aktif, şu an boş randevu yok (Schritt 4 kanıtı ektedir)."
                    send_telegram_photo(caption, screenshot_path)
                else:
                    print(f"5 dakikalik kontrol tamamlandi (Dakika: {current_minute}). Bos yer yok, sessiz mod.")

        except Exception as e:
            print(f"Hata detayi: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
