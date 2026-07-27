"""
Etapas 6 y 7 del pipeline: capa de recuperación (RAG) y
producción/validación de respuestas.

Este módulo expone la clase LunaShopAgent, que:
1. Convierte la pregunta del colaborador en un embedding.
2. Busca los fragmentos más relevantes en Chroma (similitud semántica).
3. Aplica un umbral de confianza: si nada es suficientemente relevante,
   respende con un fallback claro en lugar de alucinar.
4. Genera la respuesta con el LLM configurado, citando siempre la fuente.
5. Si no hay proveedor de LLM configurado (modo demo), arma una respuesta
   extractiva a partir de los fragmentos recuperados, para poder probar
   el pipeline completo localmente sin necesidad de una API key.
"""

import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", "chroma_db")
TOP_K = int(os.getenv("TOP_K_RETRIEVAL", 6))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.25))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()

SYSTEM_PROMPT = """Eres el asistente virtual de LunaShop, una tienda de e-commerce.
Responde ÚNICAMENTE con base en el CONTEXTO proporcionado a continuación.
No uses conocimiento externo ni inventes información.
Si el contexto no contiene la respuesta, di claramente que no encontraste
esa información en los documentos disponibles y sugiere contactar al área
correspondiente (Atención al Cliente, Legal u Operaciones).
Siempre que respondas, menciona de qué documento proviene la información.

CONTEXTO:
{context}

PREGUNTA DEL COLABORADOR:
{question}

RESPUESTA (clara, directa, en español, citando la fuente):"""


class LunaShopAgent:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            # Fuerza CPU explícitamente. Sin esto, en entornos CPU-only como
            # Streamlit Community Cloud, sentence-transformers/torch puede
            # intentar inicializar el modelo en un "meta device" y fallar con
            # NotImplementedError al moverlo ("Cannot copy out of meta tensor").
            model_kwargs={"device": "cpu"},
        )
        if not os.path.isdir(VECTOR_DB_DIR):
            raise FileNotFoundError(
                f"No se encontró el índice vectorial en '{VECTOR_DB_DIR}'. "
                "Ejecuta primero: python src/ingest.py"
            )
        self.vectordb = Chroma(
            persist_directory=VECTOR_DB_DIR,
            embedding_function=self.embeddings,
            collection_name="lunashop_docs",
            # Debe coincidir con la métrica usada al crear la colección en
            # ingest.py (cosine, no la L2 por defecto de Chroma) para que
            # similarity_search_with_relevance_scores() devuelva valores
            # bien calibrados frente a SIMILARITY_THRESHOLD.
            collection_metadata={"hnsw:space": "cosine"},
        )
        self.llm = self._load_llm()

    def _load_llm(self):
        """Carga el LLM según LLM_PROVIDER. Devuelve None en modo demo."""
        if LLM_PROVIDER == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        elif LLM_PROVIDER == "cohere":
            from langchain_cohere import ChatCohere
            # "command-r" fue retirado el 15 de septiembre de 2025.
            # command-a-03-2025 es el modelo recomendado de reemplazo (más
            # potente y con mayor contexto). Puedes cambiarlo por
            # "command-r-08-2024" si buscas una opción más ligera/económica.
            model_name = os.getenv("COHERE_MODEL", "command-a-03-2025")
            return ChatCohere(model=model_name, temperature=0.2)
        elif LLM_PROVIDER == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2)
        else:
            print("[INFO] LLM_PROVIDER=none → modo demo (respuestas extractivas, sin API key).")
            return None

    def _retrieve(self, question: str):
        """Etapa 6.1-6.3: embedding de la pregunta + búsqueda semántica + umbral."""
        results = self.vectordb.similarity_search_with_relevance_scores(
            question, k=TOP_K
        )
        # Filtramos por umbral de confianza (etapa 7.3: control de alucinación)
        relevant = [(doc, score) for doc, score in results if score >= SIMILARITY_THRESHOLD]
        return relevant

    def _format_context(self, retrieved) -> str:
        blocks = []
        for doc, score in retrieved:
            source = doc.metadata.get("source", "desconocido")
            category = doc.metadata.get("categoria", "General")
            blocks.append(
                f"[Fuente: {source} | Categoría: {category} | relevancia: {score:.2f}]\n"
                f"{doc.page_content}"
            )
        return "\n\n---\n\n".join(blocks)

    def _demo_answer(self, retrieved) -> str:
        """Modo demo: respuesta extractiva simple, sin LLM, para probar el
        pipeline localmente sin API key. Muestra el fragmento más relevante
        y su fuente."""
        top_doc, top_score = retrieved[0]
        source = top_doc.metadata.get("source", "desconocido")
        snippet = top_doc.page_content.strip()
        if len(snippet) > 500:
            snippet = snippet[:500].rsplit(" ", 1)[0] + "..."
        return (
            f"(Modo demo sin LLM configurado — mostrando el fragmento más relevante)\n\n"
            f"{snippet}\n\n"
            f"Fuente: {source} (relevancia: {top_score:.2f})"
        )

    def get_status(self) -> dict:
        """Etapa 8 (frontend): info para mostrar en los cuadritos de estado
        ('qué modelo se está usando', 'a qué base de datos está conectado')."""
        provider_labels = {
            "openai": "OpenAI",
            "cohere": "Cohere",
            "gemini": "Google Gemini",
            "none": "Modo demo (sin LLM)",
        }
        model_names = {
            "openai": "gpt-4o-mini",
            "cohere": os.getenv("COHERE_MODEL", "command-a-03-2025"),
            "gemini": "gemini-1.5-flash",
            "none": "—",
        }
        try:
            count = self.vectordb._collection.count()
        except Exception:
            count = None

        return {
            "llm_provider": provider_labels.get(LLM_PROVIDER, LLM_PROVIDER),
            "llm_model": model_names.get(LLM_PROVIDER, "—"),
            "embedding_model": "all-MiniLM-L6-v2 (sentence-transformers)",
            "vector_db": "ChromaDB",
            "vector_db_path": VECTOR_DB_DIR,
            "indexed_chunks": count,
        }

    def ask(self, question: str) -> dict:
        """Etapa 7 completa: recuperación + generación + fallback + citación."""
        retrieved = self._retrieve(question)

        if not retrieved:
            return {
                "answer": (
                    "No encontré esta información en los documentos disponibles. "
                    "Te recomiendo contactar directamente al área correspondiente "
                    "(Atención al Cliente, Legal u Operaciones)."
                ),
                "sources": [],
            }

        sources = [
            {
                "archivo": doc.metadata.get("source"),
                "categoria": doc.metadata.get("categoria"),
                "relevancia": round(score, 3),
            }
            for doc, score in retrieved
        ]

        if self.llm is None:
            answer = self._demo_answer(retrieved)
        else:
            context = self._format_context(retrieved)
            prompt = SYSTEM_PROMPT.format(context=context, question=question)
            response = self.llm.invoke(prompt)
            answer = response.content if hasattr(response, "content") else str(response)

        return {"answer": answer, "sources": sources}


if __name__ == "__main__":
    agent = LunaShopAgent()
    print("=== LunaShop Agente (modo consola) — escribe 'salir' para terminar ===\n")
    while True:
        q = input("Pregunta: ")
        if q.strip().lower() in {"salir", "exit", "quit"}:
            break
        result = agent.ask(q)
        print(f"\nRespuesta: {result['answer']}")
        print(f"Fuentes: {result['sources']}\n")
