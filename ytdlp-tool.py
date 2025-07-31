import sys
import subprocess
import importlib.util
import platform
import os
import time  # Añadido para manejar el tiempo de espera en reintentos

def install_dependencies():
    """Verifica e instala dependencias faltantes específicas para cada sistema"""
    required = ["requests"]
    missing = []
    linux_distro = None
    
    # Detectar si estamos en Linux y qué distribución es
    if sys.platform.startswith('linux'):
        try:
            with open("/etc/os-release", encoding='utf-8') as f:
                for line in f:
                    if line.startswith("ID="):
                        linux_distro = line.split("=")[1].strip().strip('"')
                        break
        except Exception:
            pass
    
    # Verificar tkinter primero ya que es crítico para la GUI
    tkinter_installed = importlib.util.find_spec("tkinter") is not None
    
    # Verificar otros módulos
    for module in required:
        if not importlib.util.find_spec(module):
            missing.append(module)
    
    # Si falta tkinter en Linux, intentar instalarlo
    if not tkinter_installed and sys.platform.startswith('linux'):
        print("tkinter no está instalado. Intentando instalar...")
        
        install_cmd = []
        if linux_distro in ["ubuntu", "debian", "linuxmint"]:
            install_cmd = ["sudo", "apt", "install", "-y", "python3-tk"]
        elif linux_distro in ["fedora", "centos", "rhel"]:
            install_cmd = ["sudo", "dnf", "install", "-y", "python3-tkinter"]
        elif linux_distro in ["arch", "manjaro"]:
            install_cmd = ["sudo", "pacman", "-S", "--noconfirm", "tk"]
        else:
            print("Distribución no reconocida. Por favor instale tkinter manualmente.")
            print("Para Debian/Ubuntu: sudo apt install python3-tk")
            print("Para Fedora/CentOS: sudo dnf install python3-tkinter")
            print("Para Arch/Manjaro: sudo pacman -S tk")
            sys.exit(1)
        
        try:
            subprocess.run(install_cmd, check=True)
            print("tkinter instalado correctamente.")
        except Exception as e:
            print(f"Error instalando tkinter: {str(e)}")
            sys.exit(1)
    
    # Instalar otros módulos faltantes con pip
    if missing:
        print(f"Instalando dependencias faltantes: {', '.join(missing)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            print("Dependencias instaladas correctamente. Por favor reinicie la aplicación.")
        except Exception as e:
            print(f"No se pudieron instalar las dependencias: {str(e)}")
            sys.exit(1)
        sys.exit(0)

install_dependencies()

# Ahora podemos importar con seguridad
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import subprocess
import os
import queue
import json
import requests
from pathlib import Path
import shlex

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
        root.tk_setPalette(
            background='#2d2d2d', 
            foreground='#e6e6e6',
            activeBackground='#3d3d3d',
            activeForeground='#ffffff',
            selectColor='#4a6987',
            selectBackground='#4a6987',
            selectForeground='#ffffff'
        )
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configurar colores
        style.configure('.', background='#2d2d2d', foreground='#e6e6e6')
        style.configure('TFrame', background='#2d2d2d')
        style.configure('TLabel', background='#2d2d2d', foreground='#e6e6e6')
        style.configure('TButton', background='#3d3d3d', foreground='#e6e6e6', 
                        borderwidth=1, relief='raised')
        style.map('TButton', 
                 background=[('active', '#4a6987'), ('pressed', '#2c4763')],
                 foreground=[('active', '#ffffff')])
        
        style.configure('TEntry', fieldbackground='#3d3d3d', foreground='#ffffff')
        style.configure('TCombobox', fieldbackground='#3d3d3d', foreground='#ffffff')
        style.configure('Treeview', background='#3d3d3d', foreground='#e6e6e6', 
                        fieldbackground='#3d3d3d')
        style.configure('Treeview.Heading', background='#2c4763', foreground='#ffffff')
        style.map('Treeview', background=[('selected', '#4a6987')])
        
        style.configure('TLabelframe', background='#2d2d2d', foreground='#e6e6e6')
        style.configure('TLabelframe.Label', background='#2d2d2d', foreground='#e6e6e6')
        style.configure('TCheckbutton', background='#2d2d2d', foreground='#e6e6e6')
        style.configure('TScrollbar', background='#3d3d3d', troughcolor='#2d2d2d')
        style.configure('TSpinbox', fieldbackground='#3d3d3d', foreground='#ffffff')
        
        # Configurar menú contextual
        style.configure('Menu', background='#3d3d3d', foreground='#e6e6e6', 
                        activebackground='#4a6987', activeforeground='#ffffff')

class YTDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YT-DLP Advanced Downloader")
        self.root.geometry("900x900")  # Ventana más grande
        
        # Aplicar tema oscuro
        DarkTheme.apply(root)
        
        # Variables de configuración
        self.ytdlp_path = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.max_simultaneous = tk.IntVar(value=1)
        self.auto_remove = tk.BooleanVar(value=True)
        self.resolution = tk.StringVar(value="best")
        self.retry_attempts = tk.IntVar(value=5)  # Nuevo: reintentos por defecto
        
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
    
    def load_config(self):
        # Configuración predeterminada
        default_output = Path.home() / "Downloads"
        sistema = platform.system()
        if sistema == "Windows":
            default_ytdlp = os.path.join(os.getcwd(), "yt-dlp.exe")
        else:  # Linux, macOS, etc.
            default_ytdlp = os.path.join(os.getcwd(), "yt-dlp")
        
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r") as f:
                    config = json.load(f)
                    self.ytdlp_path.set(config.get("ytdlp_path", default_ytdlp))
                    self.output_folder.set(config.get("output_folder", str(default_output)))
                    self.max_simultaneous.set(config.get("max_simultaneous", 1))
                    self.auto_remove.set(config.get("auto_remove", True))
                    self.resolution.set(config.get("resolution", "best"))
                    self.retry_attempts.set(config.get("retry_attempts", 5))  # Cargar reintentos
            else:
                self.ytdlp_path.set(default_ytdlp)
                self.output_folder.set(str(default_output))
                self.resolution.set("best")
                self.retry_attempts.set(5)  # Valor por defecto para reintentos
        except Exception as e:
            print(f"Error loading config: {e}")
            self.ytdlp_path.set(default_ytdlp)
            self.output_folder.set(str(default_output))
            self.resolution.set("best")
            self.retry_attempts.set(5)
        
        # Crear carpeta de descargas si no existe
        os.makedirs(self.output_folder.get(), exist_ok=True)
    
    def save_config(self):
        config = {
            "ytdlp_path": self.ytdlp_path.get(),
            "output_folder": self.output_folder.get(),
            "max_simultaneous": self.max_simultaneous.get(),
            "auto_remove": self.auto_remove.get(),
            "resolution": self.resolution.get(),
            "retry_attempts": self.retry_attempts.get()  # Guardar reintentos
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
                        "En cola"
                    ))
        except Exception as e:
            print(f"Error loading queue: {e}")
    
    def save_queue(self):
        queue_data = []
        for item in self.dl_tree.get_children():
            url, custom_name, status = self.dl_tree.item(item, "values")
            queue_data.append({
                "url": url,
                "custom_name": custom_name,
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
        ttk.Button(config_frame, text="Descargar yt-dlp", command=self.download_ytdlp).grid(row=0, column=3, padx=5, pady=2)
        ttk.Button(config_frame, text="Actualizar yt-dlp", command=self.update_ytdlp).grid(row=0, column=4, padx=5, pady=2)
        
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
        
        # Resolución
        ttk.Label(config_frame, text="Resolución:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        resolution_combo = ttk.Combobox(config_frame, textvariable=self.resolution, width=12)
        resolution_combo.grid(row=3, column=1, sticky="w", padx=5, pady=2)
        resolution_combo['values'] = ("best", "144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p", "audio")
        resolution_combo.state(["readonly"])
        
        # Frame de nuevas descargas
        new_dl_frame = ttk.LabelFrame(self.root, text="Nueva Descarga")
        new_dl_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(new_dl_frame, text="URL:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.url_entry = ttk.Entry(new_dl_frame, width=50)
        self.url_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(new_dl_frame, text="Nombre Personalizado:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.custom_name = ttk.Entry(new_dl_frame, width=50)
        self.custom_name.grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Button(new_dl_frame, text="Agregar a Cola", command=self.add_to_queue).grid(row=1, column=2, padx=5, pady=2)
        
        # Lista de descargas
        dl_frame = ttk.LabelFrame(self.root, text="Cola de Descargas")
        dl_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("url", "custom_name", "status")
        self.dl_tree = ttk.Treeview(dl_frame, columns=columns, show="headings")
        
        self.dl_tree.heading("url", text="URL")
        self.dl_tree.heading("custom_name", text="Nombre Personalizado")
        self.dl_tree.heading("status", text="Estado")
        
        self.dl_tree.column("url", width=300)
        self.dl_tree.column("custom_name", width=200)
        self.dl_tree.column("status", width=100)
        
        scrollbar = ttk.Scrollbar(dl_frame, orient="vertical", command=self.dl_tree.yview)
        self.dl_tree.configure(yscrollcommand=scrollbar.set)
        
        self.dl_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Menú contextual
        self.context_menu = tk.Menu(self.root, tearoff=0, bg='#3d3d3d', fg='#e6e6e6')
        self.context_menu.add_command(label="Cambiar URL", command=self.change_url)
        self.context_menu.add_command(label="Eliminar", command=self.remove_download)
        self.dl_tree.bind("<Button-3>", self.show_context_menu)
        
        # Botones de control
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(btn_frame, text="Iniciar Descargas", command=self.start_downloads).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Eliminar", command=self.remove_download).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Limpiar Completadas", command=self.clear_completed).pack(side="left", padx=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Listo")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")
    
    def download_ytdlp(self):
        try:
            sistema = platform.system()
            arch = platform.machine().lower()
            
            # Seleccionar la versión correcta según el sistema y arquitectura
            if sistema == "Windows":
                if "arm" in arch or "aarch" in arch:
                    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_win_arm64.exe"
                    save_path = os.path.join(os.getcwd(), "yt-dlp.exe")
                else:
                    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
                    save_path = os.path.join(os.getcwd(), "yt-dlp.exe")
            
            elif sistema == "Linux":
                if "arm" in arch or "aarch" in arch:
                    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux_aarch64"
                    save_path = os.path.join(os.getcwd(), "yt-dlp")
                else:
                    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
                    save_path = os.path.join(os.getcwd(), "yt-dlp")
            
            elif sistema == "Darwin":  # macOS
                if "arm" in arch:
                    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
                    save_path = os.path.join(os.getcwd(), "yt-dlp")
                else:
                    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
                    save_path = os.path.join(os.getcwd(), "yt-dlp")
            else:
                messagebox.showerror("Error", f"Sistema operativo no soportado: {sistema}")
                return

            self.status_var.set("Descargando yt-dlp...")
            response = requests.get(url, stream=True)
            response.raise_for_status()

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # En sistemas Unix, dar permisos de ejecución
            if sistema in ["Linux", "Darwin"]:
                os.chmod(save_path, 0o755)  # rwxr-xr-x

            self.ytdlp_path.set(save_path)
            self.status_var.set("yt-dlp descargado correctamente")
            messagebox.showinfo("Éxito", "yt-dlp se ha descargado correctamente")
        except Exception as e:
            self.status_var.set(f"Error descargando yt-dlp: {str(e)}")
            messagebox.showerror("Error", f"No se pudo descargar yt-dlp:\n{str(e)}")
    
    def update_ytdlp(self):
        """Actualiza yt-dlp a la última versión disponible"""
        try:
            sistema = platform.system()
            ytdlp_path = self.ytdlp_path.get()
            
            # Verificar si yt-dlp existe
            if not os.path.exists(ytdlp_path):
                messagebox.showwarning("Advertencia", "yt-dlp no encontrado. Descargando primero...")
                self.download_ytdlp()
                return
            
            # Preparar el comando de actualización
            if sistema == "Windows":
                cmd = [ytdlp_path, "-U"]
            else:
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
            self.status_var.set("Actualizando yt-dlp...")
            
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
        
        if not url:
            messagebox.showerror("Error", "Debe ingresar una URL")
            return
            
        self.dl_tree.insert("", "end", values=(url, name if name else "Predeterminado", "En cola"))
        self.url_entry.delete(0, "end")
        self.custom_name.delete(0, "end")
        self.status_var.set(f"Descarga agregada a cola: {url}")
    
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
        current_url, custom_name, status = self.dl_tree.item(item, "values")
        
        new_url = simpledialog.askstring(
            "Cambiar URL", 
            "Ingrese la nueva URL:", 
            initialvalue=current_url
        )
        
        if new_url and new_url.strip():
            self.dl_tree.item(item, values=(new_url.strip(), custom_name, status))
            self.status_var.set("URL actualizada")
    
    def start_downloads(self):
        if not self.dl_tree.get_children():
            messagebox.showinfo("Información", "La cola de descargas está vacía")
            return
            
        # Agregar solo elementos en cola
        for item in self.dl_tree.get_children():
            status = self.dl_tree.item(item, "values")[2]
            if status == "En cola":
                self.download_queue.put(item)
        
        self.launch_downloaders()
    
    def launch_downloaders(self):
        max_dl = min(self.max_simultaneous.get(), self.download_queue.qsize())
        
        for _ in range(max_dl):
            if not self.download_queue.empty():
                item = self.download_queue.get()
                self.start_single_download(item)
    
    def start_single_download(self, item):
        url, custom_name, _ = self.dl_tree.item(item, "values")
        self.dl_tree.item(item, values=(url, custom_name, "Descargando"))
        
        output_path = self.output_folder.get()
        cmd = [
            self.ytdlp_path.get(),
            url,
            "-o",
            os.path.join(output_path, f"{custom_name}.%(ext)s") if custom_name != "Predeterminado" else os.path.join(output_path, "%(title)s.%(ext)s"),
            "--newline"
        ]
        
        # Añadir parámetros de resolución
        resolution_choice = self.resolution.get()
        if resolution_choice == "audio":
            cmd.extend(['-f', 'bestaudio', '-x'])
        elif resolution_choice != "best":
            cmd.extend(['-S', f'res:{resolution_choice},best'])  # Fallback a mejor calidad
        
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
                    self.root.after(0, self.dl_tree.item, item, "values", (self.dl_tree.item(item, "values")[0], self.dl_tree.item(item, "values")[1], f"Error: {str(e)}"))
                    self.root.after(0, self.status_var.set, f"Error: {str(e)}")
                    self.complete_download(item, -1)
    
    def update_status(self, item, message):
        self.root.after(0, self.status_var.set, message)
    
    def complete_download(self, item, returncode):
        url, custom_name, _ = self.dl_tree.item(item, "values")
        
        if returncode == 0:
            status = "Completado"
            self.root.after(0, self.status_var.set, f"Descarga completada: {custom_name or url}")
            
            # Eliminar automáticamente si está habilitado
            if self.auto_remove.get():
                self.root.after(0, self.dl_tree.delete, item)
            else:
                self.root.after(0, self.dl_tree.item, item, "values", (url, custom_name, status))
        else:
            status = "Fallido"
            self.root.after(0, self.dl_tree.item, item, "values", (url, custom_name, status))
        
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
            
        item = selected[0]
        status = self.dl_tree.item(item, "values")[2]
        
        # Si está descargando, detener el proceso
        if status == "Descargando" and item in self.active_downloads:
            _, process = self.active_downloads[item]
            if process:
                process.terminate()
            del self.active_downloads[item]
        
        self.dl_tree.delete(item)
    
    def clear_completed(self):
        for item in self.dl_tree.get_children():
            status = self.dl_tree.item(item, "values")[2]
            if status == "Completado":
                self.dl_tree.delete(item)
    
    def on_close(self):
        self.save_config()
        self.save_queue()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = YTDownloaderApp(root)
    root.mainloop()
