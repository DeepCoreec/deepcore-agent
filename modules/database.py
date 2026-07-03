import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

from deepcore_shared.db_base import DeepCoreDB

PROG_ID = "DeepCore Agent"


class AgentDB(DeepCoreDB):
    def __init__(self):
        super().__init__(PROG_ID, "agent.db")
        self._crear_tablas()

    def _crear_tablas(self):
        self.connect().executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo      TEXT NOT NULL DEFAULT 'Nueva conversación',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL,  -- user, assistant
            content         TEXT NOT NULL,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
        """)
        self.commit()

    def new_conversation(self, titulo: str = "Nueva conversación") -> int:
        return self.lastrowid("INSERT INTO conversations(titulo) VALUES(?)", (titulo,))

    def update_titulo(self, cid: int, titulo: str):
        self.execute("UPDATE conversations SET titulo=? WHERE id=?", (titulo, cid))
        self.commit()

    def get_conversations(self) -> list[dict]:
        rows = self.fetchall("SELECT * FROM conversations ORDER BY created_at DESC")
        return [dict(r) for r in rows]

    def save_message(self, conversation_id: int, role: str, content: str):
        self.execute("INSERT INTO messages(conversation_id,role,content) VALUES(?,?,?)",
                     (conversation_id, role, content))
        self.commit()

    def get_messages(self, conversation_id: int) -> list[dict]:
        rows = self.fetchall(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at",
            (conversation_id,))
        return [dict(r) for r in rows]

    def delete_conversation(self, cid: int):
        self.execute("DELETE FROM conversations WHERE id=?", (cid,))
        self.commit()
