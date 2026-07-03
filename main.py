import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

import customtkinter as ctk
from deepcore_shared.theme import Colors, Fonts, Sizes, Styles
from deepcore_shared.components.base_window import BaseWindow
from deepcore_shared.components.sidebar import SidebarItem, Sidebar
from modules.database import AgentDB
from modules.agent_core import AgentCore
from modules.ui.chat_panel import ChatPanel, ConfigPanel


class AgentApp(ctk.CTk):
    """
    DeepCore Agent tiene UI especial: sidebar izquierdo con historial de conversaciones
    + panel de chat principal. Se hereda de CTk directamente en vez de BaseWindow
    para tener control total del layout.
    """

    PROG_ID   = "DeepCore Agent"
    PROG_NAME = "DeepCore Agent"
    VERSION   = "2.0.0"

    def __init__(self):
        super().__init__()
        self.title("DeepCore Agent")
        self.geometry("1280x800")
        self.configure(fg_color=Colors.BG)
        self._db    = AgentDB()
        self._agent = AgentCore(api_key=self._db.get_config("claude_api_key"))
        # Init RAG
        rag_dir = os.path.join(os.environ.get("APPDATA", ""), "DeepCore Agent", "rag")
        os.makedirs(rag_dir, exist_ok=True)
        try: self._agent.init_rag(rag_dir)
        except Exception: pass

        self._current_panel: ctk.CTkFrame | None = None
        self._build_ui()
        self._abrir_chat_nuevo()

    def _build_ui(self):
        # Sidebar izquierdo — conversaciones
        self._sidebar_frame = ctk.CTkFrame(self, fg_color=Colors.SIDEBAR_BG,
                                            width=240, corner_radius=0)
        self._sidebar_frame.pack(side="left", fill="y")
        self._sidebar_frame.pack_propagate(False)

        # Header sidebar
        hdr = ctk.CTkFrame(self._sidebar_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(hdr, text="◈ DeepCore Agent", font=Fonts.H2,
                     text_color=Colors.GREEN, fg_color="transparent").pack(anchor="w")

        ctk.CTkButton(self._sidebar_frame, text="+ Nueva conversación",
                      command=self._abrir_chat_nuevo, **Styles.BTN_PRIMARY,
                      height=34).pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkButton(self._sidebar_frame, text="⚙ Configuración",
                      command=self._abrir_config, **Styles.BTN_SECONDARY,
                      height=32).pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkFrame(self._sidebar_frame, height=1, fg_color=Colors.BORDER).pack(fill="x", padx=12, pady=4)

        self._conv_list = ctk.CTkScrollableFrame(self._sidebar_frame, fg_color="transparent",
                                                  corner_radius=0)
        self._conv_list.pack(fill="both", expand=True, padx=4)
        self._refresh_conv_list()

        # Área de contenido
        self._content = ctk.CTkFrame(self, fg_color=Colors.BG2, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

    def _refresh_conv_list(self):
        for w in self._conv_list.winfo_children(): w.destroy()
        for conv in self._db.get_conversations():
            btn = ctk.CTkButton(self._conv_list,
                                text=conv["titulo"][:32],
                                anchor="w", fg_color="transparent",
                                hover_color=Colors.CARD_HOVER,
                                text_color=Colors.TEXT, font=Fonts.BODY,
                                height=36,
                                command=lambda cid=conv["id"]: self._abrir_chat(cid))
            btn.pack(fill="x", pady=1)

    def _abrir_chat_nuevo(self):
        cid = self._db.new_conversation()
        self._abrir_chat(cid)
        self._refresh_conv_list()

    def _abrir_chat(self, cid: int):
        if self._current_panel:
            self._current_panel.destroy()
        self._current_panel = ChatPanel(
            self._content, self._agent, self._db, cid,
            on_title_change=lambda _: self.after(100, self._refresh_conv_list))
        self._current_panel.pack(fill="both", expand=True)

    def _abrir_config(self):
        if self._current_panel:
            self._current_panel.destroy()
        self._current_panel = ConfigPanel(self._content, self._agent, self._db)
        self._current_panel.pack(fill="both", expand=True)


if __name__ == "__main__":
    app = AgentApp()
    app.mainloop()
