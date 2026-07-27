"""
Script de migración única: sube todos los documentos que ya están en
DOCUMENTS_DIR (local) al bucket de OCI Object Storage configurado en .env
(OCI_BUCKET_NAME, OCI_NAMESPACE).

Uso:
    python migrate_documents_to_oci.py

Requisitos previos:
    - STORAGE_BACKEND=oci en .env (o se puede correr con local aún activo,
      el script fuerza el backend OCI internamente).
    - OCI_BUCKET_NAME y OCI_NAMESPACE configurados en .env.
    - Credenciales de OCI disponibles (~/.oci/config o variables de
      entorno individuales, ver src/storage.py).

Este script no borra nada localmente ni en el bucket: solo sube (o
sobrescribe si ya existe) cada archivo soportado que encuentre en
DOCUMENTS_DIR. Es seguro volver a ejecutarlo.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Forzamos el backend OCI para esta migración, sin importar qué diga
# STORAGE_BACKEND en .env (así puedes migrar antes de cambiar el flag).
os.environ["STORAGE_BACKEND"] = "oci"

from src.storage import OCIObjectStorage, SUPPORTED_EXTENSIONS  # noqa: E402

DOCUMENTS_DIR = os.getenv("DOCUMENTS_DIR", "documents")


def main():
    print("=== Migración de documentos locales -> OCI Object Storage ===\n")

    try:
        storage = OCIObjectStorage()
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a OCI Object Storage: {e}")
        sys.exit(1)

    print(f"Bucket destino: {storage.bucket} (namespace: {storage.namespace})\n")

    if not os.path.isdir(DOCUMENTS_DIR):
        print(f"[ERROR] No existe el directorio '{DOCUMENTS_DIR}'.")
        sys.exit(1)

    local_files = [
        f for f in sorted(os.listdir(DOCUMENTS_DIR))
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
    ]

    if not local_files:
        print(f"[WARN] No se encontraron documentos soportados en '{DOCUMENTS_DIR}'.")
        return

    print(f"{len(local_files)} documentos encontrados localmente:\n")

    subidos = 0
    fallidos = []
    for filename in local_files:
        path = os.path.join(DOCUMENTS_DIR, filename)
        try:
            with open(path, "rb") as f:
                content = f.read()
            storage.save_file(filename, content)
            size_kb = round(len(content) / 1024, 1)
            print(f"  [OK] {filename} ({size_kb} KB) -> subido")
            subidos += 1
        except Exception as e:
            print(f"  [ERROR] {filename}: {e}")
            fallidos.append(filename)

    print(f"\nResultado: {subidos}/{len(local_files)} documentos subidos correctamente.")
    if fallidos:
        print(f"Fallaron: {', '.join(fallidos)}")
        sys.exit(1)

    # Verificación: lista lo que el bucket reporta tener ahora.
    print("\nVerificando contenido del bucket tras la migración...")
    remote_files = storage.list_files()
    print(f"El bucket ahora reporta {len(remote_files)} documentos:")
    for f in remote_files:
        print(f"  - {f['name']} ({f['size_kb']} KB)")

    print("\n=== Migración completada ===")


if __name__ == "__main__":
    main()
