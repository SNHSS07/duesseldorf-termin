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

            # Çerez bildirimi varsa kapat
            cookie = page.locator("button:has-text('Akzeptieren'), button:has-text('Zustimmen'), button:has-text('Schließen')")
            if cookie.count() > 0 and cookie.first.is_visible():
                cookie.first.click()
                page.wait_for_timeout(1000)

            # 2. Fahrerlaubnis kategorisini aç
            cat = page.locator("text=Fahrerlaubnis").first
            cat.scroll_into_view_if_needed()
            cat.click()
            page.wait_for_timeout(2000)

            # 3. İlgili hizmeti bul ve miktarını artır
            page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const match = elements.find(el => el.children.length === 0 && el.textContent.includes('Umschreibung ausländischer Führerschein (sonstige Staaten)'));
                    if (match) {
                        const container = match.closest('tr') || match.closest('.concern') || match.parentElement.parentElement;
                        if (container) {
                            const plus = container.querySelector('input[value="+"], button.plus, .btn-plus, button:not([id*="Weiter"])');
                            if (plus) plus.click();
                            const input = container.querySelector('input[type="text"], input[type="number"]');
                            if (input) {
                                input.value = "1";
                                input.dispatchEvent(new Event('change', { bubbles: true }));
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        }
                    }
                }
            """)
            page.wait_for_timeout(2000)

            # 4. Formu zorla ilerlet
            page.evaluate("""
                () => {
                    const form = document.querySelector('form');
                    const btn = document.querySelector('#WeiterButton') || document.querySelector('input[value*="Weiter"]') || document.querySelector('button[name*="Weiter"]');
                    if (btn) {
                        btn.removeAttribute('disabled');
                        btn.classList.remove('disabledButton');
                        btn.click();
                    } else if (form) {
                        form.submit();
                    }
                }
            """)

            # Takvim sayfasının yüklenmesini bekle
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(4000)

            # 5. Ekran görüntüsünü kaydet
            screenshot_path = "ekran_kaniti.png"
            page.screenshot(path=screenshot_path, full_page=True)

            # 6. Müsaitlik durumunu tara
            body_text = page.locator("body").inner_text().lower()
            slots = page.locator("a.ekol-suggest-button, .suggest-cell a, .calendar-day.available, td.buchbar a")

            if slots.count() > 0:
                print(f"Randevu yakalandı! ({slots.count()} slot)")
                caption = "🚨 DÜSSELDORF RANDEVU ALARMI! 🚨\nEhliyet için randevu bulundu! Hemen girin:\nhttps://termine.duesseldorf.de"
                send_telegram_photo(caption, screenshot_path)
            else:
                current_minute = datetime.utcnow().minute
                event_name = os.environ.get("GITHUB_EVENT_NAME", "")

                # Saat başı taramasıysa (0-7 dk) veya manuel çalıştırmaysa kanıt görseli yolla
                if current_minute <= 7 or event_name == "workflow_dispatch":
                    print("Saat başı kanıt görseli gönderiliyor...")
                    caption = "ℹ️ Saat Başı Durum Raporu:\nTarama aktif, şu an boş randevu yok. Ekran görüntüsü ektedir."
                    send_telegram_photo(caption, screenshot_path)
                else:
                    print(f"5 dakikalık sessiz kontrol tamamlandı (Dakika: {current_minute}).")

        except Exception as e:
            print(f"Hata: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
