#!/usr/bin/env python3
"""
BNI Ventimiglia – Corsaro Nero – Member Scraper
============================================
Genera: index.html

Logo: metti il file del logo BNI nella stessa cartella
      e rinominalo  bni_logo.png

Requisiti:
    pip install requests beautifulsoup4

Esecuzione:
    python bni_scraper_ventimiglia.py
"""

import requests
import json
import time
import re
from bs4 import BeautifulSoup

# ─── Configurazione ────────────────────────────────────────────────────────────

BASE_URL       = "https://bni-riviereliguri.it"
CHAPTER_ID     = "36677"
REGION_ID      = "13076"
WEBSITE_ID     = "20473"
WEBSITE_TYPE   = "3"
LOCALE         = "it"

# URL della riunione settimanale – usato dal tasto "Vieni a trovarci!"
VISIT_URL = "https://bni-riviereliguri.it/17-riviere-liguri-corsaro-nero/it/visitorregistration?chapterId=36677"

SESSION_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": f"{BASE_URL}/17-riviere-liguri-corsaro-nero/it/memberlist",
    "Origin":  BASE_URL,
    "Accept":  "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

LANGUAGES_PAYLOAD = json.dumps({
    "availableLanguages": [{
        "type": "published",
        "url": "http://bni-riviereliguri.it/17-riviere-liguri-corsaro-nero/it/memberlist",
        "descriptionKey": "Italiano",
        "id": 14,
        "localeCode": "it"
    }],
    "activeLanguage": {
        "id": 14, "localeCode": "it",
        "descriptionKey": "Italiano", "cookieBotCode": "it"
    }
})

MEMBER_LIST_WIDGET_SETTINGS = json.dumps([
    {"key": 113, "name": "Member Names",         "value": "Nome Membro BNI"},
    {"key": 117, "name": "Profession/Specialty", "value": "Professione/Specializzazione"},
    {"key": 118, "name": "Company",              "value": "Società"},
    {"key": 119, "name": "Showing",              "value": "Mostra"},
    {"key": 120, "name": "to",                   "value": "di"},
    {"key": 121, "name": "of",                   "value": "di"},
    {"key": 122, "name": "entries",              "value": "risultati"},
    {"key": 304, "name": "Zero Records",         "value": "Nessun risultato"},
    {"key": 343, "name": "Phone",                "value": "Telefono"},
    {"key": 344, "name": "Send Mail",            "value": "Invia email"},
])

MEMBER_DETAIL_WIDGET_SETTINGS = json.dumps([
    {"key": 124, "name": "Direct",    "value": "Direct"},
    {"key": 125, "name": "Mobile",    "value": "Mobile"},
    {"key": 126, "name": "Freephone", "value": "Freephone"},
    {"key": 127, "name": "Fax",       "value": "Fax"},
    {"key": 217, "name": "Phone",     "value": "Telefono"},
])


# ─── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_member_list(session: requests.Session) -> BeautifulSoup:
    print("📋  Recupero lista membri...")
    resp = session.post(
        f"{BASE_URL}/bnicms/v3/frontend/memberlist/display",
        data={
            "parameters":           f"chapterName={CHAPTER_ID}&regionIds={REGION_ID}&chapterWebsite=1",
            "languages":            LANGUAGES_PAYLOAD,
            "cmsv3":                "true",
            "website_type":         WEBSITE_TYPE,
            "website_id":           WEBSITE_ID,
            "mappedWidgetSettings": MEMBER_LIST_WIDGET_SETTINGS,
            "pageMode":             "Live_Site",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def extract_member_ids(soup: BeautifulSoup) -> list:
    members = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        for param in ("encryptedMemberId", "encryptedUserId"):
            m = re.search(rf"[?&]{param}=([^&]+)", href)
            if m:
                eid = m.group(1)
                if eid not in seen:
                    seen.add(eid)
                    name_tag = a.find(class_=re.compile(r"name|memberName", re.I)) or a
                    name = name_tag.get_text(strip=True) or a.get_text(strip=True)
                    members.append({"id": eid, "param": param, "name_raw": name, "href": href})
                break
    if not members:
        for tag in soup.find_all(attrs={"data-encryptedmemberid": True}):
            eid = tag["data-encryptedmemberid"]
            if eid not in seen:
                seen.add(eid)
                members.append({"id": eid, "param": "encryptedMemberId",
                                 "name_raw": tag.get_text(strip=True), "href": ""})
    print(f"   → Trovati {len(members)} membri")
    return members


def fetch_member_detail(session: requests.Session, member: dict) -> dict:
    resp = session.post(
        f"{BASE_URL}/bnicms/v3/frontend/memberdetail/display",
        data={
            "parameters":           f"{member['param']}={member['id']}",
            "languages":            LANGUAGES_PAYLOAD,
            "pageMode":             "Live_Site",
            "mappedWidgetSettings": MEMBER_DETAIL_WIDGET_SETTINGS,
            "websitetype":          WEBSITE_TYPE,
            "website_type":         WEBSITE_TYPE,
            "website_id":           WEBSITE_ID,
            "memberId":             member["id"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return parse_member_detail(BeautifulSoup(resp.text, "html.parser"), member)


# ─── Parse ─────────────────────────────────────────────────────────────────────

def clean_title(text: str) -> str:
    return re.sub(
        r"^(Mr\.?|Mrs\.?|Ms\.?|Mx\.?|Dr\.?|Prof\.?|Sig\.?|Sig\.ra\.?|Dott\.?|Dott\.ssa\.?)\s+",
        "", text, flags=re.I
    ).strip()


def parse_member_detail(soup: BeautifulSoup, member: dict) -> dict:

    def txt(sel, default=""):
        t = soup.select_one(sel)
        return t.get_text(" ", strip=True) if t else default

    # Nome
    name = member["name_raw"]
    top = soup.select_one(".widgetMemberProfileTop")
    if top:
        for sel in ["h1", "h2", ".memberName", ".name"]:
            t = top.select_one(sel)
            if t:
                candidate = clean_title(t.get_text(" ", strip=True))
                if candidate and "Telefono" not in candidate and len(candidate) < 60:
                    name = candidate
                    break
    if name == member["name_raw"]:
        info_clone = BeautifulSoup(
            str(soup.select_one(".memberProfileInfo") or ""), "html.parser"
        )
        for u in info_clone.select(".profilephoto, .memberContactDetails, .smUrls"):
            u.decompose()
        lines = [l.strip() for l in info_clone.get_text("\n").split("\n") if l.strip()]
        if lines:
            candidate = clean_title(lines[0])
            if candidate and len(candidate) < 60:
                name = candidate
    name = clean_title(name)

    # Foto
    photo = ""
    img = (soup.select_one(".profilephoto img.img-responsive")
           or soup.select_one(".profilephoto img"))
    if img:
        src = img.get("src", "")
        photo = (BASE_URL + src) if src.startswith("/") else src

    # Professione
    profession = (txt(".widgetMemberProfileTop .specialty")
               or txt(".widgetMemberProfileTop .profession")
               or txt(".widgetMemberProfileTop .memberProfession"))
    if not profession:
        info = soup.select_one(".memberProfileInfo")
        if info:
            lines = [l.strip() for l in info.get_text("\n", strip=True).split("\n") if l.strip()]
            profession = lines[2] if len(lines) > 2 else ""

    # Azienda + indirizzo (salta righe che sono il nome del membro)
    company = ""
    address = ""
    text_holder = soup.select_one(".widgetMemberCompanyDetail .textHolder")
    if text_holder:
        lines = [l.strip() for l in text_holder.get_text("\n").split("\n") if l.strip()]
        name_lower = name.lower()
        filtered = [l for l in lines if clean_title(l).lower() != name_lower]
        if filtered:
            company = filtered[0]
            addr_parts = [l for l in filtered[1:4]
                          if l.lower() not in ("italia", "italy", "france", "monaco")]
            address = ", ".join(addr_parts)

    # Telefono
    phone = ""
    contact = soup.select_one(".memberContactDetails")
    if contact:
        tel_a = contact.find("a", href=re.compile(r"^tel:"))
        if tel_a:
            phone = tel_a.get_text(strip=True)
        else:
            raw = contact.get_text(" ", strip=True)
            m = re.search(r"(\+?[\d\s\-\/]{8,})", raw)
            if m:
                phone = m.group(1).strip()

    # Email
    email = ""
    for a in soup.find_all("a", href=re.compile(r"^mailto:")):
        email = a["href"].replace("mailto:", "").strip()
        break

    # Social
    social = {}
    sm_div = soup.select_one(".smUrls")
    if sm_div:
        for a in sm_div.find_all("a", href=True):
            href = a["href"]
            img_tag = a.find("img")
            alt = img_tag.get("alt", "") if img_tag else ""
            if "facebook" in href.lower() or "facebook" in alt.lower():
                social["facebook"] = href
            elif "linkedin" in href.lower() or "linkedin" in alt.lower():
                social["linkedin"] = href
            elif "instagram" in href.lower():
                social["instagram"] = href
            elif href.startswith("http"):
                social.setdefault("website", href)

    # Bio
    bio = ""
    bio_sec = soup.select_one(".widgetMemberTxtVideo")
    if bio_sec:
        paras = []
        for el in bio_sec.find_all(["p", "div"], recursive=False):
            t = el.get_text(" ", strip=True)
            if t and t.lower() not in ("my business", "il mio business", ""):
                paras.append(t)
        if paras:
            bio = " ".join(paras)
        else:
            bio = re.sub(r"^(My Business|Il mio business)\s*", "",
                         bio_sec.get_text(" ", strip=True), flags=re.I).strip()

    # Logo aziendale
    company_logo = ""
    logo_img = soup.select_one(".companyLogo img")
    if logo_img:
        src = logo_img.get("src", "")
        company_logo = (BASE_URL + src) if src.startswith("/") else src

    return {
        "name":         name,
        "photo":        photo,
        "profession":   profession,
        "company":      company,
        "address":      address,
        "phone":        phone,
        "email":        email,
        "bio":          bio,
        "social":       social,
        "company_logo": company_logo,
        "detail_url":   f"{BASE_URL}/17-riviere-liguri-corsaro-nero/it/memberdetails"
                        f"?{member['param']}={member['id']}",
    }


# ─── HTML ──────────────────────────────────────────────────────────────────────

HTML_HEAD = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BNI Ventimiglia – Corsaro Nero | Membri</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=Lato:wght@300;400;700;900&display=swap" rel="stylesheet">
<link rel="icon" type="image/png" href="bni_logo.png">
<link rel="apple-touch-icon" href="bni_logo.png">
<style>
:root{
  --red:#E2001A;--dark-red:#B5001A;--white:#fff;--off-white:#f7f7f7;--gray:#555;--border:#e0e0e0;
  --hero-right-bg:#E2001A;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Lato',sans-serif;background:var(--off-white);color:#222}

/* ── HERO ── */
.hero{display:flex;min-height:100vh;overflow:hidden}

/* Lato sinistro: bianco con logo */
.hero-left{
  flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
  padding:60px 50px;background:#fff;position:relative;gap:24px;
}
.hero-left::after{
  content:'';position:absolute;top:0;right:0;width:4px;height:100%;background:var(--red)
}
.bni-logo-large{
  width:260px;max-width:80%;
  /* Se bni_logo.png non esiste mostra niente senza rompere il layout */
}
.chapter-badge{
  background:var(--red);color:#fff;
  font-family:'Lato',sans-serif;font-weight:900;font-size:1rem;
  letter-spacing:.25em;text-transform:uppercase;
  padding:8px 22px;border-radius:2px;
}

/* Lato destro: rosso */
.hero-right{
  width:45%;background:var(--hero-right-bg);
  display:flex;flex-direction:column;
  padding:60px 50px;color:#fff;gap:0;
}

/* Blocco BNI spelled out */
.hero-bni-spelled{
  border-left:3px solid rgba(255,255,255,.35);
  padding-left:22px;margin-bottom:32px;
}
.hero-bni-spelled .bni-line{
  font-family:'Lato',sans-serif;font-weight:900;
  font-size:2.8rem;line-height:1;letter-spacing:.04em;
  display:flex;align-items:baseline;gap:6px;
}
.hero-bni-spelled .bni-line .letter{
  font-size:3.2rem;color:#fff;
}
.hero-bni-spelled .bni-line .word{
  font-size:1.5rem;font-weight:300;letter-spacing:.12em;text-transform:uppercase;opacity:.92;
}

/* Divisore */
.hero-divider{
  width:48px;height:2px;background:rgba(255,255,255,.35);
  margin:28px 0;
}

/* Mission */
.hero-mission-label{
  font-family:'Lato',sans-serif;font-weight:700;
  font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;
  opacity:.6;margin-bottom:10px;
}
.hero-mission-text{
  font-size:.9rem;line-height:1.75;opacity:.88;
  border-left:2px solid rgba(255,255,255,.25);
  padding-left:16px;
}

/* Tagline */
.hero-tagline{
  margin-top:auto;padding-top:36px;
  border-top:1px solid rgba(255,255,255,.2);
}
.hero-tagline p{
  font-family:'Playfair Display',serif;font-style:italic;
  font-size:1.35rem;line-height:1.5;opacity:.95;
}

/* ── CTA bar (sotto l'hero) ── */
.cta-bar{
  background:var(--dark-red);
  padding:22px 40px;
  display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:16px;
}
.cta-bar-text{
  color:#fff;font-size:.9rem;line-height:1.6;opacity:.9;
}
/* Tasto pill stile BNI */
.btn-bni{
  display:inline-flex;align-items:center;gap:14px;
  background:var(--red);color:#fff;
  font-family:'Lato',sans-serif;font-weight:700;font-size:.95rem;letter-spacing:.03em;
  text-decoration:none;
  padding:14px 28px;
  border-radius:50px;          /* pill shape */
  border:2px solid var(--red);
  transition:background .22s ease,color .22s ease;
  white-space:nowrap;
}
.btn-bni .btn-arrow{
  font-size:1.1rem;font-weight:400;transition:transform .22s ease;
}
.btn-bni:hover{
  background:#fff;
  color:var(--red);
  border-color:var(--red);
}
.btn-bni:hover .btn-arrow{
  transform:translateX(4px);
}

/* ── HERO FOOTER (info riunione) ── */
.hero-footer{
  background:var(--red);border-top:3px solid var(--dark-red);
  padding:18px 40px;text-align:center;color:#fff;font-size:.88rem;line-height:1.7;
}

/* ── SECTION HEADER ── */
.section-header{
  background:var(--red);color:#fff;text-align:center;
  padding:50px 20px 40px;position:relative;
}
.section-header h2{
  font-family:'Playfair Display',serif;font-size:2.4rem;font-weight:700;margin-bottom:10px;
}
.section-header p{font-size:1rem;opacity:.85}
.section-header::after{
  content:'';position:absolute;bottom:-18px;left:50%;transform:translateX(-50%);
  width:0;height:0;
  border-left:20px solid transparent;border-right:20px solid transparent;
  border-top:20px solid var(--red);
}

/* ── GRID ── */
.members-container{
  max-width:1200px;margin:60px auto 80px;padding:0 24px;
  display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:32px;
}

/* ── CARD ── */
.member-card{
  background:#fff;border-radius:4px;overflow:hidden;
  box-shadow:0 2px 12px rgba(0,0,0,.07);border:1px solid var(--border);
  display:flex;flex-direction:column;transition:box-shadow .25s,transform .25s;
}
.member-card:hover{box-shadow:0 8px 28px rgba(226,0,26,.14);transform:translateY(-3px)}
.card-header{
  background:var(--red);padding:22px 22px 0;
  display:flex;align-items:flex-end;gap:18px;min-height:110px;
}
.card-avatar{
  width:80px;height:80px;border-radius:50%;border:3px solid #fff;
  object-fit:cover;flex-shrink:0;background:#fff;position:relative;top:16px;
}
.card-avatar-placeholder{
  width:80px;height:80px;border-radius:50%;border:3px solid #fff;flex-shrink:0;
  background:rgba(255,255,255,.25);display:flex;align-items:center;justify-content:center;
  position:relative;top:16px;font-size:1.8rem;color:rgba(255,255,255,.7);
}
.card-header-info{padding-bottom:14px;color:#fff;flex:1;min-width:0}
.card-header-info h3{font-size:1rem;line-height:1.3;margin-bottom:4px;font-weight:400}
.card-firstname{font-weight:700}
.card-lastname{font-weight:700}
.card-role{font-size:.8rem;opacity:.85;font-weight:300;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card-body{padding:28px 22px 18px;flex:1;display:flex;flex-direction:column;gap:10px}
.card-company-row{display:flex;align-items:center;gap:10px}
.card-company{font-weight:700;font-size:.95rem;color:var(--red)}
.card-company-logo{height:28px;width:auto;object-fit:contain;border-radius:3px;flex-shrink:0}
.card-address{font-size:.8rem;color:#888}
.card-bio{font-size:.85rem;color:#555;line-height:1.6;flex:1}
.card-footer{
  padding:14px 22px;border-top:1px solid var(--border);
  display:flex;align-items:center;flex-wrap:wrap;gap:8px;
}
.card-phone{font-weight:700;font-size:.9rem;color:var(--red);text-decoration:none}
.card-phone:hover{text-decoration:underline}
.card-email{font-size:.82rem;color:var(--gray);text-decoration:none;word-break:break-all}
.card-social-row{display:flex;gap:6px;align-items:center;margin-left:2px}
.card-social img{opacity:.75;transition:opacity .2s}.card-social:hover img{opacity:1}
.card-detail-link{
  margin-left:auto;font-size:.78rem;color:var(--red);text-decoration:none;
  border:1px solid var(--red);padding:3px 9px;border-radius:3px;white-space:nowrap;
}
.card-detail-link:hover{background:var(--red);color:#fff}

/* ── FOOTER ── */
.site-footer{background:#111;color:rgba(255,255,255,.6);text-align:center;padding:30px 20px;font-size:.82rem}
.site-footer strong{color:#fff}

/* ── RESPONSIVE ── */
@media(max-width:750px){
  .hero{flex-direction:column;min-height:auto}
  .hero-left{padding:50px 30px}
  .hero-left::after{width:100%;height:4px;top:auto;right:0;bottom:0}
  .hero-right{width:100%;padding:44px 30px}
  .hero-bni-spelled .bni-line .letter{font-size:2.4rem}
  .hero-bni-spelled .bni-line .word{font-size:1.2rem}
  .cta-bar{flex-direction:column;align-items:flex-start;padding:20px 24px}
  .members-container{grid-template-columns:1fr}
}
</style>
</head>
<body>

<!-- ═══════════════════════════════════════════════ HERO ══ -->
<section class="hero">

  <!-- Sinistra: logo + nome capitolo -->
  <div class="hero-left">
    <!--
      LOGO: rinomina il file del logo BNI come  bni_logo.png
            e mettilo nella stessa cartella di questo script.
            Se non esiste, viene mostrato il testo di fallback.
    -->
    <img class="bni-logo-large"
         src="./img/bni_logo.png"
         alt="BNI – Business Networking International"
         onerror="this.style.display='none'">
    <div class="chapter-badge">Capitolo Corsaro Nero</div>
  </div>

  <!-- Destra: copy + mission + tagline -->
  <div class="hero-right">

    <div class="hero-bni-spelled">
      <div class="bni-line"><span class="letter">B</span><span class="word">usiness</span></div>
      <div class="bni-line"><span class="letter">N</span><span class="word">etworking</span></div>
      <div class="bni-line"><span class="letter">I</span><span class="word">nternational</span></div>
    </div>

    <div class="hero-divider"></div>

    <div class="hero-mission-label">La nostra Mission</div>
    <p class="hero-mission-text">
      Aiutare i Membri ad aumentare il proprio business tramite un programma
      basato sul passaparola strutturato, positivo e professionale, che permetta
      loro di sviluppare relazioni significative e a lungo termine con imprenditori
      e professionisti di valore.
    </p>

    <div class="hero-tagline">
      <p>&#8220;Cambiamo il modo<br>in cui il mondo<br>fa affari!&#8221;</p>
    </div>

  </div>
</section>

<!-- Info riunione -->
<div class="hero-footer">
  <strong>BNI VENTIMIGLIA &ndash; Capitolo Corsaro Nero</strong><br>
  INCONTRO SETTIMANALE: Ogni venerd&igrave; ore 7:00<br>
  Ristorante Palo Santo &ndash; Passeggiata G. Marconi, 5/48-49 &ndash; Ventimiglia (IM)
</div>

<!-- ═══════════════════════════ TASTO "VIENI A TROVARCI" ══ -->
<div class="cta-bar">
  <div class="cta-bar-text">
    Vuoi scoprire come funziona BNI? Partecipa come ospite alla nostra prossima riunione.
  </div>
  <a class="btn-bni" href="https://bni-riviereliguri.it/17-riviere-liguri-corsaro-nero/it/visitorregistration?chapterId=36677" target="_blank">
    Vieni a trovarci! <span class="btn-arrow">&#8594;</span>
  </a>
</div>

<!-- ═══════════════════════════════════ GRIGLIA MEMBRI ══ -->
<div class="section-header">
  <h2>I Nostri Membri</h2>
  <p>Professionisti e imprenditori del territorio che fanno rete ogni settimana</p>
</div>
<div class="members-container">
"""

HTML_FOOT = """
</div>
<footer class="site-footer">
  <strong>BNI Ventimiglia &ndash; Capitolo Corsaro Nero</strong><br>
  &copy; 2025 BNI Global LLC. All Rights Reserved.
</footer>
</body>
</html>
"""


# ─── Render card ───────────────────────────────────────────────────────────────

def render_card(m: dict) -> str:
    if m["photo"]:
        avatar = (
            f'<img class="card-avatar" src="{m["photo"]}" alt="{m["name"]}" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'<div class="card-avatar-placeholder" style="display:none">&#128100;</div>'
        )
    else:
        avatar = '<div class="card-avatar-placeholder">&#128100;</div>'

    role_txt     = m.get("profession") or ""
    company_html = f'<div class="card-company">{m["company"]}</div>'        if m.get("company") else ""
    address_html = f'<div class="card-address">&#128205; {m["address"]}</div>' if m.get("address") else ""
    bio_html     = f'<div class="card-bio">{m["bio"]}</div>'                if m.get("bio")     else ""
    logo_html    = (f'<img class="card-company-logo" src="{m["company_logo"]}" alt="logo">'
                    if m.get("company_logo") else "")

    phone_clean = re.sub(r"[\s\-\/]", "", m["phone"]) if m.get("phone") else ""
    phone_html  = (f'<a class="card-phone" href="tel:{phone_clean}">&#128222; {m["phone"]}</a>'
                   if m.get("phone") else "")
    email_html  = (f'<a class="card-email" href="mailto:{m["email"]}">{m["email"]}</a>'
                   if m.get("email") else "")
    detail_html = (f'<a class="card-detail-link" href="{m["detail_url"]}" target="_blank">Dettagli &#8594;</a>'
                   if m.get("detail_url") else "")

    social = m.get("social", {})
    icons = {
        "facebook":  ("https://www.google.com/s2/favicons?domain=facebook.com",  "Facebook"),
        "linkedin":  ("https://www.google.com/s2/favicons?domain=linkedin.com",   "LinkedIn"),
        "instagram": ("https://www.google.com/s2/favicons?domain=instagram.com",  "Instagram"),
        "website":   ("https://www.google.com/s2/favicons?domain=google.com",     "Sito web"),
    }
    social_links = [
        f'<a class="card-social" href="{social[k]}" target="_blank" title="{lbl}">'
        f'<img src="{ico}" width="16" height="16" alt="{lbl}"></a>'
        for k, (ico, lbl) in icons.items() if social.get(k)
    ]
    social_html = ('<div class="card-social-row">' + "".join(social_links) + '</div>'
                   if social_links else "")

    raw_name   = m["name"].strip()
    clean_name = re.sub(r"^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?|Sig\.?|Sig\.ra\.?)\s+",
                        "", raw_name, flags=re.I).strip()
    parts = clean_name.split()
    first_name = parts[0] if parts else clean_name
    last_name  = " ".join(parts[1:]) if len(parts) > 1 else ""

    name_html = (
        f'<h3>'
        f'<span class="card-firstname">{first_name}</span>'
        + (f' <span class="card-lastname">{last_name}</span>' if last_name else "")
        + '</h3>'
    )

    return f"""
  <div class="member-card">
    <div class="card-header">
      {avatar}
      <div class="card-header-info">
        {name_html}
        <div class="card-role">{role_txt}</div>
      </div>
    </div>
    <div class="card-body">
      <div class="card-company-row">{logo_html}{company_html}</div>
      {address_html}
      {bio_html}
    </div>
    <div class="card-footer">
      {phone_html}
      {email_html}
      {social_html}
      {detail_html}
    </div>
  </div>"""


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    output_file = "index.html"

    session = requests.Session()
    session.headers.update(SESSION_HEADERS)

    list_soup    = fetch_member_list(session)
    members_meta = extract_member_ids(list_soup)

    if not members_meta:
        print("⚠️  Nessun membro trovato.")
        with open("debug_list.html", "w", encoding="utf-8") as f:
            f.write(list_soup.prettify())
        return

    cards_html = []
    for i, meta in enumerate(members_meta, 1):
        print(f"   [{i:02d}/{len(members_meta)}] {meta['name_raw'][:40]:40s}", end="", flush=True)
        try:
            detail = fetch_member_detail(session, meta)
            print(f"→ {detail['name']}")
            cards_html.append(render_card(detail))
        except Exception as e:
            print(f"→ ⚠️  {e}")
        time.sleep(0.4)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(HTML_HEAD)
        f.write("\n".join(cards_html))
        f.write(HTML_FOOT)

    print(f"\n✅  Fatto! → {output_file}  ({len(cards_html)}/{len(members_meta)} membri)")


if __name__ == "__main__":
    main()