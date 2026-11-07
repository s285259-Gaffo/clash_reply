"""Verifica in 5 secondi che chiave e modello nel .env funzionano.
Uso:  python test_chiave.py
"""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import os  # noqa: E402

from crewai import LLM  # noqa: E402

modello = os.getenv("LLM_MODEL", "gemini/gemini-3.8-flash")
print(f"Provo il modello: {modello} ...")
try:
    risposta = LLM(model=modello).call("Rispondi solo con: funziona!")
    print("OK ->", risposta)
except Exception as e:
    print("ERRORE ->", e)
