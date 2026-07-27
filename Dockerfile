# Este Dockerfile es un camino de deploy SECUNDARIO/OPCIONAL.
# El deploy principal del proyecto es Streamlit Community Cloud (ver README,
# sección "Despliegue en Streamlit Community Cloud"), que no requiere Docker.
# Usa esta imagen solo si prefieres autohospedar la app (por ejemplo, en una
# instancia de OCI Compute) en vez de usar Streamlit Cloud.
FROM python:3.10-slim

WORKDIR /app

# Dependencias del sistema necesarias para unstructured/pypdf/lxml y el healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# La ingesta se ejecuta una vez al construir la imagen para que el índice
# vectorial ya venga listo. Si prefieres regenerarlo en runtime, comenta
# esta línea y ejecútala manualmente en el contenedor.
RUN python src/ingest.py

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
