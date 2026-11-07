"""
Converte il materiale MIT OCW scaricato (materiale/mit_18-01_fall2006/*.txt)
nel formato letto da Studente Fantasma (materiale/mit_18-01_integrali/).

- appunti del docente: ogni pagina diventa una "slide" citabile
      ## Slide K — Appunti lezione N, pagina P
- trascrizioni (senza timestamp nell'originale): divise in blocchi di ~120 parole,
  con minuto STIMATO dal ritmo medio del parlato (~150 parole/minuto)
- esame e soluzioni copiati come testo

Uso:  python prepara_mit.py            (tutte le lezioni scaricate)
      python prepara_mit.py 18 19 20   (solo alcune lezioni, per un test piu' rapido)
"""
import json
import re
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent / "materiale"
ORIGINE = BASE / "mit_18-01_fall2006"
DESTINAZIONE = BASE / "mit_18-01_integrali"
PAROLE_PER_MINUTO = 150
PAROLE_PER_BLOCCO = 120


def pagine(testo: str) -> list[str]:
    parti = re.split(r"^=== Pagina \d+ ===\s*$", testo, flags=re.MULTILINE)
    return [p.strip() for p in parti if p.strip()]


def pulisci(t: str) -> str:
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def main():
    if not ORIGINE.exists():
        print(f"Non trovo {ORIGINE}. Prima esegui scarica_materiale_mit.bat")
        return
    scelte = {int(x) for x in sys.argv[1:] if x.isdigit()}
    DESTINAZIONE.mkdir(parents=True, exist_ok=True)
    slide_globale = 0
    lezioni_fatte = []

    for n in range(1, 40):
        if scelte and n not in scelte:
            continue
        appunti = ORIGINE / f"lezione{n}_appunti.txt"
        trascr = ORIGINE / f"lezione{n}_trascrizione.txt"
        if not appunti.exists() and not trascr.exists():
            continue
        lezioni_fatte.append(n)
        if appunti.exists():
            righe = []
            for p, testo in enumerate(pagine(appunti.read_text(encoding="utf-8", errors="replace")), 1):
                slide_globale += 1
                righe.append(f"## Slide {slide_globale} — Appunti lezione {n}, pagina {p}\n{pulisci(testo)}\n")
            (DESTINAZIONE / f"slide_lezione_{n:02d}.md").write_text("\n".join(righe), encoding="utf-8")
        if trascr.exists():
            testo = " ".join(pagine(trascr.read_text(encoding="utf-8", errors="replace")))
            parole = re.sub(r"\s+", " ", testo).split(" ")
            righe = []
            for i in range(0, len(parole), PAROLE_PER_BLOCCO):
                secondi = int(i / PAROLE_PER_MINUTO * 60)
                righe.append(f"[{secondi // 60:02d}:{secondi % 60:02d}] " + " ".join(parole[i:i + PAROLE_PER_BLOCCO]))
            (DESTINAZIONE / f"trascrizione_lezione_{n:02d}.md").write_text("\n".join(righe), encoding="utf-8")

    # esame e soluzioni: preferisci i file con testo vero (le scansioni danno .txt quasi vuoti)
    def migliore(pattern):
        candidati = [(p, len(p.read_text(encoding="utf-8", errors="replace").strip()))
                     for p in ORIGINE.glob(pattern)]
        candidati = [c for c in candidati if c[1] > 400]
        return max(candidati, key=lambda c: c[1])[0] if candidati else None

    esame = migliore("exam*[!l].txt") or migliore("*exam*.txt")
    soluzioni = migliore("*sol*.txt")
    if esame:
        (DESTINAZIONE / "esame.md").write_text(pulisci(esame.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
    if soluzioni:
        (DESTINAZIONE / "soluzioni.md").write_text(pulisci(soluzioni.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")

    (DESTINAZIONE / "brief_docente.md").write_text(
        "Corso reale: MIT 18.01 Single Variable Calculus (Fall 2006), docente David Jerison.\n"
        f"Lezioni incluse: {lezioni_fatte} (integrale definito e applicazioni).\n"
        "Studenti: primo anno, provenienze scolastiche diverse.\n"
        "Nota: il materiale e' in inglese; le trascrizioni originali non hanno i minuti, "
        "quelli indicati sono STIMATI dalla posizione nel testo (~150 parole/minuto).\n", encoding="utf-8")
    if (ORIGINE / "FONTE_E_LICENZA.md").exists():
        shutil.copy(ORIGINE / "FONTE_E_LICENZA.md", DESTINAZIONE / "FONTE_E_LICENZA.md")

    print(f"Fatto: {DESTINAZIONE}")
    print(f"  lezioni: {lezioni_fatte}  -  slide (pagine di appunti): {slide_globale}")
    print(f"  esame: {esame.name if esame else 'NON TROVATO (serve un .txt con testo)'}")
    print(f"  soluzioni: {soluzioni.name if soluzioni else 'NON TROVATE (scansione? serve OCR)'}")
    tot = sum(len(p.read_text(encoding='utf-8')) for p in DESTINAZIONE.glob('*.md'))
    print(f"  dimensione totale testo: {tot:,} caratteri" + ("  -> molto grande: prova con meno lezioni" if tot > 300_000 else ""))
    print(json.dumps({"lezioni": lezioni_fatte}, ensure_ascii=False))


if __name__ == "__main__":
    main()
