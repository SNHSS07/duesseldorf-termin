import os, re, time, datetime, requests
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

URL = "https://termine.duesseldorf.de/"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]
API = f"https://api.telegram.org/bot{TOKEN}"
MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
SHOT = "screen.png"

RUN_MINUTES = 27          # bir çalışmanın açık kalma süresi
INTERVAL_SECONDS = 90     # iki kontrol arası bekleme
FAIL_ALERT_AFTER = 5      # art arda kaç hatadan sonra "takıldı" mesajı
TZ = ZoneInfo("Europe/Berlin")


def send_text(text):
    try:
        requests.post(f"{API}/sendMessage", data={"chat_id": CHAT, "text": text}, timeout=30)
    except Exception as e:
        print("Telegram mesaj hatası:", e)


def send_photo(caption):
    try:
        with open(SHOT, "rb") as f:
            requests.post(f"{API}/sendPhoto", data={"chat_id": CHAT, "caption": caption},
                          files={"photo": f}, timeout=60)
    except Exception as e:
        print("Telegram foto hatası:", e)


def accept_cookies(page):
    for name in ["Alle akzeptieren", "Alle Cookies akzeptieren", "Akzeptieren",
                 "Zustimmen", "Alle zulassen", "Einverstanden"]:
        try:
            btn = page.get_by_role("button", name=re.compile(name, re.I)).first
            if btn.is_visible(timeout=1500):
                btn.click()
                page.wait_for_timeout(800)
                return
        except Exception:
            pass


def click_text(page, text, exact=False):
    page.get_by_text(text, exact=exact).first.click(timeout=15000)
    page.wait_for_timeout(1200)


def click_weiter(page):
    btn = page.get_by_role("button", name=re.compile(r"^\s*Weiter\s*$"))
    if btn.count():
        btn.first.click(timeout=15000)
    else:
        page.get_by_text("Weiter", exact=True).last.click(timeout=15000)
    page.wait_for_timeout(1500)


def dismiss_hinweis(page):
    try:
        ok = page.get_by_text("OK", exact=True).first
        if ok.is_visible(timeout=2500):
            ok.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass


def check_once(browser):
    """Akışı yürür. 'none' (randevu yok) veya 'slot' (randevu olabilir) döner; sorun olursa hata fırlatır."""
    context = browser.new_context(viewport={"width": 1280, "height": 1000}, locale="de-DE")
    page = context.new_page()
    page.set_default_timeout(30000)
    try:
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)
        accept_cookies(page)

        click_text(page, "Fahrerlaubnisbehörde", exact=True)
        accept_cookies(page)

        click_text(page, "Umschreibung ausländische Fahrerlaubnis / Dienstfahrerlaubnis")

        label = page.get_by_text("sonstige Staaten").first
        label.wait_for(timeout=15000)
        label.scroll_into_view_if_needed()
        lb = label.bounding_box()
        wb = page.get_by_text("Weiter", exact=True).last.bounding_box()
        page.mouse.click(wb["x"] + wb["width"] - 46, lb["y"] + lb["height"] / 2)
        page.wait_for_timeout(1500)

        dismiss_hinweis(page)
        click_weiter(page)
        dismiss_hinweis(page)

        page.wait_for_timeout(1500)
        if "standort" in page.inner_text("body").lower():
            try:
                click_weiter(page)
            except Exception:
                pass

        page.wait_for_timeout(4000)
        page.screenshot(path=SHOT, full_page=True)
        body = page.inner_text("body").lower()
    except Exception:
        try:
            page.screenshot(path=SHOT, full_page=True)
        except Exception:
            pass
        raise
    finally:
        context.close()

    if "keine zeiten verfügbar" in body or "keine freien termine" in body:
        return "none"
    if "schritt 4" in body or "schritt 5" in body:
        return "slot"
    raise RuntimeError("Beklenmeyen sayfa: Schritt 4'e ulaşılamadı")


def main():
    deadline = time.time() + RUN_MINUTES * 60
    last_hour = None
    fails = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        while True:
            now = datetime.datetime.now(TZ)
            try:
                result = check_once(browser)
                fails = 0
                print(now.strftime("%H:%M:%S"), "sonuç:", result, flush=True)

                if result == "slot":
                    send_text("🚨 RANDEVU ÇIKMIŞ OLABİLİR! Hemen gir:\nhttps://termine.duesseldorf.de/")
                    send_photo("Sayfanın şu anki hali")
                elif MANUAL:
                    send_photo("Test: hâlâ randevu yok (Keine Zeiten verfügbar).")
                elif now.hour != last_hour and (last_hour is not None or now.minute < 10):
                    send_photo("Hâlâ randevu yok (Keine Zeiten verfügbar), aramaya devam ediyorum.")
                last_hour = now.hour

            except Exception as e:
                fails += 1
                print(now.strftime("%H:%M:%S"), "HATA:", type(e).__name__, str(e)[:200], flush=True)
                if MANUAL or fails == FAIL_ALERT_AFTER:
                    send_text(f"⚠️ Bot takıldı ({fails}. hata): {type(e).__name__}: {str(e)[:300]}")
                    if os.path.exists(SHOT):
                        send_photo("Takıldığı andaki ekran")
                try:
                    browser.close()
                except Exception:
                    pass
                browser = p.chromium.launch()

            if MANUAL or time.time() + INTERVAL_SECONDS + 90 > deadline:
                break
            time.sleep(INTERVAL_SECONDS)

        try:
            browser.close()
        except Exception:
            pass


main()
