import streamlit as st
import yt_dlp
import os
import shutil
import zipfile
import re

st.set_page_config(page_title="Descargador YouTube", page_icon="⬇️")
st.title("Descargador YouTube")

# --- 1. CONFIGURACIÓN DE RUTAS ---
DOWNLOAD_PATH = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

if 'download_ready' not in st.session_state:
    st.session_state.download_ready = False
if 'playlist_title' not in st.session_state:
    st.session_state.playlist_title = "Playlist"
if 'total_videos' not in st.session_state:
    st.session_state.total_videos = 0
if 'completed_videos' not in st.session_state:
    st.session_state.completed_videos = 0



# --- 2. UI ---
st.markdown("---")
playlist_status_box = st.empty()
progress_bar = st.progress(0)
status_text = st.empty()

def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# --- 3. LOGGER ---
class MyLogger:
    def debug(self, msg):
        if msg.startswith('[download] Sleeping'):
            clean_msg = clean_ansi(msg)
            status_text.warning(f"💤 {clean_msg}")
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): print(f"❌ {msg}")

# --- 4. HOOK CON PROGRESO ---
def progress_hook(d):
    if d['status'] == 'downloading':
        p_text = clean_ansi(d.get('_percent_str', '0%'))
        s_text = clean_ansi(d.get('_speed_str', 'N/A'))
        e_text = clean_ansi(d.get('_eta_str', 'N/A'))
        
        try:
            p_number = float(p_text.replace('%','').strip()) / 100
            progress_bar.progress(min(max(p_number, 0.0), 1.0))
            status_text.text(f"Velocidad Descarga: {s_text} | Completado: {p_text} | Falta: {e_text}")
        except: pass

        idx = d.get('playlist_index')
        total = d.get('playlist_count') or d.get('n_entries')
        if idx and total:
            playlist_status_box.info(f"💽 **Video {idx} de {total}**")

    elif d['status'] == 'finished':
        st.session_state.completed_videos += 1
        
        total = st.session_state.total_videos
        done = st.session_state.completed_videos
        
        if total > 0:
            playlist_progress = done / total
            progress_bar.progress(min(playlist_progress, 1.0))
            playlist_status_box.info(f"📦 Progreso Playlist: {done}/{total}")
        
        status_text.success("✅ Archivo completado.")


# --- 5. INPUTS ---
url = st.text_input("🔗 Link de YouTube:", placeholder="Video o Playlist...")
tipo = st.radio("💿 Formato:", ["MP4 (Video)", "MP3 (Audio)"])

calidad = "1080"
if tipo == "MP4 (Video)":
    calidad = st.selectbox("Calidad Máxima:", ["2160", "1440", "1080", "720"])

# --- 6. LÓGICA TURBO ---
if st.button("INICIAR DESCARGA"):
    if not url:
        st.warning("Escribe un link.")
    else:
        if os.path.exists(DOWNLOAD_PATH):
            shutil.rmtree(DOWNLOAD_PATH)
        os.makedirs(DOWNLOAD_PATH)
        
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
                
                # --- AQUÍ ESTÁ LA VELOCIDAD ---
                'concurrent_fragment_downloads': 8, # <--- ¡ESTO ACELERA LA DESCARGA!
                
                # Reducimos la espera un poco (Equilibrio Rapidez/Seguridad)
                'sleep_interval': 2,      
                'max_sleep_interval': 5, 
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
                    # Forzamos MP4 + M4A (AAC)
                    'format': f'bestvideo[height<={calidad}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'merge_output_format': 'mp4',
                })

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            st.session_state.download_ready = True
            playlist_status_box.success(f"Descarga de {st.session_state.playlist_title} Completada ")

        except Exception as e:
            st.error(f"Error: {e}")

# --- 7. DESCARGA FINAL ---
if st.session_state.download_ready:
    archivos = [f for f in os.listdir(DOWNLOAD_PATH) if os.path.isfile(os.path.join(DOWNLOAD_PATH, f))]
    
    if archivos:
        st.write("---")
        if len(archivos) == 1:
            archivo_final = os.path.join(DOWNLOAD_PATH, archivos[0])
            with open(archivo_final, "rb") as f:
                st.download_button(
                    label=f"⬇️ Descargar: {archivos[0]}",
                    data=f,
                    file_name=archivos[0],
                    mime="video/mp4" if tipo == "MP4 (Video)" else "audio/mpeg",
                    key="descarga_ok"
                )
            # 🔥 Eliminamos el archivo después de generar el botón
            if os.path.exists(archivo_final):
                os.remove(archivo_final)
        else:
            clean_title = re.sub(r'[^\w\s-]', '', st.session_state.playlist_title).strip()
            if not clean_title: clean_title = "playlist"
            zip_name = f"{clean_title}.zip"
            zip_path = os.path.join(os.getcwd(), zip_name)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in archivos:
                    zipf.write(os.path.join(DOWNLOAD_PATH, file), file)
            
            with open(zip_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ DESCARGAR ZIP",
                    data=f,
                    file_name=zip_name,
                    mime="application/zip",
                    key="descarga_zip_ok"
                )

            # 🔥 Limpiamos archivos individuales también
            for file in archivos:
                file_path = os.path.join(DOWNLOAD_PATH, file)
                if os.path.exists(file_path):
                    os.remove(file_path)

            # 🔥 Eliminamos el zip final
            if os.path.exists(zip_path):
                os.remove(zip_path)
