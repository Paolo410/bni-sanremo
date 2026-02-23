#!/usr/bin/env python3
"""
BNI Sanremo – Corsaro Nero – Member Scraper
============================================
Questo script:
1. Fa una POST all'endpoint AJAX di BNI per ottenere la lista membri
2. Per ogni membro fa una seconda POST per ottenere i dettagli (foto, bio, telefono, ecc.)
3. Genera un file HTML completo con cover page e schede membri

Requisiti:
    pip install requests beautifulsoup4

Esecuzione:
    python bni_scraper.py
    
Output:
    bni_sanremo_members.html  (apri nel browser)
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
        "url": f"http://bni-riviereliguri.it/17-riviere-liguri-corsaro-nero/it/memberlist",
        "descriptionKey": "Italiano",
        "id": 14,
        "localeCode": "it"
    }],
    "activeLanguage": {
        "id": 14,
        "localeCode": "it",
        "descriptionKey": "Italiano",
        "cookieBotCode": "it"
    }
})

MEMBER_LIST_WIDGET_SETTINGS = json.dumps([
    {"key": 113, "name": "Member Names",          "value": "Nome Membro BNI"},
    {"key": 117, "name": "Profession/Specialty",  "value": "Professione/Specializzazione"},
    {"key": 118, "name": "Company",               "value": "Società"},
    {"key": 119, "name": "Showing",               "value": "Mostra"},
    {"key": 120, "name": "to",                    "value": "di"},
    {"key": 121, "name": "of",                    "value": "di"},
    {"key": 122, "name": "entries",               "value": "risultati"},
    {"key": 304, "name": "Zero Records",          "value": "Nessun risultato"},
    {"key": 343, "name": "Phone",                 "value": "Telefono"},
    {"key": 344, "name": "Send Mail",             "value": "Invia email"},
])

MEMBER_DETAIL_WIDGET_SETTINGS = json.dumps([
    {"key": 124, "name": "Direct",    "value": "Direct"},
    {"key": 125, "name": "Mobile",    "value": "Mobile"},
    {"key": 126, "name": "Freephone", "value": "Freephone"},
    {"key": 127, "name": "Fax",       "value": "Fax"},
    {"key": 217, "name": "Phone",     "value": "Telefono"},
])


# ─── Step 1: recupera lista membri ─────────────────────────────────────────────

def fetch_member_list(session: requests.Session) -> BeautifulSoup:
    print("📋  Recupero lista membri...")
    resp = session.post(
        f"{BASE_URL}/bnicms/v3/frontend/memberlist/display",
        data={
            "parameters":            f"chapterName={CHAPTER_ID}&regionIds={REGION_ID}&chapterWebsite=1",
            "languages":             LANGUAGES_PAYLOAD,
            "cmsv3":                 "true",
            "website_type":          WEBSITE_TYPE,
            "website_id":            WEBSITE_ID,
            "mappedWidgetSettings":  MEMBER_LIST_WIDGET_SETTINGS,
            "pageMode":              "Live_Site",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def extract_member_ids(soup: BeautifulSoup) -> list[dict]:
    """
    Dalla risposta HTML cerca i link ai dettagli membro.
    Il link tipico è:  memberdetails?encryptedMemberId=XXXX
    oppure:            memberdetails?encryptedUserId=XXXX
    """
    members = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # prova i due pattern usati da BNI
        for param in ("encryptedMemberId", "encryptedUserId"):
            m = re.search(rf"[?&]{param}=([^&]+)", href)
            if m:
                eid = m.group(1)
                if eid not in seen:
                    seen.add(eid)
                    # cerca il nome nella riga più vicina
                    name_tag = a.find(class_=re.compile(r"name|memberName", re.I)) or a
                    name = name_tag.get_text(strip=True) or a.get_text(strip=True)
                    members.append({"id": eid, "param": param, "name_raw": name, "href": href})
                break

    # fallback: cerca data-attributes comuni nei template BNI
    if not members:
        for tag in soup.find_all(attrs={"data-encryptedmemberid": True}):
            eid = tag["data-encryptedmemberid"]
            if eid not in seen:
                seen.add(eid)
                members.append({"id": eid, "param": "encryptedMemberId",
                                 "name_raw": tag.get_text(strip=True), "href": ""})

    print(f"   → Trovati {len(members)} membri")
    return members


# ─── Step 2: recupera dettagli singolo membro ──────────────────────────────────

def fetch_member_detail(session: requests.Session, member: dict) -> dict:
    param_str = f"{member['param']}={member['id']}"
    resp = session.post(
        f"{BASE_URL}/bnicms/v3/frontend/memberdetail/display",
        data={
            "parameters":            param_str,
            "languages":             LANGUAGES_PAYLOAD,
            "pageMode":              "Live_Site",
            "mappedWidgetSettings":  MEMBER_DETAIL_WIDGET_SETTINGS,
            "websitetype":           WEBSITE_TYPE,
            "website_type":          WEBSITE_TYPE,
            "website_id":            WEBSITE_ID,
            "memberId":              member["id"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return parse_member_detail(soup, member)


def parse_member_detail(soup: BeautifulSoup, member: dict) -> dict:

    def txt(selector, default=""):
        tag = soup.select_one(selector)
        return tag.get_text(" ", strip=True) if tag else default

    def attr(selector, attribute, default=""):
        tag = soup.select_one(selector)
        return tag.get(attribute, default) if tag else default

    # ── Nome ─────────────────────────────────────────────────────────────────
    # Dal debug: il nome è la PRIMA riga di .memberProfileInfo (prima di azienda/telefono)
    name = member["name_raw"]  # fallback

    # Tentativo 1: tag semantici dentro widgetMemberProfileTop
    top = soup.select_one(".widgetMemberProfileTop")
    if top:
        for sel in ["h1", "h2", ".memberName", ".name"]:
            t = top.select_one(sel)
            if t:
                candidate = t.get_text(" ", strip=True)
                if candidate and "Telefono" not in candidate and len(candidate) < 60:
                    name = candidate
                    break

    # Tentativo 2: prima riga di .memberProfileInfo (struttura reale BNI)
    if name == member["name_raw"]:
        info_clone = BeautifulSoup(
            str(soup.select_one(".memberProfileInfo") or ""), "html.parser"
        )
        for unwanted in info_clone.select(".profilephoto, .memberContactDetails, .smUrls"):
            unwanted.decompose()
        lines = [ln.strip() for ln in info_clone.get_text("\n").split("\n") if ln.strip()]
        if lines:
            candidate = re.sub(
                r"^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?|Sig\.?ra?\.?)\s+",
                "", lines[0], flags=re.I
            ).strip()
            if candidate and len(candidate) < 60:
                name = candidate

    # ── Foto profilo ─────────────────────────────────────────────────────────
    # <div class="profilephoto"><img class="img-responsive" src="/web/open/appsCmsImageDownload?...">
    photo = ""
    img_tag = soup.select_one(".profilephoto img.img-responsive")
    if not img_tag:
        img_tag = soup.select_one(".profilephoto img")
    if img_tag:
        src = img_tag.get("src", "")
        if src:
            photo = BASE_URL + src if src.startswith("/") else src

    # ── Professione / specializzazione ───────────────────────────────────────
    # Nella sezione widgetMemberProfileTop, dopo nome e azienda
    profession = (txt(".widgetMemberProfileTop .specialty")
               or txt(".widgetMemberProfileTop .profession")
               or txt(".widgetMemberProfileTop .memberProfession"))
    # fallback: seconda riga del banner (spesso è profession/industry)
    if not profession:
        info = soup.select_one(".memberProfileInfo")
        if info:
            lines = [ln.strip() for ln in info.get_text("\n", strip=True).split("\n") if ln.strip()]
            # la struttura tipica è: Nome, Azienda, Professione, Tel …
            profession = lines[2] if len(lines) > 2 else ""

    # ── Azienda ──────────────────────────────────────────────────────────────
    # <section class="widgetMemberCompanyDetail"> → <div class="textHolder">
    company = ""
    text_holder = soup.select_one(".widgetMemberCompanyDetail .textHolder")
    if text_holder:
        # primo elemento significativo (nome azienda è di solito il primo strong/p/li)
        for el in text_holder.find_all(["strong", "b", "h3", "h4", "p", "li"]):
            c = el.get_text(" ", strip=True)
            if c and len(c) > 2:
                company = c
                break
        if not company:
            company = text_holder.get_text(" ", strip=True).split("\n")[0].strip()

    # ── Indirizzo ────────────────────────────────────────────────────────────
    address = ""
    if text_holder:
        lines = [ln.strip() for ln in text_holder.get_text("\n").split("\n") if ln.strip()]
        # l'indirizzo di solito compare dopo il nome azienda
        address = ", ".join(lines[1:4]) if len(lines) > 1 else ""

    # ── Telefono ─────────────────────────────────────────────────────────────
    # <div class="memberContactDetails"> contiene "Telefono XXXXXXXXXX"
    phone = ""
    contact = soup.select_one(".memberContactDetails")
    if contact:
        # cerca link tel: prima
        tel_a = contact.find("a", href=re.compile(r"^tel:"))
        if tel_a:
            phone = tel_a.get_text(strip=True).replace("tel:", "")
        else:
            # estrai solo i numeri dal testo (es. "Telefono 3400061836")
            raw = contact.get_text(" ", strip=True)
            m = re.search(r"(\+?[\d\s\-\/]{8,})", raw)
            if m:
                phone = m.group(1).strip()

    # ── Email ────────────────────────────────────────────────────────────────
    email = ""
    for a in soup.find_all("a", href=re.compile(r"^mailto:")):
        email = a["href"].replace("mailto:", "").strip()
        break

    # ── Social ───────────────────────────────────────────────────────────────
    social = {}
    sm_div = soup.select_one(".smUrls")
    if sm_div:
        for a in sm_div.find_all("a", href=True):
            href = a["href"]
            img  = a.find("img")
            alt  = img.get("alt", "") if img else ""
            if "facebook" in href.lower() or "facebook" in alt.lower():
                social["facebook"] = href
            elif "linkedin" in href.lower() or "linkedin" in alt.lower():
                social["linkedin"] = href
            elif "instagram" in href.lower():
                social["instagram"] = href
            elif href.startswith("http"):
                social.setdefault("website", href)

    # ── Bio / descrizione business ───────────────────────────────────────────
    # <section class="widgetMemberTxtVideo"> contiene il testo libero del membro
    bio = ""
    bio_section = soup.select_one(".widgetMemberTxtVideo")
    if bio_section:
        # ignora eventuali titoli "My Business" e prendi solo i paragrafi
        paras = []
        for el in bio_section.find_all(["p", "div"], recursive=False):
            t = el.get_text(" ", strip=True)
            if t and t.lower() not in ("my business", "il mio business", ""):
                paras.append(t)
        # se non trova nulla col metodo diretto, prende tutto il testo
        if not paras:
            full = bio_section.get_text(" ", strip=True)
            # rimuove la label "My Business" se presente
            full = re.sub(r"^(My Business|Il mio business)\s*", "", full, flags=re.I).strip()
            bio = full
        else:
            bio = " ".join(paras)

    # ── Logo aziendale ───────────────────────────────────────────────────────
    company_logo = ""
    logo_img = soup.select_one(".companyLogo img")
    if logo_img:
        src = logo_img.get("src", "")
        if src:
            company_logo = BASE_URL + src if src.startswith("/") else src

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


# ─── Step 3: genera HTML ────────────────────────────────────────────────────────

HTML_HEAD = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BNI Sanremo – Corsaro Nero | Membri</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=Lato:wght@300;400;700&display=swap" rel="stylesheet">
<style>
:root{--red:#CC0000;--dark-red:#990000;--white:#fff;--off-white:#fafafa;--gray:#555;--border:#e0e0e0}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Lato',sans-serif;background:var(--off-white);color:#222}
/* ── HERO ── */
.hero{display:flex;min-height:100vh;overflow:hidden}
.hero-left{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 50px;background:#fff;position:relative}
.hero-left::after{content:'';position:absolute;top:0;right:0;width:4px;height:100%;background:var(--red)}
.bni-logo-large{width:300px;max-width:80%;margin-bottom:24px}
.chapter-name{font-family:'Lato',sans-serif;font-weight:700;font-size:2.8rem;letter-spacing:.15em;color:#111;text-align:center}
.hero-right{width:42%;background:var(--red);display:flex;flex-direction:column;justify-content:space-between;padding:60px 44px 40px;color:#fff}
.hero-title-block{border-left:3px solid rgba(255,255,255,.4);padding-left:20px}
.hero-title-block p{font-family:'Playfair Display',serif;font-style:italic;font-size:1.5rem;line-height:1.5;letter-spacing:.05em}
.hero-title-block p span{font-weight:700;font-style:normal}
.hero-desc{font-size:.95rem;line-height:1.7;opacity:.9}
.hero-mission{border-top:1px solid rgba(255,255,255,.3);padding-top:30px}
.hero-mission h3{font-family:'Playfair Display',serif;font-weight:700;font-size:1.1rem;letter-spacing:.1em;margin-bottom:12px;text-transform:uppercase}
.hero-tagline{margin-top:auto;border-top:1px solid rgba(255,255,255,.3);padding-top:30px}
.hero-tagline p{font-family:'Playfair Display',serif;font-style:italic;font-weight:700;font-size:1.6rem;line-height:1.4;text-align:center}
.hero-footer{background:var(--red);border-top:3px solid var(--dark-red);padding:20px 40px;text-align:center;color:#fff;font-size:.9rem;line-height:1.7}
/* ── SECTION HEADER ── */
.section-header{background:var(--red);color:#fff;text-align:center;padding:50px 20px 40px;position:relative}
.section-header h2{font-family:'Playfair Display',serif;font-size:2.4rem;font-weight:700;letter-spacing:.05em;margin-bottom:10px}
.section-header p{font-size:1rem;opacity:.85}
.section-header::after{content:'';position:absolute;bottom:-18px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:20px solid transparent;border-right:20px solid transparent;border-top:20px solid var(--red)}
/* ── GRID ── */
.members-container{max-width:1200px;margin:60px auto 80px;padding:0 24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:32px}
/* ── CARD ── */
.member-card{background:#fff;border-radius:4px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.07);border:1px solid var(--border);display:flex;flex-direction:column;transition:box-shadow .25s,transform .25s}
.member-card:hover{box-shadow:0 8px 28px rgba(204,0,0,.15);transform:translateY(-3px)}
.card-header{background:var(--red);padding:22px 22px 0;display:flex;align-items:flex-end;gap:18px;min-height:110px}
.card-avatar{width:80px;height:80px;border-radius:50%;border:3px solid #fff;object-fit:cover;flex-shrink:0;background:#fff;position:relative;top:16px}
.card-avatar-placeholder{width:80px;height:80px;border-radius:50%;border:3px solid #fff;flex-shrink:0;background:rgba(255,255,255,.25);display:flex;align-items:center;justify-content:center;position:relative;top:16px;font-size:1.8rem;color:rgba(255,255,255,.7)}
.card-header-info{padding-bottom:14px;color:#fff;flex:1;min-width:0}
.card-header-info h3{font-family:'Lato',sans-serif;font-weight:700;font-size:1rem;line-height:1.3;margin-bottom:4px}
.card-firstname{font-weight:300;opacity:.85}
.card-lastname{font-weight:700}
.card-role{font-size:.8rem;opacity:.85;font-weight:300;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card-body{padding:28px 22px 18px;flex:1;display:flex;flex-direction:column;gap:10px}
.card-company-row{display:flex;align-items:center;gap:10px}
.card-company{font-weight:700;font-size:.95rem;color:var(--red)}
.card-company-logo{height:28px;width:auto;object-fit:contain;border-radius:3px;flex-shrink:0}
.card-address{font-size:.8rem;color:#888}
.card-bio{font-size:.85rem;color:#555;line-height:1.6;flex:1}
.card-footer{padding:14px 22px;border-top:1px solid var(--border);display:flex;align-items:center;flex-wrap:wrap;gap:8px}
.card-phone{font-weight:700;font-size:.9rem;color:var(--red);text-decoration:none}
.card-phone:hover{text-decoration:underline}
.card-email{font-size:.82rem;color:var(--gray);text-decoration:none;word-break:break-all}
.card-social-row{display:flex;gap:6px;align-items:center;margin-left:2px}
.card-social img{opacity:.75;transition:opacity .2s}.card-social:hover img{opacity:1}
.card-detail-link{margin-left:auto;font-size:.78rem;color:var(--red);text-decoration:none;border:1px solid var(--red);padding:3px 9px;border-radius:3px;white-space:nowrap}
.card-detail-link:hover{background:var(--red);color:#fff}
.site-footer{background:#111;color:rgba(255,255,255,.6);text-align:center;padding:30px 20px;font-size:.82rem}
.site-footer strong{color:#fff}
@media(max-width:700px){
  .hero{flex-direction:column;min-height:auto}
  .hero-left{padding:50px 30px}
  .hero-left::after{width:100%;height:4px;top:auto;right:0;bottom:0}
  .hero-right{width:100%;padding:40px 30px}
  .chapter-name{font-size:2rem}
  .members-container{grid-template-columns:1fr}
}
</style>
</head>
<body>
<section class="hero">
  <div class="hero-left">
    <svg class="bni-logo-large" viewBox="0 0 320 120" xmlns="http://www.w3.org/2000/svg">
      <rect width="320" height="120" fill="white"/>
      <path d="M20 15 L20 105 L70 105 Q100 105 100 82 Q100 68 85 63 Q98 58 98 43 Q98 15 70 15 Z
               M42 35 L65 35 Q77 35 77 46 Q77 57 65 57 L42 57 Z
               M42 72 L68 72 Q80 72 80 84 Q80 96 68 96 L42 96 Z" fill="#CC0000"/>
      <path d="M110 15 L110 105 L132 105 L132 50 L175 105 L197 105 L197 15 L175 15 L175 70 L132 15 Z" fill="#CC0000"/>
      <path d="M207 15 L207 105 L229 105 L229 15 Z" fill="#CC0000"/>
      <path d="M235 105 L260 15 L270 15 L245 105 Z" fill="#CC0000"/>
      <text x="272" y="38" font-family="serif" font-size="18" fill="#CC0000">®</text>
    </svg>
    <div class="chapter-name">SANREMO</div>
  </div>
  <div class="hero-right">
    <div class="hero-title-block">
      <p><span>B</span>USINESS<br><span>N</span>ETWORKING<br><span>I</span>NTERNATIONAL</p>
      <p style="margin-top:14px;font-size:.92rem;">la più grande organizzazione a livello internazionale esperta nel <em>Marketing Referenziale</em></p>
    </div>
    <div class="hero-mission">
      <h3>Mission</h3>
      <p class="hero-desc">Aiutare i Membri ad aumentare il proprio business tramite un programma basato sul passaparola strutturato, positivo e professionale, che permetta loro di sviluppare relazioni significative e a lungo termine con imprenditori e professionisti di valore.</p>
    </div>
    <div class="hero-tagline">
      <p>Cambiamo il modo<br>in cui il mondo<br>fa affari!</p>
    </div>
  </div>
</section>
<div class="hero-footer">
  <strong>BNI SANREMO – Capitolo Corsaro Nero</strong><br>
  INCONTRI SETTIMANALI: Ogni martedì ore 7:00–7:30 Business Breakfast · 7:30–9:00 Riunione operativa<br>
  Palafiori di Sanremo – Corso Garibaldi 1 – Sanremo (IM)
</div>
<div class="section-header">
  <h2>I Nostri Membri</h2>
  <p>Professionisti e imprenditori del territorio che fanno rete ogni settimana</p>
</div>
<div class="members-container">
"""

HTML_FOOT = """
</div>
<footer class="site-footer">
  <strong>BNI Sanremo – Capitolo Corsaro Nero</strong><br>
  © 2025 BNI Global LLC. All Rights Reserved.
</footer>
</body>
</html>
"""


def render_card(m: dict) -> str:
    # ── Avatar ────────────────────────────────────────────────────────────────
    if m["photo"]:
        avatar = (
            f'<img class="card-avatar" src="{m["photo"]}" alt="{m["name"]}" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'\n      <div class="card-avatar-placeholder" style="display:none">👤</div>'
        )
    else:
        avatar = '<div class="card-avatar-placeholder">👤</div>'

    # ── Corpo card ────────────────────────────────────────────────────────────
    role_txt     = m.get("profession") or ""
    company_html = f'<div class="card-company">{m["company"]}</div>' if m.get("company") else ""
    address_html = f'<div class="card-address">📍 {m["address"]}</div>' if m.get("address") else ""
    bio_html     = f'<div class="card-bio">{m["bio"]}</div>'            if m.get("bio")     else ""

    # Logo aziendale piccolo accanto al nome azienda
    logo_html = ""
    if m.get("company_logo"):
        logo_html = f'<img class="card-company-logo" src="{m["company_logo"]}" alt="logo">'

    # ── Footer ────────────────────────────────────────────────────────────────
    phone_clean = re.sub(r"[\s\-\/]", "", m["phone"]) if m.get("phone") else ""
    phone_html  = f'<a class="card-phone" href="tel:{phone_clean}">📞 {m["phone"]}</a>' if m.get("phone") else ""
    email_html  = f'<a class="card-email" href="mailto:{m["email"]}">{m["email"]}</a>' if m.get("email") else ""
    detail_html = f'<a class="card-detail-link" href="{m["detail_url"]}" target="_blank">Dettagli →</a>' if m.get("detail_url") else ""

    # Social icons
    social = m.get("social", {})
    social_html = ""
    icons = {
        "facebook":  ("https://www.google.com/s2/favicons?domain=facebook.com",  "Facebook"),
        "linkedin":  ("https://www.google.com/s2/favicons?domain=linkedin.com",   "LinkedIn"),
        "instagram": ("https://www.google.com/s2/favicons?domain=instagram.com",  "Instagram"),
        "website":   ("https://www.google.com/s2/favicons?domain=google.com",     "Sito web"),
    }
    social_links = []
    for key, (icon_url, label) in icons.items():
        if social.get(key):
            social_links.append(
                f'<a class="card-social" href="{social[key]}" target="_blank" title="{label}">'
                f'<img src="{icon_url}" alt="{label}" width="16" height="16"></a>'
            )
    if social_links:
        social_html = '<div class="card-social-row">' + "".join(social_links) + '</div>'

    # ── Nome: pulizia e separazione nome/cognome ─────────────────────────────
    raw_name = m["name"].strip()
    # rimuove prefissi titolari tipo "Mr." "Mrs." "Dr." "Sig." ecc.
    clean_name = re.sub(r"^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?|Sig\.?|Sig\.ra\.?)\s+", "", raw_name, flags=re.I).strip()
    # splitta in token: il primo è il nome, il resto il cognome
    parts = clean_name.split()
    if len(parts) >= 2:
        first_name = parts[0]
        last_name  = " ".join(parts[1:])
    else:
        first_name = clean_name
        last_name  = ""

    name_html = (
        f'<h3>'
        f'<span class="card-firstname">{first_name}</span>'
        + (f' <span class="card-lastname">{last_name}</span>' if last_name else "")
        + f'</h3>'
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
      <div class="card-company-row">
        {logo_html}
        {company_html}
      </div>
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


# ─── Main ───────────────────────────────────────────────────────────────────────

def main():
    output_file = "bni_sanremo_members.html"

    session = requests.Session()
    session.headers.update(SESSION_HEADERS)

    # 1. Lista membri
    list_soup = fetch_member_list(session)
    members_meta = extract_member_ids(list_soup)

    if not members_meta:
        print("⚠️  Nessun membro trovato nella risposta. Salvo la risposta grezza in debug_list.html per ispezione.")
        with open("debug_list.html", "w", encoding="utf-8") as f:
            f.write(list_soup.prettify())
        print("   Apri debug_list.html e cerca i link ai profili membro per capire la struttura.")
        return

    # 2. Dettagli ogni membro
    cards_html = []
    for i, meta in enumerate(members_meta, 1):
        print(f"   [{i:02d}/{len(members_meta)}]  {meta['name_raw'][:40]:40s}", end="")
        try:
            detail = fetch_member_detail(session, meta)
            print(f"→ {detail['name']}")
            cards_html.append(render_card(detail))
        except Exception as e:
            print(f"→ ⚠️  Errore: {e} – scheda saltata")
        time.sleep(0.4)  # pausa educata tra le richieste

    # 3. Scrivi HTML
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(HTML_HEAD)
        f.write("\n".join(cards_html))
        f.write(HTML_FOOT)

    print(f"\n✅  Fatto! File generato: {output_file}")
    print(f"   Membri scritti: {len(cards_html)}/{len(members_meta)}")
    print(f"   Apri {output_file} nel browser per vedere il risultato.")


if __name__ == "__main__":
    main()
