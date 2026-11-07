"""Crea una pagina locale con lo stato delle prove e dei report salvati.

Uso: python visualizza_verifica.py [nome_corso]
La pagina e' una fotografia dei JSON presenti, non esegue chiamate API.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import fantasma
import materiale


def testo(valore) -> str:
    return html.escape(str(valore if valore is not None else "—"))


def pagina(nome_corso: str = "analisi1_simulato") -> Path:
    corso = materiale.carica_corso(nome_corso)
    cartella = corso.cartella / "report"
    cartella.mkdir(exist_ok=True)
    files = sorted(cartella.glob("mappa_lacune_*.json"), reverse=True)
    fixture = cartella / "demo_completa.json"
    if fixture.exists():
        files.append(fixture)
    tutti_esercizi = set(re.findall(r"(?im)^#{1,4}\s*Esercizio\s+(\d+)\b", corso.esame))

    sezioni = []
    for file in files:
        try:
            dati = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        demo = bool(dati.get("simulato") or file == fixture)
        analizzati = {str(fantasma._num_es(e.get("id"))) for e in
                      dati.get("brief", {}).get("esercizi", []) if fantasma._num_es(e.get("id"))}
        parziale = bool(tutti_esercizi and analizzati != tutti_esercizi)
        chiave = ([k for k in (corso.chiave or [])
                   if k.get("tipo") == "gialla" or
                   str(fantasma._num_es(k.get("esercizio_esame"))) in analizzati]
                  if parziale else corso.chiave)
        valutazione = fantasma.valuta(dati.get("lacune", []), chiave) or {}
        intestazione = ("Simulazione" if demo else "Esecuzione reale salvata") + " · " + file.name
        ambito = ("Confronto parziale: esercizi " + ", ".join(sorted(analizzati))
                  if parziale else "Confronto sull'intero esame")
        lacune = "".join(
            f"<tr><td>{testo(g.get('tipo'))}</td><td>{testo(g.get('esercizio'))}</td>"
            f"<td>{testo(g.get('passo'))}</td><td>{testo(g.get('titolo') or g.get('testo_passo'))}</td></tr>"
            for g in dati.get("lacune", []))
        mancanti = "".join(f"<li>{testo(x)}</li>" for x in valutazione.get("mancate", []))
        sezioni.append(f"""
        <section>
          <h2>{testo(intestazione)}</h2>
          <p><em>{testo(ambito)}</em></p>
          <p>Passi analizzati: <strong>{testo(dati.get('passi_totali'))}</strong> ·
             Lacune segnalate: <strong>{len(dati.get('lacune', []))}</strong> ·
             Precisione: <strong>{testo(valutazione.get('precision'))}</strong> ·
             Recall: <strong>{testo(valutazione.get('recall'))}</strong> ·
             Falso amico segnalato: <strong>{testo(valutazione.get('falso_amico_segnalato'))}</strong></p>
          <details><summary>Lacune segnalate</summary>
            <table><thead><tr><th>Tipo</th><th>Esercizio</th><th>Passo</th><th>Descrizione</th></tr></thead>
            <tbody>{lacune or '<tr><td colspan="4">Nessuna</td></tr>'}</tbody></table>
          </details>
          <details><summary>Lacune della chiave non trovate</summary>
            <ul>{mancanti or '<li>Nessuna</li>'}</ul>
          </details>
        </section>""")

    pagina_html = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Verifica crash test · {testo(nome_corso)}</title>
<style>
body {{ font: 16px/1.55 system-ui,sans-serif; margin: 0 auto; padding: 32px 20px; max-width: 1050px;
       color: #18212f; background: #f5f7fb; }}
h1 {{ margin-bottom: 4px; }} h2 {{ margin-top: 0; font-size: 1.25rem; }}
section {{ background: white; border: 1px solid #d8e0ea; border-radius: 12px; margin: 22px 0; padding: 24px;
           box-shadow: 0 2px 10px #1620360a; }}
.nota {{ background: #fff4d4; padding: 12px 16px; border-radius: 8px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }} th,td {{ text-align: left; padding: 8px;
       border-bottom: 1px solid #e5eaf0; vertical-align: top; }}
th {{ background: #edf2f8; }} details {{ margin-top: 14px; }} summary {{ cursor: pointer; font-weight: 600; }}
</style></head><body>
<h1>Verifica dei report · {testo(nome_corso)}</h1>
<p class="nota">I report gia' salvati sono precedenti ai nuovi controlli. La simulazione e' indicata a parte.
Per misurare i nuovi controlli serve una nuova esecuzione reale del crash test.</p>
{''.join(sezioni) or '<p>Nessun report salvato. Avvia il crash test e rigenera questa pagina.</p>'}
</body></html>"""
    destinazione = cartella / "verifica_guardrail.html"
    destinazione.write_text(pagina_html, encoding="utf-8")
    return destinazione


if __name__ == "__main__":
    print(pagina(sys.argv[1] if len(sys.argv) > 1 else "analisi1_simulato"))
