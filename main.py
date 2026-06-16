from tkinter import *
from tkinter import filedialog, ttk
from PyPDF2 import PdfReader
import pyttsx4  
import threading
import re
import os
import hashlib
import json
import queue  

# =========================
# STATE MANAGER
# =========================
class PlayerState:
    def __init__(self):
        self.lock = threading.Lock()
        self.pdf_reader = None
        self.current_page = 0
        self.is_playing = False
        self.stop_flag = False
        self.file_hash = None

state = PlayerState()
BOOKMARK_FILE = "books_history.json"

speech_queue = queue.Queue()
local_engine = None

# =========================
# UTILITIES
# =========================
def file_hash(path):
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            buf = f.read(1024 * 1024 * 10)
            h.update(buf)
        return h.hexdigest()
    except Exception as e:
        print(f"Hash calculation failure: {e}")
        return None

def save_bookmark():
    if not state.pdf_reader:
        return

    data = {}    
    if os.path.exists(BOOKMARK_FILE):    
        try:    
            with open(BOOKMARK_FILE, "r") as f:    
                data = json.load(f)    
        except Exception:    
            pass    

    with state.lock:    
        data[state.file_hash] = state.current_page    

    try:    
        with open(BOOKMARK_FILE, "w") as f:    
            json.dump(data, f, indent=4)    
    except Exception as e:    
        print(f"Error saving bookmark data: {e}")

def load_bookmark():
    if not (state.pdf_reader and state.file_hash):
        return

    if os.path.exists(BOOKMARK_FILE):    
        try:    
            with open(BOOKMARK_FILE, "r") as f:    
                data = json.load(f)    

            if state.file_hash in data:    
                p = data[state.file_hash]    
                if 0 <= p < len(state.pdf_reader.pages):    
                    with state.lock:    
                        state.current_page = p    
        except Exception as e:    
            print(f"Error loading bookmark data: {e}")

# =========================
# AUDIO WORKER & PIPELINE
# =========================
def audio_loop():
    """Background thread worker: Extracts text data only, no direct audio execution."""
    while True:
        with state.lock:
            if state.stop_flag or not state.is_playing:
                break    
            if not state.pdf_reader:    
                break    
            if state.current_page >= len(state.pdf_reader.pages):    
                state.is_playing = False    
                root.after(0, lambda: status.config(text="Finished Audiobook!"))    
                root.after(0, lambda: play_btn.config(text="Play"))    
                break    

            page_index = state.current_page    

        try:    
            page = state.pdf_reader.pages[page_index]    
            text = page.extract_text() or ""    
        except Exception:
            text = ""    

        if not text.strip():
            root.after(0, lambda p=page_index: status.config(text=f"Page {p + 1} is empty. Skipping..."))    
            with state.lock:    
                state.current_page += 1    
            root.after(0, update_ui)    
            save_bookmark()  
            continue    

        root.after(0, lambda p=page_index: status.config(text=f"Reading Page {p + 1}..."))    
            
        cleaned_text = text.replace("-\n", "").replace("\n", " ")    
        sentences = re.split(r'(?<=[.!?…])\s+|(?<=[,;])\s+(?=[A-Za-z])', cleaned_text.strip())    

        for s in sentences:  
            if s.strip():  
                speech_queue.put(s.strip())  

        # Wait for the main UI thread to empty out the current page sentences
        while not speech_queue.empty():  
            with state.lock:  
                if state.stop_flag or not state.is_playing:  
                    return  
            threading.Event().wait(0.1)  

        with state.lock:    
            if state.current_page == page_index:    
                state.current_page += 1    

        save_bookmark()    
        root.after(0, update_ui)

def process_speech_pipeline():
    """Main UI thread worker: Safe driver execution with no background apartment crashes."""
    global local_engine
    if local_engine is None:
        try:
            local_engine = pyttsx4.init()  
        except Exception as e:
            status.config(text=f"TTS Init Error: {e}")
            return

    with state.lock:  
        should_run = state.is_playing and not state.stop_flag  

    if not should_run:  
        # Purge text strings if playback was actively paused/stopped
        while not speech_queue.empty():  
            try: speech_queue.get_nowait()  
            except queue.Empty: break  
        return  

    if not speech_queue.empty():
        try:    
            sentence = speech_queue.get_nowait()  
            local_engine.setProperty("rate", int(speed.get()))    
            local_engine.setProperty("volume", float(volume.get()))    
            local_engine.say(sentence)    
            local_engine.runAndWait()    
        except queue.Empty:  
            pass  
        except Exception as engine_err:    
            print(f"Driver execution loop interrupt error: {engine_err}")    

    # Always reschedule the check so the main loop keeps polling safely
    root.after(20, process_speech_pipeline)

# =========================
# CONTROL FUNCTIONS
# =========================
def load_pdf():
    path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
    if not path:
        return

    try:    
        status.config(text="Verifying file structures...")
        root.update_idletasks()    
            
        state.pdf_reader = PdfReader(path)    
        state.file_hash = file_hash(path)    
        state.current_page = 0    

        load_bookmark()    
        update_ui()    
        status.config(text="Book loaded successfully.")    
    except Exception:    
        status.config(text=f"Error loading PDF: Corrupted file.")

def play_pause():
    if not state.pdf_reader:
        status.config(text="Please load a PDF file first.")
        return

    with state.lock:    
        if not state.is_playing:    
            if state.current_page >= len(state.pdf_reader.pages):  
                state.current_page = 0  

            state.is_playing = True    
            state.stop_flag = False    

            while not speech_queue.empty():  
                try: speech_queue.get_nowait()  
                except queue.Empty: break  

            threading.Thread(target=audio_loop, daemon=True).start()    
            root.after(20, process_speech_pipeline)  
            status.config(text="Playing...")    
            play_btn.config(text="Pause")    
        else:    
            state.is_playing = False    
            if local_engine:    
                try: local_engine.stop()    
                except Exception: pass    
            status.config(text="Paused")    
            play_btn.config(text="Play")    
    save_bookmark()

def stop():
    with state.lock:
        state.is_playing = False
        state.stop_flag = True

    if local_engine:    
        try: local_engine.stop()    
        except Exception: pass    
            
    while not speech_queue.empty():  
        try: speech_queue.get_nowait()  
        except queue.Empty: break  

    save_bookmark()    
    root.after(0, update_ui)    
    status.config(text="Stopped & Position Saved")    
    play_btn.config(text="Play")

def next_page():
    if not state.pdf_reader: return
    should_restart = False
    with state.lock:
        if state.current_page < len(state.pdf_reader.pages) - 1:
            state.current_page += 1
            if state.is_playing:
                should_restart = True
    if should_restart:
        stop()
        play_pause()
    else:
        update_ui()
        save_bookmark()

def prev_page():
    if not state.pdf_reader: return
    should_restart = False
    with state.lock:
        if state.current_page > 0:
            state.current_page -= 1
            if state.is_playing:
                should_restart = True
    if should_restart:
        stop()
        play_pause()
    else:
        update_ui()
        save_bookmark()

def update_ui():
    if state.pdf_reader:
        with state.lock:
            p_idx = state.current_page
        page_label.config(text=f"Page {p_idx + 1}/{len(state.pdf_reader.pages)}")

def on_close():
    with state.lock:
        state.is_playing = False
        state.stop_flag = True
    if local_engine:
        try: local_engine.stop()
        except Exception: pass
    root.destroy()

# =========================
# UI BUILD
# =========================
root = Tk()
root.title("Audiobook Player Pro")
root.geometry("450x480")
root.configure(bg="#f5f5f7")

style = ttk.Style()
style.theme_use('clam')

Label(root, text="Audiobook Player Pro", font=("Arial", 16, "bold"), bg="#f5f5f7", fg="#2c3e50").pack(pady=15)

ttk.Button(root, text="📁 Open PDF File", command=load_pdf, width=20).pack(pady=5)

page_label = Label(root, text="No PDF Document Loaded", font=("Arial", 11), bg="#f5f5f7", fg="#7f8c8d")
page_label.pack(pady=10)

controls = Frame(root, bg="#f5f5f7")
controls.pack(pady=5)

play_btn = ttk.Button(controls, text="Play", command=play_pause, width=10)
play_btn.pack(side=LEFT, padx=5)

ttk.Button(controls, text="Stop", command=stop, width=10).pack(side=LEFT, padx=5)

nav = Frame(root, bg="#f5f5f7")
nav.pack(pady=5)

ttk.Button(nav, text="⏮ Back Page", command=prev_page, width=12).pack(side=LEFT, padx=5)
ttk.Button(nav, text="Skip Page ⏭", command=next_page, width=12).pack(side=LEFT, padx=5)

sliders_frame = Frame(root, bg="#f5f5f7")
sliders_frame.pack(fill=X, padx=30, pady=15)
sliders_frame.columnconfigure(1, weight=1)

Label(sliders_frame, text="Speed Rate:", bg="#f5f5f7").grid(row=0, column=0, sticky="w", pady=5)
speed = ttk.Scale(sliders_frame, from_=100, to=250)
speed.set(175)
speed.grid(row=0, column=1, sticky="ew", padx=5)

Label(sliders_frame, text="Volume Level:", bg="#f5f5f7").grid(row=1, column=0, sticky="w", pady=5)
volume = ttk.Scale(sliders_frame, from_=0.0, to=1.0)
volume.set(0.85)
volume.grid(row=1, column=1, sticky="ew", padx=5)

status = Label(root, text="System Standby", font=("Arial", 10, "italic"), bd=1, relief=SUNKEN, anchor=W, bg="#eef2f3", padx=10)
status.pack(side=BOTTOM, fill=X)

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()