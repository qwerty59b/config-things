### Dependencias ###
# sudo pacman -S python-pip python-requests tk  #Arch
# sudo apt install python3-tk python3-pip python3-requests # Debian/Ubuntu
# sudo dnf install python3-tkinter python3-pip python3-requests  # Fedora

import sys
import subprocess
import importlib.util
import platform
import os
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import queue
import json
import requests
from pathlib import Path
import shlex
import re
from datetime import datetime, timedelta

# Configurar rutas persistentes
def get_app_data_dir():
    home = Path.home()
    if sys.platform == "win32":
        app_data_dir = home / "AppData" / "Local" / "YTDownloader"
    else:
        app_data_dir = home / ".ytdownloader"
    app_data_dir.mkdir(parents=True, exist_ok=True)
    return app_data_dir

APP_DATA_DIR = get_app_data_dir()
CONFIG_PATH = APP_DATA_DIR / "config.json"
QUEUE_PATH = APP_DATA_DIR / "queue.json"

class DarkTheme:
    @staticmethod
    def apply(root):
        # Colores mejorados para mejor contraste
        root.configure(bg='#333333')
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configuración de colores
        style.configure('.', 
                       background='#333333', 
                       foreground='#CCCCCC',  # Gris claro para mejor contraste
                       fieldbackground='#444444',
                       selectbackground='#4a6987',
                       selectforeground='#FFFFFF')
        
        style.map('TButton',
                 background=[('active', '#4a6987'), ('pressed', '#2c4763')],
                 foreground=[('active', '#FFFFFF')])
        
        style.configure('TFrame', background='#333333')
        style.configure('TLabel', background='#333333', foreground='#CCCCCC')
        style.configure('TButton', background='#444444', foreground='#CCCCCC')
        style.configure('TEntry', fieldbackground='#444444', foreground='#FFFFFF')
        style.configure('TCombobox', fieldbackground='#444444', foreground='#FFFFFF')
        style.configure('Treeview', 
                        background='#444444', 
                        foreground='#CCCCCC',
                        fieldbackground='#444444')
        style.configure('Treeview.Heading', 
                       background='#2c4763', 
                       foreground='#FFFFFF')
        style.map('Treeview', 
                 background=[('selected', '#4a6987')])
        style.configure('TLabelframe', background='#333333', foreground='#CCCCCC')
        style.configure('TLabelframe.Label', background='#333333', foreground='#CCCCCC')
        style.configure('TCheckbutton', background='#333333', foreground='#CCCCCC')
        style.configure('TScrollbar', background='#444444', troughcolor='#333333')
        style.configure('TSpinbox', fieldbackground='#444444', foreground='#FFFFFF')
        style.configure('Menu', 
                       background='#444444', 
                       foreground='#CCCCCC', 
                       activebackground='#4a6987', 
                       activeforeground='#FFFFFF')
        
        # Estilo para botón de actualización cuando hay nueva versión
        style.configure('UpdateButton.TButton', background='#d9534f', foreground='white')  # Rojo
        # Fuente en negrita para la barra de estado
        style.configure('Bold.TLabel', font=('TkDefaultFont', 9, 'bold'))

class YTDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YT-DLP Advanced Downloader")
        self.root.geometry("1360x650")
        
        # Aplicar tema oscuro mejorado
        DarkTheme.apply(root)
        
        # Variables de configuración
        self.ytdlp_path = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.max_simultaneous = tk.IntVar(value=1)
        self.auto_remove = tk.BooleanVar(value=True)
        self.retry_attempts = tk.IntVar(value=5)
        self.concurrent_fragments = tk.IntVar(value=5)
        self.selected_resolution = tk.StringVar(value="best")
        self.last_update_check = tk.StringVar(value="")
        self.new_version_available = False
        
        # Estado de las descargas
        self.download_queue = queue.Queue()
        self.active_downloads = {}
        
        # Cargar configuración
        self.load_config()
        
        # Crear interfaz
        self.create_widgets()
        
        # Cargar cola guardada
        self.load_queue()
        
        # Configurar cierre
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Configurar atajos de teclado
        self.setup_keyboard_shortcuts()
        
        # Verificar actualización cada 7 días
        self.check_update_periodically()
    
    def setup_keyboard_shortcuts(self):
        # Seleccionar todo
        self.root.bind("<Control-a>", self.select_all)
        self.root.bind("<Control-A>", self.select_all)
        
        # Agregar a cola
        self.root.bind("<Control-n>", lambda e: self.add_to_queue())
        
        # Iniciar descargas
        self.root.bind("<Control-d>", lambda e: self.start_downloads())
        
        # Eliminar seleccionados
        self.root.bind("<Delete>", lambda e: self.remove_download())
        
        # Limpiar completados
        self.root.bind("<Control-l>", lambda e: self.clear_completed())
    
    def select_all(self, event=None):
        """Selecciona todos los elementos en la cola de descargas"""
        items = self.dl_tree.get_children()
        self.dl_tree.selection_set(items)
        self.status_var.set(f"{len(items)} elementos seleccionados")
    
    def load_config(self):
        default_output = Path.home() / "Downloads"
        sistema = platform.system()
        if sistema == "Windows":
            default_ytdlp = os.path.join(os.getcwd(), "yt-dlp.exe")
        else:
            default_ytdlp = os.path.join(os.getcwd(), "yt-dlp")
        
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r") as f:
                    config = json.load(f)
                    self.ytdlp_path.set(config.get("ytdlp_path", default_ytdlp))
                    self.output_folder.set(config.get("output_folder", str(default_output)))
                    self.max_simultaneous.set(config.get("max_simultaneous", 1))
                    self.auto_remove.set(config.get("auto_remove", True))
                    self.retry_attempts.set(config.get("retry_attempts", 5))
                    self.concurrent_fragments.set(config.get("concurrent_fragments", 5))
                    self.selected_resolution.set(config.get("selected_resolution", "best"))
                    self.last_update_check.set(config.get("last_update_check", ""))
            else:
                self.ytdlp_path.set(default_ytdlp)
                self.output_folder.set(str(default_output))
                self.retry_attempts.set(5)
                self.concurrent_fragments.set(5)
                self.selected_resolution.set("best")
        except Exception as e:
            print(f"Error loading config: {e}")
            self.ytdlp_path.set(default_ytdlp)
            self.output_folder.set(str(default_output))
            self.selected_resolution.set("best")
        
        os.makedirs(self.output_folder.get(), exist_ok=True)
    
    def save_config(self):
        config = {
            "ytdlp_path": self.ytdlp_path.get(),
            "output_folder": self.output_folder.get(),
            "max_simultaneous": self.max_simultaneous.get(),
            "auto_remove": self.auto_remove.get(),
            "retry_attempts": self.retry_attempts.get(),
            "concurrent_fragments": self.concurrent_fragments.get(),
            "selected_resolution": self.selected_resolution.get(),
            "last_update_check": self.last_update_check.get()
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f)
    
    def load_queue(self):
        try:
            if QUEUE_PATH.exists():
                with open(QUEUE_PATH, "r") as f:
                    queue_data = json.load(f)
                
                for item in queue_data:
                    self.dl_tree.insert("", "end", values=(
                        item["url"], 
                        item["custom_name"], 
                        item.get("resolution", self.selected_resolution.get()),
                        item.get("status", "En cola")
                    ))
        except Exception as e:
            print(f"Error loading queue: {e}")
    
    def save_queue(self):
        queue_data = []
        for item in self.dl_tree.get_children():
            values = self.dl_tree.item(item, "values")
            if values and len(values) >= 4:
                url, custom_name, resolution, status = values
                queue_data.append({
                    "url": url,
                    "custom_name": custom_name,
                    "resolution": resolution,
                    "status": status
                })
        
        with open(QUEUE_PATH, "w") as f:
            json.dump(queue_data, f)
    
    def create_widgets(self):
        # Frame de configuración
        config_frame = ttk.LabelFrame(self.root, text="Configuración")
        config_frame.pack(fill="x", padx=10, pady=5)
        
        # Path de yt-dlp
        ttk.Label(config_frame, text="Ruta de yt-dlp:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(config_frame, textvariable=self.ytdlp_path, width=50).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(config_frame, text="Examinar", command=self.browse_ytdlp).grid(row=0, column=2, padx=5, pady=2)
        ttk.Button(config_frame, text="Descargar yt-dlp", command=self.show_download_ytdlp).grid(row=0, column=3, padx=5, pady=2)
        
        # Botón de actualización con posible estilo especial
        self.update_btn = ttk.Button(
            config_frame, 
            text="Actualizar yt-dlp", 
            command=self.update_ytdlp,
            style='UpdateButton.TButton' if self.new_version_available else None
        )
        self.update_btn.grid(row=0, column=4, padx=5, pady=2)
        
        # Botón de guía
        ttk.Button(config_frame, text="Guía de uso", command=self.show_usage_guide).grid(row=0, column=5, padx=5, pady=2)
        
        # Carpeta destino
        ttk.Label(config_frame, text="Carpeta Destino:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(config_frame, textvariable=self.output_folder, width=50).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(config_frame, text="Examinar", command=self.browse_output).grid(row=1, column=2, padx=5, pady=2)
        
        # Descargas simultáneas
        ttk.Label(config_frame, text="Descargas Simultáneas:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(config_frame, from_=1, to=10, textvariable=self.max_simultaneous, width=5).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        
        # Auto eliminar al completar
        ttk.Checkbutton(config_frame, text="Eliminar al completar", variable=self.auto_remove).grid(row=2, column=2, padx=10, pady=2)
        
        # Reintentos
        ttk.Label(config_frame, text="Reintentos:").grid(row=2, column=3, sticky="e", padx=(10,5), pady=2)
        ttk.Spinbox(config_frame, from_=0, to=20, textvariable=self.retry_attempts, width=5).grid(row=2, column=4, sticky="w", padx=5, pady=2)
        
        # Fragmentos concurrentes
        ttk.Label(config_frame, text="Fragmentos Concurrentes:").grid(row=2, column=5, sticky="e", padx=(10,5), pady=2)
        ttk.Spinbox(
            config_frame, 
            from_=1, 
            to=16, 
            textvariable=self.concurrent_fragments, 
            width=5
        ).grid(row=2, column=6, sticky="w", padx=5, pady=2)
        
        # Frame de nuevas descargas
        new_dl_frame = ttk.LabelFrame(self.root, text="Nueva Descarga")
        new_dl_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(new_dl_frame, text="URL:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.url_entry = ttk.Entry(new_dl_frame, width=50)
        self.url_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(new_dl_frame, text="Nombre Personalizado:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.custom_name = ttk.Entry(new_dl_frame, width=50)
        self.custom_name.grid(row=1, column=1, padx=5, pady=2)
        
        # Selector de resolución
        ttk.Label(new_dl_frame, text="Resolución:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        resolutions = [
            "Mejor video (default)", 
            "360p", 
            "480p", 
            "720p", 
            "1080p", 
            "2160p (4K)", 
            "Solo audio (mejor calidad)"
        ]
        resolution_combo = ttk.Combobox(
            new_dl_frame, 
            textvariable=self.selected_resolution, 
            values=resolutions,
            state="readonly",
            width=25
        )
        resolution_combo.grid(row=2, column=1, padx=5, pady=2, sticky="w")
        resolution_combo.current(0)
        
        ttk.Button(new_dl_frame, text="Agregar a Cola", command=self.add_to_queue).grid(row=2, column=2, padx=5, pady=2)
        
        # Lista de descargas
        dl_frame = ttk.LabelFrame(self.root, text="Cola de Descargas")
        dl_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("url", "custom_name", "resolution", "status")
        self.dl_tree = ttk.Treeview(dl_frame, columns=columns, show="headings")
        
        self.dl_tree.heading("url", text="URL")
        self.dl_tree.heading("custom_name", text="Nombre Personalizado")
        self.dl_tree.heading("resolution", text="Resolución")
        self.dl_tree.heading("status", text="Estado")
        
        self.dl_tree.column("url", width=300)
        self.dl_tree.column("custom_name", width=200)
        self.dl_tree.column("resolution", width=120)
        self.dl_tree.column("status", width=100)
        
        scrollbar = ttk.Scrollbar(dl_frame, orient="vertical", command=self.dl_tree.yview)
        self.dl_tree.configure(yscrollcommand=scrollbar.set)
        
        self.dl_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Frame para botones de movimiento
        move_frame = ttk.Frame(dl_frame)
        move_frame.pack(side="right", fill="y", padx=5)
        
        # Botones de movimiento
        ttk.Button(move_frame, text="▲ Subir", command=self.move_up).pack(fill="x", pady=2)
        ttk.Button(move_frame, text="▼ Bajar", command=self.move_down).pack(fill="x", pady=2)
        ttk.Button(move_frame, text="⏫ Inicio", command=self.move_to_top).pack(fill="x", pady=2)
        ttk.Button(move_frame, text="⏬ Final", command=self.move_to_bottom).pack(fill="x", pady=2)
        
        # Menú contextual
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Cambiar URL", command=self.change_url)
        self.context_menu.add_command(label="Mover arriba", command=self.move_up)
        self.context_menu.add_command(label="Mover abajo", command=self.move_down)
        self.context_menu.add_command(label="Mover al inicio", command=self.move_to_top)
        self.context_menu.add_command(label="Mover al final", command=self.move_to_bottom)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Eliminar", command=self.remove_download)
        self.dl_tree.bind("<Button-3>", self.show_context_menu)
        
        # Botones de control
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(btn_frame, text="Iniciar Descargas", command=self.start_downloads).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Eliminar", command=self.remove_download).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Limpiar Completadas", command=self.clear_completed).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Seleccionar todo", command=self.select_all).pack(side="left", padx=5)
        
        # Status bar con fuente en negrita
        self.status_var = tk.StringVar(value="Listo")
        status_bar = ttk.Label(
            self.root, 
            textvariable=self.status_var, 
            relief="sunken", 
            anchor="w", 
            style='Bold.TLabel'
        )
        status_bar.pack(side="bottom", fill="x")
    
    def move_item(self, item, new_index):
        """Mueve un elemento a una nueva posición en el Treeview"""
        values = self.dl_tree.item(item, "values")
        self.dl_tree.delete(item)
        self.dl_tree.insert("", new_index, values=values)
    
    def move_up(self):
        """Mueve el elemento seleccionado una posición arriba"""
        selected = self.dl_tree.selection()
        if not selected:
            return
            
        item = selected[0]
        current_index = self.dl_tree.index(item)
        if current_index > 0:
            self.move_item(item, current_index - 1)
            self.status_var.set("Elemento movido hacia arriba")
    
    def move_down(self):
        """Mueve el elemento seleccionado una posición abajo"""
        selected = self.dl_tree.selection()
        if not selected:
            return
            
        item = selected[0]
        current_index = self.dl_tree.index(item)
        total_items = len(self.dl_tree.get_children())
        if current_index < total_items - 1:
            self.move_item(item, current_index + 1)
            self.status_var.set("Elemento movido hacia abajo")
    
    def move_to_top(self):
        """Mueve el elemento seleccionado al inicio de la lista"""
        selected = self.dl_tree.selection()
        if not selected:
            return
            
        item = selected[0]
        self.move_item(item, 0)
        self.status_var.set("Elemento movido al inicio")
    
    def move_to_bottom(self):
        """Mueve el elemento seleccionado al final de la lista"""
        selected = self.dl_tree.selection()
        if not selected:
            return
            
        item = selected[0]
        self.move_item(item, "end")
        self.status_var.set("Elemento movido al final")
    
    def show_usage_guide(self):
        """Muestra una ventana con la guía de uso"""
        guide_window = tk.Toplevel(self.root)
        guide_window.title("Guía de Uso")
        guide_window.geometry("800x600")
        guide_window.transient(self.root)
        guide_window.grab_set()
        
        # Frame principal con scrollbar
        main_frame = ttk.Frame(guide_window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Contenido de la guía
        content = [
            ("Guía de Uso - YT-DLP Advanced Downloader", 16, True),
            ("Primera configuración", 14, True),
            ("1. Descargar yt-dlp:", 12, True),
            ("   - Si es tu primera vez usando el programa, necesitas descargar yt-dlp.",
             11, False),
            ("   - Haz clic en 'Descargar yt-dlp' para obtener el ejecutable.",
             11, False),
            ("   - Después de descargarlo, usa 'Examinar' para seleccionar su ubicación.",
             11, False),
            ("2. Configurar carpeta destino:", 12, True),
            ("   - Selecciona la carpeta donde se guardarán tus descargas.",
             11, False),
            ("", 1, False),
            ("Funciones principales", 14, True),
            ("- Agregar descargas:", 12, True),
            ("   - Introduce la URL y un nombre personalizado (opcional).",
             11, False),
            ("   - Selecciona la resolución deseada (o 'Solo audio').",
             11, False),
            ("   - Haz clic en 'Agregar a Cola'.",
             11, False),
            ("- Iniciar descargas:", 12, True),
            ("   - Haz clic en 'Iniciar Descargas' para comenzar todas las descargas en cola.",
             11, False),
            ("   - Puedes configurar el número de descargas simultáneas.",
             11, False),
            ("- Gestionar la cola:", 12, True),
            ("   - Click derecho en un item para cambiar URL o eliminarlo.",
             11, False),
            ("   - 'Limpiar Completadas' elimina los items completados de la lista.",
             11, False),
            ("   - Usa los botones de movimiento para reorganizar la cola.",
             11, False),
            ("   - Atajos de teclado: Ctrl+A (seleccionar todo), Ctrl+D (iniciar descargas), Delete (eliminar)",
             11, False),
            ("", 1, False),
            ("Configuraciones avanzadas", 14, True),
            ("- Reintentos:", 12, True),
            ("   - Número de intentos si una descarga falla.",
             11, False),
            ("- Fragmentos concurrentes:", 12, True),
            ("   - Mejora la velocidad de descarga (valores más altos = más rápido).",
             11, False),
            ("- Auto eliminar:", 12, True),
            ("   - Elimina automáticamente los items completados de la lista.",
             11, False),
            ("", 1, False),
            ("Mantenimiento", 14, True),
            ("- Actualización automática:", 12, True),
            ("   - El programa verifica actualizaciones de yt-dlp cada 7 días.",
             11, False),
            ("   - El botón 'Actualizar yt-dlp' cambiará de color si hay nueva versión.",
             11, False),
            ("", 1, False),
            ("Consejos:", 14, True),
            ("- Para videos privados, asegúrate de incluir cookies si es necesario.",
             11, False),
            ("- Si una resolución no está disponible, se intentará con la siguiente superior.",
             11, False),
            ("- Las descargas se guardan automáticamente al cerrar el programa.",
             11, False),
        ]
        
        for text, size, is_bold in content:
            if text == "":
                ttk.Label(scrollable_frame).pack(pady=5)
                continue
                
            font = ("TkDefaultFont", size)
            if is_bold:
                font += ("bold",)
                
            label = ttk.Label(
                scrollable_frame, 
                text=text, 
                font=font,
                wraplength=750,
                justify="left"
            )
            label.pack(anchor="w", padx=10, pady=2)
        
        ttk.Button(
            guide_window, 
            text="Cerrar", 
            command=guide_window.destroy
        ).pack(pady=10)
    
    def check_update_periodically(self):
        """Verifica actualizaciones cada 7 días"""
        last_check = self.last_update_check.get()
        if last_check:
            last_date = datetime.strptime(last_check, "%Y-%m-%d")
            if datetime.now() - last_date < timedelta(days=7):
                return
        
        # Realizar verificación en segundo plano
        threading.Thread(target=self.check_ytdlp_update, daemon=True).start()
    
    def check_ytdlp_update(self):
        """Verifica si hay una nueva versión de yt-dlp disponible"""
        try:
            self.root.after(0, self.status_var.set, "Verificando actualizaciones...")
            ytdlp_path = self.ytdlp_path.get()
            
            if not os.path.exists(ytdlp_path):
                self.root.after(0, self.status_var.set, "yt-dlp no encontrado")
                return
                
            # Obtener versión local
            local_version = subprocess.check_output(
                [ytdlp_path, "--version"],
                stderr=subprocess.STDOUT,
                text=True
            ).strip()
            
            # Obtener última versión disponible
            try:
                latest_version = subprocess.check_output(
                    [ytdlp_path, "-U", "--get-only"],
                    stderr=subprocess.STDOUT,
                    text=True
                ).strip()
            except subprocess.CalledProcessError:
                # Usar versión local como fallback
                latest_version = local_version
                self.root.after(0, self.status_var.set, "Error al verificar actualización")
            
            # Comparar versiones
            if local_version != latest_version:
                self.new_version_available = True
                self.root.after(0, self.update_update_button_style)
                self.root.after(0, messagebox.showinfo, "Actualización disponible", 
                              f"Hay una nueva versión de yt-dlp disponible: {latest_version}\n"
                              "Haz clic en 'Actualizar yt-dlp' para instalar la última versión.")
            
            # Actualizar fecha de última verificación
            self.last_update_check.set(datetime.now().strftime("%Y-%m-%d"))
            self.save_config()
            
        except Exception as e:
            print(f"Error checking update: {e}")
            self.root.after(0, self.status_var.set, f"Error: {str(e)}")
        finally:
            self.root.after(0, self.status_var.set, "Listo")
    
    def update_update_button_style(self):
        """Actualiza el estilo del botón de actualización si hay nueva versión"""
        if self.new_version_available:
            self.update_btn.configure(style='UpdateButton.TButton')
        else:
            self.update_btn.configure(style='TButton')
    
    def show_download_ytdlp(self):
        """Muestra un diálogo con la URL de descarga de yt-dlp"""
        sistema = platform.system()
        arch = platform.machine().lower()
        
        # Seleccionar URL según sistema operativo
        if sistema == "Windows":
            if "arm" in arch or "aarch" in arch:
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_win_arm64.exe"
            else:
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        elif sistema == "Linux":
            if "arm" in arch or "aarch" in arch:
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux_aarch64"
            else:
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
        elif sistema == "Darwin":
            url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
        else:
            messagebox.showerror("Error", f"Sistema operativo no soportado: {sistema}")
            return

        # Crear ventana de diálogo
        dialog = tk.Toplevel(self.root)
        dialog.title("Descargar yt-dlp")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"URL para descargar yt-dlp:").pack(padx=10, pady=5)
        
        entry = ttk.Entry(dialog, width=70)
        entry.insert(0, url)
        entry.pack(padx=10, pady=5)
        entry.select_range(0, tk.END)
        entry.focus()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(padx=10, pady=10)
        
        def copy_url():
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.status_var.set("URL copiada al portapapeles")
        
        ttk.Button(btn_frame, text="Copiar URL", command=copy_url).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Abrir en navegador", command=lambda: webbrowser.open(url)).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cerrar", command=dialog.destroy).pack(side="left", padx=5)
    
    def update_ytdlp(self):
        """Actualiza yt-dlp a la última versión disponible"""
        try:
            sistema = platform.system()
            ytdlp_path = self.ytdlp_path.get()
            
            # Verificar si yt-dlp existe
            if not os.path.exists(ytdlp_path):
                messagebox.showwarning("Advertencia", "yt-dlp no encontrado. Por favor descárguelo primero.")
                return
            
            # Preparar el comando de actualización
            cmd = [ytdlp_path, "-U"]
            
            # Ejecutar en un hilo para no bloquear la GUI
            threading.Thread(
                target=self.run_update_command,
                args=(cmd,),
                daemon=True
            ).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar yt-dlp:\n{str(e)}")
    
    def run_update_command(self, cmd):
        """Ejecuta el comando de actualización y muestra el resultado"""
        try:
            self.root.after(0, self.status_var.set, "Actualizando yt-dlp...")
            
            # Preparar el proceso
            sistema = platform.system()
            if sistema != "Windows":
                cmd_str = " ".join(shlex.quote(arg) for arg in cmd)
                process = subprocess.Popen(
                    cmd_str,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                    universal_newlines=True,
                    shell=True
                )
            else:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                    universal_newlines=True
                )
            
            # Capturar la salida
            output_lines = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    output_lines.append(line.strip())
                    self.root.after(0, self.status_var.set, line.strip())
            
            # Mostrar resultado
            returncode = process.returncode
            output = "\n".join(output_lines)
            
            if returncode == 0:
                messagebox.showinfo("Actualización completada", 
                                   f"yt-dlp se ha actualizado correctamente:\n\n{output}")
                self.new_version_available = False
                self.root.after(0, self.update_update_button_style)
            else:
                messagebox.showerror("Error en actualización", 
                                    f"Error al actualizar yt-dlp (código {returncode}):\n\n{output}")
                
        except Exception as e:
            self.root.after(0, messagebox.showerror, "Error", f"Excepción al actualizar yt-dlp:\n{str(e)}")
        finally:
            self.root.after(0, self.status_var.set, "Listo")
    
    def browse_ytdlp(self):
        sistema = platform.system()
        if sistema == "Windows":
            filetypes = [("Ejecutable", "*.exe"), ("Todos los archivos", "*.*")]
        else:
            filetypes = [("Ejecutable", "*"), ("Todos los archivos", "*.*")]
            
        filepath = filedialog.askopenfilename(
            title="Seleccionar yt-dlp",
            filetypes=filetypes
        )
        if filepath:
            self.ytdlp_path.set(filepath)
    
    def browse_output(self):
        folder = filedialog.askdirectory(title="Seleccionar Carpeta Destino")
        if folder:
            self.output_folder.set(folder)
    
    def add_to_queue(self):
        url = self.url_entry.get().strip()
        name = self.custom_name.get().strip()
        resolution = self.selected_resolution.get()
        
        if not url:
            messagebox.showerror("Error", "Debe ingresar una URL")
            return
            
        self.dl_tree.insert("", "end", values=(
            url, 
            name if name else "Predeterminado", 
            resolution,
            "En cola"
        ))
        self.url_entry.delete(0, "end")
        self.custom_name.delete(0, "end")
        self.status_var.set(f"Descarga agregada a cola: {url}")
        self.save_config()  # Guardar la resolución seleccionada
    
    def show_context_menu(self, event):
        item = self.dl_tree.identify_row(event.y)
        if item:
            self.dl_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def change_url(self):
        selected = self.dl_tree.selection()
        if not selected:
            return
            
        item = selected[0]
        values = self.dl_tree.item(item, "values")
        if not values or len(values) < 4:
            return
            
        current_url = values[0]
        custom_name = values[1]
        resolution = values[2]
        status = values[3]
        
        new_url = simpledialog.askstring(
            "Cambiar URL", 
            "Ingrese la nueva URL:", 
            initialvalue=current_url
        )
        
        if new_url and new_url.strip():
            self.dl_tree.item(item, values=(new_url.strip(), custom_name, resolution, status))
            self.status_var.set("URL actualizada")
    
    def start_downloads(self):
        if not self.dl_tree.get_children():
            messagebox.showinfo("Información", "La cola de descargas está vacía")
            return
            
        # Agregar solo elementos en cola
        for item in self.dl_tree.get_children():
            values = self.dl_tree.item(item, "values")
            if values and len(values) >= 4 and values[3] == "En cola":
                self.download_queue.put(item)
        
        self.launch_downloaders()
    
    def launch_downloaders(self):
        max_dl = min(self.max_simultaneous.get(), self.download_queue.qsize())
        
        for _ in range(max_dl):
            if not self.download_queue.empty():
                item = self.download_queue.get()
                self.start_single_download(item)
    
    def start_single_download(self, item):
        # Verificar si el elemento aún existe
        if not self.dl_tree.exists(item):
            return
            
        values = self.dl_tree.item(item, "values")
        if not values or len(values) < 4:
            return
            
        url, custom_name, resolution, _ = values
        self.dl_tree.item(item, values=(url, custom_name, resolution, "Descargando"))
        
        output_path = self.output_folder.get()
        cmd = [
            self.ytdlp_path.get(),
            url,
            "-o",
            os.path.join(output_path, f"{custom_name}.%(ext)s") if custom_name != "Predeterminado" else os.path.join(output_path, "%(title)s.%(ext)s"),
            "--newline"
        ]
        
        # Añadir parámetros de fragmentos concurrentes
        cmd.extend(['--concurrent-fragments', str(self.concurrent_fragments.get())])
        
        # Manejar selección de resolución
        if resolution == "Solo audio (mejor calidad)":
            cmd.extend(['-f', 'bestaudio', '-x'])
        elif resolution != "Mejor video (default)":
            # Extraer el número de la resolución (ej: "720p" -> 720)
            try:
                height = int(re.search(r'\d+', resolution).group())
            except:
                height = 720
            
            # Definir resoluciones en orden ascendente
            resolutions = [360, 480, 720, 1080, 1440, 2160]
            # Filtrar resoluciones >= a la seleccionada
            valid_res = [r for r in resolutions if r >= height]
            # Crear cadena de formato para yt-dlp
            format_parts = []
            for r in valid_res:
                format_parts.append(f'bestvideo[height={r}]+bestaudio')
                format_parts.append(f'best[height={r}]')
            format_parts.append('best')
            format_str = '/'.join(format_parts)
            cmd.extend(['-f', format_str])
        
        thread = threading.Thread(
            target=self.run_download_with_retries,
            args=(cmd, item, self.retry_attempts.get()),
            daemon=True
        )
        thread.start()
        
        # Guardar referencia al proceso
        self.active_downloads[item] = (thread, None)
    
    def run_download_with_retries(self, cmd, item, max_retries):
        """Ejecuta la descarga con reintentos"""
        attempts = 0
        success = False
        
        while attempts <= max_retries and not success:
            attempts += 1
            try:
                sistema = platform.system()
                if sistema != "Windows":
                    # Convertir a comando de shell para mejor compatibilidad
                    cmd_str = " ".join(shlex.quote(arg) for arg in cmd)
                    process = subprocess.Popen(
                        cmd_str,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        bufsize=1,
                        universal_newlines=True,
                        shell=True
                    )
                else:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        bufsize=1,
                        universal_newlines=True
                    )
                
                # Actualizar referencia al proceso
                self.active_downloads[item] = (threading.current_thread(), process)
                
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        # Mostrar progreso en negrita
                        self.update_status(item, output.strip())
                
                returncode = process.returncode
                
                if returncode == 0:
                    success = True
                    self.complete_download(item, returncode)
                else:
                    # Si no es el último intento, esperar 3 segundos
                    if attempts <= max_retries:
                        self.update_status(item, f"Falló. Reintentando en 3 segundos... (intento {attempts}/{max_retries})")
                        time.sleep(3)
                    else:
                        self.complete_download(item, returncode)
            
            except Exception as e:
                # Si no es el último intento, esperar 3 segundos
                if attempts <= max_retries:
                    self.update_status(item, f"Error: {str(e)}. Reintentando en 3 segundos... (intento {attempts}/{max_retries})")
                    time.sleep(3)
                else:
                    self.root.after(0, self.dl_tree.item, item, "values", 
                                  (self.dl_tree.item(item, "values")[0], 
                                   self.dl_tree.item(item, "values")[1],
                                   self.dl_tree.item(item, "values")[2],
                                   f"Error: {str(e)}"))
                    self.root.after(0, self.status_var.set, f"Error: {str(e)}")
                    self.complete_download(item, -1)
    
    def update_status(self, item, message):
        # Filtrar mensajes de progreso para mostrar solo los importantes
        if "ETA" in message or "of" in message or "%" in message:
            self.root.after(0, self.status_var.set, message)
    
    def complete_download(self, item, returncode):
        # Verificar si el elemento aún existe
        if not self.dl_tree.exists(item):
            return
            
        values = self.dl_tree.item(item, "values")
        if not values or len(values) < 4:
            return
            
        url, custom_name, resolution, _ = values
        
        if returncode == 0:
            status = "Completado"
            self.root.after(0, self.status_var.set, f"Descarga completada: {custom_name or url}")
            
            # Eliminar automáticamente si está habilitado
            if self.auto_remove.get():
                self.root.after(0, self.dl_tree.delete, item)
            else:
                self.root.after(0, self.dl_tree.item, item, "values", (url, custom_name, resolution, status))
        else:
            status = "Fallido"
            self.root.after(0, self.dl_tree.item, item, "values", (url, custom_name, resolution, status))
        
        # Eliminar de activos
        if item in self.active_downloads:
            del self.active_downloads[item]
        
        # Iniciar siguiente descarga
        if not self.download_queue.empty():
            next_item = self.download_queue.get()
            self.start_single_download(next_item)
    
    def remove_download(self):
        selected = self.dl_tree.selection()
        if not selected:
            return
            
        # Eliminar todos los elementos seleccionados
        for item in selected:
            # Verificar si el elemento existe antes de intentar acceder
            if not self.dl_tree.exists(item):
                continue
                
            values = self.dl_tree.item(item, "values")
            if values and len(values) >= 4:
                status = values[3]
                
                # Si está descargando, detener el proceso
                if status == "Descargando" and item in self.active_downloads:
                    _, process = self.active_downloads[item]
                    if process:
                        try:
                            process.terminate()
                        except:
                            pass
                    del self.active_downloads[item]
            
            self.dl_tree.delete(item)
    
    def clear_completed(self):
        for item in self.dl_tree.get_children():
            # Verificar si el elemento existe
            if not self.dl_tree.exists(item):
                continue
                
            values = self.dl_tree.item(item, "values")
            if values and len(values) >= 4 and values[3] == "Completado":
                self.dl_tree.delete(item)
    
    def on_close(self):
        # Cambiar estado de descargas activas a "En cola"
        for item, (_, process) in list(self.active_downloads.items()):
            # Verificar si el elemento existe
            if not self.dl_tree.exists(item):
                continue
                
            # Detener proceso si existe
            if process:
                try:
                    process.terminate()
                except:
                    pass
            
            # Actualizar estado en la lista
            values = self.dl_tree.item(item, "values")
            if values and len(values) >= 4:
                url, custom_name, resolution, _ = values
                # Cambiar estado a "En cola" para continuar después
                self.dl_tree.item(item, values=(url, custom_name, resolution, "En cola"))
        
        # Limpiar lista de descargas activas
        self.active_downloads.clear()
        
        # Guardar configuración y cola
        self.save_config()
        self.save_queue()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = YTDownloaderApp(root)
    root.mainloop()
