"""
Capa de almacenamiento de documentos.

Soporta dos backends, seleccionables con STORAGE_BACKEND en .env:

- "local": guarda los documentos directamente en la carpeta DOCUMENTS_DIR
  del sistema de archivos. Simple, pero en plataformas con sistema de
  archivos efímero (como Streamlit Community Cloud) los archivos subidos
  se pierden si la app se reinicia o se redepliega.

- "oci": usa OCI Object Storage (capa Always Free: 20 GB, 50,000
  solicitudes/mes) como almacenamiento persistente. El bucket se crea a
  mano desde la consola de OCI (no se usa Terraform en este proyecto).
  Los documentos se guardan en el bucket y se sincronizan a DOCUMENTS_DIR
  en cada arranque de la app y tras cada cambio, para que el resto del
  pipeline (src/ingest.py) siga leyendo de disco local sin modificaciones.
"""

import os
import glob
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

DOCUMENTS_DIR = os.getenv("DOCUMENTS_DIR", "documents")
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()

SUPPORTED_EXTENSIONS = {".md", ".pdf", ".docx", ".xlsx", ".csv", ".json", ".html", ".htm", ".pptx"}


class LocalStorage:
    """Backend simple: lee/escribe directamente en DOCUMENTS_DIR."""

    def __init__(self):
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)

    def list_files(self):
        files = []
        for path in sorted(glob.glob(os.path.join(DOCUMENTS_DIR, "*"))):
            if os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS:
                files.append({
                    "name": os.path.basename(path),
                    "size_kb": round(os.path.getsize(path) / 1024, 1),
                    "modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                })
        return files

    def save_file(self, filename: str, content: bytes):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Formato no soportado: {ext}")
        path = os.path.join(DOCUMENTS_DIR, filename)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def delete_file(self, filename: str):
        path = os.path.join(DOCUMENTS_DIR, filename)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def sync_to_local(self):
        """No-op: ya estamos en local."""
        pass


class OCIObjectStorage:
    """Backend persistente sobre OCI Object Storage (capa Always Free).

    El bucket se crea manualmente desde la consola de OCI (Storage >
    Buckets > Create Bucket) — este proyecto no usa Terraform.

    Requiere en .env: OCI_BUCKET_NAME, OCI_NAMESPACE (visible en la parte
    superior de la consola de Buckets), y credenciales de OCI disponibles
    para el SDK, ya sea vía ~/.oci/config (perfil por defecto "DEFAULT",
    igual que la CLI de OCI) o construidas a partir de variables de entorno
    individuales si prefieres no tener un archivo de config en disco (ver
    _build_config más abajo).
    """

    def __init__(self):
        import oci

        bucket = os.getenv("OCI_BUCKET_NAME")
        namespace = os.getenv("OCI_NAMESPACE")
        if not bucket or not namespace:
            raise EnvironmentError(
                "STORAGE_BACKEND=oci requiere OCI_BUCKET_NAME y OCI_NAMESPACE en .env"
            )

        config = self._build_config()
        self.client = oci.object_storage.ObjectStorageClient(config)
        self.bucket = bucket
        self.namespace = namespace
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)

    def _build_config(self):
        """Arma la configuración del SDK de OCI. Usa ~/.oci/config si
        existe; si no, la construye desde variables de entorno individuales
        (útil para *secrets* de Streamlit Cloud, donde no quieres subir un
        archivo de config al repo)."""
        import oci

        profile = os.getenv("OCI_CONFIG_PROFILE", "DEFAULT")
        oci_config_path = os.path.expanduser("~/.oci/config")

        if os.path.exists(oci_config_path):
            return oci.config.from_file(profile_name=profile)

        required = ["OCI_TENANCY_OCID", "OCI_USER_OCID", "OCI_FINGERPRINT", "OCI_PRIVATE_KEY_CONTENT"]
        missing = [v for v in required if not os.getenv(v)]
        if missing:
            raise EnvironmentError(
                "No se encontró ~/.oci/config y faltan estas variables de entorno "
                f"para armar la configuración manualmente: {', '.join(missing)}"
            )

        return {
            "tenancy": os.getenv("OCI_TENANCY_OCID"),
            "user": os.getenv("OCI_USER_OCID"),
            "fingerprint": os.getenv("OCI_FINGERPRINT"),
            "key_content": os.getenv("OCI_PRIVATE_KEY_CONTENT"),
            "region": os.getenv("OCI_REGION", "mx-queretaro-1"),
        }

    def list_files(self):
        objects = self.client.list_objects(self.namespace, self.bucket, prefix="documents/").data.objects
        files = []
        for obj in objects:
            name = obj.name.split("/", 1)[-1]
            if not name or os.path.splitext(name)[1].lower() not in SUPPORTED_EXTENSIONS:
                continue
            files.append({
                "name": name,
                "size_kb": round((obj.size or 0) / 1024, 1),
                "modified": obj.time_modified.isoformat() if obj.time_modified else None,
            })
        return files

    def save_file(self, filename: str, content: bytes):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Formato no soportado: {ext}")
        object_name = f"documents/{filename}"
        self.client.put_object(self.namespace, self.bucket, object_name, content)
        # Reflejamos el cambio localmente para que ingest.py lo recoja de inmediato.
        with open(os.path.join(DOCUMENTS_DIR, filename), "wb") as f:
            f.write(content)

    def delete_file(self, filename: str):
        object_name = f"documents/{filename}"
        try:
            self.client.delete_object(self.namespace, self.bucket, object_name)
        except Exception:
            return False
        local_path = os.path.join(DOCUMENTS_DIR, filename)
        if os.path.exists(local_path):
            os.remove(local_path)
        return True

    def sync_to_local(self):
        """Descarga todos los objetos del bucket a DOCUMENTS_DIR. Se llama
        al arrancar la app para reconstruir el estado local (necesario
        porque el filesystem de Streamlit Cloud es efímero)."""
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)
        objects = self.client.list_objects(self.namespace, self.bucket, prefix="documents/").data.objects
        for obj in objects:
            name = obj.name.split("/", 1)[-1]
            if not name or os.path.splitext(name)[1].lower() not in SUPPORTED_EXTENSIONS:
                continue
            data = self.client.get_object(self.namespace, self.bucket, obj.name).data.content
            with open(os.path.join(DOCUMENTS_DIR, name), "wb") as f:
                f.write(data)

    def append_log(self, jsonl_line: str):
        """Bonus: además del log local, respalda cada interacción en el
        bucket bajo logs/interactions.jsonl, para no perder el historial
        cuando la app se reinicia en Streamlit Cloud."""
        object_name = "logs/interactions.jsonl"
        try:
            existing = self.client.get_object(self.namespace, self.bucket, object_name).data.content
        except Exception:
            existing = b""
        updated = existing + jsonl_line.encode("utf-8")
        self.client.put_object(self.namespace, self.bucket, object_name, updated)


def get_storage():
    """Factory: devuelve el backend configurado en STORAGE_BACKEND."""
    if STORAGE_BACKEND == "oci":
        return OCIObjectStorage()
    return LocalStorage()
