"""
DeepCore Agent — motor IA.
Usa Claude Haiku 4.5 como LLM + ChromaDB para RAG local.
La API key se guarda encriptada en la DB de config.
"""
import threading
import json

try:
    import anthropic
    _ANTHROPIC_OK = True
except ImportError:
    _ANTHROPIC_OK = False

try:
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    _CHROMA_OK = True
except ImportError:
    _CHROMA_OK = False

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096
SYSTEM_PROMPT = """Eres Aria, asistente IA de DeepCore Ecuador.
Eres experta en negocios, contabilidad, RRHH, facturación SRI, tecnología y normativas ecuatorianas.
Responde en español. Sé concisa, útil y profesional.
Si tienes contexto del usuario (documentos cargados), úsalo al responder."""


class AgentCore:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key
        self._model   = model or DEFAULT_MODEL
        self._client  = None
        self._chroma  = None
        self._collection = None
        self._history: list[dict] = []
        self._on_token = None
        if api_key:
            self._init_client(api_key)

    def set_api_key(self, key: str):
        self._api_key = key
        self._init_client(key)

    def set_model(self, model: str):
        self._model = model

    def _init_client(self, key: str):
        if not _ANTHROPIC_OK:
            raise RuntimeError("anthropic no instalado. pip install anthropic")
        self._client = anthropic.Anthropic(api_key=key)

    def init_rag(self, persist_dir: str):
        if not _CHROMA_OK: return
        self._chroma = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._chroma.get_or_create_collection(
            "deepcore_docs", embedding_function=DefaultEmbeddingFunction())

    def add_document(self, text: str, doc_id: str, metadata: dict | None = None):
        if not self._collection: return
        chunks = self._chunk(text)
        self._collection.add(
            documents=chunks,
            ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
            metadatas=[metadata or {}] * len(chunks))

    def _chunk(self, text: str, size: int = 400, overlap: int = 50) -> list[str]:
        words = text.split()
        chunks, i = [], 0
        while i < len(words):
            chunks.append(" ".join(words[i:i + size]))
            i += size - overlap
        return chunks or [text]

    def _retrieve(self, query: str, n: int = 3) -> str:
        if not self._collection: return ""
        results = self._collection.query(query_texts=[query], n_results=n)
        docs = results.get("documents", [[]])[0]
        return "\n\n".join(docs) if docs else ""

    def chat(self, user_msg: str, on_token=None, on_done=None):
        if not self._client:
            if on_done: on_done("Error: configura tu API key de Claude primero.", False)
            return
        context = self._retrieve(user_msg)
        system  = SYSTEM_PROMPT
        if context:
            system += f"\n\n## Contexto de documentos del usuario:\n{context}"
        self._history.append({"role": "user", "content": user_msg})

        def _run():
            full = ""
            try:
                with self._client.messages.stream(
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    messages=self._history[-20:]
                ) as stream:
                    for delta in stream.text_stream:
                        full += delta
                        if on_token: on_token(delta)
                self._history.append({"role": "assistant", "content": full})
                if on_done: on_done(full, True)
            except Exception as e:
                if on_done: on_done(str(e), False)

        threading.Thread(target=_run, daemon=True).start()

    def clear_history(self):
        self._history.clear()

    def list_docs(self) -> list[str]:
        if not self._collection: return []
        data = self._collection.get()
        ids  = data.get("ids", [])
        seen = set()
        return [i.rsplit("_", 1)[0] for i in ids if not (i.rsplit("_", 1)[0] in seen or seen.add(i.rsplit("_", 1)[0]))]

    def delete_doc(self, doc_id: str):
        if not self._collection: return
        all_ids = self._collection.get()["ids"]
        to_del  = [i for i in all_ids if i.startswith(doc_id + "_")]
        if to_del: self._collection.delete(ids=to_del)
