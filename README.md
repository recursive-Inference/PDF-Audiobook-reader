# PDF-Audiobook-reader

A Python-based GUI application that converts PDF documents into audiobooks using a text-to-speech engine.  
It features a multi-threaded speech pipeline, bookmark saving, and smooth playback controls built with Tkinter.

---

## 🚀 Features

- 📂 Load and read PDF files
- 🔊 Text-to-speech audiobook playback
- ⏯ Play / Pause / Stop controls
- 📄 Page-by-page navigation (Next / Previous)
- 💾 Automatic bookmark saving (resume where you left off)
- ⚡ Thread-safe speech processing pipeline
- 🎚 Adjustable reading speed and volume
- 🧠 Queue-based sentence processing for smooth playback

---

## 🧠 How It Works

- PDF is loaded using **PyPDF2**
- Text is extracted page by page
- Sentences are split and pushed into a queue
- Speech engine reads sentences sequentially
- Progress and page position are saved automatically

---

## 🛠️ Requirements

Install dependencies using pip:

```bash
pip install PyPDF2 pyttsx4
