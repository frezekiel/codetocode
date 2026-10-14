"""Scan pane: local images/PDFs and direct HTTP(S) file URLs."""
import io
import queue
import threading
import urllib.request
import urllib.parse
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import pymupdf


def read_scan(location):
    if urllib.parse.urlsplit(location).scheme in {'http', 'https'}:
        request = urllib.request.Request(location, headers={'User-Agent': 'CtC/0.6'})
        with urllib.request.urlopen(request, timeout=25) as response:
            data = response.read(50 * 1024 * 1024 + 1)
        if len(data) > 50 * 1024 * 1024:
            raise ValueError('Datei ist größer als 50 MB. Bitte lokal öffnen.')
    else:
        data = Path(location).read_bytes()
    if data.lstrip().startswith(b'%PDF'):
        document = pymupdf.open(stream=data, filetype='pdf')
        try:
            pages = []
            for index in range(min(len(document), 100)):
                pages.append(index)
            pix = document[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5))
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            return image, data, len(document)
        finally:
            document.close()
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        return image.convert('RGB'), None, 1
    except Exception as exc:
        raise ValueError('Die URL liefert keinen Bildscan/PDF. Bitte eine direkte Bild-URL oder einen heruntergeladenen Scan öffnen. Login- und JavaScript-Portale werden hier nicht unterstützt.') from exc


class ScanPane(ttk.Frame):
    def __init__(self, parent, state, on_reference):
        super().__init__(parent)
        self.state = state
        self.on_reference = on_reference
        self.url = tk.StringVar(value=state.get('reference', ''))
        self.image_data = state.get('image')
        self.pdf_data = state.get('pdf')
        self.page = state.get('page', 0)
        self.page_count = state.get('pages', 1)
        self.zoom = state.get('zoom', 1.0)
        self.results = queue.Queue()
        self.request_id = 0
        ttk.Label(self, text='Scan / Quelle', font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=8, pady=6)
        ttk.Entry(self, textvariable=self.url).pack(fill='x', padx=8)
        tools = ttk.Frame(self); tools.pack(fill='x', padx=8, pady=6)
        ttk.Button(tools, text='URL laden', command=self.load_url).pack(side='left')
        ttk.Button(tools, text='Datei öffnen', command=self.open_file).pack(side='left', padx=4)
        ttk.Button(self, text='URL in Aktmetadaten übernehmen', command=self.copy_reference).pack(anchor='w', padx=8)
        nav = ttk.Frame(self); nav.pack(fill='x', padx=8, pady=6)
        for label, command in [('−', lambda:self.resize(.8)), ('+', lambda:self.resize(1.25)), ('Einpassen', self.fit), ('← Seite', lambda:self.turn(-1)), ('Seite →', lambda:self.turn(1))]:
            ttk.Button(nav, text=label, command=command).pack(side='left', padx=2)
        self.status = ttk.Label(self, text='Bilddatei oder PDF öffnen. URLs müssen direkt auf den Scan zeigen.', wraplength=430)
        self.status.pack(fill='x', padx=8, pady=4)
        box=ttk.Frame(self); box.pack(fill='both', expand=True)
        self.canvas=tk.Canvas(box, background='#262b32', highlightthickness=0)
        vs=ttk.Scrollbar(box, orient='vertical', command=self.canvas.yview)
        hs=ttk.Scrollbar(box, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        box.columnconfigure(0,weight=1); box.rowconfigure(0,weight=1)
        self.canvas.grid(row=0,column=0,sticky='nsew');vs.grid(row=0,column=1,sticky='ns');hs.grid(row=1,column=0,sticky='ew')
        self.canvas.bind('<ButtonPress-1>', lambda e:self.canvas.scan_mark(e.x,e.y))
        self.canvas.bind('<B1-Motion>', lambda e:self.canvas.scan_dragto(e.x,e.y,gain=1))
        self.url.trace_add('write',lambda *_:self.state.update(reference=self.url.get()))
        self.timer=self.after(100,self.poll)
        self.bind('<Destroy>',self.cleanup,add='+')
        if self.image_data is not None:self.after_idle(self.draw)

    def cleanup(self,event):
        if event.widget is self:self.after_cancel(self.timer)

    def open_file(self):
        path=filedialog.askopenfilename(parent=self, filetypes=[('Scans','*.png *.jpg *.jpeg *.tif *.tiff *.gif *.pdf'),('Alle Dateien','*.*')])
        if path:self.load(path)

    def load_url(self):
        self.load(self.url.get().strip())

    def load(self,location):
        if not location:return
        self.request_id+=1; request_id=self.request_id
        self.status.config(text='Scan wird geladen …')
        def worker():
            try:self.results.put((request_id,location,read_scan(location),None))
            except Exception as exc:self.results.put((request_id,location,None,str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        try:
            while True:
                request_id,location,result,error=self.results.get_nowait()
                if request_id!=self.request_id:continue
                if error:self.status.config(text=error);continue
                self.image_data,self.pdf_data,self.page_count=result; self.page=0
                self.on_reference("")
                self.url.set(location)
                self.state.update(image=self.image_data,pdf=self.pdf_data,page=0,pages=self.page_count)
                self.fit()
        except queue.Empty:pass
        self.timer=self.after(100,self.poll)

    def copy_reference(self):
        if self.url.get().strip():
            self.on_reference(self.url.get().strip())
            self.status.config(text='Quellenverweis für den aktuellen Akt übernommen.')

    def turn(self,delta):
        if not self.pdf_data:return
        self.page=max(0,min(self.page_count-1,self.page+delta))
        with pymupdf.open(stream=self.pdf_data,filetype='pdf') as document:
            pix=document[self.page].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5))
            self.image_data=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
        self.state.update(image=self.image_data,page=self.page)
        self.draw()

    def resize(self,factor):
        self.zoom=max(.05,min(4,self.zoom*factor));self.draw()

    def fit(self):
        if self.image_data:
            self.zoom=min(max(100,self.canvas.winfo_width())/self.image_data.width,max(100,self.canvas.winfo_height())/self.image_data.height)
            self.draw()

    def draw(self):
        if self.image_data is None:return
        width=max(1,int(self.image_data.width*self.zoom));height=max(1,int(self.image_data.height*self.zoom))
        if width*height>40_000_000:
            self.status.config(text='Zoomgrenze erreicht.');return
        self.photo=ImageTk.PhotoImage(self.image_data.resize((width,height),Image.Resampling.LANCZOS))
        self.canvas.delete('all');self.canvas.create_image(0,0,anchor='nw',image=self.photo)
        self.canvas.configure(scrollregion=(0,0,width,height))
        self.state['zoom']=self.zoom
        self.status.config(text=f'Seite {self.page+1} / {self.page_count} · {self.zoom:.0%} · Ziehen zum Verschieben')
