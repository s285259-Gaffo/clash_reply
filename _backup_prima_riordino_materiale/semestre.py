"""
Ciclo di miglioramento DURANTE il semestre (lato studente + lato docente).

  studente  --domanda-->  Tutor socratico (cita le fonti del corso, non risolve esercizi d'esame)
  studente  --"Non ho capito" (dove mi sono bloccato)-->  dubbi.json
  codice    --raggruppa per argomento + soglia di anonimato (>= 5 studenti distinti)-->
  Aggregatore dei dubbi  --gruppo + collegamento alla Mappa delle Lacune del crash test-->
  Consulente di intervento  --proposta mirata-->  docente: Approva / Modifica / Scarta
  approvato  -->  chiarimento + domanda di verifica visibili agli studenti  -->  risultati al docente

Guardrail IN CODICE (valgono anche in modalita' reale, con LLM):
  - anti-soluzione: le domande che chiedono di risolvere un esercizio d'esame vengono bloccate
    prima del modello, e la risposta del modello e' ricontrollata contro le soluzioni ufficiali;
  - fonti: il recupero delle fonti e' fatto in codice; le citazioni del modello che non sono tra
    le fonti recuperate vengono tolte; se non ci sono fonti il tutor lo dice e non inventa;
  - anonimato: il docente vede un gruppo solo con almeno SOGLIA_ANONIMATO studenti distinti,
    mai pseudonimi; gli esempi di dubbi sono ripuliti da possibili dati personali;
  - limite: 1 segnalazione "Non ho capito" per argomento per studente.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import threading
import time
import uuid
from collections import Counter
from pathlib import Path

import crew
import materiale

CORSO_DEFAULT = "analisi1_simulato"
SOGLIA_ANONIMATO = int(os.getenv("SOGLIA_ANONIMATO", "5"))
ISCRITTI = int(os.getenv("ISCRITTI_CORSO", "400"))
_LOCK = threading.RLock()

# --------------------------------------------------------------------------- #
#  Specifiche degli agenti (RUOLO / OBIETTIVO / CONOSCENZA / REGOLE / PROCEDURA / MEMORIA / FORMATO)
# --------------------------------------------------------------------------- #
SPEC_TUTOR = """RUOLO: Tutor socratico del corso, per gli studenti, durante il semestre.
OBIETTIVO: aiutare lo studente a capire un argomento del corso facendolo ragionare, partendo dal materiale del docente.
CONOSCENZA: SOLO i frammenti del corso forniti nel messaggio (slide [S12], minuti di videolezione [L3@41:20]). Nient'altro.
REGOLE:
- Ogni affermazione sul corso cita una fonte tra quelle fornite, con il suo ID tra parentesi quadre. Non inventare ID.
- Non risolvere esercizi d'esame o valutati, non dare risultati finali di esercizi: guida con domande.
- Se i frammenti non bastano, dillo chiaramente ("Nel materiale del corso non trovo...") e suggerisci di segnalare il dubbio al docente.
- Tono gentile, frasi brevi, italiano. Massimo 120 parole.
- Chiudi sempre con UNA domanda guida che faccia fare allo studente il passo successivo.
PROCEDURA: 1) leggi la domanda e i frammenti; 2) scegli i 2-3 frammenti piu' pertinenti; 3) spiega l'idea citandoli; 4) fai la domanda guida.
MEMORIA: nessuna tra una domanda e l'altra (ogni domanda e' indipendente); lo studente e' anonimo.
FORMATO DI USCITA: solo JSON {"testo": "...markdown con citazioni [ID]...", "fonti": ["S22","L3@51:30"], "domanda_guida": "...", "fonti_sufficienti": true}"""

SPEC_AGGREGATORE = """RUOLO: Aggregatore dei dubbi degli studenti.
OBIETTIVO: riassumere in modo neutro e anonimo cosa blocca gli studenti su un argomento.
CONOSCENZA: i dubbi anonimi gia' raggruppati dal codice (argomento, dove si sono bloccati, frasi brevi), le lacune del crash test.
REGOLE:
- Non riportare nomi, pseudonimi o dettagli che identificano qualcuno. Non citare frasi lunghe.
- Linguaggio neutro: descrivi il materiale, mai giudizi sul docente o sugli studenti.
- Il raggruppamento e la soglia di anonimato li decide il codice: tu non aggiungi ne' togli dubbi.
PROCEDURA: 1) trova il punto comune; 2) indica dove (slide/minuto) si concentrano i blocchi; 3) di' se coincide con la lacuna del crash test indicata.
MEMORIA: nessuna; lavori sul gruppo che ricevi.
FORMATO DI USCITA: solo JSON {"sintesi": "1-2 frasi", "punto_critico": "..."}"""

SPEC_CONSULENTE = """RUOLO: Consulente di intervento didattico, al servizio del docente.
OBIETTIVO: proporre un intervento piccolo e mirato (pochi minuti) che chiarisca il dubbio del gruppo, piu' un chiarimento scritto per gli studenti e una domanda di verifica.
CONOSCENZA: sintesi del gruppo di dubbi, fonti del corso pertinenti (con ID), lacuna del crash test se presente, numero della prossima lezione.
REGOLE:
- Non riscrivere la lezione al posto del docente: proponi, il docente decide (Approva / Modifica / Scarta).
- Linguaggio neutro, mai giudizi sul docente. Cita le fonti con [ID].
- L'esempio del chiarimento NON deve essere un esercizio dell'esame ne' la sua soluzione.
- La domanda di verifica e' a scelta multipla, 4 opzioni, una sola corretta, non e' un voto.
PROCEDURA: 1) individua il passaggio mancante; 2) scegli dove inserirlo (inizio della prossima lezione, slide da integrare); 3) scrivi un esempio nuovo e breve; 4) scrivi la domanda di verifica.
MEMORIA: le decisioni precedenti del docente su questo argomento (se scartato, non riproporre uguale).
FORMATO DI USCITA: solo JSON {"intervento": "...", "chiarimento": {"titolo": "...", "testo": "markdown"}, "quiz": {"domanda": "...", "opzioni": ["...","...","...","..."], "corretta": 0, "spiegazione": "..."}}"""

# --------------------------------------------------------------------------- #
#  Argomenti del corso simulato (scelta lato studente + raggruppamento lato docente)
# --------------------------------------------------------------------------- #
ARGOMENTI = [
    {"id": "limiti_notevoli", "titolo": "Limiti notevoli", "lezione": 1,
     "parole": ["limite", "notevole", "notevoli", "seno", "esponenziale", "forma", "indeterminata"]},
    {"id": "retta_tangente", "titolo": "Derivata e retta tangente", "lezione": 2,
     "parole": ["retta", "tangente", "pendenza", "coefficiente", "angolare", "derivata"]},
    {"id": "sostituzione_indefiniti", "titolo": "Integrazione per sostituzione (indefiniti)", "lezione": 3,
     "parole": ["sostituzione", "sostituire", "primitiva", "indefinito", "catena", "dt"]},
    {"id": "per_parti", "titolo": "Integrazione per parti", "lezione": 4,
     "parole": ["parti", "logaritmo", "derivare", "integrare", "fattore"]},
    {"id": "estremi_sostituzione", "titolo": "Sostituzione negli integrali definiti: cambio degli estremi",
     "lezione": 4,
     "parole": ["estremi", "estremo", "cambio", "cambiare", "sostituzione", "definito", "definiti", "variabile"],
     "fonti": ["S22", "S30", "S29", "L4@80:30"],
     "domande_guida": [
         "Se poni t = g(x) e x va da a a b, quali valori assume t quando x = a e quando x = b?",
         "Nella procedura di [S22] l'ultimo passo e' \"tornare alla variabile x\": in un integrale definito, che cosa potresti fare invece di tornare a x?",
     ],
     "nota_copertura": "Nel materiale la procedura di sostituzione si chiude con \"tornare alla variabile x\" [S22], "
                       "e gli integrali definiti si calcolano trovando una primitiva e valutandola agli estremi [S30]. "
                       "Il caso della sostituzione *dentro* un integrale definito e' nominato a lezione [L4@80:30] "
                       "ma non e' svolto: se resta il dubbio, premi **Non ho capito**, il docente lo vede in forma anonima."},
    {"id": "area_segno", "titolo": "Area con funzione che cambia segno", "lezione": 4,
     "parole": ["area", "segno", "negativa", "valore", "assoluto", "zeri", "spezzare"],
     "fonti": ["S28", "L4@49:15", "L4@52:30"],
     "domande_guida": ["Nell'intervallo, in quali punti la funzione vale zero? E tra quei punti e' sopra o sotto l'asse x?"]},
]
PER_ARG = {a["id"]: a for a in ARGOMENTI}

_STOP = set("""a ad al allo ai agli alla alle anche avere c che chi ci come con cosa cui da dal dallo dai dagli dalla dalle
de del dello dei degli della delle di dove e ed era fa fare gli ha hai ho i il in io la le lo li ma mi ne nel nello nei
negli nella nelle no non o per perche piu poi puo qua quale quali quando quanto quel quella quelle quelli quello questa
queste questi questo se si sia sono su sul sulla sulle sui tra tu tuo un una uno va vi viene vuol dire mio mia cioe
ok ciao grazie prof professoressa scusate scusa allora quindi esempio esattamente sempre ogni capito capisco non""".split())

_RICHIESTA_SOLUZIONE = re.compile(
    r"risolv\w*|soluzion\w*|svolg\w*|fammi\s+(l|il|lo|la|gli|le|un|una)?\s*'?\s*(esercizio|compito|integrale|limite|derivata)"
    r"|fai\s+tu|scrivimi\s+(i\s+)?passaggi|quanto\s+(fa|viene|vale)|qual\s*e'?\s+il\s+risultato|dammi\s+(il\s+)?risultato",
    re.IGNORECASE)
_FRASI_BLOCCO = re.compile(
    r"risolvimi|risolvetemi|svolgimi|dammi\s+la\s+soluzione|fammi\s+l\s*'?\s*esercizio|fammi\s+il\s+compito"
    r"|soluzione\s+dell\s*'?\s*(esame|appello|esercizio)", re.IGNORECASE)
_RIF_ESAME = re.compile(r"\b(esame|appello|compito|esercizio\s*\d|prova\s+scritta|valutat\w*)\b", re.IGNORECASE)
_SINONIMI = {"integrale": "int", "integrali": "int", "integrare": "int", "seno": "sin", "coseno": "cos",
             "pigreco": "pi", "greco": "pi", "logaritmo": "ln", "log": "ln", "radice": "sqrt", "quadro": "2",
             "cubo": "3", "mezzi": "2", "limite": "lim", "limiti": "lim", "tende": "to", "tendente": "to",
             "infinito": "infty"}
_RUMORE_LATEX = {"displaystyle", "frac", "left", "right", "dfrac", "mathrm", "quad", "calcolare", "data", "dato",
                 "usando", "seguenti", "scrivere", "calcolarne", "punti"}


# --------------------------------------------------------------------------- #
#  Utilita' testo
# --------------------------------------------------------------------------- #
def _tok(t: str) -> list[str]:
    return [w for w in materiale._normalizza(t).split() if len(w) >= 3 and w not in _STOP]


def _radice(w: str) -> str:
    return w[:5]


def _radici(t: str) -> set[str]:
    return {_radice(w) for w in _tok(t)}


def _tok_math(t: str) -> set[str]:
    """Token per confrontare con il testo d'esame: separa lettere e cifre, tiene sin/cos/pi/x."""
    t = materiale._normalizza(t.replace("^", " ").replace("/", " "))
    out = set()
    for w in re.findall(r"[a-z]+|\d+", t):
        w = _SINONIMI.get(w, w)
        if w in _STOP or w in _RUMORE_LATEX:
            continue
        out.add(w)
    return out


def _scrivi_json(p: Path, dati):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)  # scrittura atomica


def _leggi_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# --------------------------------------------------------------------------- #
#  Corso (cache) e persistenza
# --------------------------------------------------------------------------- #
_cache: dict[str, tuple[float, materiale.Corso, dict]] = {}


def corso(nome: str = CORSO_DEFAULT) -> tuple[materiale.Corso, dict]:
    """Corso + indice per la ricerca (df delle radici), ricaricato se i file cambiano."""
    cartella = materiale.CARTELLA_MATERIALE / nome
    firma = max((p.stat().st_mtime for p in cartella.glob("*.md")), default=0)
    if nome in _cache and _cache[nome][0] == firma:
        return _cache[nome][1], _cache[nome][2]
    c = materiale.carica_corso(nome)
    radici = {fid: _radici(f.titolo + " " + f.testo) for fid, f in c.fonti.items()}
    df = Counter(r for rs in radici.values() for r in rs)
    indice = {"radici": radici, "df": df, "n": len(radici), "esame": _voci_esame(c.esame),
              "soluzioni": [s for s in re.split(r"\n+", c.soluzioni) if s.strip().lower().startswith("passo")]}
    _cache[nome] = (firma, c, indice)
    return c, indice


def cartella_dati(nome: str = CORSO_DEFAULT) -> Path:
    return materiale.CARTELLA_MATERIALE / nome / "semestre"


FILE = ("dubbi", "segnalazioni", "chiarimenti", "verifiche")


def leggi(nome_corso: str, quale: str):
    p = cartella_dati(nome_corso) / f"{quale}.json"
    if not p.exists():
        reset(nome_corso)
    return _leggi_json(p, [] if quale != "segnalazioni" else {})


def scrivi(nome_corso: str, quale: str, dati):
    _scrivi_json(cartella_dati(nome_corso) / f"{quale}.json", dati)


def reset(nome_corso: str = CORSO_DEFAULT) -> dict:
    """Ripristina i dati di simulazione (seed_iniziale.json) - utile per registrare la demo."""
    with _LOCK:
        seed = _leggi_json(cartella_dati(nome_corso) / "seed_iniziale.json", {})
        for q in FILE:
            scrivi(nome_corso, q, seed.get(q, {} if q == "segnalazioni" else []))
        return {"ok": True, **{q: len(seed.get(q, [])) for q in FILE}}


# --------------------------------------------------------------------------- #
#  Recupero delle fonti (in codice, parole chiave pesate idf)
# --------------------------------------------------------------------------- #
def _frase_migliore(testo: str, radici_q: set[str], max_c: int = 220) -> str:
    righe = [r.strip(" -*") for r in re.split(r"(?<=[.!?])\s+|\n", testo) if r.strip(" -*")]
    if not righe:
        return testo[:max_c]
    migliore = max(righe, key=lambda r: len(_radici(r) & radici_q))
    return migliore if len(migliore) <= max_c else migliore[:max_c - 1] + "…"


def cerca_fonti(nome_corso: str, testo: str, lezione: int | None = None, k: int = 3) -> dict:
    c, ind = corso(nome_corso)
    q = _radici(testo)
    if not q:
        return {"fonti": [], "copertura": 0.0}
    punti = []
    for fid, rs in ind["radici"].items():
        comuni = q & rs
        if not comuni:
            continue
        s = sum(math.log(1 + ind["n"] / ind["df"][r]) for r in comuni)
        f = c.fonti[fid]
        if lezione and f.lezione == lezione:
            s *= 1.3
        if f.tipo == "slide":
            s *= 1.1
        punti.append((s, fid, comuni))
    punti.sort(reverse=True)
    top = punti[:k]
    if not top:
        return {"fonti": [], "copertura": 0.0}
    unione = set().union(*(x[2] for x in punti[:5]))
    copertura = len(unione) / len(q)
    migliore = len(top[0][2]) / len(q)
    sufficienti = copertura >= 0.5 and migliore >= 0.34
    fonti = [_fonte_dict(c.fonti[fid], q) for _, fid, _ in top] if sufficienti else []
    return {"fonti": fonti, "copertura": round(copertura, 2)}


_LATEX = {r"\int": "∫", r"\alpha": "α", r"\beta": "β", r"\to": "→", r"\infty": "∞", r"\pi": "π", r"\ge": "≥",
          r"\le": "≤", r"\neq": "≠", r"\Rightarrow": "⇒", r"\cdot": "·", r"\ln": "ln", r"\sin": "sin", r"\cos": "cos",
          r"\xi": "ξ", r"\Delta": "Δ", r"\big": "", r"\left": "", r"\right": "", r"\displaystyle": "", r"\,": " "}


def leggibile(t: str) -> str:
    """LaTeX semplice -> testo leggibile (per gli estratti mostrati nelle chip)."""
    for k, v in _LATEX.items():
        t = t.replace(k, v)
    t = re.sub(r"\\[d]?frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", t)
    t = re.sub(r"\\[a-zA-Z]+", "", t)
    return t.replace("$", "").replace("{", "").replace("}", "")


def _fonte_dict(f: materiale.Fonte, radici_q: set[str] | None = None) -> dict:
    return {"id": f.id, "tipo": f.tipo, "lezione": f.lezione, "titolo": leggibile(f.titolo),
            "testo": leggibile(f.testo[:600]), "estratto": leggibile(_frase_migliore(f.testo, radici_q or set()))}


def fonti_per_id(nome_corso: str, ids: list[str]) -> list[dict]:
    c, _ = corso(nome_corso)
    return [_fonte_dict(c.fonti[i]) for i in ids if i in c.fonti]


# --------------------------------------------------------------------------- #
#  Guardrail anti-soluzione (in codice)
# --------------------------------------------------------------------------- #
def _voci_esame(esame: str) -> list[dict]:
    voci = []
    for m in re.finditer(r"##\s*Esercizio\s+(\d+)[^\n]*\n(.*?)(?=\n##\s|\Z)", esame, re.S):
        n, corpo = m.group(1), m.group(2)
        parti = re.split(r"\n\s*\(([a-z])\)\s*", "\n" + corpo)
        if len(parti) > 1:
            for i in range(1, len(parti) - 1, 2):
                voci.append({"id": f"{n}{parti[i]}", "testo": parti[i + 1].strip(),
                             "token": _tok_math(parti[i + 1])})
        else:
            voci.append({"id": n, "testo": corpo.strip(), "token": _tok_math(corpo)})
    return voci


def controlla_confine(nome_corso: str, domanda: str) -> dict:
    """True se la domanda chiede di risolvere un esercizio d'esame / valutato."""
    _, ind = corso(nome_corso)
    qt = _tok_math(domanda)
    migliore, sim, comuni, coperto = None, 0.0, 0, 0.0
    for v in ind["esame"]:
        if not v["token"]:
            continue
        comuni_v = qt & v["token"]
        inter = len(comuni_v)
        # solo cifre e 'x' non bastano: servono almeno 2 token "parlanti" in comune (sin, int, pi, retta...)
        if sum(1 for w in comuni_v if len(w) >= 2 and not w.isdigit()) < 2:
            continue
        s = inter / math.sqrt(len(v["token"]) * max(1, len(qt)))  # coseno tra insiemi di token
        if s > sim:
            migliore, sim, comuni, coperto = v, s, inter, inter / len(v["token"])
    chiede = bool(_RICHIESTA_SOLUZIONE.search(domanda))
    blocco = bool(_FRASI_BLOCCO.search(domanda))
    rif = bool(_RIF_ESAME.search(domanda))
    simile = sim >= 0.5 and comuni >= 4 and coperto >= 0.6
    simile_debole = sim >= 0.3 and comuni >= 3
    if blocco:
        motivo = "richiesta esplicita di una soluzione"
    elif simile:
        motivo = f"testo molto simile all'esercizio {migliore['id']} dell'esame"
    elif chiede and (simile_debole or rif):
        motivo = "richiesta di soluzione di un esercizio d'esame o valutato"
    else:
        return {"blocca": False, "somiglianza": round(sim, 2)}
    return {"blocca": True, "motivo": motivo, "somiglianza": round(sim, 2),
            "esercizio": migliore["id"] if migliore and (simile or simile_debole) else None,
            "testo_esercizio": migliore["testo"] if migliore and (simile or simile_debole) else ""}


def _seq_math(t: str) -> list[str]:
    t = materiale._normalizza(t.replace("^", " ").replace("/", " "))
    return [w for w in (_SINONIMI.get(x, x) for x in re.findall(r"[a-z]+|\d+", t))
            if w not in _STOP and w not in _RUMORE_LATEX]


def _trigrammi(seq: list[str]) -> set[tuple]:
    """Trigrammi con almeno un numero: i dati specifici dell'esercizio (x0 generico non conta)."""
    unito = []
    for w in seq:
        if w == "0" and unito and unito[-1] == "x":
            unito[-1] = "x0"
        else:
            unito.append(w)
    return {tuple(unito[i:i + 3]) for i in range(len(unito) - 2) if any(w.isdigit() for w in unito[i:i + 3])}


def _contiene_soluzione(nome_corso: str, risposta: str) -> bool:
    """Controllo a valle: il testo non deve ricalcare i passi delle soluzioni ufficiali
    (confronto di sequenze di 3 token, cosi' simboli comuni come x, 0, cos non bastano)."""
    _, ind = corso(nome_corso)
    rt = _trigrammi(_seq_math(risposta))
    for passo in ind["soluzioni"]:
        pt = _trigrammi(_seq_math(re.sub(r"^passo\s*\d+\s*:", "", passo, flags=re.I)))
        if len(pt) >= 4 and len(pt & rt) / len(pt) >= 0.5:
            return True
    return False


# --------------------------------------------------------------------------- #
#  Tutor
# --------------------------------------------------------------------------- #
def _argomento_da_testo(testo: str) -> str | None:
    r = _radici(testo)
    punti = [(len(r & {_radice(p) for p in a["parole"]}), a["id"]) for a in ARGOMENTI]
    punti.sort(reverse=True)
    return punti[0][1] if punti and punti[0][0] >= 2 else None


def _domanda_guida(arg_id: str | None, fonti: list[dict], seme: str) -> str:
    a = PER_ARG.get(arg_id or "")
    if a and a.get("domande_guida"):
        lista = a["domande_guida"]
        return lista[sum(map(ord, seme)) % len(lista)]
    if fonti:
        return f"Rileggi [{fonti[0]['id']}]: quale passaggio ti blocca, e che cosa ti aspetteresti di fare dopo?"
    return "Quale parte dell'argomento ti e' meno chiara?"


def _cita(f: dict) -> str:
    if f["tipo"] == "slide":
        return f"[{f['id']}] (Lezione {f['lezione']}, «{f['titolo']}»)"
    return f"[{f['id']}] (videolezione {f['lezione']}, minuto {f['id'].split('@')[1]})"


def rispondi(nome_corso: str, domanda: str, argomento: str | None = None) -> dict:
    domanda = (domanda or "").strip()[:800]
    if len(domanda) < 4:
        return {"tipo": "errore", "testo": "Scrivi una domanda un po' piu' lunga."}
    a = PER_ARG.get(argomento or "")
    lezione = a["lezione"] if a else None

    # 1) guardrail anti-soluzione, PRIMA di qualsiasi modello
    confine = controlla_confine(nome_corso, domanda)
    if confine["blocca"]:
        base = domanda + " " + confine.get("testo_esercizio", "")
        definito = re.search(r"int_|integrale\s+da\s+\S+\s+a\s", base, re.I)  # integrale con estremi
        arg_es = _argomento_da_testo(base + (" definito estremi" if definito else ""))
        if not confine.get("esercizio") and not arg_es:
            arg_es = argomento
        if arg_es and PER_ARG[arg_es].get("fonti"):
            trovate = fonti_per_id(nome_corso, PER_ARG[arg_es]["fonti"][:3])
        else:
            trovate = cerca_fonti(nome_corso, base + " " + " ".join(PER_ARG.get(arg_es or "", {}).get("parole", [])),
                                  PER_ARG.get(arg_es or "", {}).get("lezione", lezione), k=3)["fonti"]
        es = f" (somiglia all'**Esercizio {confine['esercizio']}** dell'appello)" if confine.get("esercizio") else ""
        rivedi = ", ".join(_cita(f) for f in trovate) or "le slide della lezione dell'argomento"
        testo = (f"Questa richiesta e' un esercizio d'esame o valutato{es}: **non posso risolverlo al posto tuo**, "
                 f"ma posso aiutarti a ragionarci.\n\nDa rivedere prima di riprovare: {rivedi}.")
        return {"tipo": "confine", "testo": testo, "fonti": trovate, "motivo": confine["motivo"],
                "domanda_guida": _domanda_guida(arg_es, trovate, domanda), "modalita": _modalita()}

    # 2) recupero delle fonti in codice
    ricerca = cerca_fonti(nome_corso, domanda, lezione, k=3)
    fonti = ricerca["fonti"]
    if not fonti:
        return {"tipo": "non_trovato", "fonti": [], "copertura": ricerca["copertura"], "modalita": _modalita(),
                "testo": "Nel materiale del corso non trovo questo argomento, quindi non ti rispondo a memoria "
                         "per non rischiare di dirti cose diverse da quelle del corso. "
                         "Vuoi inviare il dubbio al docente? Lo vede in forma anonima.",
                "domanda_guida": ""}
    arg_testo = _argomento_da_testo(domanda)  # argomento riconosciuto dal testo (>= 2 parole chiave)
    arg_q = arg_testo or (argomento if a and (_radici(domanda) & {_radice(p) for p in a["parole"]}) else None)

    # 3) risposta: LLM in modalita' reale, template in modalita' simulata
    if not crew.modalita_demo():
        try:
            return _rispondi_llm(nome_corso, domanda, fonti, arg_q)
        except Exception as e:  # noqa: BLE001 - se il modello fallisce, risposta da template
            print(f"[semestre] tutor LLM non disponibile: {str(e)[:120]}")
    modalita = _modalita() if crew.modalita_demo() else "riserva (template, LLM non disponibile)"
    righe = ["Nel corso questo punto e' trattato qui:"]
    for f in fonti[:3]:
        righe.append(f"- {_cita(f)}: «{f['estratto']}»")
    nota = PER_ARG.get(arg_testo or "", {}).get("nota_copertura")
    if nota:
        citati = re.findall(r"\[([SL][^\]]+)\]", nota)
        fonti = fonti + [f for f in fonti_per_id(nome_corso, citati) if f["id"] not in {x["id"] for x in fonti}]
        righe.append("\n" + nota)
    else:
        righe.append(f"\nParti da [{fonti[0]['id']}] e prova a rifare il ragionamento con parole tue.")
    return {"tipo": "risposta", "testo": "\n".join(righe), "fonti": fonti,
            "domanda_guida": _domanda_guida(arg_testo, fonti, domanda), "modalita": modalita}


def _modalita() -> str:
    return "simulata" if crew.modalita_demo() else "reale"


def _chiama_llm(spec: str, utente: str) -> dict:
    from fantasma import estrai_json
    llm = crew.crea_llm_con_riserva(lambda e: None)
    risposta = llm.call([{"role": "system", "content": spec + "\nRispondi sempre in italiano."},
                         {"role": "user", "content": utente}])
    dati = estrai_json(risposta)
    if not isinstance(dati, dict):
        raise ValueError("JSON non e' un oggetto")
    return dati


def _rispondi_llm(nome_corso, domanda, fonti, arg_q) -> dict:
    blocchi = "\n\n".join(f"[{f['id']}] ({f['tipo']}, lezione {f['lezione']}) {f['titolo']}\n{f['testo']}" for f in fonti)
    dati = _chiama_llm(SPEC_TUTOR, f"Domanda dello studente: {domanda}\n\nFrammenti del corso:\n{blocchi}")
    testo = str(dati.get("testo", "")).strip()
    ammessi = {f["id"] for f in fonti}
    # guardrail sulle citazioni: via gli ID non recuperati
    testo = re.sub(r"\[([^\]]+)\]", lambda m: m.group(0) if materiale.normalizza_id(m.group(1)) in ammessi else "", testo)
    if _contiene_soluzione(nome_corso, testo):
        return {"tipo": "confine", "fonti": fonti, "motivo": "la risposta ricalcava una soluzione ufficiale",
                "testo": "Questa risposta conterrebbe i passaggi di una soluzione d'esame: **non posso dartela**. "
                         "Rivedi " + ", ".join(_cita(f) for f in fonti) + ".",
                "domanda_guida": _domanda_guida(arg_q, fonti, domanda), "modalita": "reale"}
    if not dati.get("fonti_sufficienti", True) or not testo:
        return {"tipo": "non_trovato", "fonti": fonti, "modalita": "reale",
                "testo": "Nel materiale del corso non trovo abbastanza per rispondere. Vuoi inviare il dubbio al docente?"}
    return {"tipo": "risposta", "testo": testo, "fonti": fonti, "modalita": "reale",
            "domanda_guida": str(dati.get("domanda_guida") or _domanda_guida(arg_q, fonti, domanda))}


# --------------------------------------------------------------------------- #
#  Dubbi ("Non ho capito")
# --------------------------------------------------------------------------- #
_RE_PSEUDO = re.compile(r"^[a-z]{3,10}-[a-z0-9]{4,12}$")


def segnala_dubbio(nome_corso: str, pseudonimo: str, argomento: str, dove: str, testo: str = "") -> dict:
    if not _RE_PSEUDO.match(pseudonimo or ""):
        return {"ok": False, "errore": "pseudonimo non valido"}
    if argomento not in PER_ARG:
        return {"ok": False, "errore": "argomento sconosciuto"}
    dove = (dove or "").strip()[:120]
    if len(dove) < 2:
        return {"ok": False, "errore": "Indica dove ti sei bloccato (slide, minuto o una frase breve)."}
    with _LOCK:
        dubbi = leggi(nome_corso, "dubbi")
        if any(d["pseudonimo"] == pseudonimo and d["argomento"] == argomento for d in dubbi):
            return {"ok": False, "errore": "Hai gia' segnalato un dubbio su questo argomento (max 1 per argomento)."}
        dubbi.append({"id": uuid.uuid4().hex[:8], "pseudonimo": pseudonimo, "argomento": argomento,
                      "dove": dove, "testo": (testo or "").strip()[:300], "ts": int(time.time()), "simulato": False})
        scrivi(nome_corso, "dubbi", dubbi)
    return {"ok": True}


def miei(nome_corso: str, pseudonimo: str) -> dict:
    dubbi = leggi(nome_corso, "dubbi")
    ver = leggi(nome_corso, "verifiche")
    return {"segnalati": sorted({d["argomento"] for d in dubbi if d["pseudonimo"] == pseudonimo}),
            "verifiche": {v["chiarimento"]: v["risposta"] for v in ver if v["pseudonimo"] == pseudonimo}}


_RE_ANCORA = re.compile(r"\b(?:slide\s*(\d+)|s(\d+))\b|\bl(\d+)\s*(?:@|minuto|min\.?)?\s*(\d{1,2}:\d{2})|\bminut\w*\s*(\d{1,2}(?::\d{2})?)",
                        re.IGNORECASE)


def _ancore(dove: str) -> list[str]:
    out = []
    for m in _RE_ANCORA.finditer(dove):
        if m.group(1) or m.group(2):
            out.append(f"S{int(m.group(1) or m.group(2))}")
        elif m.group(3):
            out.append(f"L{m.group(3)}@{m.group(4)}")
        elif m.group(5):
            out.append(f"minuto {m.group(5)}")
    return out


def _anonimizza(t: str) -> str:
    t = re.sub(r"\S+@\S+", "[email]", t)
    t = re.sub(r"\b\d{5,}\b", "[numero]", t)
    t = re.sub(r"\b([Mm]i chiamo|[Ss]ono|[Ii]o sono)\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)?", r"\1 [nome]", t)
    return t[:140]


# --------------------------------------------------------------------------- #
#  Lato docente: gruppi, collegamento alla Mappa delle Lacune, proposte
# --------------------------------------------------------------------------- #
ETICHETTE = {"rossa": "\U0001f534 mai spiegato", "verde": "\U0001f7e2 solo a voce",
             "gialla": "\U0001f7e1 fuori ordine", "prerequisito": "\U0001f535 prerequisito dato per scontato"}


def _lacune_crash_test(c: materiale.Corso) -> list[dict]:
    try:
        import fantasma
        r = fantasma._ultimo_report(c)
    except Exception:  # noqa: BLE001
        r = None
    return (r or {}).get("lacune", [])


def collega_lacuna(c: materiale.Corso, arg: dict) -> dict | None:
    """Abbinamento per parole chiave tra l'argomento del gruppo e le lacune del crash test."""
    chiave = {_radice(p) for p in arg["parole"]} | _radici(arg["titolo"])
    migliore, punti = None, 0
    for g in _lacune_crash_test(c):
        if g.get("tipo") not in ETICHETTE or g.get("revisione") in ("falso_allarme",):
            continue
        testo = " ".join([str(g.get("titolo", "")), str(g.get("testo_passo", "")), str(g.get("perche_conta", ""))]
                         + [str(e.get("citazione", "")) for e in g.get("evidenza", []) or []])
        p = len(chiave & _radici(testo))
        if p > punti:
            migliore, punti = g, p
    if not migliore or punti < 2:
        return None
    return {"titolo": migliore.get("titolo"), "tipo": migliore.get("tipo"), "chiave": migliore.get("chiave"),
            "etichetta": ETICHETTE.get(migliore.get("tipo"), migliore.get("tipo")),
            "evidenza": migliore.get("evidenza") or [], "punteggio": punti}


def _gruppi(nome_corso: str) -> dict[str, list[dict]]:
    """Raggruppa per argomento scelto; i dubbi senza argomento valido vanno per parole chiave."""
    gruppi: dict[str, list[dict]] = {}
    for d in leggi(nome_corso, "dubbi"):
        arg = d["argomento"] if d["argomento"] in PER_ARG else _argomento_da_testo(d["dove"] + " " + d.get("testo", ""))
        if arg:
            gruppi.setdefault(arg, []).append(d)
    return gruppi


def _proposta_mock(nome_corso: str, arg: dict, dubbi: list[dict], lacuna: dict | None, prossima: int) -> dict:
    c, _ = corso(nome_corso)
    if arg["id"] == "estremi_sostituzione":
        return {
            "intervento": f"Dedicare circa 5 minuti all'inizio della Lezione {prossima} al cambio degli estremi "
                          "nella sostituzione per integrali definiti. Si puo' riprendere la procedura di [S22], che "
                          "oggi si chiude con \"tornare alla variabile x\", e affiancarle la variante per i definiti: "
                          "trasformare gli estremi con t = g(x) e non tornare piu' a x, ricordando lo scambio degli "
                          "estremi con cambio di segno di [S29]. Esempio proposto (non d'esame): "
                          "∫₀^{π/2} cos x · e^{sin x} dx con t = sin x. Eventualmente aggiungere un punto alla Slide 22 "
                          "o una slide dopo la Slide 31.",
            "chiarimento": {
                "titolo": "Sostituzione negli integrali definiti: cosa fare con gli estremi",
                "testo": "Quando usi la sostituzione **t = g(x)** in un integrale definito da *a* a *b* hai due strade, "
                         "entrambe corrette:\n\n"
                         "1. **Cambi anche gli estremi**: quando x = a, t vale g(a); quando x = b, t vale g(b). "
                         "Integri in t tra g(a) e g(b) e **non torni piu' a x**.\n"
                         "2. **Torni a x** come nella procedura di [S22] e valuti la primitiva agli estremi originali, "
                         "come in [S30].\n\n"
                         "**Esempio** ∫₀^{π/2} cos x · e^{sin x} dx, con t = sin x, dt = cos x dx.\n"
                         "Estremi: x = 0 → t = sin 0 = 0; x = π/2 → t = sin(π/2) = 1.\n"
                         "Diventa ∫₀¹ e^t dt = [e^t]₀¹ = e − 1.\n\n"
                         "Se il nuovo estremo inferiore e' piu' grande del superiore va bene lo stesso: "
                         "puoi scambiarli cambiando segno [S29].",
                "fonti": ["S22", "S29", "S30", "L4@80:30"]},
            "quiz": {"domanda": "Vuoi calcolare ∫₁² 2x·cos(x²) dx con t = x² e integrare direttamente in t, senza "
                                "tornare a x. Tra quali estremi integri in t?",
                     "opzioni": ["da 1 a 2", "da 1 a 4", "da 0 a 4", "da 1 a √2"], "corretta": 1,
                     "spiegazione": "Gli estremi si trasformano con t = x²: x = 1 → t = 1, x = 2 → t = 4. "
                                    "Lasciare 1 e 2 e' corretto solo se torni alla variabile x."}}
    # proposta generica, costruita dalle fonti recuperate in codice
    fonti = cerca_fonti(nome_corso, " ".join(arg["parole"]), arg["lezione"], k=2)["fonti"]
    ids = ", ".join(f"[{f['id']}]" for f in fonti) or "le slide della lezione"
    return {"intervento": f"Dedicare qualche minuto all'inizio della Lezione {prossima} a «{arg['titolo']}», "
                          f"riprendendo {ids} con un esempio svolto nuovo.",
            "chiarimento": {"titolo": arg["titolo"], "testo": f"Ripassa {ids}. (Chiarimento da completare a cura del docente.)",
                            "fonti": [f["id"] for f in fonti]},
            "quiz": None}


def _proposta_llm(nome_corso, arg, dubbi, lacuna, prossima) -> dict:
    fonti = cerca_fonti(nome_corso, " ".join(arg["parole"]), arg["lezione"], k=4)["fonti"]
    esempi = [_anonimizza(d["dove"] + (" - " + d["testo"] if d.get("testo") else "")) for d in dubbi[:8]]
    sintesi = _chiama_llm(SPEC_AGGREGATORE, json.dumps({"argomento": arg["titolo"], "dubbi": esempi,
                                                        "lacuna_crash_test": lacuna}, ensure_ascii=False))
    blocchi = "\n".join(f"[{f['id']}] {f['titolo']} {f['testo'][:400]}" for f in fonti)
    p = _chiama_llm(SPEC_CONSULENTE, f"Gruppo: {arg['titolo']} ({len(dubbi)} studenti)\nSintesi: {json.dumps(sintesi, ensure_ascii=False)}\n"
                                     f"Lacuna del crash test: {json.dumps(lacuna, ensure_ascii=False)}\n"
                                     f"Prossima lezione: {prossima}\nFonti:\n{blocchi}")
    q = p.get("quiz") or {}
    if not (isinstance(q.get("opzioni"), list) and len(q["opzioni"]) >= 2 and 0 <= int(q.get("corretta", -1)) < len(q["opzioni"])):
        p["quiz"] = None
    ch = p.get("chiarimento") or {}
    ch["fonti"] = re.findall(r"\[([SL][^\]]+)\]", ch.get("testo", "")) or [f["id"] for f in fonti]
    p["chiarimento"] = ch
    if _contiene_soluzione(nome_corso, ch.get("testo", "")):  # mai pubblicare soluzioni d'esame agli studenti
        raise ValueError("il chiarimento ricalca una soluzione d'esame")
    p["sintesi"] = sintesi.get("sintesi")
    return p


def vista_docente(nome_corso: str = CORSO_DEFAULT) -> dict:
    c, _ = corso(nome_corso)
    prossima = max(f.lezione for f in c.fonti.values()) + 1
    with _LOCK:
        segn = leggi(nome_corso, "segnalazioni")
        chiar = {x["id"]: x for x in leggi(nome_corso, "chiarimenti")}
        ver = leggi(nome_corso, "verifiche")
        visibili, in_attesa, modificato = [], [], False
        gruppi = _gruppi(nome_corso)
        for arg_id in set(gruppi) | set(segn):
            arg = PER_ARG[arg_id]
            dubbi = gruppi.get(arg_id, [])
            studenti = len({d["pseudonimo"] for d in dubbi})
            s = segn.get(arg_id)
            if studenti < SOGLIA_ANONIMATO and not (s and s.get("n_studenti", 0) >= SOGLIA_ANONIMATO):
                if studenti:
                    in_attesa.append({"argomento": arg_id, "titolo": arg["titolo"], "n": studenti})
                continue
            lacuna = collega_lacuna(c, arg)
            if s is None:
                try:
                    if crew.modalita_demo():
                        raise RuntimeError("simulata")
                    prop = _proposta_llm(nome_corso, arg, dubbi, lacuna, prossima)
                    origine = "reale"
                except Exception:  # noqa: BLE001
                    prop, origine = _proposta_mock(nome_corso, arg, dubbi, lacuna, prossima), "simulata"
                s = {"stato": "proposta", "proposta": prop, "origine": origine, "creata": int(time.time())}
                segn[arg_id] = s
                modificato = True
            if s.get("stato") == "proposta":
                s["n_studenti"] = studenti
            ancore = Counter(a for d in dubbi for a in _ancore(d["dove"]))
            parole = Counter(w for d in dubbi for w in set(_tok(d["dove"] + " " + d.get("testo", "")))
                             if w not in {"slide", "minuto", "lezione"})
            esempi = [_anonimizza(d.get("testo") or d["dove"]) for d in dubbi if (d.get("testo") or d["dove"])][:3]
            n = s.get("n_studenti", studenti)
            certezza = "alta" if lacuna and n >= 8 else ("media" if lacuna or n >= 8 else "bassa")
            ch = chiar.get(s.get("chiarimento", ""))
            risultati = None
            if ch:
                r = [v for v in ver if v["chiarimento"] == ch["id"]]
                corr = sum(1 for v in r if v.get("corretta"))
                risultati = {"risposte": len(r), "corrette": corr,
                             "percentuale": round(100 * corr / len(r)) if r else None}
            fonti_ev = fonti_per_id(nome_corso, (s.get("proposta", {}).get("chiarimento", {}) or {}).get("fonti", [])[:4])
            visibili.append({
                "argomento": arg_id, "titolo": arg["titolo"], "lezione": arg["lezione"],
                "n_studenti": n, "iscritti": ISCRITTI, "n_dubbi": len(dubbi),
                "dove": [{"ancora": k, "n": v} for k, v in ancore.most_common(4)],
                "parole_chiave": [w for w, _ in parole.most_common(5)],
                "esempi": esempi, "lacuna": lacuna, "certezza": certezza, "fonti": fonti_ev,
                "stato": s.get("stato"), "proposta": s.get("proposta"), "origine": s.get("origine", "simulata"),
                "nota_docente": s.get("nota", ""), "chiarimento": ch, "risultati": risultati})
        if modificato:
            scrivi(nome_corso, "segnalazioni", segn)
    ordine = {"proposta": 0, "approvata": 1, "scartata": 2}
    visibili.sort(key=lambda g: (ordine.get(g["stato"], 3), -g["n_studenti"]))
    return {"gruppi": visibili, "in_attesa": in_attesa, "soglia": SOGLIA_ANONIMATO, "iscritti": ISCRITTI,
            "modalita": _modalita(), "ha_report": bool(_lacune_crash_test(c))}


def decidi(nome_corso: str, argomento: str, azione: str, testo: str = "", nota: str = "") -> dict:
    if azione not in ("approva", "modifica", "scarta", "riapri"):
        return {"ok": False, "errore": "azione non valida"}
    with _LOCK:
        segn = leggi(nome_corso, "segnalazioni")
        s = segn.get(argomento)
        if not s:
            return {"ok": False, "errore": "nessuna proposta per questo argomento"}
        if azione == "scarta":
            s["stato"], s["nota"] = "scartata", nota[:300]
        elif azione == "riapri":
            s["stato"] = "proposta"
        else:
            prop = s["proposta"]
            ch = dict(prop.get("chiarimento") or {})
            if azione == "modifica" and testo.strip():
                ch["testo"] = testo.strip()[:4000]
            if _contiene_soluzione(nome_corso, ch.get("testo", "")):
                return {"ok": False, "errore": "Il testo contiene i passaggi di una soluzione d'esame: non viene pubblicato."}
            chiar = leggi(nome_corso, "chiarimenti")
            cid = s.get("chiarimento") or f"ch-{uuid.uuid4().hex[:6]}"
            chiar = [x for x in chiar if x["id"] != cid]
            chiar.append({"id": cid, "argomento": argomento, "titolo": ch.get("titolo", PER_ARG[argomento]["titolo"]),
                          "testo": ch.get("testo", ""), "fonti": ch.get("fonti", []), "quiz": prop.get("quiz"),
                          "approvato": int(time.time()), "modificato_dal_docente": azione == "modifica",
                          "simulato": False})
            scrivi(nome_corso, "chiarimenti", chiar)
            s["stato"], s["chiarimento"] = "approvata", cid
        segn[argomento] = s
        scrivi(nome_corso, "segnalazioni", segn)
    return {"ok": True, "stato": s["stato"]}


# --------------------------------------------------------------------------- #
#  Lato studente: chiarimenti + domanda di verifica
# --------------------------------------------------------------------------- #
def chiarimenti_studente(nome_corso: str, pseudonimo: str = "") -> list[dict]:
    mie = {v["chiarimento"]: v for v in leggi(nome_corso, "verifiche") if v["pseudonimo"] == pseudonimo}
    out = []
    for ch in sorted(leggi(nome_corso, "chiarimenti"), key=lambda x: -x.get("approvato", 0)):
        q = ch.get("quiz")
        quiz = None
        if q:
            quiz = {"domanda": q["domanda"], "opzioni": q["opzioni"]}
            if ch["id"] in mie:  # la risposta giusta si vede solo dopo aver risposto
                quiz.update(corretta=q["corretta"], spiegazione=q.get("spiegazione", ""), mia=mie[ch["id"]]["risposta"])
        out.append({"id": ch["id"], "argomento": ch["argomento"], "titolo": ch["titolo"],
                    "argomento_titolo": PER_ARG.get(ch["argomento"], {}).get("titolo", ""),
                    "testo": ch["testo"], "fonti": fonti_per_id(nome_corso, ch.get("fonti", [])), "quiz": quiz})
    return out


def rispondi_verifica(nome_corso: str, pseudonimo: str, chiarimento: str, risposta: int) -> dict:
    if not _RE_PSEUDO.match(pseudonimo or ""):
        return {"ok": False, "errore": "pseudonimo non valido"}
    with _LOCK:
        ch = next((x for x in leggi(nome_corso, "chiarimenti") if x["id"] == chiarimento), None)
        if not ch or not ch.get("quiz"):
            return {"ok": False, "errore": "chiarimento non trovato"}
        q = ch["quiz"]
        if not 0 <= risposta < len(q["opzioni"]):
            return {"ok": False, "errore": "risposta non valida"}
        ver = leggi(nome_corso, "verifiche")
        gia = next((v for v in ver if v["pseudonimo"] == pseudonimo and v["chiarimento"] == chiarimento), None)
        if not gia:  # conta solo la prima risposta
            ver.append({"pseudonimo": pseudonimo, "chiarimento": chiarimento, "risposta": risposta,
                        "corretta": risposta == q["corretta"], "ts": int(time.time()), "simulato": False})
            scrivi(nome_corso, "verifiche", ver)
        r = gia["risposta"] if gia else risposta
    return {"ok": True, "corretta": r == q["corretta"], "corretta_indice": q["corretta"],
            "spiegazione": q.get("spiegazione", ""), "mia": r}
