"""
API del ciclo di miglioramento durante il semestre (lato studente /studente e lato docente /docente).
Collegamento in server.py:   import semestre_api; app.include_router(semestre_api.router)
"""
import fastapi
from fastapi import HTTPException
from pydantic import BaseModel

import materiale
import semestre

router = fastapi.APIRouter(prefix="/api/semestre")


def _corso(nome: str) -> str:
    if nome not in materiale.elenca_corsi():
        raise HTTPException(404, f"Corso '{nome}' non trovato")
    return nome


class Domanda(BaseModel):
    domanda: str
    argomento: str | None = None
    corso: str = semestre.CORSO_DEFAULT


class Dubbio(BaseModel):
    pseudonimo: str
    argomento: str
    dove: str
    testo: str = ""
    corso: str = semestre.CORSO_DEFAULT


class Verifica(BaseModel):
    pseudonimo: str
    chiarimento: str
    risposta: int
    corso: str = semestre.CORSO_DEFAULT


class Intervento(BaseModel):
    argomento: str
    azione: str  # approva | modifica | scarta | riapri
    testo: str = ""
    nota: str = ""
    corso: str = semestre.CORSO_DEFAULT


@router.get("/argomenti")
def argomenti(corso: str = semestre.CORSO_DEFAULT):
    c, _ = semestre.corso(_corso(corso))
    titoli = {}
    for f in c.fonti.values():
        if f.tipo == "slide":
            titoli.setdefault(f.lezione, f.titolo)
    return {"corso": corso, "modalita": semestre._modalita(), "soglia": semestre.SOGLIA_ANONIMATO,
            "lezioni": sorted({f.lezione for f in c.fonti.values()}),
            "argomenti": [{k: a[k] for k in ("id", "titolo", "lezione")} for a in semestre.ARGOMENTI]}


@router.post("/domanda")
def domanda(d: Domanda):
    return semestre.rispondi(_corso(d.corso), d.domanda, d.argomento)


@router.post("/dubbio")
def dubbio(d: Dubbio):
    r = semestre.segnala_dubbio(_corso(d.corso), d.pseudonimo, d.argomento, d.dove, d.testo)
    if not r["ok"]:
        raise HTTPException(409 if "gia'" in r["errore"] else 400, r["errore"])
    return r


@router.get("/miei")
def miei(pseudonimo: str, corso: str = semestre.CORSO_DEFAULT):
    return semestre.miei(_corso(corso), pseudonimo)


@router.get("/chiarimenti")
def chiarimenti(pseudonimo: str = "", corso: str = semestre.CORSO_DEFAULT):
    return {"chiarimenti": semestre.chiarimenti_studente(_corso(corso), pseudonimo)}


@router.post("/verifica")
def verifica(v: Verifica):
    r = semestre.rispondi_verifica(_corso(v.corso), v.pseudonimo, v.chiarimento, v.risposta)
    if not r["ok"]:
        raise HTTPException(400, r["errore"])
    return r


@router.get("/docente")
def docente(corso: str = semestre.CORSO_DEFAULT):
    return semestre.vista_docente(_corso(corso))


@router.post("/intervento")
def intervento(i: Intervento):
    r = semestre.decidi(_corso(i.corso), i.argomento, i.azione, i.testo, i.nota)
    if not r["ok"]:
        raise HTTPException(400, r["errore"])
    return r


@router.post("/reset")
def reset(corso: str = semestre.CORSO_DEFAULT):
    return semestre.reset(_corso(corso))
