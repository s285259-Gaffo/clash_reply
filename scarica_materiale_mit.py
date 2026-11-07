"""Scarica materiale reale e pubblico da MIT OpenCourseWare per la demo "Studente Fantasma".

Corso: 18.01 Single Variable Calculus, Fall 2006 (Prof. David Jerison)
Argomento: l'integrale definito e le sue applicazioni (lezioni 18-24)
           + Esame 3 (copre proprio le sessioni 18-24) con soluzioni ufficiali
           + Esami di prova 3A/3B con soluzioni.

Per ogni lezione: appunti del docente (PDF) + trascrizione della videolezione (PDF).
Le trascrizioni OCW NON hanno timestamp (testo continuo): il link al video e'
riportato in indice.json e in FONTE_E_LICENZA.md.

Solo libreria standard. Se e' installata pypdf, estrae anche il testo in .txt
(una sezione per pagina, utile per citare "pagina N").

Uso:  python scarica_materiale_mit.py
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

try:  # console di Windows: evita errori con caratteri non ASCII
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CORSO_ID = "18-01-single-variable-calculus-fall-2006"
CORSO_TITOLO = "18.01 Single Variable Calculus, Fall 2006"
DOCENTE = "Prof. David Jerison"
BASE = f"https://ocw.mit.edu/courses/{CORSO_ID}/"
BASE_WWW = f"https://www.ocw.mit.edu/courses/{CORSO_ID}/"
CARTELLA = Path(__file__).resolve().parent / "materiale" / "mit_18-01_fall2006"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# Lezioni: (numero, titolo, slug della pagina video, URL diretti noti della trascrizione)
LEZIONI = [
    (18, "Definite integrals", "lecture-18-definite-integrals",
     ["hjZhPczMkL4.pdf"]),
    (19, "First fundamental theorem of calculus", "lecture-19-first-fundamental-theorem",
     ["d009101aee4d4c11142f6b477fc84ebe_1RLctDS2hUQ.pdf"]),
    (20, "Second fundamental theorem", "lecture-20-second-fundamental-theorem", []),
    (21, "Applications to logarithms and geometry", "lecture-21-applications-to-logarithms", []),
    (22, "Volumes by disks and shells", "lecture-22-volumes", []),
    (23, "Work, average value, probability", "lecture-23-work",
     ["R9a_NHXrBcg.pdf"]),
    (24, "Numerical integration", "lecture-24-numerical-integration",
     ["jBkXbAgMj6s.pdf"]),
]

# Hash noti (da risultati di ricerca) per gli appunti; se mancano si legge la pagina.
HASH_APPUNTI = {
    18: "d1b3d809b6505825b5cde0cee823fa0f",
    20: "3cd98c68cec64e9214c8c9003f6cf983",
    21: "df90380a9805621e488cac35fe009764",
    22: "dcd410f264f661f8ac1e53ea6df740cc",
    23: "c9b0814986c30ee6aca81d0c9b3614d6",
}

ESAMI = [
    ("exam3", "Esame 3 (copre sessioni 18-24) - testo", "18c69a89fa69a1ae1f3db40f887c1760"),
    ("exam3sol", "Esame 3 - soluzioni ufficiali", None),
    ("prexam3a", "Esame di prova 3A - testo", None),
    ("prexam3asol", "Esame di prova 3A - soluzioni", None),
    ("prexam3b", "Esame di prova 3B - testo", None),
    ("prexam3bsol", "Esame di prova 3B - soluzioni", None),
]

HASH_RE = re.compile(r"^[0-9a-f]{32}_")


def scarica_bytes(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def pdf_nella_pagina(url_pagina, filtro):
    """Legge la pagina HTML di una risorsa OCW e restituisce gli URL .pdf che passano il filtro."""
    html = scarica_bytes(url_pagina).decode("utf-8", errors="replace")
    trovati = []
    for href in re.findall(r'href="([^"]+?\.pdf)"', html):
        url = urljoin(url_pagina, href)
        stem = HASH_RE.sub("", url.rsplit("/", 1)[-1])[:-4]
        if filtro(stem) and url not in trovati:
            trovati.append(url)
    return trovati


def prova_scaricare(destinazione, candidati, pagine_risorsa, filtro):
    """Prova gli URL noti, poi cerca il link vero nelle pagine della risorsa.
    Restituisce (url_usato, None) oppure (None, messaggio_errore)."""
    if destinazione.exists() and destinazione.stat().st_size > 1000:
        return "(gia' presente)", None
    errori = []
    tentati = set()

    def tenta(url):
        if url in tentati:
            return False
        tentati.add(url)
        try:
            dati = scarica_bytes(url)
        except urllib.error.HTTPError as e:
            errori.append(f"{url} -> HTTP {e.code}")
            return False
        except Exception as e:  # rete, timeout, SSL...
            errori.append(f"{url} -> {type(e).__name__}: {e}")
            return False
        if not dati.startswith(b"%PDF"):
            errori.append(f"{url} -> non e' un PDF")
            return False
        destinazione.write_bytes(dati)
        return True

    for url in candidati:
        if tenta(url):
            return url, None
    for pagina in pagine_risorsa:
        try:
            trovati = pdf_nella_pagina(pagina, filtro)
        except Exception as e:
            errori.append(f"pagina {pagina} -> {type(e).__name__}: {e}")
            continue
        for url in trovati:
            if tenta(url):
                return url, None
        time.sleep(0.5)
    return None, "; ".join(errori[-3:]) or "nessun link PDF trovato"


def estrai_testo(pdf_path):
    """Estrae il testo con pypdf, se disponibile. Restituisce un messaggio di stato."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return "testo non estratto (pypdf non installato: pip install pypdf)"
    try:
        reader = PdfReader(str(pdf_path))
        parti, caratteri = [], 0
        for i, pagina in enumerate(reader.pages, start=1):
            testo = pagina.extract_text() or ""
            caratteri += len(testo.strip())
            parti.append(f"=== Pagina {i} ===\n{testo.strip()}\n")
        pdf_path.with_suffix(".txt").write_text("\n".join(parti), encoding="utf-8")
        n = len(reader.pages)
        if n and caratteri / n < 100:  # meno di 100 caratteri a pagina in media
            return f"testo estratto ({n} pag.) ma quasi vuoto: probabilmente scansione, serve OCR"
        return f"testo estratto ({n} pag., {caratteri} caratteri)"
    except Exception as e:
        return f"estrazione testo fallita: {type(e).__name__}: {e}"


def pagine(slug):
    return [f"{BASE}resources/{slug}/", f"{BASE_WWW}resources/{slug}/"]


def scrivi_licenza(indice):
    righe = [
        "# Fonte e licenza del materiale",
        "",
        f"**Corso:** MIT {CORSO_TITOLO} - {DOCENTE}",
        f"**URL del corso:** {BASE}",
        "**Editore:** MIT OpenCourseWare, Massachusetts Institute of Technology",
        "**Licenza:** Creative Commons Attribuzione - Non commerciale - Condividi allo stesso modo "
        "4.0 Internazionale (CC BY-NC-SA 4.0) - https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "**Termini d'uso OCW:** https://ocw.mit.edu/pages/privacy-and-terms-of-use/",
        "",
        "## Attribuzione da usare (es. nel README, nelle slide e nell'interfaccia della demo)",
        "",
        f"> David Jerison. *18.01 Single Variable Calculus.* Fall 2006. Massachusetts Institute of "
        f"Technology: MIT OpenCourseWare, {BASE}. License: Creative Commons BY-NC-SA.",
        "",
        "Condizioni: citare MIT OCW e il docente; uso NON commerciale; eventuali materiali derivati "
        "(es. estratti .txt, mappe delle lacune generate) vanno distribuiti con la stessa licenza; "
        "non usare il marchio MIT per suggerire approvazione del progetto.",
        "",
        "## Note sul materiale",
        "",
        "- Le videolezioni sono state registrate nel 2007 (file `ocw-18.01-f07-lecNN`) e "
        "pubblicate dentro il corso Fall 2006.",
        "- Le trascrizioni OCW sono testo continuo SENZA timestamp. Per avere i minuti servono "
        "i sottotitoli YouTube o una trascrizione automatica (es. Whisper) del video MP4.",
        "- Alcune soluzioni d'esame possono essere scansioni: se il .txt e' quasi vuoto serve OCR.",
        "",
        "## File",
        "",
        "| File | Contenuto | URL di origine |",
        "|---|---|---|",
    ]
    for voce in indice:
        righe.append(f"| {voce['file']} | {voce['descrizione']} | {voce['url'] or 'NON SCARICATO'} |")
    righe.append("")
    righe.append("Video (non scaricati, ~100-200 MB ciascuno): "
                 "https://archive.org/download/MIT18.01JF07/ocw-18.01-f07-lecNN_300k.mp4 (NN = 18..24)")
    (CARTELLA / "FONTE_E_LICENZA.md").write_text("\n".join(righe) + "\n", encoding="utf-8")


def main():
    CARTELLA.mkdir(parents=True, exist_ok=True)
    print(f"Scarico materiale MIT OCW - {CORSO_TITOLO}")
    print(f"Cartella: {CARTELLA}\n")

    lavori = []  # (nome_file, descrizione, candidati, pagine_risorsa, filtro, extra)
    for n, titolo, slug_video, trascr_note in LEZIONI:
        cand = []
        if n in HASH_APPUNTI:
            cand += [f"{BASE}{HASH_APPUNTI[n]}_lec{n}.pdf", f"{BASE_WWW}{HASH_APPUNTI[n]}_lec{n}.pdf"]
        cand += [f"{BASE}lec{n}.pdf"]
        lavori.append((f"lezione{n}_appunti.pdf", f"Lezione {n}: {titolo} - appunti del docente",
                       cand, pagine(f"lec{n}"), lambda s, n=n: s == f"lec{n}",
                       {"tipo": "appunti", "lezione": n}))
        lavori.append((f"lezione{n}_trascrizione.pdf",
                       f"Lezione {n}: {titolo} - trascrizione videolezione (senza timestamp)",
                       [BASE + t for t in trascr_note], pagine(slug_video),
                       lambda s: not s.lower().startswith("lec"),
                       {"tipo": "trascrizione", "lezione": n, "timestamp": False,
                        "pagina_video": f"{BASE}resources/{slug_video}/",
                        "video_mp4": f"https://archive.org/download/MIT18.01JF07/ocw-18.01-f07-lec{n}_300k.mp4"}))
    for nome, descr, h in ESAMI:
        cand = [f"{BASE}{h}_{nome}.pdf"] if h else []
        cand += [f"{BASE}{nome}.pdf"]
        lavori.append((f"{nome}.pdf", descr, cand, pagine(nome), lambda s, nome=nome: s == nome,
                       {"tipo": "soluzioni" if nome.endswith("sol") else "esame"}))

    indice, ok, ko = [], 0, 0
    for nome_file, descr, cand, pag, filtro, extra in lavori:
        dest = CARTELLA / nome_file
        url, errore = prova_scaricare(dest, cand, pag, filtro)
        if url:
            ok += 1
            stato_txt = estrai_testo(dest)
            print(f"[SCARICATO] {nome_file}  - {stato_txt}")
        else:
            ko += 1
            print(f"[ERRORE]    {nome_file}  - {errore}")
        indice.append({"file": nome_file, "descrizione": descr, "url": url if url else None, **extra})
        time.sleep(0.3)

    (CARTELLA / "indice.json").write_text(json.dumps(indice, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    scrivi_licenza(indice)
    print("\n--- Riepilogo ---")
    print(f"Scaricati: {ok}   Errori: {ko}   Totale: {len(lavori)}")
    print(f"Scritti anche: {CARTELLA / 'indice.json'} e {CARTELLA / 'FONTE_E_LICENZA.md'}")
    if ko:
        print("Per i file in errore apri la pagina della risorsa su ocw.mit.edu e scaricali a mano.")


if __name__ == "__main__":
    main()
