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
            viewport={"width": 1280, "height": 1000}
        )
        page = context.new_page()

        try:
            # 1. Ana sayfaya git
            page.goto("https://termine.duesseldorf.de/", timeout=60000)
            page.wait_for_timeout(3000)

            # Çerez bildirimi varsa kapat
            page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('button, input, a'));
                    const accept = btns.find(b => b.innerText && b.innerText.includes('Akzeptieren'));
                    if (accept) accept.click();
                    const modal = document.querySelector('.cookie-notice, #cookie-modal');
                    if (modal) modal.remove();
                }
            """)
            page.wait_for_timeout(1500)

            # 2. Sayfa Schritt 2'de değilse Fahrerlaubnis seç
            if "schritt 2" not in page.locator("body").inner_text().lower():
                page.locator("text=Fahrerlaubnis").first.click()
                page.wait_for_timeout(2000)

            # 3. Akordiyon başlığını aç: "+ Umschreibung ausländische Fahrerlaubnis"
            page.evaluate("""
                () => {
                    const accordions = Array.from(document.querySelectorAll('*'));
                    const target = accordions.find(el => el.children.length === 0 && el.textContent.includes('Umschreibung ausländische Fahrerlaubnis'));
                    if (target) {
                        const parentBtn = target.closest('button') || target.closest('div');
                        if (parentBtn) parentBtn.click();
                    }
                }
            """)
            page.wait_for_timeout(1500)

            # 4. Üçüncü sıradaki "sonstige Staaten" satırının artı (+) butonuna bas
            page.evaluate("""
                () => {
                    const rows = Array.from(document.querySelectorAll('tr, div'));
                    const row = rows.find(r => r.innerText && r.innerText.includes('sonstige Staaten'));
                    if (row) {
                        const plusBtn = row.querySelector('button, input[type="button"], a');
                        if (plusBtn) plusBtn.click();
                    }
                }
            """)
            page.wait_for_timeout(1500)

            # 5. Açılan "Hinweis" uyarısındaki mavi "OK" butonuna tıkla
            ok_button = page.locator("button:has-text('OK'), a:has-text('OK'), input[value='OK']").first
            if ok_button.is_visible():
                ok_button.click()
                page.wait_for_timeout(1500)

            # 6. Schritt 2'nin altındaki ilk "Weiter" butonuna bas
            next_step_1 = page.locator("#WeiterButton, input[value='Weiter'], button:has-text('Weiter')").first
            next_step_1.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 7. Schritt 3 (Standortauswahl): İkinci "Weiter" butonuna bas
            next_step_2 = page.locator("#WeiterButton, input[value='Weiter'], button:has-text('Weiter')").first
            next_step_2.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 8. Hedef ekran (Schritt 4) görüntüsünü al
            screenshot_path = "ekran_kaniti.png"
            page.screenshot(path=screenshot_path, full_page=True)

            # 9. Randevu Kontrolü
            body_text = page.locator("body").inner_text().lower()
            
            # "keine zeiten verfügbar" veya "keine freien termine" varsa randevu kesinlikle yoktur
            has_no_appointments = "keine zeiten verfügbar" in body_text or "keine freien termine" in body_text

            # Tıklanabilir takvim slotu/tarih bağlantısı var mı?
            slots = page.locator("a.ekol-suggest-button, .suggest-cell a, .calendar-day.available, td.buchbar a")

            if not has_no_appointments and slots.count() > 0:
                print("Randevu bulundu!")
                caption = "🚨 DÜSSELDORF RANDEVU ALARMI! 🚨\nEhliyet için randevu açıldı! Hemen girin:\nhttps://termine.duesseldorf.de"
                send_telegram_photo(caption, screenshot_path)
            else:
                current_minute = datetime.utcnow().minute
                event_name = os.environ.get("GITHUB_EVENT_NAME", "")

                # Saat başı taramasıysa (0-7 dk) veya elle tetiklendiyse kanıt görselini at
                if current_minute <= 7 or event_name == "workflow_dispatch":
                    print("Saat başı kanıtı gönderiliyor...")
                    caption = "ℹ️ Saat Başı Durum Raporu:\nTarama aktif, şu an boş randevu yok. Ekran görüntüsü ektedir."
                    send_telegram_photo(caption, screenshot_path)
                else:
                    print(f"5 dakikalık periyodik kontrol yapıldı (Dakika: {current_minute}). Boş yer yok, sessiz mod.")

        except Exception as e:
            print(f"Hata: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
