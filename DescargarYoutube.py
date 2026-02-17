import streamlit as st
import yt_dlp
import os
import shutil
import zipfile
import re
import tempfile

# --- 1. CONFIGURACIÓN DE RUTAS ---
# ### CAMBIO: Usamos una subcarpeta con ID único para evitar choques en la nube
if 'session_id' not in st.session_state:
    st.session_state.session_id = next(tempfile._get_candidate_names())

DOWNLOAD_PATH = os.path.join(tempfile.gettempdir(), f"descargas_{st.session_state.session_id}")
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

st.set_page_config(page_title="Descargador YouTube", page_icon="⬇️")
st.title("Descargador YouTube")

# --- AREA DE DEBUG (NUEVO) ---
debug_expander = st.expander("🕵️ Ver Logs de Depuración", expanded=True)
def log_debug(msg):
    debug_expander.write(f"🐞 {msg}")
    print(f"DEBUG: {msg}")

# --- 2. SESSION STATE (TU CÓDIGO ORIGINAL) ---
if 'download_ready' not in st.session_state:
    st.session_state.download_ready = False
if 'playlist_title' not in st.session_state:
    st.session_state.playlist_title = "Playlist"
if 'total_videos' not in st.session_state:
    st.session_state.total_videos = 0
if 'completed_videos' not in st.session_state:
    st.session_state.completed_videos = 0

# --- 3. UI (TU CÓDIGO ORIGINAL) ---
st.markdown("---")
playlist_status_box = st.empty()
progress_bar = st.progress(0)
status_text = st.empty()

def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# --- 4. LOGGER (TU CÓDIGO ORIGINAL CON DEBUGS AÑADIDOS) ---
class MyLogger:
    def debug(self, msg):
        # Mantenemos tu lógica original
        if msg.startswith('[download] Sleeping'):
            status_text.warning(f"💤 {clean_ansi(msg)}")
        # Añadimos chivato para ver si hay error 403 oculto
        if '403' in msg:
            log_debug(f"ALERTA 403 DETECTADA: {msg}")
            
    def info(self, msg): pass
    def warning(self, msg): 
        log_debug(f"WARNING: {msg}")
    def error(self, msg): 
        st.error(f"❌ {msg}")
        log_debug(f"ERROR: {msg}")

# --- 5. HOOK CON PROGRESO (TU CÓDIGO ORIGINAL) ---
def progress_hook(d):
    if d['status'] == 'downloading':
        p_text = clean_ansi(d.get('_percent_str', '0%'))
        s_text = clean_ansi(d.get('_speed_str', 'N/A'))
        e_text = clean_ansi(d.get('_eta_str', 'N/A'))
        
        try:
            p_number = float(p_text.replace('%','').strip()) / 100
            progress_bar.progress(min(max(p_number, 0.0), 1.0))
            status_text.text(f"Velocidad: {s_text} | Completado: {p_text} | Falta: {e_text}")
        except: pass

        idx = d.get('playlist_index')
        total = d.get('playlist_count') or d.get('n_entries')
        if idx and total:
            playlist_status_box.info(f"💽 Video {idx} de {total}")

    elif d['status'] == 'finished':
        st.session_state.completed_videos += 1
        
        total = st.session_state.total_videos
        done = st.session_state.completed_videos
        
        if total > 0:
            playlist_progress = done / total
            progress_bar.progress(min(playlist_progress, 1.0))
            playlist_status_box.info(f"📦 Progreso Playlist: {done}/{total}")
        
        status_text.success("✅ Archivo completado.")
        log_debug(f"Archivo finalizado: {d.get('filename')}")

# --- 6. INPUTS ---
url = st.text_input("🔗 Link de YouTube:", placeholder="Video o Playlist...")
tipo = st.radio("💿 Formato:", ["MP4 (Video)", "MP3 (Audio)"])

calidad = "1080"
if tipo == "MP4 (Video)":
    calidad = st.selectbox("Calidad Máxima:", ["2160", "1440", "1080", "720"])

# --- 7. DESCARGA ---
if st.button("INICIAR DESCARGA"):
    log_debug("Botón pulsado. Iniciando...")
    if not url:
        st.warning("Escribe un link.")
    else:
        # Limpiamos carpeta
        if os.path.exists(DOWNLOAD_PATH):
            shutil.rmtree(DOWNLOAD_PATH)
        os.makedirs(DOWNLOAD_PATH, exist_ok=True)
        
        st.session_state.download_ready = False
        playlist_status_box.empty()
        status_text.empty()

        try:
            log_debug("Intentando extraer info (extract_flat)...")
            # Extraemos info sin descargar
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                raw_title = info.get('title', 'descarga_youtube')
                if 'entries' in info:
                    st.session_state.total_videos = len(info['entries'])
                else:
                    st.session_state.total_videos = 1
                st.session_state.completed_videos = 0
                st.session_state.playlist_title = clean_ansi(raw_title)

            log_debug(f"Info extraída. Video: {raw_title}")

            # ### CAMBIO IMPORTANTE: AÑADIDO BLOQUEO ANTI-BOTS (HEADERS)
            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s',
                'progress_hooks': [progress_hook],
                'logger': MyLogger(), 
                'noplaylist': False,
                'ignoreerrors': True,
                'noprogress': False,
                'quiet': False, 
                'no_color': True,
                'concurrent_fragment_downloads': 8,
                'sleep_interval': 2,      
                'max_sleep_interval': 5, 
                # --- AQUÍ ESTÁ LA SOLUCIÓN AL ERROR 403 ---
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            }

            if tipo == "MP3 (Audio)":
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                ydl_opts.update({
                    'format': f'bestvideo[height<={calidad}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'merge_output_format': 'mp4',
                })

            log_debug("Iniciando ydl.download()...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            log_debug("Función download terminada.")
            st.session_state.download_ready = True
            playlist_status_box.success(f"Descarga de {st.session_state.playlist_title} completada 🎉")
            
            # ### CAMBIO: Forzamos recarga para que salgan los botones
            log_debug("Haciendo Rerun para mostrar botones...")
            st.rerun()

        except Exception as e:
            log_debug(f"EXCEPCIÓN CRÍTICA: {e}")
            st.error(f"Error: {e}")

# --- 8. DESCARGA FINAL ---
if st.session_state.download_ready:
    log_debug("Renderizando botones de descarga final...")
    archivos = [f for f in os.listdir(DOWNLOAD_PATH) if os.path.isfile(os.path.join(DOWNLOAD_PATH, f))]
    log_debug(f"Archivos encontrados: {len(archivos)}")
    
    if archivos:
        st.write("---")
        if len(archivos) == 1:
            archivo_final = os.path.join(DOWNLOAD_PATH, archivos[0])
            if os.path.exists(archivo_final):
                with open(archivo_final, "rb") as f:
                    st.download_button(
                        label=f"⬇️ Descargar: {archivos[0]}",
                        data=f,
                        file_name=archivos[0],
                        mime="video/mp4" if tipo == "MP4 (Video)" else "audio/mpeg",
                        key="descarga_ok"
                    )
                # ### CAMBIO: COMENTADO EL REMOVE PARA QUE NO FALLE AL DAR CLICK
                # os.remove(archivo_final) 
        else:
            clean_title = re.sub(r'[^\w\s-]', '', st.session_state.playlist_title).strip()
            if not clean_title: clean_title = "playlist"
            zip_name = f"{clean_title}.zip"
            # ### CAMBIO: Ruta del zip a tempfile seguro
            zip_path = os.path.join(tempfile.gettempdir(), f"{st.session_state.session_id}_zip.zip")
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in archivos:
                    zipf.write(os.path.join(DOWNLOAD_PATH, file), file)
            
            if os.path.exists(zip_path):
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label=f"⬇️ DESCARGAR ZIP",
                        data=f,
                        file_name=zip_name,
                        mime="application/zip",
                        key="descarga_zip_ok"
                    )
            
            # Limpiamos archivos individuales (TU CÓDIGO)
            # Nota: Esto está bien, pero recuerda que si borras aquí, el botón individual de arriba no funcionará si la logica entrase aquí.
            # Como está dentro del "else" (para varios archivos), está bien.
            for file in archivos:
                file_path = os.path.join(DOWNLOAD_PATH, file)
                if os.path.exists(file_path):
                    os.remove(file_path)
            # Limpiamos zip
            # if os.path.exists(zip_path):
            #    os.remove(zip_path) # Comentado por seguridad del botón