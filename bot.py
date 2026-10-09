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
            print(f"Telegram yaniti: {res.status_code}")
    except Exception as e:
        print(f"Gorsel gonderme hatasi: {e}")

def run():
    print("Düsseldorf randevu botu baslatiliyor...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 900}
        )
        page = context.new_page()

        try:
            # 1. Ana sayfaya git
            print("1. Ana sayfa aciliyor...")
            page.goto("https://termine.duesseldorf.de/", timeout=60000)
            page.wait_for_timeout(2500)

            # Çerez (Cookie) katmanını temizle
            page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('div[class*="cookie"], div[id*="cookie"], .modal-backdrop, .overlay');
                    elements.forEach(el => el.remove());
                }
            """)

            # 2. Schritt 1: Fahrerlaubnisbehörde seç
            print("2. Fahrerlaubnisbehörde seciliyor...")
            page.locator("text=Fahrerlaubnisbehörde").first.click(force=True)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # 3. Schritt 2: Akordiyon başlığını aç
            print("3. Akordiyon basligi aciliyor...")
            accordion = page.locator("text=Umschreibung ausländische Fahrerlaubnis / Dienstfahrerlaubnis").first
            accordion.scroll_into_view_if_needed()
            accordion.click(force=True)
            page.wait_for_timeout(1500)

            # 4. 'sonstige Staaten' satırını bul ve sağdaki mavi '+' butonuna tıkla
            print("4. 'sonstige Staaten' '+' butonuna basiliyor...")
            page.evaluate("""
                () => {
                    const rows = Array.from(document.querySelectorAll('tr, .row, div'));
                    const targetRow = rows.find(r => r.innerText && r.innerText.includes('sonstige Staaten') && !r.innerText.includes('Auswahl des Anliegens'));
                    if (targetRow) {
                        // Satırdaki son tıklanabilir eleman mavi '+' butonudur
                        const buttons = Array.from(targetRow.querySelectorAll('a, button, input[type="button"], div[role="button"]'));
                        if (buttons.length > 0) {
                            buttons[buttons.length - 1].click();
                        }
                    }
                }
            """)
            page.wait_for_timeout(2000)

            # 5. Açılan 'Hinweis' modal penceresindeki mavi onay butonuna tıkla
            print("5. Modal pencere onaylaniyor...")
            page.evaluate("""
                () => {
                    const modals = document.querySelectorAll('.modal.show, .modal.in, div[role="dialog"]');
                    modals.forEach(modal => {
                        const btns = Array.from(modal.querySelectorAll('button, a, input'));
                        const confirmBtn = btns.find(b => b.innerText && (b.innerText.includes('OK') || b.innerText.includes('Schließen')));
                        if (confirmBtn) {
                            confirmBtn.click();
                        }
                    });
                }
            """)
            page.wait_for_timeout(2000)

            # 6. Schritt 2 altındaki ilk 'Weiter' butonuna tıkla
            print("6. Schritt 2 -> Weiter tiklaniyor...")
            page.evaluate("""
                () => {
                    const btn = document.querySelector('#WeiterButton') || Array.from(document.querySelectorAll('button, input')).find(b => b.value === 'Weiter' || b.innerText.includes('Weiter'));
                    if (btn
