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
        print(f"Telegram hatasi: {e}")

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

            # Çerez kutusu varsa kapat
            cookie = page.locator("button:has-text('Akzeptieren'), button:has-text('Zustimmen'), button:has-text('Schließen')")
            if cookie.count() > 0 and cookie.first.is_visible():
                cookie.first.click()
                page.wait_for_timeout(1000)

            # 2. Fahrerlaubnis kategorisini tıkla
            page.locator("text=Fahrerlaubnis").first.click()
            page.wait_for_timeout(2000)

            # 3. Umschreibung satırını bul ve 1 adet seç
            row = page.locator("tr, div").filter(has_text="Umschreibung ausländischer Führerschein (sonstige Staaten)").first
            
            # Artı butonu varsa tıkla, select kutusu varsa 1 yap
            plus = row.locator("input[value='+'], button:has-text('+')").first
            if plus.is_visible():
                plus.click()
            else:
                select = row.locator("select").first
                if select.is_visible():
                    select.select_option("1")

            page.wait_for_timeout(2000)

            # 4. Sayfanın en altındaki Weiter butonuna tıkla
            next_btn = page.locator("input[type='submit'][value*='Weiter'], button:has-text('Weiter'), input[value*='Weiter']").first
            next_btn.click()
            
            # Takvim sayfasının yüklenmesini bekle
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(5000)

            # 5. GERÇEK RANDEVU KONTROLÜ
            # Takvimde tıklanabilir gün/saat var mı?
            # TEVIS sisteminde randevusu olan günler aktif link veya buton olur
            body_text = page.locator("body").inner_text().lower()

            # Açıkça randevu yok yazıyorsa:
            if "keine zeiten verfügbar" in body_text or "keine freien termine" in body_text:
                print("Sonuç: Takvim ekranına ulaşıldı, boş randevu yok.")
                return

            # Tıklanabilir randevu butonlarını ara (TEVIS şablonu sınıfları)
            slots = page.locator("a.ekol-suggest-button, .suggest-cell a, .calendar-day.available, td.buchbar a")
            
            if slots.count() > 0:
                print(f"BULDUM! {slots.count()} adet uygun randevu slotu var!")
                send_telegram(
                    "🚨 DÜSSELDORF RANDEVU ALARMI! 🚨\n\n"
                    "Ehliyet denkliği için GERÇEK randevu açıldı!\n"
                    "Hemen al:\n"
                    "https://termine.duesseldorf.de"
                )
            else:
                print("Sonuç: Takvimde seçilebilir boş gün/saat bulunamadı (Yanlış alarm engellendi).")

        except Exception as e:
            print(f"Hata oluştu: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
