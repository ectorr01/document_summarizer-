"""
Document Summarizer - Applicazione Python per riassumere documenti con AI locale
Usa LM Studio come modello di linguaggio
"""

import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import requests
from pypdf import PdfReader


# Configurazione AI (modifica in base al tuo setup LM Studio)
MODEL_URL = os.getenv("MODEL_URL", "http://localhost:1235/v1/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3.5-4b")
REQUEST_TIMEOUT = 300

# Limite di caratteri inviati in una singola richiesta (evita di sforare il contesto)
MAX_CHARS = 15000
# Dimensione dei blocchi quando il documento è troppo lungo (riassunto a due passaggi)
CHUNK_SIZE = 10000

# Prompt per il riassunto (il testo e l'istruzione vengono inseriti con replace)
SUMMARIZE_PROMPT = """Agisci come un assistente intelligente. Ecco il testo da riassumere:

__TEXT__

__INSTRUCTION__ Mantieni le informazioni chiave ma elimina ripetizioni e dettagli non essenziali."""

# Prompt usato per riassumere le singole parti di un documento molto lungo
CHUNK_PROMPT = """Riassumi in modo conciso la seguente parte di un documento.
Mantieni nomi, numeri, date e informazioni chiave.

__TEXT__"""

# Livello di dettaglio: istruzione per il modello e token massimi della risposta
DETAIL_SETTINGS = {
    "breve": ("Riassumi il contenuto in massimo 3-4 frasi.", 400),
    "medio": ("Riassumi il contenuto in uno o due paragrafi.", 800),
    "lungo": ("Riassumi il contenuto in modo dettagliato, con sezioni e punti elenco quando utile.", 1600),
}


def short(text, limit=500):
    """Tronca un testo per mostrarlo nei messaggi di errore"""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def split_text(text, size):
    """Divide il testo in blocchi di al massimo `size` caratteri"""
    units = re.split(r"(?<=[.!?])\s+|\n\s*\n", text)
    chunks = []
    current = ""

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue

        # Un singolo paragrafo più lungo del limite viene spezzato a forza
        while len(unit) > size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(unit[:size])
            unit = unit[size:]

        if len(current) + len(unit) + 1 > size:
            chunks.append(current)
            current = unit
        else:
            current = f"{current} {unit}" if current else unit

    if current:
        chunks.append(current)

    return chunks or [text[:size]]


class DocumentSummarizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Document Summarizer - AI Assistant")
        self.root.geometry("800x600")

        # Variabili di stato
        self.file_path = None
        self.document_text = ""
        self.is_working = False
        self.has_summary = False

        self.create_widgets()

    def create_widgets(self):
        """Crea l'interfaccia grafica"""

        # Frame principale
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        # L'area di output è la riga 3: è quella che deve espandersi
        main_frame.rowconfigure(3, weight=1)

        # Titolo
        title_label = ttk.Label(main_frame, text="📝 Document Summarizer",
                                font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(0, 20))

        # Sezione: Carica File
        file_frame = ttk.LabelFrame(main_frame, text="Carica un Documento", padding="5")
        file_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        file_frame.columnconfigure(0, weight=1)

        # Label per il percorso del file
        self.file_path_label = ttk.Label(file_frame, text="Nessun file selezionato")
        self.file_path_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        # Button per selezionare il file (testo o PDF)
        btn_frame = ttk.Frame(file_frame)
        btn_frame.grid(row=1, column=0, pady=(5, 0), sticky="e")

        self.select_file_btn = ttk.Button(btn_frame, text="📂 Seleziona File",
                                          command=self.select_file)
        self.select_file_btn.pack(side=tk.RIGHT, padx=2)

        # Sezione: Impostazioni
        settings_frame = ttk.LabelFrame(main_frame, text="Impostazioni", padding="5")
        settings_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # Livello di dettaglio
        detail_label = ttk.Label(settings_frame, text="Livello di dettaglio:")
        detail_label.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")

        self.detail_var = tk.StringVar(value="medio")
        detail_combo = ttk.Combobox(settings_frame, textvariable=self.detail_var,
                                    values=["breve", "medio", "lungo"], state="readonly",
                                    width=10)
        detail_combo.grid(row=0, column=1, padx=(5, 20), pady=2, sticky="w")

        # Nome del modello caricato in LM Studio
        model_label = ttk.Label(settings_frame, text="Modello:")
        model_label.grid(row=1, column=0, padx=(0, 5), pady=2, sticky="w")

        self.model_var = tk.StringVar(value=MODEL_NAME)
        model_entry = ttk.Entry(settings_frame, textvariable=self.model_var, width=30)
        model_entry.grid(row=1, column=1, padx=(5, 20), pady=2, sticky="w")

        # Sezione: Output
        output_frame = ttk.LabelFrame(main_frame, text="Riassunto Generato", padding="5")
        output_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        # Text area per il riassunto (con scrollbar)
        self.summary_text = tk.Text(output_frame, wrap=tk.WORD, height=25,
                                    font=("Courier New", 10), state=tk.DISABLED)
        self.summary_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL,
                                  command=self.summary_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.summary_text.configure(yscrollcommand=scrollbar.set)

        # Sezione: Controlli
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=4, column=0, pady=(10, 0), sticky="e")

        self.copy_btn = ttk.Button(control_frame, text="📋 Copia",
                                   command=self.copy_summary, state=tk.DISABLED)
        self.copy_btn.pack(side=tk.RIGHT, padx=2)

        self.summarize_btn = ttk.Button(control_frame, text="🚀 Riassumi",
                                        command=self.summarize_document)
        self.summarize_btn.pack(side=tk.RIGHT, padx=2)

        # Info label
        self.info_label = ttk.Label(main_frame, text="", foreground="gray")
        self.info_label.grid(row=5, column=0, sticky="w", pady=(10, 0))

    def set_status(self, text):
        """Aggiorna la label informativa"""
        self.info_label.config(text=text)

    def select_file(self):
        """Seleziona un documento (.txt, .md o .pdf) e ne legge il contenuto"""
        filetypes = [
            ("Documenti", "*.txt *.md *.pdf"),
            ("File di testo", "*.txt *.md"),
            ("PDF", "*.pdf"),
            ("Tutti i file", "*.*")
        ]

        filepath = filedialog.askopenfilename(
            title="Seleziona un documento",
            filetypes=filetypes
        )

        if not filepath:
            return

        try:
            if filepath.lower().endswith(".pdf"):
                text = self.read_pdf(filepath)
            else:
                text = self.read_text_file(filepath)
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile leggere il file:\n{e}")
            return

        # Lo stato viene aggiornato solo se la lettura è andata a buon fine
        if not text.strip():
            messagebox.showwarning(
                "Documento vuoto",
                "Il file non contiene testo estraibile "
                "(potrebbe essere un PDF scansionato)."
            )
            self.set_status("⚠️ Nessun testo estraibile dal file selezionato.")
            return

        self.file_path = filepath
        self.document_text = text.strip()
        self.file_path_label.config(text=os.path.basename(filepath))
        self.set_status(f"✅ File caricato ({len(self.document_text):,} caratteri).")

    def read_text_file(self, filepath):
        """Legge un file di testo, con fallback sugli encoding più comuni"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='cp1252', errors='replace') as f:
                return f.read()

    def read_pdf(self, filepath):
        """Estrae il testo da un PDF"""
        reader = PdfReader(filepath)

        if reader.is_encrypted:
            # Prova con password vuota, altrimenti segnala il problema
            try:
                if not reader.decrypt(""):
                    raise ValueError("Il PDF è protetto da password.")
            except Exception:
                raise ValueError("Il PDF è protetto da password.")

        # Unisci il testo di tutte le pagine
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n\n"

        return full_text

    def summarize_document(self):
        """Avvia il riassunto in un thread separato per non bloccare la GUI"""

        if self.is_working:
            return

        if not self.document_text:
            messagebox.showwarning("Attenzione", "Carica prima un documento!")
            return

        detail = self.detail_var.get()
        text = self.document_text

        self.is_working = True
        self.summarize_btn.config(state=tk.DISABLED)
        self.root.config(cursor="watch")
        self.set_status("⏳ Invio del documento al modello...")

        worker = threading.Thread(
            target=self._summarize_worker, args=(text, detail), daemon=True
        )
        worker.start()

    def _summarize_worker(self, text, detail):
        """Esegue le chiamate al modello fuori dal thread della GUI"""
        try:
            summary = self.generate_summary(text, detail)
        except requests.exceptions.ConnectionError:
            self._ui(lambda: messagebox.showerror(
                "Connessione",
                "LM Studio non è avviato o l'URL è errato.\n"
                f"Verifica che il server sia in ascolto su:\n{MODEL_URL}\n\n"
                "Assicurati che LM Studio sia aperto!"
            ))
            self._ui(lambda: self.set_status("❌ Connessione a LM Studio non riuscita."))
        except Exception as e:
            error = str(e)
            self._ui(lambda: messagebox.showerror(
                "Errore", f"Impossibile generare il riassunto:\n{error}"
            ))
            self._ui(lambda: self.set_status("❌ Errore durante la generazione."))
        else:
            self._ui(lambda: self.display_summary(summary, detail))
        finally:
            self._ui(self._end_work)

    def _ui(self, func):
        """Esegue una funzione sul thread della GUI"""
        self.root.after(0, func)

    def _end_work(self):
        """Ripristina i controlli al termine dell'elaborazione"""
        self.is_working = False
        self.summarize_btn.config(state=tk.NORMAL)
        self.root.config(cursor="")

    def generate_summary(self, text, detail):
        """Genera il riassunto, con riassunto a due passaggi per documenti lunghi"""
        instruction, max_tokens = DETAIL_SETTINGS.get(detail, DETAIL_SETTINGS["medio"])

        if len(text) <= MAX_CHARS:
            return self.call_model(self.build_prompt(text, instruction), max_tokens)

        # Documento troppo lungo: riassumi ogni parte e poi sintetizza il tutto
        chunks = split_text(text, CHUNK_SIZE)
        partials = []

        for index, chunk in enumerate(chunks, start=1):
            self._ui(lambda i=index, n=len(chunks): self.set_status(
                f"⏳ Riassumo la parte {i}/{n}..."
            ))
            partials.append(
                self.call_model(CHUNK_PROMPT.replace("__TEXT__", chunk), 500)
            )

        combined = "\n\n".join(partials)
        if len(combined) > MAX_CHARS:
            combined = combined[:MAX_CHARS] + "\n[...]"

        self._ui(lambda: self.set_status("⏳ Preparo il riassunto finale..."))
        return self.call_model(self.build_prompt(combined, instruction), max_tokens)

    @staticmethod
    def build_prompt(text, instruction):
        """Costruisce il prompt senza usare str.format (le graffe nel testo lo romperebbero)"""
        prompt = SUMMARIZE_PROMPT.replace("__TEXT__", text)
        return prompt.replace("__INSTRUCTION__", instruction)

    def call_model(self, prompt, max_tokens):
        """Invia una richiesta al modello locale e restituisce il testo della risposta"""
        model = self.model_var.get().strip() or MODEL_NAME

        response = requests.post(MODEL_URL, json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": False
        }, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            raise RuntimeError(
                f"Risposta AI non valida (HTTP {response.status_code}):\n"
                f"{short(response.text)}"
            )

        try:
            data = response.json()
        except ValueError as e:
            raise RuntimeError(
                f"Risposta AI non in formato JSON:\n{e}\n\n{short(response.text)}"
            )

        # Formato OpenAI/LM Studio (chat completions)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            # Fallback per altri formati di risposta
            if isinstance(data, dict) and isinstance(data.get("output"), str):
                content = data["output"]
            elif isinstance(data, dict) and isinstance(data.get("content"), str):
                content = data["content"]
            else:
                raise RuntimeError(
                    f"Struttura risposta non riconosciuta:\n{short(response.text)}"
                )

        content = (content or "").strip()
        if not content:
            raise RuntimeError("Il modello ha restituito una risposta vuota.")
        return content

    def display_summary(self, summary, detail_level):
        """Mostra il riassunto nel text area"""

        if detail_level == "breve":
            formatted = f"📌 RIASSUNTO BREVE\n\n{summary}"
        elif detail_level == "medio":
            formatted = (f"📌 RIASSUNTO MEDIO\n\n{summary}\n\n"
                         "💡 Questo riassunto mantiene le informazioni principali "
                         "ma elimina dettagli non essenziali.")
        else:  # lungo
            formatted = (f"📌 RIASSUNTO LUNGO\n\n{summary}\n\n"
                         "✨ Questo riassunto è completo e copre tutti gli aspetti "
                         "importanti del documento originale.")

        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, formatted)
        self.summary_text.config(state=tk.DISABLED)

        self.has_summary = True
        self.copy_btn.config(state=tk.NORMAL)
        self.set_status("✅ Riassunto generato!")

    def copy_summary(self):
        """Copia il riassunto negli appunti"""
        if not self.has_summary:
            return

        content = self.summary_text.get(1.0, tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.set_status("📋 Riassunto copiato negli appunti.")


def main():
    """Funzione principale dell'applicazione"""

    root = tk.Tk()

    # Crea l'interfaccia
    app = DocumentSummarizerApp(root)
    app.set_status(f"Modello: {MODEL_NAME} — {MODEL_URL}")

    # Avvia il loop principale
    root.mainloop()


if __name__ == "__main__":
    main()
