import streamlit as st
import yt_dlp
import os
import shutil
import zipfile
import re
import tempfile

# --- 1. CONFIGURACIÓN DE RUTAS ---
# Cambio menor: Carpeta única por sesión para que no choque con otros usuarios en la nube
if 'session_id' not in st.session_state:
    st.session_state.session_id = next(tempfile._get_candidate_names())

DOWNLOAD_PATH = os.path.join(tempfile.gettempdir(), f"descargas_{st.session_state.session_id}")
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)

st.set_page_config(page_title="Descargador YouTube", page_icon="⬇️")
st.title("Descargador YouTube")

# --- 2. SESSION STATE ---
if 'download_ready' not in st.session_state:
    st.session_state.download_ready = False
if 'playlist_title' not in st.session_state:
    st.session_state.playlist_title = "Playlist"
if 'total_videos' not in st.session_state:
    st.session_state.total_videos = 0
if 'completed_videos' not in st.session_state:
    st.session_state.completed_videos = 0

# --- 3. UI ---
st.markdown("---")
playlist_status_box = st.empty()
progress_bar = st.progress(0)
status_text = st.empty()

def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# --- 4. LOGGER ---
class MyLogger:
    def debug(self, msg):
        if msg.startswith('[download] Sleeping'):
            status_text.warning(f"💤 {clean_ansi(msg)}")
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): print(f"❌ {msg}")

# --- 5. HOOK CON PROGRESO ---
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

# --- 6. INPUTS ---
url = st.text_input("🔗 Link de YouTube:", placeholder="Video o Playlist...")
tipo = st.radio("💿 Formato:", ["MP4 (Video)", "MP3 (Audio)"])

calidad = "1080"
if tipo == "MP4 (Video)":
    calidad = st.selectbox("Calidad Máxima:", ["2160", "1440", "1080", "720"])

# --- 7. DESCARGA ---
if st.button("INICIAR DESCARGA"):
    if not url:
        st.warning("Escribe un link.")
    else:
        # Limpiamos carpeta antes de empezar nueva descarga
        if os.path.exists(DOWNLOAD_PATH):
            shutil.rmtree(DOWNLOAD_PATH)
        os.makedirs(DOWNLOAD_PATH, exist_ok=True)
        
        st.session_state.download_ready = False
        playlist_status_box.empty()
        status_text.empty()

        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                raw_title = info.get('title', 'descarga_youtube')
                if 'entries' in info:
                    st.session_state.total_videos = len(info['entries'])
                else:
                    st.session_state.total_videos = 1
                st.session_state.completed_videos = 0
                st.session_state.playlist_title = clean_ansi(raw_title)

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

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            st.session_state.download_ready = True
            # CAMBIO CLAVE: Forzamos a Streamlit a refrescar para ver el botón de descarga
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

# --- 8. DESCARGA FINAL ---
if st.session_state.download_ready:
    archivos = [f for f in os.listdir(DOWNLOAD_PATH) if os.path.isfile(os.path.join(DOWNLOAD_PATH, f))]
    
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
                # IMPORTANTE: No borramos el archivo aquí o el botón fallará al hacer clic
        else:
            clean_title = re.sub(r'[^\w\s-]', '', st.session_state.playlist_title).strip()
            if not clean_title: clean_title = "playlist"
            zip_name = f"{clean_title}.zip"
            zip_path = os.path.join(tempfile.gettempdir(), f"{st.session_state.session_id}.zip")
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in archivos:
                    zipf.write(os.path.join(DOWNLOAD_PATH, file), file)
            
            if os.path.exists(zip_path):
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label=f"⬇️ DESCARGAR ZIP: {zip_name}",
                        data=f,
                        file_name=zip_name,
                        mime="application/zip",
                        key="descarga_zip_ok"
                    )