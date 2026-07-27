# 🛍️ LunaShop Agente — Agente de IA para Soporte de E-commerce

Proyecto final del reto **Alura Agente** (programa ONE — Oracle Next Education).
Agente de inteligencia artificial que responde preguntas de colaboradores sobre
las políticas y documentos internos de **LunaShop**, una tienda de e-commerce
ficticia, usando RAG (Retrieval-Augmented Generation).

> ⚠️ **Nota:** LunaShop es una empresa ficticia creada exclusivamente para
> este proyecto educativo. Todos los documentos, políticas y datos son
> generados con fines de demostración.

> **Nota sobre OCI:** este proyecto despliega en Streamlit Community Cloud
> y usa OCI Object Storage (capa Always Free, creado manualmente desde la
> consola — sin Terraform) para el almacenamiento persistente de
> documentos, cumpliendo así el uso de al menos un servicio de Oracle
> Cloud Infrastructure.

---

## 📋 Índice

- [El problema que resuelve](#-el-problema-que-resuelve)
- [Arquitectura](#-arquitectura)
- [Formatos soportados y documentos incluidos](#-formatos-soportados-y-documentos-incluidos)
- [Gestión de documentos desde el frontend](#-gestión-de-documentos-desde-el-frontend)
- [Cuadritos de estado (modelo y base de datos)](#-cuadritos-de-estado-modelo-y-base-de-datos)
- [Ejemplos de preguntas y respuestas](#-ejemplos-de-preguntas-y-respuestas)
- [Cómo ejecutar el proyecto localmente](#-cómo-ejecutar-el-proyecto-localmente)
- [Despliegue en Streamlit Community Cloud](#-despliegue-en-streamlit-community-cloud)
- [Almacenamiento de documentos: local o OCI Object Storage](#-almacenamiento-de-documentos-local-o-oci-object-storage)
- [Registro de conversaciones (logs)](#-registro-de-conversaciones-logs)
- [Deploy alterno con Docker (opcional/secundario)](#-deploy-alterno-con-docker-opcionalsecundario)
- [Solución de problemas comunes](#-solución-de-problemas-comunes)
- [Estructura del repositorio](#-estructura-del-repositorio)
- [Roadmap / mejoras futuras](#-roadmap--mejoras-futuras)

---

## 🎯 El problema que resuelve

Los colaboradores de LunaShop (equipos de Atención al Cliente, Operaciones,
Legal, etc.) pierden tiempo buscando manualmente en documentos de políticas
internas para responder preguntas simples: "¿cuántos días tiene el cliente
para devolver un producto?", "¿cuál es el costo de envío express?", etc.

Este agente permite hacer esas preguntas en lenguaje natural y obtener una
respuesta directa, citando siempre el documento de origen. Además, cualquier
colaborador autorizado puede subir nuevos documentos o eliminar los que ya
no apliquen directamente desde la interfaz, sin tocar código.

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Community Cloud                     │
│  (deploy vinculado directo a GitHub, sin Docker)                   │
│                                                                     │
│   ┌───────────────────────┐        ┌───────────────────────────┐ │
│   │  app.py (Python)        │◀──────▶│  frontend/ (HTML+CSS+JS)   │ │
│   │  - Orquesta el agente    │ evento │  - Todo lo que ve el       │ │
│   │  - Sirve el frontend     │ ────── │    usuario: chat, tabs,     │ │
│   │    como Custom Component │ render │    subir/borrar documentos, │ │
│   │  - Sin widgets visibles  │        │    cuadritos de estado      │ │
│   │    de Streamlit           │        │  - Sin frameworks (JS puro) │ │
│   └───────────┬───────────┘        └───────────────────────────┘ │
│               │                                                   │
│   ┌───────────▼───────────┐                                       │
│   │  src/rag_agent.py       │  Recuperación semántica + LLM         │
│   │  src/ingest.py           │  Extracción, chunking, indexación     │
│   │  src/storage.py          │  Abstracción de almacenamiento         │
│   └───────────┬───────────┘                                       │
└───────────────┼───────────────────────────────────────────────────┘
                │
    ┌───────────┴───────────┐
    │                         │
    ▼                         ▼
┌─────────────┐     ┌──────────────────────┐
│  ChromaDB     │     │  Almacenamiento de     │
│  (índice        │     │  documentos:            │
│  vectorial,      │     │  - local (por defecto)  │
│  se reconstruye  │     │  - OCI Object Storage    │
│  al iniciar)     │     │    (capa Always Free,     │
│                  │     │    creado manualmente)    │
└─────────────┘     └──────────────────────┘
```

**Flujo de una pregunta:** el frontend (HTML/CSS/JS) envía la pregunta a
Python a través del protocolo de Streamlit Components (`postMessage`, sin
React ni build tools) → `rag_agent.py` convierte la pregunta en un
embedding, busca los fragmentos más relevantes en ChromaDB, arma el
contexto y genera la respuesta con el LLM configurado → Python devuelve el
historial actualizado al componente → el frontend se vuelve a dibujar con
la respuesta y sus fuentes citadas.

**Flujo de subir/borrar un documento:** el frontend envía el archivo
(codificado en base64) o el nombre a borrar → `storage.py` lo guarda/elimina
en el backend configurado (local o OCI Object Storage) → se dispara una re-indexación
completa (`ingest.py`) → el frontend recibe la lista de documentos y el
contador de fragmentos actualizados.

**Por qué el frontend es 100% HTML/CSS/JS sin widgets de Streamlit:**
Streamlit Community Cloud despliega un único proceso Python por app — no
permite correr, gratis, un frontend estático y una API separada como dos
servicios. Este proyecto usa la API oficial de **Streamlit Custom
Components** (`components.declare_component`) en su variante sin build
tools: Streamlit sirve `frontend/index.html`, `style.css` y `script.js` tal
cual dentro de un iframe, y la comunicación con Python ocurre por el
protocolo nativo de mensajería de Streamlit. Docker queda como un camino de
deploy secundario/opcional.

## 📄 Formatos soportados y documentos incluidos

El pipeline de ingesta (`src/ingest.py`) soporta los **7 formatos requeridos
por el reto**:

| Formato | Extensión | Librería usada | Estado |
|---|---|---|---|
| Markdown | `.md` | lectura nativa | ✅ Soportado |
| PDF | `.pdf` | `pypdf` | ✅ Soportado |
| Word | `.docx` | `python-docx` | ✅ Soportado |
| Excel | `.xlsx` | `pandas` + `openpyxl` | ✅ Soportado |
| PowerPoint | `.pptx` | `python-pptx` | ✅ Soportado |
| CSV | `.csv` | `pandas` | ✅ Soportado |
| JSON | `.json` | librería estándar | ✅ Soportado |
| HTML | `.html` / `.htm` | `beautifulsoup4` | ✅ Soportado |

El repositorio incluye **12 documentos de ejemplo** cubriendo los 7 formatos:

| Documento | Formato | Categoría |
|---|---|---|
| `politica_privacidad.md` | Markdown | Legal y Compliance |
| `politica_reembolsos.md` | Markdown | Operacional |
| `preguntas_frecuentes.md` | Markdown | Atención al Cliente |
| `guia_envios_entregas.md` | Markdown | Operacional |
| `terminos_condiciones.md` | Markdown | Legal y Compliance |
| `manual_atencion_cliente.pdf` | PDF | Operacional |
| `politica_proveedores.docx` | Word | Legal y Compliance |
| `catalogo_productos_ventas.xlsx` | Excel (2 hojas) | Datos y Sistemas |
| `presentacion_lunapuntos.pptx` | PowerPoint (7 diapositivas) | Marketing y Comercial |
| `historial_promociones.csv` | CSV | Marketing y Comercial |
| `configuracion_api_publica.json` | JSON | Datos y Sistemas |
| `ayuda_garantias_soporte.html` | HTML | Atención al Cliente |

## 📁 Gestión de documentos desde el frontend

En la pestaña **"📁 Documentos"** de la interfaz, cualquier persona puede:

- **Subir un documento nuevo**: arrastrándolo o haciendo clic en la zona de carga. Se valida el formato, se guarda en el backend de almacenamiento configurado y se re-indexa automáticamente.
- **Eliminar un documento existente**: con el botón 🗑 junto a cada archivo listado. También dispara una re-indexación.

No es necesario tocar código ni redeployar la app para actualizar la base
de conocimiento.

## 🧩 Cuadritos de estado (modelo y base de datos)

En la parte superior de la interfaz, tres cuadritos muestran en todo
momento:

- **Modelo (LLM)**: el proveedor y modelo configurado (por ejemplo "Cohere · command-a-03-2025"), o "Modo demo (sin LLM)" si `LLM_PROVIDER=none`.
- **Embeddings**: el modelo usado para vectorizar preguntas y documentos (`all-MiniLM-L6-v2`).
- **Base de datos vectorial**: el motor usado (ChromaDB) y cuántos fragmentos hay indexados en ese momento.

Se calcula en `LunaShopAgent.get_status()` y se actualiza solo.

## 💬 Ejemplos de preguntas y respuestas

| Pregunta | Respuesta del agente (resumen) | Fuente citada |
|---|---|---|
| "¿Cuántos días tengo para devolver un producto electrónico?" | 15 días naturales desde la entrega (menor que el general de 30 días, por depreciación acelerada). | `politica_reembolsos.md` |
| "¿Qué pasa si mi pedido llega tarde?" | Si el retraso supera los 10 días hábiles respecto a la fecha estimada, puedes solicitar el reembolso del costo de envío sin devolver el producto. | `politica_reembolsos.md`, `guia_envios_entregas.md` |
| "¿Puedo pagar en meses sin intereses?" | Sí, 3, 6 y 12 MSI en compras mayores a $1,500 MXN con tarjetas participantes. | `preguntas_frecuentes.md` |
| "¿LunaShop vende mis datos a terceros?" | No. Solo se comparten datos con paqueterías, procesadores de pago certificados y autoridades cuando exista requerimiento legal. | `politica_privacidad.md` |
| "¿Cuál es el costo del envío el mismo día?" | $249 MXN, disponible solo en zonas metropolitanas seleccionadas y pedidos antes de las 12:00 h. | `guia_envios_entregas.md` |
| "¿Cuáles son los niveles de membresía de LunaPuntos?" | Plata (0–4,999 pts), Oro (5,000–14,999 pts, envío gratis), Platino (15,000+ pts, envío gratis + acceso anticipado). | `presentacion_lunapuntos.pptx` |
| "¿Cuál es la política de vacaciones de los empleados?" | *(fuera del alcance de los documentos)* → el agente responde que no encontró esa información en vez de inventar una respuesta. | — (fallback controlado) |

## 🚀 Cómo ejecutar el proyecto localmente

**1. Clona el repositorio e instala dependencias**

```bash
git clone https://github.com/TU_USUARIO/aluraagente-ecommerce.git
cd aluraagente-ecommerce
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> El proyecto está fijado a **Python 3.10** (ver `.python-version`).

**2. Configura las variables de entorno**

```bash
cp .env.example .env
```

Por defecto, `LLM_PROVIDER=none` activa el **modo demo**: el agente
recupera los fragmentos relevantes y arma una respuesta extractiva sin
necesitar ninguna API key. `STORAGE_BACKEND=local` guarda los documentos en
la carpeta `documents/` del propio repo.

**3. Corre la app**

```bash
streamlit run app.py
```

Abre `http://localhost:8501`. La primera vez, la app construye el índice
vectorial automáticamente (puede tardar uno o dos minutos).

## ☁️ Despliegue en Streamlit Community Cloud

1. Sube el repositorio a GitHub (público, como pide el reto).
2. Entra a [share.streamlit.io](https://share.streamlit.io) e inicia sesión con tu cuenta de GitHub.
3. Clic en **"New app"** → selecciona el repositorio, la rama `main` y el archivo principal `app.py`.
4. En **"Advanced settings" → "Secrets"**, pega algo como:
   ```toml
   LLM_PROVIDER = "cohere"
   COHERE_API_KEY = "tu_api_key_aqui"
   COHERE_MODEL = "command-a-03-2025"

   STORAGE_BACKEND = "local"
   ```
   (o `STORAGE_BACKEND = "oci"` con tus credenciales de OCI, ver siguiente sección).
5. Clic en **"Deploy"**. Streamlit Cloud instala `requirements.txt` y
   levanta `app.py` automáticamente. Cada `git push` a `main` re-despliega
   la app sola.
6. Copia la URL pública (algo como `https://tu-usuario-aluraagente-ecommerce.streamlit.app`)
   y agrégala aquí como evidencia del deploy, junto con una captura de pantalla.

> **No se necesita Dockerfile para este camino de deploy** — Streamlit
> Cloud construye el entorno directamente desde `requirements.txt`.

## 🗄️ Almacenamiento de documentos: local o OCI Object Storage

Con `STORAGE_BACKEND=local` (el valor por defecto) no necesitas configurar
nada más: los documentos viven en la carpeta `documents/` del repo. La
única limitación es que los archivos que subas *desde la interfaz* durante
el uso de la app no sobrevivirán a un redeploy en Streamlit Cloud, porque
su sistema de archivos es efímero. Para la mayoría de las entregas del reto
esto es suficiente.

Si quieres que las subidas persistan entre redeploys — y de paso cumplir el
uso de un servicio de OCI — usa `STORAGE_BACKEND=oci` con **OCI Object
Storage** (capa Always Free: 20 GB de almacenamiento, 50,000
solicitudes/mes). El bucket se crea **a mano desde la consola**, sin
Terraform:

### Crear el bucket (consola de OCI, sin Terraform)

1. Entra a la consola de OCI → menú ☰ → **Storage → Buckets**.
2. Selecciona el compartment donde quieras crearlo y clic en **"Create Bucket"**.
3. Nombra el bucket, por ejemplo `lunashop-documentos`. Deja "Default Storage Tier" en `Standard` y visibilidad `Private`.
4. Clic en **"Create"**.
5. En la misma página de Buckets, copia el **namespace** que aparece arriba a la derecha (algo como `axabc1d2e3f4`) — lo necesitarás como `OCI_NAMESPACE`.

### Crear la API key (credenciales)

1. En la consola, clic en tu ícono de perfil (arriba a la derecha) → **"User settings"**.
2. En la pestaña **"API keys"**, clic en **"Add API key"** → **"Generate API Key Pair"** → descarga la llave privada.
3. OCI te muestra un bloque de configuración con `tenancy`, `user`, `fingerprint` y `region` — guárdalo, lo necesitas para el siguiente paso.

### Configurar el proyecto

**Opción A — con archivo `~/.oci/config` (más simple si corres localmente):**
Pega el bloque de configuración que copiaste en `~/.oci/config` y guarda la
llave privada descargada en la ruta que ese bloque indique (por ejemplo
`~/.oci/oci_api_key.pem`). Luego en tu `.env`:

```
STORAGE_BACKEND=oci
OCI_BUCKET_NAME=lunashop-documentos
OCI_NAMESPACE=tu_namespace_aqui
```

**Opción B — solo variables de entorno (recomendado para *secrets* de
Streamlit Cloud, donde no puedes subir un archivo `~/.oci/config`):**

```toml
STORAGE_BACKEND = "oci"
OCI_BUCKET_NAME = "lunashop-documentos"
OCI_NAMESPACE = "tu_namespace_aqui"
OCI_TENANCY_OCID = "ocid1.tenancy.oc1..xxxxx"
OCI_USER_OCID = "ocid1.user.oc1..xxxxx"
OCI_FINGERPRINT = "xx:xx:xx:...:xx"
OCI_PRIVATE_KEY_CONTENT = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
OCI_REGION = "mx-queretaro-1"
```

`src/storage.py` detecta automáticamente cuál de las dos opciones usar: si
existe `~/.oci/config` lo usa directamente; si no, arma la configuración a
partir de esas variables de entorno individuales.

## 📊 Registro de conversaciones (logs)

Cada interacción (pregunta, respuesta, fuentes, feedback 👍/👎) se registra
en `logs/interactions.jsonl`, en formato JSON Lines con timestamp.

Si `STORAGE_BACKEND=oci`, cada línea del log también se respalda
automáticamente en el bucket (`logs/interactions.jsonl` dentro del bucket),
para no perder el historial cuando Streamlit Cloud reinicia la app.

## 🐳 Deploy alterno con Docker (opcional/secundario)

Si prefieres autohospedar la app en vez de usar Streamlit Community Cloud:

```bash
docker compose up -d --build
```

No es necesario para el deploy principal.

## 🛠️ Solución de problemas comunes

**`NotFoundError: model 'command-r' was removed on September 15, 2025`**
Cohere retiró el modelo `command-r`. El proyecto usa por defecto
`command-a-03-2025`. Si tienes una copia previa, define en tu `.env`:
```
COHERE_MODEL=command-a-03-2025
```

**El índice tarda en construirse en cada redeploy**
Es esperado: Streamlit Cloud tiene sistema de archivos efímero, así que el
índice de ChromaDB se reconstruye desde cero en cada arranque. Con los 12
documentos de ejemplo tarda menos de un minuto.

**Subí un documento pero el agente no lo usa**
Revisa el cuadrito "Base de datos vectorial": debe mostrar más fragmentos
que antes. Si no cambió, revisa los logs de la app en Streamlit Cloud
("Manage app" → "Logs") para ver si la extracción del archivo falló.

## 📁 Estructura del repositorio

```
aluraagente-ecommerce/
├── documents/                    # Documentos internos de LunaShop (fuente de conocimiento)
├── src/
│   ├── ingest.py                  # Pipeline de extracción, chunking e indexación
│   ├── rag_agent.py               # Capa de recuperación + generación (RAG) + estado
│   └── storage.py                 # Abstracción de almacenamiento (local / OCI Object Storage)
├── frontend/                      # Frontend 100% HTML + CSS + JS (Streamlit Custom Component)
│   ├── index.html
│   ├── style.css
│   └── script.js
├── app.py                         # Punto de entrada Streamlit: orquesta agente + aloja el frontend
├── test_queries.py                # Preguntas de prueba end-to-end
├── requirements.txt
├── Dockerfile                     # Deploy alterno/secundario (no requerido para Streamlit Cloud)
├── docker-compose.yml
├── .python-version                 # Pin a Python 3.10
├── .env.example
├── COMMITS.md                     # Guía de commits/ramas paso a paso para subir el proyecto a GitHub
└── README.md
```

## 🔭 Roadmap / mejoras futuras

- Añadir reranking (modelo cross-encoder) sobre los top-20 candidatos antes de generar la respuesta.
- Migrar el índice vectorial a un servicio persistente para no reconstruirlo en cada redeploy.
- Añadir autenticación básica antes de exponer la subida/borrado de documentos a cualquier visitante del link público.
- Añadir CI con GitHub Actions para correr `test_queries.py` en cada push.

---

Proyecto desarrollado como parte del reto **Alura Agente** — programa **ONE (Oracle Next Education) — IA for Tech**.
