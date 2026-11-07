"""
Server web: espone gli agenti via API e serve l'interfaccia.
Avvio:  python server.py   ->  apri http://localhost:8000
"""
import json
import os
import queue
import threading
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
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
