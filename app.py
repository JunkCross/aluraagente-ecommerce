"""
Punto de entrada para el deploy en Streamlit Community Cloud.

Importante: este archivo NO dibuja la interfaz con widgets de Streamlit
(st.chat_input, st.button, etc.). Su único trabajo es:
  1. Cargar el agente y el almacenamiento de documentos.
  2. Alojar el componente estático de frontend/ (HTML + CSS + JS puro)
     usando components.declare_component.
  3. Recibir eventos del frontend (preguntas, subir/borrar documentos) y
     devolver el estado actualizado (historial, documentos, info de
     modelo/DB) para que el frontend se vuelva a dibujar.

Todo el HTML/CSS/JS que ve el usuario vive en frontend/, no aquí.
"""

import json
import os
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from src.rag_agent import LunaShopAgent
from src.storage import get_storage
from src import ingest

st.set_page_config(page_title="LunaShop — Agente de Soporte", page_icon="🛍️", layout="wide")

# Oculta el chrome por defecto de Streamlit para que solo se vea nuestro frontend.
st.markdown(
    """
    <style>
        #MainMenu, footer, header {visibility: hidden;}
        .block-container {padding: 0 !important; max-width: 100% !important;}
        iframe {min-height: 92vh;}
    </style>
    """,
    unsafe_allow_html=True,
)

LOG_FILE = "logs/interactions.jsonl"
os.makedirs("logs", exist_ok=True)

_lunashop_component = components.declare_component("lunashop_frontend", path="frontend")


def log_interaction(question, answer, sources, feedback=None):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "answer": answer,
        "sources": sources,
        "feedback": feedback,
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    # Respaldo opcional en OCI Object Storage si ese backend está activo.
    if hasattr(st.session_state.storage, "append_log"):
        try:
            st.session_state.storage.append_log(line)
        except Exception as e:
            print(f"[WARN] No se pudo respaldar el log en OCI: {e}")


@st.cache_resource(show_spinner=False)
def load_storage():
    storage = get_storage()
    storage.sync_to_local()
    return storage


def rebuild_index():
    """Vuelve a correr la ingesta completa tras subir/borrar un documento.
    Se borra el índice anterior para no dejar embeddings obsoletos de
    documentos eliminados."""
    import shutil
    if os.path.isdir(ingest.VECTOR_DB_DIR):
        shutil.rmtree(ingest.VECTOR_DB_DIR)
    docs = ingest.load_documents()
    chunks = ingest.chunk_documents(docs)
    ingest.build_index(chunks)


@st.cache_resource(show_spinner=False)
def load_agent(_index_version: int):
    """_index_version fuerza recargar el agente cuando cambian los documentos."""
    return LunaShopAgent()


# --- Estado de sesión ---
if "history" not in st.session_state:
    st.session_state.history = []
if "storage" not in st.session_state:
    st.session_state.storage = load_storage()
if "index_version" not in st.session_state:
    st.session_state.index_version = 0
if "last_nonce" not in st.session_state:
    st.session_state.last_nonce = None
if "index_ready" not in st.session_state:
    # Primera carga: construye el índice si aún no existe.
    if not os.path.isdir(ingest.VECTOR_DB_DIR):
        with st.spinner("Preparando el índice de documentos (primera carga)..."):
            rebuild_index()
    st.session_state.index_ready = True

agent = load_agent(st.session_state.index_version)


def documents_payload():
    return st.session_state.storage.list_files()


def status_payload():
    return agent.get_status()


# --- Renderiza el frontend y espera eventos ---
event = _lunashop_component(
    history=st.session_state.history,
    documents=documents_payload(),
    status=status_payload(),
    default=None,
    key="lunashop_component",
)

if event and isinstance(event, dict) and event.get("nonce") != st.session_state.last_nonce:
    st.session_state.last_nonce = event.get("nonce")
    action = event.get("action")

    if action == "ask":
        question = (event.get("question") or "").strip()
        if question:
            result = agent.ask(question)
            st.session_state.history.append(
                {"question": question, "answer": result["answer"], "sources": result["sources"]}
            )
            log_interaction(question, result["answer"], result["sources"])
        st.rerun()

    elif action == "feedback":
        log_interaction(
            event.get("question", ""),
            event.get("answer", ""),
            event.get("sources", []),
            event.get("feedback"),
        )
        st.rerun()

    elif action == "upload":
        filename = event.get("filename")
        content_b64 = event.get("content_b64")
        if filename and content_b64:
            import base64
            try:
                content = base64.b64decode(content_b64)
                st.session_state.storage.save_file(filename, content)
                with st.spinner(f"Indexando '{filename}'..."):
                    rebuild_index()
                st.session_state.index_version += 1
                load_agent.clear()
            except Exception as e:
                print(f"[ERROR] Falló la carga de {filename}: {e}")
        st.rerun()

    elif action == "delete":
        filename = event.get("filename")
        if filename:
            st.session_state.storage.delete_file(filename)
            with st.spinner(f"Actualizando el índice tras borrar '{filename}'..."):
                rebuild_index()
            st.session_state.index_version += 1
            load_agent.clear()
        st.rerun()
