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
            requests.post(url, data=data, files=files, timeout=25)
    except Exception as e:
        print(f"Görsel gönderme hatası: {e}")

def run():
    print("Düsseldorf randevu botu başlatılıyor...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            # 1. Ana sayfaya git
            page.goto("https://termine.duesseldorf.de/", timeout=60000)
            page.wait_for_timeout(3000)

            # Çerez uyarısı varsa kapat
            cookie = page.locator("button:has-text('Akzeptieren'), button:has-text('Zustimmen'), button:has-text('Schließen')")
            if cookie.count() > 0 and cookie.first.is_visible():
                cookie.first.click()
                page.wait_for_timeout(1000)

            # 2. Fahrerlaubnis kategorisini aç
            cat = page.locator("text=Fahrerlaubnis").first
            cat.scroll_into_view_if_needed()
            cat.click()
            page.wait_for_timeout(2000)

            # 3. Umschreibung hizmetinde sayıyı 1 yap
            service_row = page.locator("tr, div").filter(
                has_text="Umschreibung ausländischer Führerschein (sonstige Staaten)"
            ).first

            plus_btn = service_row.locator("input[value='+'], button:has-text('+')").first
            input_box = service_row.locator("input[type='text'], input[type='number']").first

            if plus_btn.is_visible():
                plus_btn.click(force=True)
            elif input_box.is_visible():
                input_box.fill("1")
                input_box.dispatch_event("change")
            else:
                page.evaluate("""
                    const rows = Array.from(document.querySelectorAll('tr, div'));
                    const target = rows.find(r => r.innerText.includes('Umschreibung ausländischer Führerschein (sonstige Staaten)'));
                    if (target) {
                        const btn = target.querySelector('input[value="+"], button');
                        if (btn) btn.click();
                        const inp = target.querySelector('input[type="text"]');
                        if (inp) { inp.value = "1"; inp.dispatchEvent(new Event('change', { bubbles: true })); }
                    }
                """)

            page.wait_for_timeout(2500)

            # 4. Weiter butonuna tıkla
            weiter_btn = page.locator("#WeiterButton, input[value='Weiter']").first
            page.wait_for_function(
                "document.querySelector('#WeiterButton') && !document.querySelector('#WeiterButton').classList.contains('disabledButton')",
                timeout=10000
            )
            weiter_btn.
