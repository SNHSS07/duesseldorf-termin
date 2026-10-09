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
        print(f"Görsel gönderme hatasi: {e}")

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

            # Çerez uyarısını kapat
            page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('*'));
                    const accept = btns.find(b => b.innerText && b.innerText.trim() === 'Akzeptieren');
                    if (accept) accept.click();
                }
            """)
            page.wait_for_timeout(1000)

            # 2. Schritt 2'de değilsek Fahrerlaubnis seç
            if "schritt 2" not in page.locator("body").inner_text().lower():
                page.evaluate("""
                    () => {
                        const all = Array.from(document.querySelectorAll('*'));
                        const item = all.find(el => el.innerText && el.innerText.trim() === 'Fahrerlaubnis');
                        if (item) item.click();
                    }
                """)
                page.wait_for_timeout(2000)

            # 3. Akordiyon başlığını aç (Umschreibung ausländische Fahrerlaubnis...)
            print("Akordiyon basligi aciliyor...")
            page.evaluate("""
                () => {
                    const all = Array.from(document.querySelectorAll('*'));
                    const acc = all.find(el => el.innerText && el.innerText.includes('Umschreibung ausländische Fahrerlaubnis / Dienstfahrerlaubnis'));
                    if (acc) acc.click();
                }
            """)
            page.wait_for_timeout(1500)

            # 4. 'sonstige Staaten' satırını ve yanındaki '+' elementini tıkla
            print("Hizmetin '+' ikonuna tiklaniyor...")
            clicked = page.evaluate("""
                () => {
                    // Metni barındıran en alt elemanı bul
                    const all = Array.from(document.querySelectorAll('*'));
                    const match = all.find(el => el.children.length === 0 && el.textContent.includes('sonstige Staaten'));
                    if (!match) return false;

                    // Satır kapsayıcısını bul
                    let parent = match.parentElement;
                    while (parent && parent.tagName !== 'TR' && !parent.classList.contains('row') && !parent.classList.contains('concern')) {
                        if (parent.querySelector('button, .btn, span, a')) break;
                        parent = parent.parentElement;
                    }

                    // Satırdaki tüm elemanlar içinde text'i '+' olanı bul ve tıkla
                    const rowElements = Array.from((parent || document).querySelectorAll('*'));
                    const plus = rowElements.find(el => el.textContent.trim() === '+' || el.value === '+');
                    if (plus) {
                        plus.click();
                        return true;
                    }
                    return false;
                }
            """)
            print(f"Plus butonuna tiklandi mi: {clicked}")
            page.wait_for_timeout(2000)

            # 5. Açılan 'Hinweis' modal penceresindeki 'OK' butonuna tıkla
            print("Modal OK araniyor...")
            page.evaluate("""
                () => {
                    const all = Array.from(document.querySelectorAll('button, a, input'));
                    const okBtn = all.find(el => el.innerText && el.innerText.trim().startsWith('OK'));
                    if (okBtn) okBtn.click();
                }
            """)
            page.wait_for_timeout(2000)

            # 6. Schritt 2 altındaki 'Weiter' butonuna tıkla
            print("1. Weiter tiklaniyor...")
            page.evaluate("""
                () => {
                    const btn = document.querySelector('#WeiterButton') || Array.from(document.querySelectorAll('button, input')).find(b => b.value === 'Weiter' || b.innerText.includes('Weiter'));
                    if (btn) btn.click();
                }
            """)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 7. Schritt 3 (Standortauswahl): İkinci 'Weiter' butonuna tıkla
            print("2. Weiter tiklaniyor...")
            page.evaluate("""
                () => {
                    const btn = document.querySelector('#WeiterButton') || Array.from(document.querySelectorAll('button, input')).find(b => b.value === 'Weiter' || b.innerText.includes('Weiter'));
                    if (btn) btn.click();
                }
            """)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(4000)

            # 8. Schritt 4: Ekran görüntüsünü al
            screenshot_path = "ekran_kaniti.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print("Ekran goruntusu kaydedildi.")

            # 9. Randevu var mı kontrol et
            body_text = page.locator("body").inner_text().lower()
            no_termin = "keine zeiten verfügbar" in body_text or "keine freien termine" in body_text
            slots = page.locator("a.ekol-suggest-button, .suggest-cell a, .calendar-day.available, td.buchbar a")

            if not no_termin and slots.count() > 0:
                print(f"Randevu bulundu! ({slots.count()} slot)")
                caption = "🚨 DÜSSELDORF RANDEVU ALARMI! 🚨\nEhliyet için randevu açıldı! Hemen girin:\nhttps://termine.duesseldorf.de"
                send_telegram_photo(caption, screenshot_path)
            else:
                current_minute = datetime.utcnow().minute
                event_name = os.environ.get("GITHUB_EVENT_NAME", "")

                if current_minute <= 7 or event_name == "workflow_dispatch":
                    print("Saat basi raporu gonderiliyor...")
                    caption = "ℹ️ Saat Başı Durum Raporu:\nTarama aktif, şu an boş randevu yok. Ekran görüntüsü ektedir."
                    send_telegram_photo(caption, screenshot_path)
                else:
                    print(f"Sessiz tarama tamamlandi (Dakika: {current_minute}). Boş yer yok.")

        except Exception as e:
            print(f"Hata detayi: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
