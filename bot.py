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
            print("Telegram cevabı:", res.status_code, res.text)
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

            # Çerez uyarısını kapat
            accept_btn = page.locator("button:has-text('Akzeptieren'), a:has-text('Akzeptieren')").first
            if accept_btn.is_visible():
                accept_btn.click()
                page.wait_for_timeout(1000)

            # 2. Schritt 2 ekranında değilsek Fahrerlaubnis seç
            if not page.locator("text=Auswahl des Anliegens").is_visible():
                page.locator("text=Fahrerlaubnis").first.click()
                page.wait_for_timeout(2000)

            # 3. Akordiyon menüyü aç
            acc_header = page.locator("text=Umschreibung ausländische Fahrerlaubnis / Dienstfahrerlaubnis").first
            acc_header.scroll_into_view_if_needed()
            acc_header.click()
            page.wait_for_timeout(1500)

            # 4. 'sonstige Staaten' satırını bul ve yanındaki '+' butonuna tıkla
            service_row = page.locator("div, tr").filter(has_text="Umschreibung ausländischer Führerschein (sonstige Staaten)").last
            plus_btn = service_row.locator("button, input[type='button'], .btn, a").filter(has_text="+").first
            
            plus_btn.scroll_into_view_if_needed()
            plus_btn.click()
            print("'+' butonuna tıklandı.")
            page.wait_for_timeout(1500)

            # 5. Açılan 'Hinweis' modal penceresindeki mavi 'OK' butonuna bas
            ok_modal_btn = page.locator(".modal, div[role='dialog'], body").locator("button:has-text('OK'), a:has-text('OK')").first
            if ok_modal_btn.is_visible():
                ok_modal_btn.click()
                print("Modal 'OK' butonuna tıklandı.")
                page.wait_for_timeout(1500)

            # 6. Schritt 2 altındaki 'Weiter' butonuna tıkla
            weiter_1 = page.locator("#WeiterButton, input[value='Weiter']").first
            weiter_1.scroll_into_view_if_needed()
            weiter_1.click(force=True)
            print("Schritt 2 'Weiter' butonuna tıklandı.")
            
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # 7. Schritt 3 (Standortauswahl): İkinci 'Weiter' butonuna tıkla
            weiter_2 = page.locator("#WeiterButton, input[value='Weiter']").first
            weiter_2.scroll_into_view_if_needed()
            weiter_2.click(force=True)
            print("Schritt 3 'Weiter' butonuna tıklandı.")

            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(4000)

            # 8. Schritt 4: Ekran görüntüsünü al
            screenshot_path = "ekran_kaniti.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print("Ekran görüntüsü kaydedildi.")

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
                    print("Saat başı raporu gönderiliyor...")
                    caption = "ℹ️ Saat Başı Durum Raporu:\nTarama aktif, şu an boş randevu yok. Ekran görüntüsü ektedir."
                    send_telegram_photo(caption, screenshot_path)
                else:
                    print(f"Sessiz tarama tamamlandı (Dakika: {current_minute}). Boş yer yok.")

        except Exception as e:
            print(f"Hata detayı: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
