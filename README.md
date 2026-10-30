# Document Summarizer 📝

Un'applicazione Python con interfaccia grafica che usa l'AI per riassumere documenti e testi lunghi.

## 🚀 Caratteristiche
- Carica file di testo (`.txt`, `.md`) o PDF
- Genera riassunti automatici con AI locale (LM Studio)
- Tre livelli di dettaglio reali (breve, medio, lungo)
- Gestione automatica dei documenti lunghi (riassunto a più passaggi)
- Interfaccia Tkinter con scrollbar, copia del riassunto e generazione in background (la finestra non si blocca)

## 📋 Prerequisiti
1. **LM Studio** avviato con un modello locale, con il server OpenAI-compatible attivo
   (di default su `http://localhost:1235`)
2. **Python 3.8+**
3. **Librerie Python**:
```bash
pip install -r requirements.txt
```

## 🎯 Come Usare

```bash
python main.py
```

1. Clicca **📂 Seleziona File** e scegli un `.txt`, `.md` o `.pdf`
2. Scegli il livello di dettaglio e verifica il nome del modello
3. Clicca **🚀 Riassumi**
4. Usa **📋 Copia** per copiare il risultato negli appunti

## 🔧 Configurazione

In `main.py` (oppure tramite variabili d'ambiente `MODEL_URL` e `MODEL_NAME`):

```python
MODEL_URL = "http://localhost:1235/v1/chat/completions"
MODEL_NAME = "qwen3.5-4b"
```

- Il nome del modello deve combaciare con quello caricato in LM Studio
  (puoi anche modificarlo direttamente dal campo "Modello" nell'interfaccia).
- Se usi un'altra porta, aggiorna `MODEL_URL` di conseguenza.
- Per modelli con un contesto più ampio puoi aumentare `MAX_CHARS` e `CHUNK_SIZE`.

## 📁 Struttura File
```
document_summarizer/
├── main.py          # Codice principale con interfaccia GUI
├── requirements.txt # Dipendenze Python
└── README.md        # Questo file
```

## 💡 Note

- I documenti più lunghi di `MAX_CHARS` (15.000 caratteri) vengono divisi in blocchi,
  riassunti singolarmente e poi sintetizzati in un riassunto finale.
- I PDF scansionati (solo immagini) non contengono testo estraibile: l'app lo segnala.
