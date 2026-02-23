#!/usr/bin/env python3
"""
BNI Debug – ispezione struttura risposta dettaglio membro
=========================================================
Esegui questo script per salvare la risposta grezza di UN membro
e capire dove si trovano le immagini nella struttura HTML.

Uso:
    python bni_debug.py
    
Output:
    debug_memberlist.html  – risposta grezza lista membri
    debug_detail.html      – risposta grezza dettaglio primo membro
    debug_images.txt       – tutti i tag <img> trovati con src e classi
"""

import requests
import json
import re
from bs4 import BeautifulSoup

BASE_URL     = "https://bni-riviereliguri.it"
CHAPTER_ID   = "36677"
REGION_ID    = "13076"
WEBSITE_ID   = "20473"
WEBSITE_TYPE = "3"

SESSION_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": f"{BASE_URL}/17-riviere-liguri-corsaro-nero/it/memberlist",
    "Origin":  BASE_URL,
    "Accept":  "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

LANGUAGES_PAYLOAD = json.dumps({
    "availableLanguages": [{"type": "published",
        "url": "http://bni-riviereliguri.it/17-riviere-liguri-corsaro-nero/it/memberlist",
        "descriptionKey": "Italiano", "id": 14, "localeCode": "it"}],
    "activeLanguage": {"id": 14, "localeCode": "it",
                       "descriptionKey": "Italiano", "cookieBotCode": "it"}
})

MEMBER_LIST_WIDGET = json.dumps([
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

MEMBER_DETAIL_WIDGET = json.dumps([
    {"key": 124, "name": "Direct",    "value": "Direct"},
    {"key": 125, "name": "Mobile",    "value": "Mobile"},
    {"key": 126, "name": "Freephone", "value": "Freephone"},
    {"key": 127, "name": "Fax",       "value": "Fax"},
    {"key": 217, "name": "Phone",     "value": "Telefono"},
])


def main():
    session = requests.Session()
    session.headers.update(SESSION_HEADERS)

    # ── 1. Lista membri ──────────────────────────────────────────────────────
    print("📋  Recupero lista membri...")
    resp = session.post(
        f"{BASE_URL}/bnicms/v3/frontend/memberlist/display",
        data={
            "parameters":           f"chapterName={CHAPTER_ID}&regionIds={REGION_ID}&chapterWebsite=1",
            "languages":            LANGUAGES_PAYLOAD,
            "cmsv3":                "true",
            "website_type":         WEBSITE_TYPE,
            "website_id":           WEBSITE_ID,
            "mappedWidgetSettings": MEMBER_LIST_WIDGET,
            "pageMode":             "Live_Site",
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw_list = resp.text

    with open("debug_memberlist.html", "w", encoding="utf-8") as f:
        f.write(raw_list)
    print("   ✅ Salvato: debug_memberlist.html")

    soup_list = BeautifulSoup(raw_list, "html.parser")

    # ── 2. Estrai ID del primo membro ────────────────────────────────────────
    first_member = None
    for a in soup_list.find_all("a", href=True):
        for param in ("encryptedMemberId", "encryptedUserId"):
            m = re.search(rf"[?&]{param}=([^&]+)", a["href"])
            if m:
                first_member = {"id": m.group(1), "param": param,
                                "name": a.get_text(strip=True)}
                break
        if first_member:
            break

    if not first_member:
        print("\n⚠️  Nessun link a membro trovato nella lista.")
        print("   Apri debug_memberlist.html e cerca manualmente href con 'memberdetail'")

        # Mostra tutti gli href trovati
        print("\n── Tutti gli <a href> nella risposta ──")
        for a in soup_list.find_all("a", href=True)[:30]:
            print(f"   {a['href'][:120]}")
        return

    print(f"\n👤  Primo membro trovato: {first_member['name']} (id: {first_member['id'][:30]}...)")

    # ── 3. Dettaglio membro ──────────────────────────────────────────────────
    print("🔍  Recupero dettaglio membro...")
    resp2 = session.post(
        f"{BASE_URL}/bnicms/v3/frontend/memberdetail/display",
        data={
            "parameters":           f"{first_member['param']}={first_member['id']}",
            "languages":            LANGUAGES_PAYLOAD,
            "pageMode":             "Live_Site",
            "mappedWidgetSettings": MEMBER_DETAIL_WIDGET,
            "websitetype":          WEBSITE_TYPE,
            "website_type":         WEBSITE_TYPE,
            "website_id":           WEBSITE_ID,
            "memberId":             first_member["id"],
        },
        timeout=30,
    )
    resp2.raise_for_status()
    raw_detail = resp2.text

    with open("debug_detail.html", "w", encoding="utf-8") as f:
        f.write(raw_detail)
    print("   ✅ Salvato: debug_detail.html")

    soup_detail = BeautifulSoup(raw_detail, "html.parser")

    # ── 4. Analisi immagini ──────────────────────────────────────────────────
    report_lines = []
    report_lines.append(f"=== DEBUG IMMAGINI – {first_member['name']} ===\n")

    imgs = soup_detail.find_all("img")
    report_lines.append(f"Totale tag <img> trovati: {len(imgs)}\n")

    for i, img in enumerate(imgs):
        src     = img.get("src", "–")
        classes = " ".join(img.get("class", []))
        alt     = img.get("alt", "")
        parent  = img.parent.name if img.parent else "?"
        pclass  = " ".join(img.parent.get("class", [])) if img.parent else ""
        report_lines.append(
            f"\n[IMG {i+1}]\n"
            f"  src     : {src}\n"
            f"  class   : {classes}\n"
            f"  alt     : {alt}\n"
            f"  parent  : <{parent} class='{pclass}'>"
        )

    # ── 5. Analisi struttura classi principali ───────────────────────────────
    report_lines.append("\n\n=== TUTTE LE CLASSI CSS USATE ===\n")
    all_classes = set()
    for tag in soup_detail.find_all(True):
        for cls in tag.get("class", []):
            all_classes.add(cls)
    for cls in sorted(all_classes):
        report_lines.append(f"  .{cls}")

    # ── 6. Struttura div principali ─────────────────────────────────────────
    report_lines.append("\n\n=== STRUTTURA DIV/SECTION PRINCIPALI ===\n")
    for tag in soup_detail.find_all(["div", "section", "article"], class_=True):
        classes = " ".join(tag.get("class", []))
        snippet = tag.get_text(" ", strip=True)[:80].replace("\n", " ")
        report_lines.append(f"  <{tag.name} class='{classes}'>  →  {snippet}")

    report_txt = "\n".join(report_lines)
    with open("debug_images.txt", "w", encoding="utf-8") as f:
        f.write(report_txt)

    print("\n" + report_txt[:3000])  # stampa anche in console (primi 3000 char)
    print("\n   ✅ Salvato: debug_images.txt (report completo)")
    print("\n📌  Mandami il contenuto di debug_images.txt e aggiorno i selettori nello scraper!")


if __name__ == "__main__":
    main()
