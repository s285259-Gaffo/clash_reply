"""Elenca i modelli Gemini disponibili con la tua chiave.
Uso: doppio clic su elenca_modelli.bat"""
import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
chiave = os.getenv("GEMINI_API_KEY", "").strip()
req = urllib.request.Request(
    "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
    headers={"x-goog-api-key": chiave},
)
try:
    dati = json.load(urllib.request.urlopen(req, timeout=20))
    print("Modelli Gemini utilizzabili (scrivili nel .env come gemini/<nome>):\n")
    for m in dati.get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            print("  gemini/" + m["name"].split("/", 1)[1])
except Exception as e:
    print("ERRORE:", e)
