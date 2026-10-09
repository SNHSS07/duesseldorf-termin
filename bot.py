import os, re, datetime, requests
from playwright.sync_api import sync_playwright

URL = "https://termine.duesseldorf.de/"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]
API = f"https://api.telegram.org/bot{TOKEN}"
MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
SHOT = "screen.png"


def send_text(text):
    requests.post(f"{API}/sendMessage", data={"chat_id": CHAT, "text": text}, timeout=30)


def send_photo(caption):
    with open(SHOT, "rb") as f:
        requests.post(f"{API}/sendPhoto", data={"chat_id": CHAT, "caption": caption},
                      files={"photo": f}, timeout=60)


def accept_cookies(page):
    for name in ["Alle akzeptieren", "Alle Cookies akzeptieren", "Akzeptieren",
                 "Zustimmen", "Alle zulassen", "Einverstanden", "OK"]:
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
    page.get_by_role("button", name=re.compile(r"^\s*Weiter\s*$")).first.click(timeout=15000) \
        if page.get_by_role("button", name=re.compile(r"^\s*Weiter\s*$")).count() \
        else page.get_by_text("Weiter", exact=True).last.click(timeout=15000)
    page.wait_for_timeout(1500)


def dismiss_hinweis(page):
    """Hinweis-Popup'ı varsa OK'e bas."""
    try:
        ok = page.get_by_text("OK", exact=True).first
        if ok.is_visible(timeout=2500):
            ok.click()
            page.wait_for_timeout(1500)
            return True
    except Exception:
        pass
    return False


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000}, locale="de-DE")
        try:
            page.goto(URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            accept_cookies(page)

            # Adım 1: Fahrerlaubnisbehörde
            click_text(page, "Fahrerlaubnisbehörde", exact=True)
            accept_cookies(page)

            # Adım 2: Umschreibung ... akordeonunu aç
            click_text(page, "Umschreibung ausländische Fahrerlaubnis / Dienstfahrerlaubnis")

            # "(sonstige Staaten)" satırındaki + simgesine koordinatla tıkla
            label = page.get_by_text("sonstige Staaten").first
            label.wait_for(timeout=15000)
            label.scroll_into_view_if_needed()
            lb = label.bounding_box()
            weiter = page.get_by_text("Weiter", exact=True).last
            wb = weiter.bounding_box()
            plus_x = wb["x"] + wb["width"] - 46      # + simgesi sağ kenara ~46px mesafede
            plus_y = lb["y"] + lb["height"] / 2
            page.mouse.click(plus_x, plus_y)
            page.wait_for_timeout(1500)

            dismiss_hinweis(page)       # + sonrası popup çıkarsa OK
            click_weiter(page)
            dismiss_hinweis(page)       # Weiter sonrası popup çıkarsa OK

            # Adım 3: Standort -> Weiter
            page.wait_for_timeout(1500)
            if page.get_by_text("Standort", exact=False).count():
                try:
                    click_weiter(page)
                except Exception:
                    pass

            page.wait_for_timeout(4000)
            page.screenshot(path=SHOT, full_page=True)
            text = page.inner_text("body").lower()
            browser.close()
            return text
        except Exception as e:
            try:
                page.screenshot(path=SHOT, full_page=True)
            except Exception:
                pass
            browser.close()
            raise e


try:
    body = run()
    no_slot = ("keine zeiten verfügbar" in body) or ("keine freien termine" in body)
    minute = datetime.datetime.utcnow().minute

    if not no_slot:
        send_text("🚨 RANDEVU ÇIKMIŞ OLABİLİR! Hemen gir:\nhttps://termine.duesseldorf.de/\n"
                  "(Ya randevu açıldı ya da sayfa yapısı değişti, ekran görüntüsüne bak.)")
        send_photo("Sayfanın şu anki hali")
    elif MANUAL or minute < 5:
        send_photo("Hâlâ randevu yok (Keine Zeiten verfügbar), aramaya devam ediyorum.")
except Exception as e:
    minute = datetime.datetime.utcnow().minute
    if MANUAL or minute < 5:
        send_text(f"⚠️ Bot adımlardan birinde takıldı: {type(e).__name__}: {str(e)[:300]}")
        if os.path.exists(SHOT):
            send_photo("Takıldığı andaki ekran")
