"""
Caricamento del materiale di un corso e verifica delle citazioni.

Una cartella corso (materiale/<nome_corso>/) contiene file di testo/markdown:
  - slide_*.md            slide con intestazioni "## Slide N — Titolo"
  - trascrizione_*.md     righe "[mm:ss] testo" (o [hh:mm:ss])
  - esame*.md             testo d'esame (escluse le soluzioni)
  - soluzioni*.md         soluzioni ufficiali passo per passo
  - brief_docente.md      intervista/obiettivi del docente (opzionale)
  - CHIAVE_LACUNE.json    (opzionale, solo per i test) lacune piantate apposta
Anche .txt va bene. Il numero di lezione si ricava dal nome del file (es. _03).

Ogni frammento di conoscenza ha un ID citabile:
  S12        -> slide 12
  L3@41:20   -> lezione 3, minuto 41:20 della videolezione
La verifica delle citazioni e' fatta IN CODICE (guardrail), non dal modello.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

CARTELLA_MATERIALE = Path(__file__).parent / "materiale"


@dataclass
class Fonte:
    id: str            # "S12" o "L3@41:20"
    tipo: str          # "slide" | "trascrizione"
    lezione: int
    titolo: str
    testo: str


@dataclass
class Corso:
    nome: str
    cartella: Path
    fonti: dict[str, Fonte] = field(default_factory=dict)
    esame: str = ""
    soluzioni: str = ""
    brief: str = ""
    chiave: list | None = None

    # --- viste del materiale per i diversi studenti fantasma ---------------
    def testo_fonti(self, tipi=("slide", "trascrizione"), max_caratteri: int | None = None) -> str:
        righe = []
        for f in self.fonti.values():
            if f.tipo not in tipi:
                continue
            if f.tipo == "slide":
                righe.append(f"[{f.id}] (Lezione {f.lezione}) {f.titolo}\n{f.testo}\n")
            else:
                righe.append(f"[{f.id}] {f.testo}")
        testo = "\n".join(righe)
        if max_caratteri is None:
            import os
            max_caratteri = int(os.getenv("MAX_CARATTERI_MATERIALE", "300000"))
        return testo[:max_caratteri]

    def riepilogo(self) -> dict:
        n_slide = sum(f.tipo == "slide" for f in self.fonti.values())
        n_trascr = sum(f.tipo == "trascrizione" for f in self.fonti.values())
        lezioni = sorted({f.lezione for f in self.fonti.values()})
        return {"nome": self.nome, "slide": n_slide, "frammenti_trascrizione": n_trascr,
                "lezioni": lezioni, "ha_esame": bool(self.esame), "ha_soluzioni": bool(self.soluzioni),
                "ha_chiave": self.chiave is not None}


# --------------------------------------------------------------------------- #
#  Caricamento
# --------------------------------------------------------------------------- #
_RE_SLIDE = re.compile(r"^#{1,3}\s*Slide\s+(\d+)\s*[—\-–:]*\s*(.*)$", re.IGNORECASE | re.MULTILINE)
_RE_TEMPO = re.compile(r"^\s*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)$")


def _numero_lezione(nome_file: str) -> int:
    m = re.search(r"(\d+)", nome_file)
    return int(m.group(1)) if m else 0


def _leggi(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _carica_slide(p: Path, corso: Corso):
    testo = _leggi(p)
    lezione = _numero_lezione(p.stem)
    pezzi = list(_RE_SLIDE.finditer(testo))
    for i, m in enumerate(pezzi):
        fine = pezzi[i + 1].start() if i + 1 < len(pezzi) else len(testo)
        corpo = testo[m.end():fine].strip()
        sid = f"S{int(m.group(1))}"
        corso.fonti[sid] = Fonte(sid, "slide", lezione, m.group(2).strip(), corpo)


def _carica_trascrizione(p: Path, corso: Corso):
    lezione = _numero_lezione(p.stem)
    for riga in _leggi(p).splitlines():
        m = _RE_TEMPO.match(riga)
        if not m:
            continue
        tempo = m.group(1)
        if tempo.count(":") == 2:  # hh:mm:ss -> mm:ss totali
            h, mi, s = (int(x) for x in tempo.split(":"))
            tempo = f"{h * 60 + mi:02d}:{s:02d}"
        fid = f"L{lezione}@{tempo}"
        corso.fonti[fid] = Fonte(fid, "trascrizione", lezione, "", m.group(2).strip())


def elenca_corsi() -> list[str]:
    if not CARTELLA_MATERIALE.exists():
        return []
    return sorted(p.name for p in CARTELLA_MATERIALE.iterdir()
                  if p.is_dir() and not p.name.startswith(("_", ".")))


def carica_corso(nome: str) -> Corso:
    cartella = CARTELLA_MATERIALE / nome
    if not cartella.is_dir():
        raise FileNotFoundError(f"Corso '{nome}' non trovato in {CARTELLA_MATERIALE}")
    corso = Corso(nome=nome, cartella=cartella)
    file = sorted(p for p in cartella.iterdir() if p.suffix.lower() in (".md", ".txt", ".json"))
    for p in file:
        n = p.name.lower()
        if n.startswith("slide"):
            _carica_slide(p, corso)
        elif n.startswith("trascrizion") or n.startswith("transcript"):
            _carica_trascrizione(p, corso)
        elif n.startswith("soluzion") or n.startswith("solution"):
            corso.soluzioni += _leggi(p) + "\n"
        elif n.startswith("esame") or n.startswith("exam"):
            corso.esame += _leggi(p) + "\n"
        elif n.startswith("brief"):
            corso.brief += _leggi(p) + "\n"
        elif n.startswith("chiave") and p.suffix.lower() == ".json":
            try:
                dati = json.loads(_leggi(p))
                corso.chiave = dati if isinstance(dati, list) else dati.get("lacune", [])
            except json.JSONDecodeError:
                corso.chiave = None
    if not corso.fonti:
        raise ValueError(f"Nel corso '{nome}' non ho trovato slide ('## Slide N — Titolo') "
                         f"ne' trascrizioni ('[mm:ss] testo').")
    return corso


# --------------------------------------------------------------------------- #
#  Verifica delle citazioni (guardrail in codice)
# --------------------------------------------------------------------------- #
def _normalizza(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[$\\{}^_]", " ", t.lower())
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def normalizza_id(fid: str | None) -> str | None:
    """Accetta varianti come 'Slide 12', 's12', 'L3 41:20', 'Lezione 3 @ 41:20'."""
    if not fid:
        return None
    f = str(fid).strip().strip("[]()")
    m = re.match(r"^(?:slide\s*|s)\s*(\d+)$", f, re.IGNORECASE)
    if m:
        return f"S{int(m.group(1))}"
    m = re.match(r"^(?:lezione\s*|l)\s*(\d+)\s*[@ ,]+\s*(\d{1,2}):(\d{2})$", f, re.IGNORECASE)
    if m:
        return f"L{int(m.group(1))}@{int(m.group(2)):02d}:{m.group(3)}"
    return f


def verifica_citazione(corso: Corso, fid: str | None, citazione: str | None,
                       tipi_ammessi=("slide", "trascrizione"), soglia: float = 0.6) -> dict:
    """Richiede una citazione letterale non vuota nel frammento indicato.

    La soglia resta nell'interfaccia per compatibilita' con i chiamanti precedenti,
    ma una somiglianza approssimativa non costituisce una prova verificabile.
    """
    fid = normalizza_id(fid)
    if not fid:
        return {"valida": False, "motivo": "nessuna fonte indicata"}
    fonte = corso.fonti.get(fid)
    if fonte is None:
        return {"valida": False, "motivo": f"la fonte {fid} non esiste nel materiale"}
    if fonte.tipo not in tipi_ammessi:
        return {"valida": False, "motivo": f"{fonte.id} e' una {fonte.tipo}, non ammessa per questo studente"}
    citata = _normalizza(citazione or "")
    if len(citata) < 12 or len(citata.split()) < 2:
        return {"valida": False, "fonte": fonte.id,
                "motivo": "citazione assente o troppo breve per verificare il passo"}
    # Un titolo o un frammento vicino possono aiutare la ricerca, ma non sono
    # una prova che il minuto o la slide citati contengano proprio quelle parole.
    testo = _normalizza(fonte.testo)
    if citata not in testo:
        return {"valida": False, "fonte": fonte.id, "punteggio": 0.0,
                "motivo": f"il testo citato non compare letteralmente in {fonte.id}"}
    return {"valida": True, "fonte": fonte.id, "tipo": fonte.tipo, "lezione": fonte.lezione,
            "punteggio": 1.0}
