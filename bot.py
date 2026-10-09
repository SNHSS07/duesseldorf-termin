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
            requests.post(url, data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": img}, timeout=30)
    except Exception as e:
        print(f"Gorsel gonderme hatasi: {e}")

def run():
    print("Düsseldorf randevu botu baslatiliyor...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        page = context.new_page()

        try:
            page.goto("https://termine.duesseldorf.de/", timeout=60000)
            page.wait_for_timeout(2000)

            # 1. Cerez temizligi
            page.evaluate("document.querySelectorAll('div[class*=\"cookie\"], .modal-backdrop').forEach(el => el.remove());")

            # 2. Adim 1
            page.locator("text=Fahrerlaubnisbehörde").first.click(force=True)
            page.wait_for_timeout(2500)

            # 3. Adim 2 - Akordiyon
            page.locator("text=Umschreibung ausländische Fahrerlaubnis / Dienstfahrerlaubnis").first.click(force=True)
            page.wait_for_timeout(1500)

            # 4. Artiya bas
            page.evaluate("""() => {
                const rows = Array.from(document.querySelectorAll('*'));
                const targetText = rows.find(el => el.children.length === 0 && el.textContent.includes('sonstige Staaten'));
                if (targetText) {
                    const row = targetText.closest('tr') || targetText.closest('li') || targetText.parentElement.parentElement;
                    const btns = Array.from(row.querySelectorAll('button, a, input[type="button"], div[role="button"]'));
                    if (btns.length > 0) btns[btns.length - 1].click();
                }
            }""")
            page.wait_for_timeout(2000)

            # 5. OK bas
            page.evaluate("""() => {
                const ok = Array.from(document.querySelectorAll('button, a')).find(b => b.innerText && b.innerText.includes('OK'));
                if (ok) ok.click();
            }""")
            page.wait_for_timeout(2000)

            # 6. 1. Weiter
            page.evaluate("""() => {
                const btn = document.querySelector('#WeiterButton') || Array.from(document.querySelectorAll('button, input')).find(b => b.value === 'Weiter' || b.innerText.includes('Weiter'));
                if (btn) { btn.removeAttribute('disabled'); btn.click(); }
            }""")
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 7. 2. Weiter
            page.evaluate("""() => {
                const btn = document.querySelector('#WeiterButton') || Array.from(document.querySelectorAll('button, input')).find(b => b.value === 'Weiter' || b.innerText.includes('Weiter'));
                if (btn) { btn.removeAttribute('disabled'); btn.click(); }
            }""")
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 8. Screenshot
            screenshot_path = "ekran.png"
            page.screenshot(path=screenshot_path, full_page=True)

            # 9. Kontrol
            text = page.locator("body").inner_text().lower()
            no_termin = "keine zeiten verfügbar" in text or "keine freien termine" in text
            slots = page.locator("a.ekol-suggest-button, .suggest-cell a, .calendar-day.available, td.buchbar a")

            if not no_termin and slots.count() > 0:
                send_telegram_photo("🚨 RANDEVU BULUNDU! 🚨\nhttps://termine.duesseldorf.de", screenshot_path)
            elif datetime.utcnow().minute <= 7 or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
                send_telegram_photo("ℹ️ Durum Raporu: Su an bos randevu yok.", screenshot_path)

        except Exception as e:
            print(f"Hata: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
