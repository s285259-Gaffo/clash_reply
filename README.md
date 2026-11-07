# Studente Fantasma · Reply Clash

L'app analizza slide, trascrizioni, esame e soluzioni per mostrare al docente quali
passaggi dell'esame sono coperti dal materiale e quali studenti simulati rischiano
di bloccarsi. La cartella `materiale/analisi1_simulato` contiene una demo fittizia.

## Compilare e visualizzare la verifica locale

Su Windows, fai doppio clic su `verifica_e_visualizza.bat`. Il file compila i moduli
Python, esegue le prove dei guardrail e apre nel browser
`materiale/analisi1_simulato/report/verifica_guardrail.html`.
Non servono chiavi API ne' librerie aggiuntive. Serve Python 3.11 o successivo.
I report storici nella pagina sono precedenti ai nuovi controlli; la simulazione e'
segnata separatamente.

Per un altro corso, dal terminale:

```bat
verifica_e_visualizza.bat nome_corso
```

## Avviare l'app

Fai doppio clic su `avvia.bat` e apri <http://localhost:8000>. Il primo avvio
crea `.venv` nella cartella del progetto, installa li' le librerie di
`requirements.txt` e crea `.env` copiando `.env.example`. Non installa pacchetti
nell'interprete Python gestito da `uv`.
Con `MOCK_MODE=true` l'app riproduce la demo senza chiamate API. Per un nuovo
crash test reale, inserisci una chiave API nel `.env`, imposta `MOCK_MODE=false`
e usa l'interfaccia. Dopo il test, esegui di nuovo `verifica_e_visualizza.bat`
per confrontare il nuovo report con la chiave delle lacune, incluso il falso amico.

Il voto dei quattro profili e' una stima in trentesimi calcolata dai passi
giustificati; non e' un voto assegnato da un modello a uno studente reale.
