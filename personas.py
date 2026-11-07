"""
Quattro studenti, quattro voti ("collaudo degli unhappy path").

Invece di un solo studente fantasma, il crash test simula quattro profili cognitivi:
  frettoloso   ha saltato le videolezioni: studia solo sulle slide      (agente fantasma_slide)
  visivo       impara da formule, tabelle, elenchi; il testo denso no  (agente persona_visivo)
  mnemonico    sa le definizioni, ma calcola solo con un esempio simile (agente persona_mnemonico)
  applicativo  bravo nei calcoli, ricorda una regola solo se l'ha vista usata in un esempio
                                                                        (agente persona_applicativo)

Gli agenti LLM propongono una fonte per ogni passo; e' il CODICE che decide se quella fonte va bene
per quel profilo (la riga citata e' una formula/elenco? viene da un esempio svolto?) e calcola il voto
in trentesimi con i punti degli esercizi. Il modello non assegna voti.
"""
from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

import materiale

PERSONAS = [
    {"id": "frettoloso", "agente": "fantasma_slide", "icona": "\u26a1", "nome": "Lo studente frettoloso",
     "descrizione": "Ha saltato le videolezioni: ha studiato solo sulle slide.",
     "se": "si basa solo sulle slide"},
    {"id": "visivo", "agente": "persona_visivo", "icona": "\U0001f3a8", "nome": "Lo studente visivo",
     "descrizione": "Capisce formule, tabelle ed elenchi; il testo denso e il parlato gli scivolano via.",
     "se": "impara da formule e schemi e salta il testo denso"},
    {"id": "mnemonico", "agente": "persona_mnemonico", "icona": "\U0001f9e0", "nome": "Lo studente mnemonico",
     "descrizione": "Recita definizioni e regole alla perfezione, ma nei calcoli si blocca se non ha visto un esempio simile.",
     "se": "ha bisogno di esempi svolti per applicare la teoria"},
    {"id": "applicativo", "agente": "persona_applicativo", "icona": "\U0001f6e0\ufe0f", "nome": "Lo studente pratico",
     "descrizione": "Bravissimo nei calcoli, ma le definizioni pure non le ricorda: una regola gli resta solo se l'ha vista usata in un esempio.",
     "se": "impara facendo e non memorizza le definizioni"},
]
PER_ID = {p["id"]: p for p in PERSONAS}
SOGLIA_SUFFICIENZA = 18

_RE_TEORIA = re.compile(r"^\W*(\w+\W+){0,3}?(regola|limite notevole|limiti notevoli|formula|teorema|definizion|propriet|"
                        r"tabella|identit|linearit|criterio|enunciat)", re.IGNORECASE)
_RE_ESEMPIO = re.compile(r"esempi|eserciz|svolt|vediamo|facciamo|calcoliamo|proviamo|per esempio|ad esempio",
                         re.IGNORECASE)
_RE_MATH = re.compile(r"\$[^$]*\$")


# --------------------------------------------------------------------------- #
#  Proprieta' di un passo e di una fonte (decise in codice)
# --------------------------------------------------------------------------- #
def tipo_passo(passo: dict) -> str:
    """'teoria' (richiamare una regola/definizione) o 'applicazione' (calcolo).
    Usa il tipo scritto dall'analista; se manca, una regola sulle prime parole del passo."""
    t = str(passo.get("tipo", "")).strip().lower()
    if t in ("teoria", "applicazione"):
        return t
    return "teoria" if _RE_TEORIA.search(passo.get("testo", "")) else "applicazione"


def _righe(fonte: materiale.Fonte) -> list[str]:
    if fonte.tipo != "slide":
        return [fonte.testo]
    return [r.strip() for r in fonte.testo.splitlines() if r.strip()] or [fonte.titolo]


def riga_citata(fonte: materiale.Fonte, citazione: str | None) -> str:
    """La riga della fonte che contiene la citazione (la piu' simile)."""
    righe = _righe(fonte)
    if not citazione or len(righe) == 1:
        return righe[0]
    c = materiale._normalizza(citazione)
    return max(righe, key=lambda r: (c in materiale._normalizza(r),
                                     SequenceMatcher(None, c, materiale._normalizza(r)).ratio()))


def e_visiva(fonte: materiale.Fonte, riga: str) -> bool:
    """Formula, riga di tabella o voce di elenco breve. Il parlato delle lezioni non e' mai 'visivo'."""
    if fonte.tipo != "slide":
        return False
    if riga.count("|") >= 2:
        return True
    matematica = sum(len(m) for m in _RE_MATH.findall(riga))
    parole = re.findall(r"[A-Za-zÀ-ÿ]{2,}", _RE_MATH.sub(" ", riga))
    return len(parole) <= 12 or matematica >= 0.45 * max(1, len(riga))


def e_esempio(corso: materiale.Corso, fonte: materiale.Fonte, riga: str) -> bool:
    """La fonte mostra la regola APPLICATA: riga 'Esempio', slide di esercizi, o 'vediamo un esempio' a lezione."""
    if fonte.tipo == "slide":
        return bool(_RE_ESEMPIO.search(riga) or _RE_ESEMPIO.search(fonte.titolo))
    stessi = [f for f in corso.fonti.values() if f.tipo == "trascrizione" and f.lezione == fonte.lezione]
    i = next((k for k, f in enumerate(stessi) if f.id == fonte.id), 0)
    return bool(_RE_ESEMPIO.search(" ".join(f.testo for f in stessi[max(0, i - 1): i + 3])))


def esito(persona: str, corso, tipo: str, candidati: list) -> tuple[bool, str]:
    """candidati: [(Fonte, riga)] gia' verificati. Restituisce (ce la fa?, motivo se no)."""
    if not candidati:
        return False, "non trova questo passo nel materiale che ha studiato"
    if persona == "frettoloso":
        if any(f.tipo == "slide" for f, _ in candidati):
            return True, ""
        return False, "spiegato solo nelle videolezioni, che ha saltato"
    if persona == "visivo":
        if any(e_visiva(f, r) for f, r in candidati):
            return True, ""
        if all(f.tipo != "slide" for f, _ in candidati):
            return False, "spiegato solo a voce, senza una formula o uno schema"
        return False, "c'e' solo dentro testo discorsivo, senza formula, tabella o elenco"
    if persona == "mnemonico":
        if tipo == "teoria" or any(e_esempio(corso, f, r) for f, r in candidati):
            return True, ""
        return False, "nessun esempio svolto simile da imitare"
    if persona == "applicativo":
        if tipo == "applicazione" or any(e_esempio(corso, f, r) for f, r in candidati):
            return True, ""
        return False, "regola solo enunciata, mai mostrata applicata in un esempio"
    return False, "profilo sconosciuto"


# --------------------------------------------------------------------------- #
#  Voto in trentesimi
# --------------------------------------------------------------------------- #
def calcola_voto(brief: dict, esiti: dict) -> dict:
    """esiti: {(esercizio, passo): (ok, motivo)}. Ogni esercizio vale i suoi punti; un passo mancato
    toglie la sua quota dei punti dell'esercizio. Voto riportato a 30."""
    esercizi = [e for e in brief.get("esercizi", []) if e.get("passi")]
    if not esercizi:
        return {"voto": None, "esercizi": [], "motivi": []}
    def punti(e):
        try:
            return float(e.get("punti") or 0)
        except (TypeError, ValueError):
            return 0.0
    totale = sum(punti(e) for e in esercizi)
    if totale <= 0:  # punti non indicati: esercizi con lo stesso peso
        pesi = {str(e.get("id")): 30 / len(esercizi) for e in esercizi}
        totale = 30.0
    else:
        pesi = {str(e.get("id")): punti(e) for e in esercizi}
    ottenuti, righe, motivi, esempi = 0.0, [], Counter(), {}
    for e in esercizi:
        eid, passi = str(e.get("id")), e.get("passi", [])
        ok = 0
        for p in passi:
            k = (eid, str(p.get("n")))
            riuscito, motivo = esiti.get(k, (False, "passo non analizzato"))
            if riuscito:
                ok += 1
            else:
                motivi[motivo] += 1
                esempi.setdefault(motivo, f"Es. {eid}, passo {p.get('n')}: {p.get('testo', '')}"[:140])
        quota = pesi[eid] * ok / len(passi)
        ottenuti += quota
        righe.append({"esercizio": eid, "argomento": e.get("argomento", ""), "passi": len(passi), "riusciti": ok,
                      "punti": round(pesi[eid], 1), "punti_ottenuti": round(quota, 1)})
    voto = round(30 * ottenuti / totale)
    return {"voto": voto, "esercizi": righe,
            "motivi": [{"motivo": m, "passi": n, "esempio": esempi[m]} for m, n in motivi.most_common(3)]}


def assembla(brief: dict, esiti_per_persona: dict, simulato: bool = False) -> dict:
    """esiti_per_persona: {id_persona: {(es, passo): (ok, motivo)}} -> blocco 'personas' del risultato."""
    schede = []
    for p in PERSONAS:
        if p["id"] not in esiti_per_persona:
            continue
        v = calcola_voto(brief, esiti_per_persona[p["id"]])
        if v["voto"] is None:
            continue
        frase = f"Se un tuo studente {p['se']}, all'esame prenderebbe circa {v['voto']}/30"
        frase += "." if v["voto"] >= SOGLIA_SUFFICIENZA else ": non lo supererebbe."
        schede.append({**{k: p[k] for k in ("id", "icona", "nome", "descrizione")}, **v,
                       "superato": v["voto"] >= SOGLIA_SUFFICIENZA, "frase": frase})
    if not schede:
        return {}
    peggiore = min(schede, key=lambda s: s["voto"])
    migliore = max(schede, key=lambda s: s["voto"])
    return {"schede": schede, "titolo": peggiore["frase"],
            "divario": migliore["voto"] - peggiore["voto"], "simulato": simulato,
            "nota": ("Stima indicativa: ogni passo senza una fonte adatta a quel profilo toglie la sua quota "
                     "dei punti dell'esercizio. Il voto lo calcola il programma, non il modello.")
                    + (" In simulazione le fonti di ogni profilo sono cercate per parole chiave nel materiale, "
                       "partendo dall'esito reale del crash test." if simulato else "")}


# --------------------------------------------------------------------------- #
#  Esecuzione reale: dagli output (gia' verificati) degli agenti agli esiti
# --------------------------------------------------------------------------- #
def esiti_da_agenti(corso, brief: dict, indicizzati: dict) -> dict:
    """indicizzati: {id_agente: {(es, passo): passo_con__verifica}} come prodotto dal verificatore."""
    risultato = {}
    for p in PERSONAS:
        idx = indicizzati.get(p["agente"])
        if idx is None:
            continue
        esiti = {}
        for es in brief.get("esercizi", []):
            for passo in es.get("passi", []):
                k = (str(es.get("id")), str(passo.get("n")))
                x = idx.get(k, {})
                v = x.get("_verifica", {})
                candidati = []
                if v.get("valida") and v.get("fonte") in corso.fonti:
                    f = corso.fonti[v["fonte"]]
                    candidati.append((f, riga_citata(f, x.get("citazione"))))
                esiti[k] = esito(p["id"], corso, tipo_passo(passo), candidati)
        risultato[p["id"]] = esiti
    return risultato


# --------------------------------------------------------------------------- #
#  Simulazione (nessuna chiamata API): fonti cercate per parole chiave,
#  vincolate all'esito reale del crash test (slide / solo a voce / mai spiegato)
# --------------------------------------------------------------------------- #
_STOP = set("della delle dello degli dei del per con che una uno gli nel nella sulla sono come dove "
            "quando poi anche ogni questa questo valori valore risultato ottenere ottiene usare".split())


def _parole_chiave(testo: str) -> set:
    return {w for w in materiale._normalizza(testo).split() if len(w) >= 4 and w not in _STOP}


def candidati_ricerca(corso, testo_passo: str, stato: str) -> list:
    if stato == "mai":
        return []
    tipi = ("slide", "trascrizione") if stato == "slide" else ("trascrizione",)
    chiave = _parole_chiave(testo_passo)
    punteggi = []
    for f in corso.fonti.values():
        if f.tipo not in tipi:
            continue
        for r in _righe(f):
            parole = set(materiale._normalizza(r + (" " + f.titolo if f.tipo == "slide" else "")).split())
            n = len(chiave & parole)
            if n:
                punteggi.append((n, f, r))
    if not punteggi:
        return []
    migliore = max(n for n, _, _ in punteggi)
    soglia = max(1, 0.6 * migliore)
    scelti = sorted([x for x in punteggi if x[0] >= soglia], key=lambda x: -x[0])[:6]
    if stato == "slide" and not any(f.tipo == "slide" for _, f, _ in scelti):
        # il crash test reale ha trovato il passo nelle slide: tieni la riga di slide piu' vicina
        slide = [x for x in punteggi if x[1].tipo == "slide"]
        if slide:
            scelti.append(max(slide, key=lambda x: x[0]))
    return [(f, r) for _, f, r in scelti]


def esiti_simulati(corso, brief: dict, stato_passi: list) -> dict:
    stato = {(str(s.get("esercizio")), str(s.get("passo"))): s.get("stato") for s in stato_passi}
    risultato = {p["id"]: {} for p in PERSONAS}
    for es in brief.get("esercizi", []):
        for passo in es.get("passi", []):
            k = (str(es.get("id")), str(passo.get("n")))
            st = stato.get(k, "mai")
            candidati = candidati_ricerca(corso, passo.get("testo", ""), st)
            if not candidati and st != "mai":  # passo di puro calcolo ("Risultato ..."): cerca con l'argomento
                candidati = candidati_ricerca(corso, f"{passo.get('testo', '')} {es.get('argomento', '')}", st)
            tipo = tipo_passo(passo)
            for p in PERSONAS:
                if p["id"] == "frettoloso":  # e' esattamente il fantasma 'solo slide' del crash test reale
                    risultato["frettoloso"][k] = (True, "") if st == "slide" else esito("frettoloso", corso, tipo, candidati)
                else:
                    risultato[p["id"]][k] = esito(p["id"], corso, tipo, candidati)
    return risultato


def markdown(blocco: dict, solo: str | None = None) -> str:
    """Testo per la card di un agente (solo=id persona) o per il report."""
    out = []
    for s in blocco.get("schede", []):
        if solo and s["id"] != solo:
            continue
        out.append(f"**{s['icona']} {s['nome']}: {s['voto']}/30** {'✅' if s['superato'] else '❌'}")
        out += [f"- Es. {e['esercizio']}: {e['riusciti']}/{e['passi']} passi, {e['punti_ottenuti']}/{e['punti']} punti"
                for e in s["esercizi"]]
        if s["motivi"]:
            out.append("- Si blocca su: " + "; ".join(f"{m['motivo']} ({m['passi']} passi)" for m in s["motivi"]))
        out.append("")
    return "\n".join(out).strip()
