"""
Motore: costruisce la crew CrewAI a partire da agenti.py e manda
eventi ("agente X ha iniziato", "agente X ha finito"...) all'interfaccia.
Di solito NON serve modificarlo: si lavora su agenti.py e su .env.

Cambio automatico di modello: ogni singola chiamata prova il modello principale
e, se e' occupato (503), al limite (429) o troppo lento, passa subito al successivo
della lista LLM_MODELLI_RISERVA. Il modello che funziona resta quello attivo.
"""
import os
import time
import warnings
from typing import Any

# Avviso innocuo di CrewAI sui callback (non usiamo i checkpoint): lo nascondiamo.
warnings.filterwarnings("ignore", message="A function callback cannot be saved")

from agenti import AGENTI  # noqa: E402


def modalita_demo() -> bool:
    return os.getenv("MOCK_MODE", "false").strip().lower() in ("1", "true", "si", "yes")


def nome_modello() -> str:
    return os.getenv("LLM_MODEL", "gemini/gemini-3.8-flash").strip()


_CHIAVI = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY",
           "openrouter": "OPENROUTER_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def modelli_da_provare() -> list[str]:
    """Modello principale + riserve (LLM_MODELLI_RISERVA, separati da virgola).
    Salta i provider di cui non c'e' la chiave nel .env."""
    lista = [nome_modello()] + [
        m.strip() for m in os.getenv("LLM_MODELLI_RISERVA", "").split(",") if m.strip()
    ]
    utili = []
    for m in lista:
        chiave = _CHIAVI.get(m.split("/")[0])
        if chiave and not os.getenv(chiave, "").strip():
            continue
        if m not in utili:
            utili.append(m)
    return utili or [nome_modello()]


def _errore_temporaneo(msg: str) -> bool:
    low = msg.lower()
    return any(t in low for t in ("503", "429", "500", "502", "504", "unavailable", "overloaded",
                                  "high demand", "quota", "rate limit", "resource_exhausted",
                                  "404", "not_found", "timeout", "timed out", "deadline", "thinking",
                                  "empty", "no content"))


def _opzioni_llm(modello: str) -> dict:
    """Opzioni extra per Gemini: ragionamento breve (molto piu' veloce) e tempo massimo di attesa."""
    secondi = int(os.getenv("TIMEOUT_SECONDI", "120"))
    if not modello.startswith("gemini/"):
        return {"timeout": secondi}
    from google.genai import types

    opzioni: dict[str, Any] = {"client_params": {"http_options": types.HttpOptions(timeout=secondi * 1000)}}
    livello = os.getenv("RAGIONAMENTO", "low").strip().lower()
    if livello and livello != "auto":
        opzioni["thinking_config"] = types.ThinkingConfig(include_thoughts=False, thinking_level=livello)
    return opzioni


def crea_llm_con_riserva(emit):
    """Un 'LLM' per CrewAI che, chiamata per chiamata, passa al modello successivo se quello attivo fallisce."""
    from crewai import LLM
    from crewai.llms.base_llm import BaseLLM

    nomi = modelli_da_provare()
    temperatura = float(os.getenv("TEMPERATURA", "0.4"))

    class LLMConRiserva(BaseLLM):
        nomi_modelli: list[str]
        istanze: dict[str, Any] = {}
        attivo: int = 0

        def _istanza(self, i: int):
            nome = self.nomi_modelli[i]
            if nome not in self.istanze:
                self.istanze[nome] = LLM(model=nome, temperature=temperatura, **_opzioni_llm(nome))
            return self.istanze[nome]

        def call(self, messages, tools=None, callbacks=None, available_functions=None,
                 from_task=None, from_agent=None, response_model=None):
            ultimo_errore = None
            for i in range(self.attivo, len(self.nomi_modelli)):
                try:
                    risposta = self._istanza(i).call(
                        messages, tools=tools, callbacks=callbacks,
                        available_functions=available_functions, from_task=from_task,
                        from_agent=from_agent, response_model=response_model)
                    if i != self.attivo:
                        self.attivo = i
                    return risposta
                except Exception as e:
                    ultimo_errore = e
                    if not _errore_temporaneo(str(e)) or i == len(self.nomi_modelli) - 1:
                        break
                    succ = self.nomi_modelli[i + 1]
                    print(f"[riserva] {self.nomi_modelli[i]} non disponibile ({str(e)[:70]}...), passo a {succ}")
                    emit({"tipo": "avviso", "messaggio": f"{self.nomi_modelli[i]} occupato, passo a {succ}"})
                    emit({"tipo": "modello", "modello": succ})
            # tutti i modelli hanno fallito: la prossima chiamata riparte dal principale
            self.attivo = 0
            raise ultimo_errore

        def supports_function_calling(self) -> bool:
            return False

        def supports_stop_words(self) -> bool:
            return False

        def get_context_window_size(self) -> int:
            return 32000

    return LLMConRiserva(model=nomi[0], nomi_modelli=nomi, temperature=temperatura)


def _testo_compito(agente: dict, richiesta: str) -> str:
    return agente["compito"].replace("{richiesta}", richiesta)


def esegui_demo(richiesta: str, emit) -> str:
    """Finta esecuzione: utile per provare la UI senza chiavi e senza consumare quota."""
    emit({"tipo": "inizio", "modello": "demo (nessuna chiamata API)"})
    fase = fasi()
    risultato = ""
    for f in range(1, max(fase.values()) + 1):
        gruppo = [a for a in AGENTI if fase[a["id"]] == f]
        for a in gruppo:  # gli agenti della stessa fase partono insieme
            emit({"tipo": "agente_inizio", "id": a["id"]})
        for n, a in enumerate(gruppo):
            time.sleep(1.5 if n == 0 else 0.4)
            risultato = (
                f"### {a['icona']} {a['nome']} (demo)\n\n"
                f"Qui comparira' l'output reale dell'agente **{a['nome']}**.\n\n"
                f"- Richiesta ricevuta: _{richiesta[:120]}_\n"
                f"- Formato atteso: {a['risultato']}\n"
            )
            emit({"tipo": "agente_fine", "id": a["id"], "output": risultato})
    emit({"tipo": "fine", "output": risultato})
    return risultato


def dipendenze(agenti: list[dict] = None) -> dict[str, list[str]]:
    """Da chi dipende ogni agente. Se 'dipende_da' manca, dipende dall'agente precedente
    (comportamento in sequenza). 'dipende_da': [] = parte subito."""
    agenti = agenti or AGENTI
    ids = [a["id"] for a in agenti]
    dip = {}
    for i, a in enumerate(agenti):
        d = a.get("dipende_da")
        if d is None:
            d = [ids[i - 1]] if i > 0 else []
        sconosciuti = [x for x in d if x not in ids]
        if sconosciuti:
            raise ValueError(f"L'agente '{a['id']}' dipende da agenti inesistenti: {sconosciuti}")
        dip[a["id"]] = list(d)
    return dip


def fasi(agenti: list[dict] = None) -> dict[str, int]:
    """Numero di fase di ogni agente: 1 = parte subito, 2 = dopo la fase 1, ecc.
    Agenti nella stessa fase lavorano in parallelo."""
    dip = dipendenze(agenti)
    fase: dict[str, int] = {}

    def calcola(i, visti=()):
        if i in visti:
            raise ValueError(f"Dipendenze circolari tra agenti: {' -> '.join(visti + (i,))}")
        if i not in fase:
            fase[i] = 1 + max((calcola(d, visti + (i,)) for d in dip[i]), default=0)
        return fase[i]

    for i in dip:
        calcola(i)
    return fase


def _esegui_agente(cfg: dict, richiesta: str, materiale: dict[str, str], llm) -> str:
    """Esegue un singolo agente come mini-crew, passandogli il lavoro degli agenti da cui dipende."""
    from crewai import Agent, Crew, Process, Task

    agente = Agent(
        role=cfg["ruolo"],
        goal=cfg["obiettivo"],
        backstory=cfg["storia"] + " Rispondi sempre in italiano.",
        llm=llm,
        allow_delegation=False,
        max_iter=int(os.getenv("MAX_ITER", "3")),
        max_retry_limit=1,
        verbose=False,
    )
    descrizione = _testo_compito(cfg, richiesta)
    if materiale:
        nomi = {a["id"]: f"{a['icona']} {a['nome']}" for a in AGENTI}
        blocchi = "\n\n".join(f"### Lavoro di {nomi[i]}\n{testo}" for i, testo in materiale.items())
        descrizione += f"\n\n---\nRichiesta originale dell'utente: \"{richiesta}\"\n\nMateriale prodotto dagli altri agenti:\n\n{blocchi}"
    compito = Task(description=descrizione, expected_output=cfg["risultato"], agent=agente)
    crew = Crew(
        agents=[agente], tasks=[compito], process=Process.sequential,
        max_rpm=int(os.getenv("MAX_RPM", "10")),
        verbose=os.getenv("VERBOSE", "false").lower() == "true",
    )
    return str(crew.kickoff().raw)


def esegui_crew(richiesta: str, emit, llm=None) -> str:
    """Coordinatore: fa partire ogni agente appena tutti quelli da cui dipende hanno finito.
    Agenti indipendenti lavorano in parallelo."""
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    llm = llm or crea_llm_con_riserva(emit)
    emit({"tipo": "inizio", "modello": llm.model})

    dip = dipendenze()
    per_id = {a["id"]: a for a in AGENTI}
    risultati: dict[str, str] = {}
    in_corso = {}

    with ThreadPoolExecutor(max_workers=int(os.getenv("MAX_PARALLELO", "4"))) as pool:
        while len(risultati) < len(AGENTI):
            for aid, d in dip.items():
                if aid in risultati or aid in in_corso.values():
                    continue
                if all(x in risultati for x in d):
                    materiale = {x: risultati[x] for x in d}
                    emit({"tipo": "agente_inizio", "id": aid})
                    fut = pool.submit(_esegui_agente, per_id[aid], richiesta, materiale, llm)
                    in_corso[fut] = aid
            fatti, _ = wait(list(in_corso), return_when=FIRST_COMPLETED)
            for fut in fatti:
                aid = in_corso.pop(fut)
                try:
                    risultati[aid] = fut.result()
                except Exception:
                    for altro in in_corso:
                        altro.cancel()
                    raise
                emit({"tipo": "agente_fine", "id": aid, "output": risultati[aid]})

    # risultato finale: gli agenti da cui non dipende nessuno (di solito uno solo, l'ultimo)
    usati = {x for d in dip.values() for x in d}
    finali = [a["id"] for a in AGENTI if a["id"] not in usati]
    risultato = "\n\n---\n\n".join(risultati[i] for i in finali)
    emit({"tipo": "fine", "output": risultato})
    return risultato


def esegui(richiesta: str, emit) -> str:
    try:
        if modalita_demo():
            return esegui_demo(richiesta, emit)
        return esegui_crew(richiesta, emit)
    except Exception as e:  # mostra l'errore nell'interfaccia invece di bloccarsi
        msg = str(e)
        consiglio = ""
        low = msg.lower()
        if _errore_temporaneo(msg):
            consiglio = ("Tutti i modelli sono occupati o al limite gratuito: aspetta un minuto e riprova, "
                         "oppure aggiungi una chiave Groq nel .env come riserva.")
        elif "api key" in low or "api_key" in low or "401" in msg or "403" in msg:
            consiglio = "Chiave API mancante o non valida: controlla il file .env."
        emit({"tipo": "errore", "messaggio": msg[:600], "consiglio": consiglio})
        return ""
