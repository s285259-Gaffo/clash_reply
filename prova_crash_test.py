"""Esegue il crash test da terminale e salva un registro completo (per il debug).
Uso: python prova_crash_test.py [nome_corso]     (default: analisi1_simulato)
Registro: materiale/<corso>/report/debug/ (risposte grezze degli agenti) e log_prova.txt
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
corso = sys.argv[1] if len(sys.argv) > 1 else "analisi1_simulato"
cartella = Path(__file__).parent / "materiale" / corso / "report"
cartella.mkdir(parents=True, exist_ok=True)
os.environ["DEBUG_DIR"] = str(cartella / "debug")

import fantasma  # noqa: E402

log = open(cartella / "log_prova.txt", "w", encoding="utf-8")
t0 = time.time()


def emit(ev):
    riga = f"[{time.time() - t0:6.1f}s] {ev.get('tipo')} {ev.get('id', '')} " \
           f"{(ev.get('messaggio') or ev.get('modello') or '')}".rstrip()
    print(riga, flush=True)
    log.write(riga + "\n")
    if ev.get("tipo") in ("agente_fine", "errore"):
        log.write(json.dumps(ev, ensure_ascii=False, default=str)[:6000] + "\n")
    if ev.get("tipo") == "lacune":
        r = ev["risultato"]
        sintesi = {k: r.get(k) for k in ("passi_totali", "passi_coperti_da_slide", "citazioni_scartate",
                                          "valutazione", "secondi", "file_report")}
        sintesi["lacune"] = [(g["tipo"], g.get("esercizio"), g.get("passo"), g.get("titolo")) for g in r["lacune"]]
        txt = json.dumps(sintesi, ensure_ascii=False, indent=1)
        print(txt)
        log.write(txt + "\n")
    log.flush()


try:
    print(f"Crash test del corso: {corso}\n")
    fantasma.esegui(corso, emit)
except Exception:
    log.write(traceback.format_exc())
    traceback.print_exc()
finally:
    log.close()
    print(f"\nRegistro salvato in: {cartella / 'log_prova.txt'}")
