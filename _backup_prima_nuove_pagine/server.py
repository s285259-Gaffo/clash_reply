"""
Server web: espone gli agenti via API e serve l'interfaccia.
Avvio:  python server.py   ->  apri http://localhost:8000
"""
import json
import os
import queue
import re
import shutil
import threading
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import agenti  # noqa: E402
import crew  # noqa: E402
import fantasma  # noqa: E402
import materiale  # noqa: E402

import logging  # noqa: E402


class _IgnoraDisconnessioniWindows(logging.Filter):
    """Su Windows, quando il browser chiude la connessione, asyncio stampa un
    ConnectionResetError innocuo. Lo nascondiamo per non sporcare il terminale."""

    def filter(self, record):
        exc = record.exc_info[1] if record.exc_info else None
        return not isinstance(exc, ConnectionResetError)


logging.getLogger("asyncio").addFilter(_IgnoraDisconnessioniWindows())

app = FastAPI(title="Studente Fantasma")
STATIC = Path(__file__).parent / "static"
_esecuzioni: dict[str, queue.Queue] = {}
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Richiesta(BaseModel):
    corso: str


class Decisione(BaseModel):
    corso: str
    chiave: str
    decisione: str  # "da_sistemare" | "voluta" | "falso_allarme"
    nota: str = ""


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


# --- Lato studente e docente (ciclo di miglioramento durante il semestre) ---
try:
    import semestre_api  # noqa: E402
    app.include_router(semestre_api.router)
except ImportError as e:  # il modulo semestre non e' ancora presente
    print(f"[avviso] modulo semestre non caricato: {e}")


@app.get("/studente")
def pagina_studente():
    return FileResponse(STATIC / "studente.html")


@app.get("/docente")
def pagina_docente():
    return FileResponse(STATIC / "docente.html")


@app.get("/api/config")
def config():
    fasi, dip = crew.fasi(), crew.dipendenze()
    corsi = []
    for nome in materiale.elenca_corsi():
        try:
            corsi.append(materiale.carica_corso(nome).riepilogo())
        except Exception as e:  # noqa: BLE001  cartella non valida: la mostriamo con l'errore
            corsi.append({"nome": nome, "errore": str(e)})
    return {
        "titolo": agenti.TITOLO_APP,
        "sottotitolo": agenti.SOTTOTITOLO_APP,
        "modalita": "demo" if crew.modalita_demo() else "live",
        "modello": "demo" if crew.modalita_demo() else crew.nome_modello(),
        "corsi": corsi,
        "agenti": [
            {**{k: a[k] for k in ("id", "nome", "icona", "ruolo")},
             "fase": fasi[a["id"]], "dipende_da": dip[a["id"]], "codice": a.get("codice", False)}
            for a in agenti.AGENTI
        ],
    }


class FileCorso(BaseModel):
    percorso: str  # percorso relativo dentro la cartella trascinata (es. "corso/slide_01.md")
    testo: str


class Caricamento(BaseModel):
    nome: str
    files: list[FileCorso]
    sovrascrivi: bool = False


# file riconosciuti da materiale.carica_corso (vedi docstring di materiale.py)
_PREFISSI_CORSO = ("slide", "trascrizion", "transcript", "soluzion", "solution", "esame", "exam", "brief", "chiave")
_MAX_BYTE_CORSO = 25 * 1024 * 1024


@app.post("/api/corsi")
def carica_corso(c: Caricamento):
    """Riceve la cartella di un corso trascinata nell'interfaccia e la salva in materiale/<nome>/.
    I file vengono prima scritti in una cartella temporanea e validati con materiale.carica_corso:
    se il materiale non e' leggibile non si tocca nulla."""
    nome = re.sub(r"[^a-z0-9_-]+", "_", c.nome.strip().lower()).strip("_-")[:60]
    if not nome:
        raise HTTPException(400, "Dai un nome al corso (lettere, numeri, trattini).")
    accettati: dict[str, str] = {}
    ignorati: list[str] = []
    for f in c.files:
        parti = [x for x in re.split(r"[\\/]+", f.percorso) if x and x not in (".", "..")]
        base = parti[-1] if parti else ""
        bl = base.lower()
        in_sottocartella_generata = any(x.lower() in ("report", "semestre") for x in parti[:-1])
        if (in_sottocartella_generata or not bl.endswith((".md", ".txt", ".json"))
                or not bl.startswith(_PREFISSI_CORSO)):
            ignorati.append(f.percorso)
            continue
        accettati[base] = f.testo
    if not accettati:
        raise HTTPException(400, "Nella cartella non ho trovato file del corso. Servono file .md o .txt "
                                 "che iniziano con slide_, trascrizione_, esame, soluzioni (e opzionale brief_docente).")
    if sum(len(t.encode("utf-8")) for t in accettati.values()) > _MAX_BYTE_CORSO:
        raise HTTPException(413, "Il materiale supera 25 MB: riduci i file o caricali in piu' corsi.")
    dest = materiale.CARTELLA_MATERIALE / nome
    if dest.exists() and not c.sovrascrivi:
        raise HTTPException(409, f"Esiste gia' un corso '{nome}'.")
    tmp = materiale.CARTELLA_MATERIALE / f"_caricamento_{uuid.uuid4().hex[:8]}"
    tmp.mkdir(parents=True)
    try:
        for base, testo in accettati.items():
            (tmp / base).write_text(testo, encoding="utf-8")
        materiale.carica_corso(tmp.name)  # valida: solleva un errore se slide/trascrizioni non sono leggibili
        dest.mkdir(parents=True, exist_ok=True)
        for p in tmp.iterdir():
            os.replace(p, dest / p.name)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, "Materiale non valido: " + str(e).replace(tmp.name, nome)) from e
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"corso": materiale.carica_corso(nome).riepilogo(), "file": sorted(accettati),
            "ignorati": len(ignorati), "esempi_ignorati": ignorati[:8]}


@app.post("/api/run")
def avvia(r: Richiesta):
    if r.corso not in materiale.elenca_corsi():
        raise HTTPException(404, f"Corso '{r.corso}' non trovato nella cartella materiale")
    run_id = uuid.uuid4().hex[:8]
    q: queue.Queue = queue.Queue()
    _esecuzioni[run_id] = q

    def lavoro():
        fantasma.esegui(r.corso, q.put)
        q.put(None)  # segnale di chiusura

    threading.Thread(target=lavoro, daemon=True).start()
    return {"run_id": run_id}


@app.post("/api/revisione")
def revisione(d: Decisione):
    if d.decisione not in ("da_sistemare", "voluta", "falso_allarme", ""):
        raise HTTPException(400, "Decisione non valida")
    if d.corso not in materiale.elenca_corsi():
        raise HTTPException(404, "Corso non trovato")
    return fantasma.salva_revisione(d.corso, d.chiave, d.decisione, d.nota)


@app.get("/api/report/{corso}")
def ultimo_report(corso: str):
    if corso not in materiale.elenca_corsi():
        raise HTTPException(404, "Corso non trovato")
    cartella = materiale.CARTELLA_MATERIALE / corso / "report"
    files = sorted(cartella.glob("mappa_lacune_*.md")) if cartella.exists() else []
    if not files:
        raise HTTPException(404, "Nessun report ancora generato")
    return FileResponse(files[-1], filename=files[-1].name, media_type="text/markdown")


@app.get("/api/stream/{run_id}")
def stream(run_id: str):
    q = _esecuzioni.get(run_id)
    if q is None:
        raise HTTPException(404, "Esecuzione non trovata")

    def eventi():
        while True:
            try:
                ev = q.get(timeout=15)
            except queue.Empty:
                yield ": ping\n\n"  # tiene viva la connessione
                continue
            if ev is None:
                _esecuzioni.pop(run_id, None)
                yield "event: chiuso\ndata: {}\n\n"
                return
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(eventi(), media_type="text/event-stream")


if __name__ == "__main__":
    porta = int(os.getenv("PORT", "8000"))
    print(f"\n  Apri http://localhost:{porta}  (modalita': {'DEMO' if crew.modalita_demo() else crew.nome_modello()})\n")
    # reload: il server si riavvia da solo quando cambia il codice (.py) o l'interfaccia
    uvicorn.run("server:app", host=os.getenv("HOST", "127.0.0.1"), port=porta,
                reload=os.getenv("AUTO_RELOAD", "true").lower() == "true",
                reload_dirs=[str(Path(__file__).parent)], reload_includes=["*.py", "*.env"])
