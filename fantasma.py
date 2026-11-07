"""
Studente Fantasma - orchestratore del crash test di un corso.

Ciclo: PIANIFICA (analista) -> AGISCI (fantasmi in parallelo) -> OSSERVA (verificatore
in codice) -> SINTETIZZA (cartografo) -> REVISIONE UMANA (docente, nell'interfaccia).

Eventi verso l'interfaccia (stessi del motore generico):
  inizio, agente_inizio, agente_fine, avviso, modello, lacune, fine, errore
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import crew
import materiale
import personas
from agenti import AGENTI

PER_ID = {a["id"]: a for a in AGENTI}
MAX_PASSI_PER_CORSO = int(os.getenv("MAX_PASSI", "60"))  # budget: oltre, si chiede al docente di ridurre


# --------------------------------------------------------------------------- #
#  Utilita'
# --------------------------------------------------------------------------- #
def estrai_json(testo: str):
    """Estrae il primo oggetto JSON da una risposta (tollera ```json ... ``` e testo attorno)."""
    if isinstance(testo, (dict, list)):
        return testo
    t = str(testo).strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.MULTILINE).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    inizio = min([i for i in (t.find("{"), t.find("[")) if i >= 0], default=-1)
    if inizio < 0:
        raise ValueError("La risposta del modello non contiene JSON")
    for fine in range(len(t), inizio, -1):
        if t[fine - 1] in "}]":
            try:
                return json.loads(t[inizio:fine])
            except json.JSONDecodeError:
                continue
    raise ValueError("JSON non valido nella risposta del modello")


def chiedi(llm, agente_id: str, contenuto: str, tentativi: int = 2):
    """Chiama un agente LLM con la sua specifica come system prompt e restituisce il JSON."""
    spec = PER_ID[agente_id]["spec"]
    messaggi = [{"role": "system", "content": spec}, {"role": "user", "content": contenuto}]
    ultimo = None
    for tentativo in range(tentativi):
        t0 = time.time()
        risposta = llm.call(messaggi)
        _debug(agente_id, tentativo, messaggi, risposta, time.time() - t0)
        try:
            return estrai_json(risposta)
        except ValueError as e:
            ultimo = e
            messaggi = messaggi + [{"role": "assistant", "content": str(risposta)[:2000]},
                                   {"role": "user", "content": "La risposta non era JSON valido. "
                                    "Rispondi di nuovo SOLO con il JSON richiesto, senza testo attorno."}]
    raise ultimo


def _num_es(x) -> int:
    """'1a', 'Esercizio 2', '3(b)' -> 1, 2, 3"""
    m = re.findall(r"\d+", str(x or ""))
    return int(m[0]) if m else 0


def _debug(agente_id, tentativo, messaggi, risposta, secondi):
    """Se DEBUG_DIR e' impostata, salva prompt e risposta grezza di ogni agente (per capire gli errori)."""
    cartella = os.getenv("DEBUG_DIR")
    if not cartella:
        return
    p = Path(cartella)
    p.mkdir(parents=True, exist_ok=True)
    lun = sum(len(str(m.get("content", ""))) for m in messaggi)
    (p / f"{agente_id}_t{tentativo}.txt").write_text(
        f"# {agente_id} - tentativo {tentativo} - {secondi:.1f}s - prompt {lun} caratteri\n\n"
        f"=== RISPOSTA ===\n{risposta}\n\n=== ULTIMO MESSAGGIO (primi 3000 caratteri) ===\n"
        f"{str(messaggi[-1].get('content', ''))[:3000]}", encoding="utf-8")


def _sintesi_passi(brief: dict) -> str:
    righe = []
    for es in brief.get("esercizi", []):
        righe.append(f"ESERCIZIO {es.get('id')} - {es.get('argomento', '')} (lezione {es.get('lezione_argomento', '?')})")
        for p in es.get("passi", []):
            righe.append(f"  passo {p.get('n')} [{personas.tipo_passo(p)}]: {p.get('testo')}")
    return "\n".join(righe)


def _indice_lezioni(corso: materiale.Corso) -> str:
    righe = []
    for f in corso.fonti.values():
        if f.tipo == "slide":
            righe.append(f"[{f.id}] Lezione {f.lezione}: {f.titolo}")
    lez_trascritte = sorted({f.lezione for f in corso.fonti.values() if f.tipo == "trascrizione"})
    if lez_trascritte:
        righe.append(f"Videolezioni trascritte disponibili: lezioni {lez_trascritte}")
    return "\n".join(righe)


def _testo_passo(brief: dict, es_id: str, n) -> str:
    for es in brief.get("esercizi", []):
        if str(es.get("id")) == str(es_id):
            for p in es.get("passi", []):
                if str(p.get("n")) == str(n):
                    return p.get("testo", "")
    return ""


# --------------------------------------------------------------------------- #
#  Memoria: decisioni del docente
# --------------------------------------------------------------------------- #
def _file_revisione(corso: materiale.Corso) -> Path:
    return corso.cartella / "revisione_docente.json"


def leggi_revisione(nome_corso: str) -> dict:
    p = materiale.CARTELLA_MATERIALE / nome_corso / "revisione_docente.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def salva_revisione(nome_corso: str, chiave: str, decisione: str, nota: str = "") -> dict:
    rev = leggi_revisione(nome_corso)
    rev[chiave] = {"decisione": decisione, "nota": nota, "quando": datetime.now().isoformat(timespec="seconds")}
    p = materiale.CARTELLA_MATERIALE / nome_corso / "revisione_docente.json"
    p.write_text(json.dumps(rev, ensure_ascii=False, indent=2), encoding="utf-8")
    return rev


# --------------------------------------------------------------------------- #
#  Verificatore + classificazione (codice, non LLM)
# --------------------------------------------------------------------------- #
def verifica_e_classifica(corso, brief, out_slide, out_lezioni, out_tecnico, out_sequenza,
                          out_trappole=None, out_personas=None) -> dict:
    registro = []  # log trasparente delle verifiche

    def verifica(agente, fonte, citazione):
        tipi = PER_ID[agente].get("conoscenza", ("slide", "trascrizione"))
        esito = materiale.verifica_citazione(corso, fonte, citazione, tipi_ammessi=tipi)
        registro.append({"agente": agente, "fonte": fonte, "citazione": (citazione or "")[:120], **esito})
        return esito

    def indicizza(out, agente):
        risultato = {}
        for p in (out or {}).get("passi", []):
            k = (str(p.get("esercizio")), str(p.get("passo")))
            if p.get("stato") == "giustificato":
                p["_verifica"] = verifica(agente, p.get("fonte"), p.get("citazione"))
            else:
                p["_verifica"] = {"valida": False, "motivo": p.get("stato", "non_trovato")}
            risultato[k] = p
        return risultato

    A = indicizza(out_slide, "fantasma_slide")
    B = indicizza(out_lezioni, "fantasma_lezioni")
    # personas: stesse verifiche delle citazioni; il frettoloso e' il fantasma 'solo slide'
    indicizzati = {"fantasma_slide": A}
    for aid, out in (out_personas or {}).items():
        indicizzati[aid] = indicizza(out, aid)

    # prerequisiti segnalati dal fantasma "istituto tecnico", per passo
    prereq_per_passo = {}
    for p in (out_tecnico or {}).get("prerequisiti", []):
        prereq_per_passo.setdefault((str(p.get("esercizio", "")), str(p.get("passo", ""))), p)

    lacune, coperti, chiarimenti = [], 0, []
    stato_passi = []   # per ogni passo: "slide" | "voce" | "mai" (serve alla copertura %)
    for es in brief.get("esercizi", []):
        for passo in es.get("passi", []):
            k = (str(es.get("id")), str(passo.get("n")))
            a, b = A.get(k, {}), B.get(k, {})
            for x in (a, b):
                if x.get("stato") == "chiarimento" and x.get("domanda"):
                    chiarimenti.append(f"Es. {k[0]} passo {k[1]}: {x['domanda']}")
            va, vb = a.get("_verifica", {}), b.get("_verifica", {})
            # quante citazioni di questo passo il verificatore ha scartato (fonte indicata ma falsa)
            scartate = sum(1 for x in (a, b) if x.get("stato") == "giustificato" and not x["_verifica"].get("valida"))
            base = {"esercizio": k[0], "passo": k[1], "testo_passo": passo.get("testo", "")}
            # lezione da cui arriva la fonte verificata (per il carico cognitivo)
            lez = va.get("lezione") if va.get("valida") else (vb.get("lezione") if vb.get("valida") else None)
            if va.get("valida"):
                coperti += 1
                stato = "slide"
            elif vb.get("valida") and vb.get("tipo") == "trascrizione":
                stato = "voce"
                lacune.append({**base, "tipo": "verde", "evidenza": [
                    {"fonte": vb["fonte"], "citazione": b.get("citazione", ""), "nota": "spiegato solo a voce"}],
                    "nota_slide": va.get("motivo", ""),
                    # certezza: alta se la citazione e' (quasi) letterale
                    "certezza": "alta" if vb.get("punteggio", 0) >= 0.9 else "media"})
            elif vb.get("valida"):
                coperti += 1  # c'e' nelle slide: il fantasma 'solo slide' l'aveva mancato
                stato = "slide"
            else:
                stato = "mai"
                certezza = "alta" if scartate == 0 else ("media" if scartate == 1 else "bassa")
                pr = prereq_per_passo.get(k)
                if pr and not pr.get("richiamato_nel_corso"):
                    # mai spiegato nel corso, ma e' un prerequisito delle superiori: lo diciamo in modo piu' utile
                    lacune.append({**base, "tipo": "prerequisito", "prerequisito": pr.get("prerequisito", ""),
                                   "evidenza": [], "perche": pr.get("perche", ""), "certezza": "media"})
                    pr["_usato"] = True
                else:
                    lacune.append({**base, "tipo": "rossa", "evidenza": [], "certezza": certezza,
                                   "nota_slide": va.get("motivo", ""), "nota_lezioni": vb.get("motivo", "")})
            stato_passi.append({"esercizio": k[0], "passo": k[1], "stato": stato, "lezione": lez,
                                "minuti": _minuti(passo)})

    # prerequisiti (fantasma da istituto tecnico) sui passi che hanno comunque una fonte
    gia = {(g["esercizio"], g["passo"]) for g in lacune if g["tipo"] in ("rossa", "prerequisito")}
    for p in (out_tecnico or {}).get("prerequisiti", []):
        if p.get("_usato") or (str(p.get("esercizio", "")), str(p.get("passo", ""))) in gia:
            continue  # gia' segnalato
        if p.get("richiamato_nel_corso"):
            v = verifica("fantasma_tecnico", p.get("fonte"), p.get("citazione"))
            if v.get("valida"):
                continue  # il corso lo richiama davvero: nessuna lacuna
        lacune.append({"tipo": "prerequisito", "esercizio": str(p.get("esercizio", "")),
                       "passo": str(p.get("passo", "")), "prerequisito": p.get("prerequisito", ""),
                       "testo_passo": _testo_passo(brief, p.get("esercizio"), p.get("passo")),
                       "evidenza": [], "perche": p.get("perche", ""), "certezza": "media"})

    # fuori ordine (revisore della sequenza): entrambe le citazioni devono essere vere
    for f in (out_sequenza or {}).get("fuori_ordine", []):
        vu = verifica("revisore_sequenza", f.get("usato_in"), f.get("citazione_uso"))
        vs = verifica("revisore_sequenza", f.get("spiegato_in"), f.get("citazione_spiegazione"))
        if vu.get("valida") and vs.get("valida") and vu["lezione"] < vs["lezione"]:
            alta = vu.get("punteggio", 0) >= 0.9 and vs.get("punteggio", 0) >= 0.9
            lacune.append({"tipo": "gialla", "concetto": f.get("concetto", ""), "esercizio": "", "passo": "",
                           "testo_passo": f"Usato in lezione {vu['lezione']}, spiegato in lezione {vs['lezione']}",
                           "certezza": "alta" if alta else "media",
                           "evidenza": [{"fonte": vu["fonte"], "citazione": f.get("citazione_uso", ""), "nota": "usato qui"},
                                        {"fonte": vs["fonte"], "citazione": f.get("citazione_spiegazione", ""),
                                         "nota": "spiegato solo qui"}]})

    # trappole (cacciatore): la frase deve essere davvero nel testo d'esame E la citazione deve essere vera
    for t in (out_trappole or {}).get("trappole", []):
        frase = t.get("frase_esame", "")
        nel_testo = frase_in_esame(frase, corso.esame)
        v = verifica("cacciatore_trappole", t.get("fonte"), t.get("citazione"))
        if not nel_testo:
            registro.append({"agente": "cacciatore_trappole", "fonte": "esame", "citazione": frase[:120],
                             "valida": False, "motivo": "la frase non compare nel testo d'esame"})
            continue
        if not v.get("valida"):
            continue
        lacune.append({"tipo": "trappola", "esercizio": str(_num_es(t.get("esercizio")) or ""), "passo": "",
                       "frase_esame": frase, "problema": t.get("problema", ""),
                       "testo_passo": f"Nel testo d'esame: “{frase}”",
                       "certezza": "alta" if v.get("punteggio", 0) >= 0.9 else "media",
                       "evidenza": [{"fonte": v["fonte"], "citazione": t.get("citazione", ""),
                                     "nota": "nel materiale del corso"}]})

    for i, g in enumerate(lacune, 1):
        g["id"] = f"g{i}"
        g["chiave"] = _chiave_lacuna(g)
    n_passi = sum(len(es.get("passi", [])) for es in brief.get("esercizi", []))
    citazioni_scartate = sum(1 for r in registro if not r.get("valida") and r.get("fonte"))
    return {"lacune": lacune, "passi_totali": n_passi, "passi_coperti_da_slide": coperti,
            "chiarimenti": chiarimenti, "registro_verifiche": registro,
            "citazioni_scartate": citazioni_scartate, "stato_passi": stato_passi,
            "copertura": calcola_copertura(stato_passi),
            "personas": personas.assembla(brief, personas.esiti_da_agenti(corso, brief, indicizzati))}


def frase_in_esame(frase: str, esame: str) -> bool:
    """La frase 'copiata' dal cacciatore compare davvero nel testo d'esame? (confronto tollerante
    su maiuscole, accenti e simboli, ma senza accettare parafrasi)."""
    from difflib import SequenceMatcher
    c, t = materiale._normalizza(frase), materiale._normalizza(esame)
    if len(c) < 8:
        return False
    if c in t:
        return True
    n = len(c)
    return any(SequenceMatcher(None, c, t[i:i + n]).ratio() >= 0.9 for i in range(0, max(1, len(t) - n + 1), 3))


def _minuti(passo: dict) -> float:
    try:
        return max(0.0, float(passo.get("minuti_stimati") or 0))
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------- #
#  Copertura %, cronometro e carico cognitivo (calcolati IN CODICE)
# --------------------------------------------------------------------------- #
def calcola_copertura(stato_passi: list) -> dict:
    """Percentuale dei passi giustificati dalle slide / solo a voce / mai spiegati.
    NON e' una 'probabilita' di superamento': misura solo il materiale."""
    n = len(stato_passi)
    conta = {s: sum(1 for p in stato_passi if p["stato"] == s) for s in ("slide", "voce", "mai")}
    pct = {s: (round(100 * v / n) if n else 0) for s, v in conta.items()}
    if n:  # gli arrotondamenti devono sommare a 100
        pct["slide"] = 100 - pct["voce"] - pct["mai"]
    return {"passi": n, **conta, "pct_slide": pct["slide"], "pct_voce": pct["voce"], "pct_mai": pct["mai"]}


def durata_esame(brief: dict, testo_esame: str) -> int | None:
    """Durata letta dall'analista; se manca, prova a leggerla dal testo ('2 ore', '90 minuti')."""
    try:
        if brief.get("durata_esame_minuti"):
            return int(brief["durata_esame_minuti"])
    except (TypeError, ValueError):
        pass
    t = (testo_esame or "").lower()
    m = re.search(r"(\d+(?:[.,]5)?)\s*or[ae]\b", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 60)
    m = re.search(r"(\d+)\s*minuti", t)
    return int(m.group(1)) if m else None


def calcola_cronometro(brief: dict, stato_passi: list, testo_esame: str = "") -> dict:
    """Somma dei minuti stimati per esercizio e totale, confronto con la durata dell'esame,
    e carico cognitivo per esercizio (quante lezioni diverse servono e quanto sono lontane)."""
    per_es = {}
    for p in stato_passi:
        per_es.setdefault(p["esercizio"], []).append(p)
    esercizi = []
    for es in brief.get("esercizi", []):
        eid = str(es.get("id"))
        passi = per_es.get(eid, [])
        lezioni = sorted({p["lezione"] for p in passi if p.get("lezione")})
        distanza = (lezioni[-1] - lezioni[0]) if lezioni else 0
        spezzare = distanza >= 2 or len(lezioni) >= 3
        esercizi.append({
            "esercizio": eid, "argomento": es.get("argomento", ""), "punti": es.get("punti"),
            "passi": len(passi), "minuti": round(sum(p.get("minuti", 0) for p in passi)),
            "lezioni": lezioni, "n_lezioni": len(lezioni), "distanza_lezioni": distanza,
            "carico": "alto" if spezzare else ("medio" if len(lezioni) == 2 else "basso"),
            "suggerimento": ("Valuta di spezzarlo in sotto-domande A/B/C: richiede di collegare "
                             f"{len(lezioni)} lezioni diverse (dalla {lezioni[0]} alla {lezioni[-1]})."
                             if spezzare else ""),
        })
    totale = sum(e["minuti"] for e in esercizi)
    durata = durata_esame(brief, testo_esame)
    if not totale:
        messaggio = "L'analista non ha stimato i tempi dei passi."
    elif durata:
        quota = round(100 * totale / durata)
        messaggio = (f"Con il metodo insegnato a lezione servono ~{totale} minuti, ne hai dati {durata} "
                     f"({quota}% del tempo disponibile).")
    else:
        messaggio = f"Con il metodo insegnato a lezione servono ~{totale} minuti (durata dell'esame non indicata)."
    return {"durata_esame_minuti": durata, "minuti_totali": totale,
            "quota_tempo": round(100 * totale / durata) if (durata and totale) else None,
            "messaggio": messaggio, "esercizi": esercizi}


def _chiave_lacuna(g: dict) -> str:
    """Identificativo stabile tra un'esecuzione e l'altra (per ricordare le decisioni del docente)."""
    if g["tipo"] == "gialla":
        return "gialla:" + re.sub(r"\W+", "-", g.get("concetto", "").lower()).strip("-")[:40]
    if g["tipo"] == "trappola":
        return "trappola:" + re.sub(r"\W+", "-", g.get("frase_esame", "").lower()).strip("-")[:40]
    if g["tipo"] == "prerequisito":
        return "prerequisito:" + re.sub(r"\W+", "-", g.get("prerequisito", "").lower()).strip("-")[:40]
    return f"{g['tipo']}:es{g.get('esercizio')}-p{g.get('passo')}"


# --------------------------------------------------------------------------- #
#  Valutazione contro la chiave delle lacune piantate (solo corsi di test)
# --------------------------------------------------------------------------- #
def _parole(t: str) -> set:
    return {w for w in re.findall(r"[a-zàèéìòù]{4,}", (t or "").lower())}


def valuta(lacune: list, chiave: list | None) -> dict | None:
    if not chiave:
        return None
    # le trappole non fanno parte della chiave delle lacune piantate: non entrano nel conteggio
    lacune = [g for g in lacune if g.get("tipo") != "trappola"]
    max_es = int(os.getenv("MAX_ESERCIZI", "0") or 0)
    if max_es > 0:
        chiave = [k for k in chiave if k.get("tipo") == "gialla" or 0 < _num_es(k.get("esercizio_esame")) <= max_es]
    vere = [k for k in chiave if k.get("tipo") != "non_lacuna"]
    finte = [k for k in chiave if k.get("tipo") == "non_lacuna"]

    def punteggio(g, k):
        es_k, es_g = _num_es(k.get("esercizio_esame")), _num_es(g.get("esercizio"))
        if es_k and es_g and es_k != es_g and g.get("tipo") != "gialla":
            return 0.0
        testo_g = " ".join([g.get("testo_passo", ""), g.get("titolo", ""), g.get("concetto", ""),
                            g.get("prerequisito", ""), " ".join(e.get("citazione", "") for e in g.get("evidenza", []))])
        testo_k = " ".join([k.get("descrizione", ""), str(k.get("passaggio_soluzione", ""))])
        a, b = _parole(testo_g), _parole(testo_k)
        sim = len(a & b) / max(1, min(len(a), len(b)))
        ps = re.findall(r"\d+", str(k.get("passaggio_soluzione", "")))
        if ps and str(g.get("passo")) == ps[0]:
            sim += 0.3
        if g.get("tipo") == k.get("tipo"):
            sim += 0.1
        return sim

    # abbinamento uno-a-uno: ogni lacuna trovata va al massimo a una voce della chiave
    coppie = sorted(((punteggio(g, k), gi, ki) for gi, g in enumerate(lacune) for ki, k in enumerate(chiave)),
                    reverse=True)
    usate_g, usate_k, abbinate = set(), set(), {}
    for s, gi, ki in coppie:
        if s < 0.3 or gi in usate_g or ki in usate_k:
            continue
        usate_g.add(gi); usate_k.add(ki); abbinate[ki] = gi
    trovate = [k for ki, k in enumerate(chiave) if ki in abbinate and k.get("tipo") != "non_lacuna"]
    falsi_su_finte = [k for ki, k in enumerate(chiave) if ki in abbinate and k.get("tipo") == "non_lacuna"]
    corrisposte = [gi for ki, gi in abbinate.items() if chiave[ki].get("tipo") != "non_lacuna"]
    return {"piantate": len(vere), "trovate": len(trovate),
            "recall": round(len(trovate) / max(1, len(vere)), 2),
            "segnalate": len(lacune), "corrispondenti": len(corrisposte),
            "precision": round(len(corrisposte) / max(1, len(lacune)), 2),
            "falso_amico_segnalato": len(falsi_su_finte),
            "mancate": [k.get("descrizione", "") for k in vere if k not in trovate]}


# --------------------------------------------------------------------------- #
#  Esecuzione completa
# --------------------------------------------------------------------------- #
def esegui(nome_corso: str, emit) -> dict | None:
    try:
        corso = materiale.carica_corso(nome_corso)
        if crew.modalita_demo():
            return _esegui_demo(corso, emit)
        return _esegui_live(corso, emit)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        consiglio = ""
        if crew._errore_temporaneo(msg):
            consiglio = "Tutti i modelli sono occupati o al limite: aspetta un minuto o controlla la chiave nel .env."
        elif "api key" in msg.lower() or "401" in msg or "403" in msg:
            consiglio = "Chiave API mancante o non valida: controlla il file .env."
        emit({"tipo": "errore", "messaggio": msg[:600], "consiglio": consiglio})
        return None


def _esegui_live(corso: materiale.Corso, emit_originale) -> dict:
    os.environ.setdefault("DEBUG_DIR", str(corso.cartella / "report" / "debug"))
    output_agenti = {}

    def emit(ev):
        if ev.get("tipo") == "agente_fine":
            output_agenti[ev["id"]] = ev.get("output", "")
        if ev.get("tipo") == "lacune":
            ev["risultato"]["output_agenti"] = output_agenti
            salva_report(corso, ev["risultato"])
        emit_originale(ev)

    llm = crew.crea_llm_con_riserva(emit)
    emit({"tipo": "inizio", "modello": llm.model, "corso": corso.riepilogo()})
    t0 = time.time()

    # FASE 1 - analista
    emit({"tipo": "agente_inizio", "id": "analista"})
    brief = chiedi(llm, "analista",
                   f"INTERVISTA/BRIEF DEL DOCENTE:\n{corso.brief or '(non fornito)'}\n\n"
                   f"INDICE DELLE LEZIONI:\n{_indice_lezioni(corso)}\n\n"
                   f"TESTO D'ESAME:\n{corso.esame}\n\nSOLUZIONI UFFICIALI:\n{corso.soluzioni}")
    max_es = int(os.getenv("MAX_ESERCIZI", "0") or 0)  # modalita' prova: solo i primi N esercizi
    if max_es > 0:
        brief["esercizi"] = [e for e in brief.get("esercizi", []) if 0 < _num_es(e.get("id")) <= max_es]
    n_passi = sum(len(es.get("passi", [])) for es in brief.get("esercizi", []))
    if n_passi > MAX_PASSI_PER_CORSO:
        brief.setdefault("domande_per_il_docente", []).append(
            f"Le soluzioni hanno {n_passi} passi: analizzo i primi {MAX_PASSI_PER_CORSO} (budget). Vuole indicare gli esercizi prioritari?")
    emit({"tipo": "agente_fine", "id": "analista", "output": _md_brief(brief), "dati": brief})

    # FASE 2 - fantasmi + revisore in parallelo, tutti con lo stesso brief
    passi = _sintesi_passi(brief)
    lavori = {
        "fantasma_slide": f"SLIDE DEL CORSO:\n{corso.testo_fonti(('slide',))}\n\nPASSI DA GIUSTIFICARE:\n{passi}",
        "fantasma_lezioni": f"MATERIALE DEL CORSO (slide + trascrizioni):\n{corso.testo_fonti()}\n\nPASSI DA GIUSTIFICARE:\n{passi}",
        "persona_visivo": f"SLIDE DEL CORSO:\n{corso.testo_fonti(('slide',))}\n\nPASSI DA GIUSTIFICARE:\n{passi}",
        "persona_mnemonico": f"MATERIALE DEL CORSO (slide + trascrizioni):\n{corso.testo_fonti()}\n\nPASSI DA GIUSTIFICARE:\n{passi}",
        "persona_applicativo": f"MATERIALE DEL CORSO (slide + trascrizioni):\n{corso.testo_fonti()}\n\nPASSI DA GIUSTIFICARE:\n{passi}",
        "fantasma_tecnico": f"MATERIALE DEL CORSO (slide + trascrizioni):\n{corso.testo_fonti()}\n\n"
                            f"PREREQUISITI CHE IL DOCENTE DA' PER SCONTATI: {brief.get('prerequisiti_dati_per_scontati', [])}\n\n"
                            f"PASSI DELLE SOLUZIONI:\n{passi}",
        "revisore_sequenza": f"MATERIALE DEL CORSO IN ORDINE (slide + trascrizioni):\n{corso.testo_fonti()}",
        "cacciatore_trappole": f"TESTO D'ESAME:\n{corso.esame}\n\n"
                               f"MATERIALE DEL CORSO (slide + trascrizioni):\n{corso.testo_fonti()}",
    }
    risultati = {}
    with ThreadPoolExecutor(max_workers=len(lavori)) as pool:
        futuri = {}
        for aid, contenuto in lavori.items():
            emit({"tipo": "agente_inizio", "id": aid})
            futuri[aid] = pool.submit(chiedi, llm, aid, contenuto)
        for aid, fut in futuri.items():
            risultati[aid] = fut.result()
            emit({"tipo": "agente_fine", "id": aid, "output": _md_fantasma(aid, risultati[aid])})

    # FASE 3 - verificatore (codice)
    emit({"tipo": "agente_inizio", "id": "verificatore"})
    analisi = verifica_e_classifica(corso, brief, risultati["fantasma_slide"], risultati["fantasma_lezioni"],
                                    risultati["fantasma_tecnico"], risultati["revisore_sequenza"],
                                    risultati["cacciatore_trappole"],
                                    {aid: risultati[aid] for aid in ("persona_visivo", "persona_mnemonico",
                                                                     "persona_applicativo")})
    emit({"tipo": "agente_fine", "id": "verificatore", "output": _md_verifica(analisi)})
    # aggiorna le card dei quattro studenti con il voto calcolato dal programma
    for p in personas.PERSONAS:
        voto = personas.markdown(analisi.get("personas") or {}, solo=p["id"])
        if voto:
            emit({"tipo": "agente_fine", "id": p["agente"],
                  "output": voto + "\n\n---\n" + _md_fantasma(p["agente"], risultati[p["agente"]])})

    # FASE 4 - cartografo
    emit({"tipo": "agente_inizio", "id": "cartografo"})
    sintesi = {"schede": [], "sintesi": ""}
    if analisi["lacune"]:
        compatte = [{k: g.get(k) for k in ("id", "tipo", "esercizio", "passo", "testo_passo", "concetto",
                                            "prerequisito", "problema", "evidenza")} for g in analisi["lacune"]]
        sintesi = chiedi(llm, "cartografo",
                         f"CORSO: {brief.get('corso', corso.nome)}\nOBIETTIVI: {brief.get('obiettivi', [])}\n\n"
                         f"LACUNE VERIFICATE:\n{json.dumps(compatte, ensure_ascii=False, indent=1)}")
    risultato = _assembla(corso, brief, analisi, sintesi, time.time() - t0)
    emit({"tipo": "agente_fine", "id": "cartografo", "output": risultato["sintesi"] or "Nessuna lacuna trovata."})
    emit({"tipo": "lacune", "risultato": risultato})
    emit({"tipo": "fine", "output": risultato["sintesi"]})
    return risultato


def _assembla(corso, brief, analisi, sintesi, secondi, salva: bool = True) -> dict:
    schede = {s.get("id"): s for s in (sintesi or {}).get("schede", [])}
    revisione = leggi_revisione(corso.nome)
    for g in analisi["lacune"]:
        s = schede.get(g["id"], {})
        g["titolo"] = (s.get("titolo") or g.get("concetto") or g.get("prerequisito") or g.get("problema")
                       or g.get("testo_passo", "")[:80])
        g["perche_conta"] = s.get("perche_conta", g.get("perche", "") or g.get("problema", ""))
        g["suggerimento"] = s.get("suggerimento", "")
        g["revisione"] = revisione.get(g["chiave"], {}).get("decisione")
    cronometro = calcola_cronometro(brief, analisi.get("stato_passi", []), corso.esame)
    domande = brief.get("domande_per_il_docente", []) + analisi["chiarimenti"]
    if cronometro["durata_esame_minuti"] is None:
        domande.append("Quanto dura l'esame? Non l'ho trovato nel testo: serve per il cronometro.")
    risultato = {
        "origine": "crash test reale", "simulato": False,
        "corso": corso.riepilogo(), "brief": brief, "lacune": analisi["lacune"],
        "copertura": analisi.get("copertura") or calcola_copertura(analisi.get("stato_passi", [])),
        "cronometro": cronometro, "stato_passi": analisi.get("stato_passi", []),
        "passi_totali": analisi["passi_totali"], "passi_coperti_da_slide": analisi["passi_coperti_da_slide"],
        "citazioni_scartate": analisi["citazioni_scartate"],
        "personas": analisi.get("personas") or {},
        "domande_per_il_docente": domande,
        "sintesi": (sintesi or {}).get("sintesi", ""), "secondi": round(secondi, 1),
        "valutazione": valuta(analisi["lacune"], corso.chiave),
        "registro_verifiche": analisi["registro_verifiche"],
    }
    if salva:
        salva_report(corso, risultato)
    return risultato


# --------------------------------------------------------------------------- #
#  AZIONE: scrive la Mappa delle Lacune su file per il docente
# --------------------------------------------------------------------------- #
ETICHETTE = {"rossa": "\U0001f534 Mai spiegato", "verde": "\U0001f7e2 Solo a voce",
             "gialla": "\U0001f7e1 Fuori ordine", "prerequisito": "\U0001f535 Prerequisito dato per scontato",
             "trappola": "\U0001faa4 Trappola nel testo d'esame"}


def salva_report(corso: materiale.Corso, r: dict) -> Path:
    cartella = corso.cartella / "report"
    cartella.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    righe = [f"# Mappa delle Lacune - {r['brief'].get('corso', corso.nome)}",
             f"_Generata da Studente Fantasma il {datetime.now():%d/%m/%Y %H:%M}_", "",
             r.get("sintesi", ""), "",
             f"Passi delle soluzioni analizzati: {r['passi_totali']} - giustificati dalle slide: "
             f"{r['passi_coperti_da_slide']} - lacune: {len(r['lacune'])}", ""]
    cop, cro = r.get("copertura"), r.get("cronometro")
    if cop and cop.get("passi"):
        righe += [f"**Copertura:** {cop['pct_slide']}% dei passi giustificati dalle slide, {cop['pct_voce']}% solo a voce, "
                  f"{cop['pct_mai']}% senza fonte nel materiale.", ""]
    if cro:
        righe += [f"**Cronometro:** {cro.get('messaggio', '')}", ""]
        for e in cro.get("esercizi", []):
            righe.append(f"- Esercizio {e['esercizio']}: ~{e['minuti']} min, lezioni {e['lezioni']}"
                         + (f" - {e['suggerimento']}" if e.get("suggerimento") else ""))
        righe.append("")
    pe = r.get("personas") or {}
    if pe.get("schede"):
        righe += ["## \U0001f3ad Quattro studenti, quattro voti", "", f"**{pe.get('titolo', '')}**", "",
                  personas.markdown(pe), "", f"_{pe.get('nota', '')}_", ""]
    righe += ["_Report privato del docente: le decisioni restano sue, nessun dato usato per valutare la didattica._", ""]
    for tipo in ("rossa", "verde", "gialla", "prerequisito", "trappola"):
        gruppo = [g for g in r["lacune"] if g["tipo"] == tipo]
        if not gruppo:
            continue
        righe.append(f"## {ETICHETTE[tipo]} ({len(gruppo)})")
        for g in gruppo:
            dove = f"Esercizio {g['esercizio']}, passo {g['passo']}" if g.get("esercizio") else ""
            righe += [f"### {g['titolo']}", f"- **Dove serve:** {dove} {g.get('testo_passo', '')}".rstrip()]
            for e in g.get("evidenza", []):
                righe.append(f"- **{e.get('nota', 'fonte')}:** [{e['fonte']}] “{e.get('citazione', '')}”")
            if g.get("perche_conta"):
                righe.append(f"- **Perche' conta:** {g['perche_conta']}")
            if g.get("suggerimento"):
                righe.append(f"- **Suggerimento:** {g['suggerimento']}")
            righe.append(f"- **Decisione del docente:** {g.get('revisione') or 'da rivedere'}")
            righe.append("")
    if r.get("domande_per_il_docente"):
        righe.append("## Domande per il docente")
        righe += [f"- {d}" for d in r["domande_per_il_docente"]]
    p = cartella / f"mappa_lacune_{stamp}.md"
    p.write_text("\n".join(righe), encoding="utf-8")
    (cartella / f"mappa_lacune_{stamp}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    r["file_report"] = str(p.relative_to(materiale.CARTELLA_MATERIALE.parent))
    return p


# --------------------------------------------------------------------------- #
#  Testi leggibili per le card degli agenti
# --------------------------------------------------------------------------- #
def _md_brief(b: dict) -> str:
    out = [f"**Corso:** {b.get('corso', '')}", "", "**Esercizi e passi da giustificare:**"]
    for es in b.get("esercizi", []):
        minuti = sum(_minuti(p) for p in es.get("passi", []))
        out.append(f"- Esercizio {es.get('id')} ({es.get('argomento', '')}, lezione {es.get('lezione_argomento', '?')}"
                   + (f", {es['punti']} punti" if es.get("punti") else "") + f"): {len(es.get('passi', []))} passi"
                   + (f", ~{minuti:.0f} min stimati" if minuti else ""))
    if b.get("durata_esame_minuti"):
        out += ["", f"**Durata dell'esame letta dal testo:** {b['durata_esame_minuti']} minuti"]
    if b.get("prerequisiti_dati_per_scontati"):
        out += ["", "**Prerequisiti dati per scontati:** " + "; ".join(b["prerequisiti_dati_per_scontati"])]
    if b.get("domande_per_il_docente"):
        out += ["", "**Domande per il docente:**"] + [f"- {d}" for d in b["domande_per_il_docente"]]
    return "\n".join(out)


def _md_fantasma(aid: str, r: dict) -> str:
    if aid == "fantasma_tecnico":
        pr = r.get("prerequisiti", [])
        return "\n".join([f"**{len(pr)} prerequisiti analizzati**"] +
                         [f"- Es. {p.get('esercizio')} passo {p.get('passo')}: {p.get('prerequisito')} "
                          f"({'richiamato' if p.get('richiamato_nel_corso') else 'NON richiamato'})" for p in pr])
    if aid == "cacciatore_trappole":
        tr = r.get("trappole", [])
        return "\n".join([f"**{len(tr)} possibili trappole proposte**"] +
                         [f"- Es. {t.get('esercizio')}: “{t.get('frase_esame')}” → {t.get('problema')} "
                          f"[{t.get('fonte')}]" for t in tr])
    if aid == "revisore_sequenza":
        fo = r.get("fuori_ordine", [])
        return "\n".join([f"**{len(fo)} concetti fuori ordine proposti**"] +
                         [f"- {f.get('concetto')}: usato in {f.get('usato_in')}, spiegato in {f.get('spiegato_in')}" for f in fo])
    passi = r.get("passi", [])
    ok = sum(p.get("stato") == "giustificato" for p in passi)
    out = [f"**{ok} passi su {len(passi)} con una fonte**", ""]
    for p in passi:
        segno = "✅" if p.get("stato") == "giustificato" else ("❓" if p.get("stato") == "chiarimento" else "❌")
        fonte = f" [{p.get('fonte')}]" if p.get("fonte") else ""
        out.append(f"- {segno} Es. {p.get('esercizio')} passo {p.get('passo')}{fonte}")
    return "\n".join(out)


def _md_verifica(a: dict) -> str:
    tot = len(a["registro_verifiche"])
    ok = sum(r.get("valida") for r in a["registro_verifiche"])
    out = [f"**{ok} citazioni su {tot} confermate**, {a['citazioni_scartate']} scartate perche' la fonte o il testo citato non esistono.", ""]
    for r in a["registro_verifiche"]:
        if not r.get("valida") and r.get("fonte"):
            out.append(f"- ❌ {r['agente']} [{r.get('fonte')}]: {r.get('motivo')}")
    tipi = {}
    for g in a["lacune"]:
        tipi[g["tipo"]] = tipi.get(g["tipo"], 0) + 1
    out += ["", "**Lacune classificate:** " + (", ".join(f"{ETICHETTE.get(t, t)}: {n}" for t, n in tipi.items()) or "nessuna")]
    pe = a.get("personas") or {}
    if pe.get("schede"):
        out += ["", "**Voti stimati dei quattro studenti:** " + " · ".join(f"{x['icona']} {x['voto']}/30" for x in pe["schede"])]
    c = a.get("copertura")
    if c and c.get("passi"):
        out += ["", f"**Copertura:** {c['pct_slide']}% slide · {c['pct_voce']}% solo a voce · {c['pct_mai']}% senza fonte"]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
#  Modalita' demo (nessuna chiamata API): usa la chiave delle lacune se c'e'
# --------------------------------------------------------------------------- #
FILE_DEMO = "demo_completa.json"  # fixture della simulazione dimostrativa (usata con priorita')


def _ultimo_report(corso: materiale.Corso) -> dict | None:
    cartella = corso.cartella / "report"
    fixture = cartella / FILE_DEMO
    if fixture.exists():
        try:
            r = json.loads(fixture.read_text(encoding="utf-8"))
            r.setdefault("origine", "simulazione dimostrativa")
            return r
        except (OSError, json.JSONDecodeError):
            pass
    for p in sorted(cartella.glob("mappa_lacune_*.json"), reverse=True) if cartella.exists() else []:
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            if r.get("passi_totali"):  # solo risultati di esecuzioni vere
                r["origine"] = "replay dell'ultimo crash test reale (" + p.stem.replace("mappa_lacune_", "") + ")"
                return r
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _esegui_demo(corso: materiale.Corso, emit) -> dict:
    """Simulazione senza chiamate API: riproduce l'ultimo crash test vero di questo corso
    (o, se non c'e', costruisce le lacune dalla chiave di test)."""
    r = _ultimo_report(corso)
    emit({"tipo": "inizio", "modello": "simulazione (nessuna chiamata API)", "corso": corso.riepilogo()})
    out = (r or {}).get("output_agenti", {})
    if r and not out:  # report vecchi senza output: ricostruisci un riassunto
        out = {"analista": _md_brief(r.get("brief", {})),
               "verificatore": f"**{len(r.get('registro_verifiche', []))} citazioni controllate**, "
                               f"{r.get('citazioni_scartate', 0)} scartate. Lacune classificate: {len(r.get('lacune', []))}.",
               "cartografo": r.get("sintesi", "")}
    debug = corso.cartella / "report" / "debug"
    for aid in ("fantasma_slide", "fantasma_lezioni", "fantasma_tecnico", "revisore_sequenza", "cacciatore_trappole"):
        if out.get(aid) or not debug.exists():
            continue
        for p in sorted(debug.glob(f"{aid}_t*.txt"), reverse=True):  # ultima risposta grezza valida
            try:
                testo = p.read_text(encoding="utf-8").split("=== RISPOSTA ===", 1)[1].split("=== ULTIMO MESSAGGIO", 1)[0]
                out[aid] = _md_fantasma(aid, estrai_json(testo))
                break
            except (IndexError, ValueError, OSError):
                continue
    if r and not (r.get("personas") or {}).get("schede") and r.get("brief") and r.get("stato_passi"):
        r["personas"] = personas.assembla(r["brief"], personas.esiti_simulati(corso, r["brief"], r["stato_passi"]),
                                          simulato=True)
    for p in personas.PERSONAS:
        voto = personas.markdown((r or {}).get("personas") or {}, solo=p["id"])
        if voto:
            out[p["agente"]] = voto + (("\n\n---\n" + out[p["agente"]]) if out.get(p["agente"]) else "")
    fasi = [["analista"], ["fantasma_slide", "fantasma_lezioni", "persona_visivo", "persona_mnemonico",
                           "persona_applicativo", "fantasma_tecnico", "revisore_sequenza", "cacciatore_trappole"],
            ["verificatore"], ["cartografo"]]
    pause = {"analista": 2.5, "verificatore": 0.8, "cartografo": 2.0}
    for gruppo in fasi:
        for aid in gruppo:
            emit({"tipo": "agente_inizio", "id": aid})
        for n, aid in enumerate(gruppo):
            time.sleep(pause.get(aid, 3.0 if n == 0 else 0.9))
            emit({"tipo": "agente_fine", "id": aid,
                  "output": out.get(aid) or f"_(simulazione)_ {PER_ID[aid]['ruolo']}: completato."})
    if r:
        _arricchisci(corso, r)
        rev = leggi_revisione(corso.nome)
        for g in r.get("lacune", []):
            g["revisione"] = rev.get(g.get("chiave"), {}).get("decisione")
        emit({"tipo": "lacune", "risultato": r})
        emit({"tipo": "fine", "output": r.get("sintesi", "")})
        return r
    return _demo_da_chiave(corso, emit)


def _arricchisci(corso: materiale.Corso, r: dict) -> None:
    """Replay: etichetta il risultato come simulazione, ricalcola la valutazione con valuta()
    (mai scritta a mano) e completa i campi che i report vecchi non avevano."""
    r["simulato"] = True
    r.setdefault("origine", "simulazione")
    r["valutazione"] = valuta(r.get("lacune", []), corso.chiave)
    stato = r.get("stato_passi")
    if not r.get("copertura") and stato:
        r["copertura"] = calcola_copertura(stato)
    elif not r.get("copertura") and r.get("passi_totali"):
        # report vecchi: ricostruisci la copertura dai conteggi salvati
        n, slide = r["passi_totali"], r.get("passi_coperti_da_slide", 0)
        voce = sum(1 for g in r.get("lacune", []) if g.get("tipo") == "verde")
        finti = [{"stato": "slide"}] * slide + [{"stato": "voce"}] * voce + [{"stato": "mai"}] * max(0, n - slide - voce)
        r["copertura"] = calcola_copertura(finti)
    if not r.get("cronometro") and stato:
        r["cronometro"] = calcola_cronometro(r.get("brief", {}), stato, corso.esame)
    for g in r.get("lacune", []):
        g.setdefault("certezza", None)  # report vecchi: nessuna certezza calcolata


def _demo_da_chiave(corso: materiale.Corso, emit) -> dict:
    lacune = []
    for i, k in enumerate([k for k in (corso.chiave or []) if k.get("tipo") != "non_lacuna"], 1):
        ev = []
        if k.get("dove_compare"):
            m = re.search(r"(\d+).*?\[(\d{1,2}:\d{2})\]", str(k["dove_compare"]))
            ev = [{"fonte": f"L{int(m.group(1))}@{m.group(2)}" if m else str(k["dove_compare"]),
                   "citazione": "", "nota": "spiegato qui"}]
        es = re.findall(r"\d+", str(k.get("esercizio_esame", "")))
        ps = re.findall(r"\d+", str(k.get("passaggio_soluzione", "")))
        g = {"id": f"g{i}", "tipo": k.get("tipo", "rossa"), "esercizio": es[0] if es else "",
             "passo": ps[0] if ps else "", "titolo": k.get("descrizione", ""),
             "testo_passo": str(k.get("passaggio_soluzione", "")), "evidenza": ev,
             "perche_conta": k.get("perche_e_una_lacuna", ""), "suggerimento": "(demo) suggerimento del cartografo"}
        g["chiave"] = _chiave_lacuna(g)
        lacune.append(g)
    risultato = {"origine": "simulazione dalla chiave di test", "simulato": True,
                 "corso": corso.riepilogo(), "brief": {"corso": corso.nome}, "lacune": lacune,
                 "passi_totali": 0, "passi_coperti_da_slide": 0, "citazioni_scartate": 0,
                 "domande_per_il_docente": [], "sintesi": "Modalita' demo: lacune lette dalla chiave di test.",
                 "secondi": 0, "valutazione": None, "registro_verifiche": []}
    rev = leggi_revisione(corso.nome)
    for g in lacune:
        g["revisione"] = rev.get(g["chiave"], {}).get("decisione")
    emit({"tipo": "lacune", "risultato": risultato})
    emit({"tipo": "fine", "output": risultato["sintesi"]})
    return risultato
