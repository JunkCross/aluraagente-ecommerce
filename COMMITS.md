# 📅 Guía de commits y ramas — LunaShop Agente

Esta guía te ayuda a subir el proyecto a GitHub mostrando un progreso
incremental real y ordenado por ramas, en el tiempo que te queda antes del
**lunes** (fecha de entrega). Está pensada para ejecutarse **hoy jueves y
en los próximos días reales**, no para simular fechas pasadas — cada commit
que hagas siguiendo esta guía tendrá una fecha real y honesta.

> Los archivos ya están todos generados en tu carpeta del proyecto. Esta
> guía simplemente te dice **en qué orden hacer `git add` y `git commit`**
> para que el historial cuente la historia real del desarrollo, en vez de
> subir todo de golpe en un solo commit.

## 0. Preparación (una sola vez)

Si tu carpeta actual ya tiene una carpeta `.git` (por ejemplo, si descargaste
el zip que te compartí antes), empieza limpio para que el historial sea
tuyo desde el primer commit:

```bash
cd aluraagente-ecommerce
rm -rf .git
git init
git branch -M main
```

Crea el repositorio vacío en GitHub (sin README, sin .gitignore — ya los
tienes localmente): ve a github.com → **New repository** → nómbralo
`aluraagente-ecommerce` → **Public** → **Create repository** (no marques
ninguna casilla de inicialización).

Conecta tu repo local con el remoto:

```bash
git remote add origin https://github.com/TU_USUARIO/aluraagente-ecommerce.git
```

---

## Día 1 — hoy, jueves — Estructura base y documentos fuente

```bash
git checkout -b feature/estructura-inicial

git add .gitignore .python-version
git commit -m "Configuracion inicial del repo: gitignore y version de Python"

git add documents/politica_privacidad.md documents/politica_reembolsos.md \
        documents/preguntas_frecuentes.md documents/guia_envios_entregas.md \
        documents/terminos_condiciones.md
git commit -m "Agrega documentos base de LunaShop en Markdown: privacidad, reembolsos, FAQ, envios, terminos"

git checkout main
git merge --no-ff feature/estructura-inicial -m "Merge: estructura inicial y documentos base"
git push -u origin main
```

## Día 1 o 2 — Pipeline de ingesta de documentos

```bash
git checkout -b feature/ingesta-documentos

git add requirements.txt .env.example
git commit -m "Agrega requirements.txt y plantilla de variables de entorno"

git add src/__init__.py src/ingest.py
git commit -m "Implementa pipeline de ingesta: extraccion, limpieza, chunking e indexacion vectorial"

git checkout main
git merge --no-ff feature/ingesta-documentos -m "Merge: pipeline de ingesta de documentos"
git push
```

## Día 2 — viernes — Agente RAG

```bash
git checkout -b feature/agente-rag

git add src/rag_agent.py
git commit -m "Implementa el agente RAG: recuperacion semantica, generacion con LLM y control de alucinacion"

git add test_queries.py
git commit -m "Agrega script de pruebas con preguntas representativas del negocio"

git checkout main
git merge --no-ff feature/agente-rag -m "Merge: agente RAG"
git push
```

## Día 3 — sábado — Más formatos de documento

```bash
git checkout -b feature/formatos-adicionales

git add documents/manual_atencion_cliente.pdf documents/politica_proveedores.docx
git commit -m "Agrega documentos de ejemplo en PDF y Word"

git add documents/catalogo_productos_ventas.xlsx documents/presentacion_lunapuntos.pptx
git commit -m "Agrega documentos de ejemplo en Excel y PowerPoint, con soporte PPTX en el pipeline de ingesta"

git add documents/historial_promociones.csv documents/configuracion_api_publica.json documents/ayuda_garantias_soporte.html
git commit -m "Agrega documentos de ejemplo en CSV, JSON y HTML: se cubren los 7 formatos requeridos"

git checkout main
git merge --no-ff feature/formatos-adicionales -m "Merge: soporte completo de formatos y documentos de ejemplo"
git push
```

## Día 4 — domingo — Almacenamiento, frontend y app principal

```bash
git checkout -b feature/frontend-y-almacenamiento

git add src/storage.py
git commit -m "Agrega capa de almacenamiento de documentos: local y OCI Object Storage"

git add frontend/index.html frontend/style.css
git commit -m "Construye el frontend: estructura HTML y estilos (chat + gestor de documentos)"

git add frontend/script.js
git commit -m "Implementa la logica del frontend en JavaScript puro: chat, subir/borrar documentos, cuadritos de estado"

git add app.py
git commit -m "Implementa app.py: aloja el frontend como Streamlit Custom Component y conecta el agente"

git checkout main
git merge --no-ff feature/frontend-y-almacenamiento -m "Merge: frontend HTML/CSS/JS y almacenamiento de documentos"
git push
```

## Día 4 o 5 — Deploy secundario con Docker y documentación

```bash
git checkout -b feature/docker-y-documentacion

git add Dockerfile docker-compose.yml
git commit -m "Agrega Dockerfile y docker-compose como opcion de deploy secundaria"

git add README.md COMMITS.md
git commit -m "Documenta arquitectura, formatos soportados, instrucciones de deploy y guia de commits"

git checkout main
git merge --no-ff feature/docker-y-documentacion -m "Merge: documentacion final y deploy secundario con Docker"
git push
```

## Día 5 — lunes — Deploy real y evidencia (entrega)

1. Despliega la app en Streamlit Community Cloud siguiendo el README (sección "Despliegue en Streamlit Community Cloud").
2. Toma una captura de pantalla de la app funcionando en la URL pública.
3. Agrega la captura a una carpeta `docs/` del repo y actualiza el README con la evidencia:

```bash
mkdir -p docs
# copia tu captura como docs/evidencia_deploy.png

git checkout -b feature/evidencia-deploy
git add docs/evidencia_deploy.png README.md
git commit -m "Agrega evidencia del deploy en Streamlit Community Cloud"

git checkout main
git merge --no-ff feature/evidencia-deploy -m "Merge: evidencia de deploy - entrega final"
git push

git tag -a v1.0 -m "Entrega final: Reto Alura Agente"
git push origin v1.0
```

---

## Resultado esperado

Al terminar tendrás en GitHub:

- **6-7 ramas de feature** (`feature/estructura-inicial`, `feature/ingesta-documentos`, `feature/agente-rag`, `feature/formatos-adicionales`, `feature/frontend-y-almacenamiento`, `feature/docker-y-documentacion`, `feature/evidencia-deploy`), todas fusionadas a `main` con `--no-ff` (esto deja un commit de merge visible en el historial, mostrando claramente cada etapa).
- **~15 commits** en `main`, cada uno con un mensaje descriptivo de una pieza concreta del trabajo.
- Un **tag `v1.0`** marcando la entrega.
- Actividad distribuida en varios días reales (jueves a lunes) en tu gráfica de contribuciones de GitHub.

## Notas importantes

- **No uses `git commit --date` para simular fechas pasadas.** Esta guía
  está pensada para que ejecutes los comandos en tiempo real, en los
  próximos días — así el historial es honesto y además es más fácil de
  explicar si alguien te pregunta sobre tu proceso de desarrollo.
- Si te queda poco tiempo y necesitas comprimir el plan, puedes hacer 2-3
  días en uno solo (por ejemplo, "Día 1" y "Día 2" el mismo jueves) — lo
  importante es mantener los commits separados por tema, no necesariamente
  estirarlos a la fuerza en 5 días distintos.
- Antes de cada `git push`, corre `python test_queries.py` (con
  `LLM_PROVIDER=none` para el modo demo) para confirmar que lo que subes
  realmente funciona.
