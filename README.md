# BNI Ventimiglia – Corsaro Nero

Sito statico con la lista aggiornata dei membri del capitolo BNI Ventimiglia, generato tramite scraping del portale BNI ufficiale.

## File

- `bni_scraper.py` — scarica i dati dei membri da BNI e genera `index.html`
- `index.html` — sito generato (non modificare manualmente)
- `img/bni_logo.png` — logo BNI usato nell'header e come favicon
- `requirements.txt` — dipendenze Python (`requests`, `beautifulsoup4`)

## Uso

```bash
pip install -r requirements.txt
python bni_scraper.py
```

## Aggiornamento automatico

GitHub Actions aggiorna `index.html` ogni giorno alle 07:00 (ora italiana).