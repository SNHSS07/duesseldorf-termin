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
        print(f"Telegram gonderim hatasi: {e}")

def run():
    print("Düsseldorf randevu botu baslatiliyor...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # 1. Ana sayfaya git
            page.goto("https://termine.duesseldorf.de/", timeout=60000)
            page.wait_for_timeout(3000)

            # 2. Çerez veya bilgilendirme kutusu varsa kabul et / geç
            cookie_btn = page.locator("button:has-text('Akzeptieren'), button:has-text('Zustimmen'), button:has-text('Schließen')")
            if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
                cookie_btn.first.click()
                page.wait_for_timeout(1000)

            # 3. "Fahrerlaubnisbehörde" veya ehliyet bölümünü bulup tıkla
            category = page.locator("text=Fahrerlaubnis").first
            if category.is_visible():
                category.click()
                page.wait_for_timeout(1500)

            # 4. "Umschreibung ausländischer Führerschein" hizmet satırını bul
            service_row = page.locator("tr, div, li").filter(has_text="Umschreibung ausländischer Führerschein (sonstige Staaten)").first
            
            if service_row.is_visible():
                # Yanındaki '+' butonunu tıkla (sayıyı 1 yap)
                plus_button = service_row.locator("button:has-text('+'), input[type='button'][value='+'], .btn-plus").first
                if plus_button.is_visible():
                    plus_button.click()
                else:
                    select_box = service_row.locator("select").first
                    if select_box.is_visible():
                        select_box.select_option("1")
            else:
                print("Hizmet başlığı sayfada doğrudan bulunamadı, genel sayfa kontrol ediliyor...")

            page.wait_for_timeout(1500)

            # 5. 'Weiter' butonuna tıkla
            next_btn = page.locator("input[value*='Weiter'], button:has-text('Weiter'), a:has-text('Weiter')").first
            if next_btn.is_visible():
                next_btn.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

            # 6. 4. Adım (Terminvorschläge) kontrolü
            content = page.content().lower()

            no_termin_phrases = [
                "keine zeiten verfügbar",
                "keine freien termine",
                "im moment sind leider keine freien termine verfügbar"
            ]

            has_no_termin = any(phrase in content for phrase in no_termin_phrases)

            if has_no_termin:
                print("Kontrol tamamlandı: Şu an müsait randevu bulunmuyor.")
            else:
                if "umschreibung" in content or "terminvorschläge" in content:
                    msg = (
                        "🚨 DÜSSELDORF RANDEVU ALARMI! 🚨\n\n"
                        "Ehliyet denkliği için randevu slotu bulundu!\n"
                        "Hemen girip randevunuzu onaylayın:\n"
                        "https://termine.duesseldorf.de"
                    )
                    print("Boş randevu yakalandı! Telegram'a bildirim gönderiliyor.")
                    send_telegram(msg)
                else:
                    print("Sayfa adımları geçilemedi veya farklı bir sayfada kalındı.")

        except Exception as e:
            print(f"Hata oluştu: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
