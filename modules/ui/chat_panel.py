import sys, os
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

import customtkinter as ctk
from deepcore_shared.theme import Colors, Fonts, Sizes, Styles
from deepcore_shared.components import Topbar


class ChatPanel(ctk.CTkFrame):
    def __init__(self, master, agent, db, conversation_id: int, on_title_change=None):
        super().__init__(master, fg_color=Colors.BG2, corner_radius=0)
        self._agent = agent
        self._db    = db
        self._cid   = conversation_id
        self._on_title_change = on_title_change
        self._msg_count = 0
        self._build_ui()
        self._cargar_historial()

    def _build_ui(self):
        Topbar(self, title="Chat con Aria").pack(fill="x")

        # Área de mensajes
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=Colors.BG2, corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=Sizes.PAD_LG, pady=(Sizes.PAD, 0))

        # Barra de entrada
        foot = ctk.CTkFrame(self, fg_color=Colors.CARD, corner_radius=0, height=60)
        foot.pack(fill="x", side="bottom"); foot.pack_propagate(False)
        inner = ctk.CTkFrame(foot, fg_color="transparent")
        inner.pack(fill="x", padx=Sizes.PAD_LG, pady=12)

        self._entry = ctk.CTkEntry(inner, placeholder_text="Escribe tu pregunta aquí…",
                                    **Styles.ENTRY, height=36)
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._entry.bind("<Return>",   self._enviar)
        self._entry.bind("<KP_Enter>", self._enviar)

        self._btn_send = ctk.CTkButton(inner, text="Enviar ▶", command=self._enviar,
                                        **Styles.BTN_PRIMARY, width=90, height=36)
        self._btn_send.pack(side="left")

        ctk.CTkButton(inner, text="Limpiar", command=self._limpiar,
                      **Styles.BTN_SECONDARY, width=80, height=36).pack(side="left", padx=(6, 0))

    # ── Render de mensajes ────────────────────────────────────────────────────

    def _add_bubble(self, role: str, text: str) -> ctk.CTkTextbox:
        is_user = role == "user"
        outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        outer.pack(fill="x", pady=4, padx=4, anchor="e" if is_user else "w")

        bg    = Colors.GREEN_DIM if is_user else Colors.CARD
        color = Colors.GREEN if is_user else Colors.TEXT
        bubble = ctk.CTkTextbox(outer, fg_color=bg, text_color=color, font=Fonts.BODY,
                                 wrap="word", corner_radius=Sizes.RADIUS,
                                 width=600, height=60, state="normal")
        bubble.insert("1.0", text)
        bubble.configure(state="disabled")
        bubble.pack(side="right" if is_user else "left")
        self._scroll.after(50, lambda: self._scroll._parent_canvas.yview_moveto(1))
        return bubble

    def _cargar_historial(self):
        msgs = self._db.get_messages(self._cid)
        for m in msgs:
            self._add_bubble(m["role"], m["content"])
        self._msg_count = len(msgs)

    # ── Enviar ────────────────────────────────────────────────────────────────

    def _enviar(self, _=None):
        texto = self._entry.get().strip()
        if not texto: return
        self._entry.delete(0, "end")
        self._btn_send.configure(state="disabled")
        self._add_bubble("user", texto)
        self._db.save_message(self._cid, "user", texto)

        # Si es el primer mensaje, usar como título
        if self._msg_count == 0:
            titulo = texto[:40]
            self._db.update_titulo(self._cid, titulo)
            if self._on_title_change: self._on_title_change(titulo)
        self._msg_count += 1

        # Burbuja de respuesta (streaming)
        resp_bub = self._add_bubble("assistant", "")
        resp_bub.configure(state="normal")

        full_resp = []

        def on_tok(delta: str):
            full_resp.append(delta)
            resp_bub.insert("end", delta)
            resp_bub.see("end")
            self._scroll._parent_canvas.yview_moveto(1)

        def on_done(full: str, ok: bool):
            resp_bub.configure(state="disabled")
            if ok:
                self._db.save_message(self._cid, "assistant", full)
            self.after(0, lambda: self._btn_send.configure(state="normal"))

        self._agent.chat(texto, on_token=lambda d: self.after(0, lambda dt=d: on_tok(dt)),
                         on_done=lambda f, ok: self.after(0, lambda: on_done(f, ok)))

    def _limpiar(self):
        for w in self._scroll.winfo_children(): w.destroy()
        self._agent.clear_history()


class ConfigPanel(ctk.CTkFrame):
    def __init__(self, master, agent, db):
        super().__init__(master, fg_color=Colors.BG2, corner_radius=0)
        self._agent = agent
        self._db    = db
        self._build_ui()

    def _build_ui(self):
        Topbar(self, title="Configuración — API Key").pack(fill="x")

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(expand=True)

        card = ctk.CTkFrame(center, fg_color=Colors.CARD, corner_radius=Sizes.RADIUS)
        card.pack(padx=80, pady=40)

        ctk.CTkLabel(card, text="Claude API Key", font=Fonts.H1,
                     text_color=Colors.TEXT, fg_color="transparent").pack(padx=40, pady=(24, 4))
        ctk.CTkLabel(card,
                     text="Obtén tu key en console.anthropic.com\nSe guarda de forma segura en tu PC.",
                     font=Fonts.BODY_SM, text_color=Colors.TEXT_MUTED, fg_color="transparent",
                     justify="center").pack(padx=40, pady=(0, 16))

        # Campo key (oculto)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(padx=40, pady=(0, 8))
        ctk.CTkLabel(row, text="API Key:", font=Fonts.BODY,
                     text_color=Colors.TEXT_MUTED, fg_color="transparent", width=80).pack(side="left")
        self._entry_key = ctk.CTkEntry(row, placeholder_text="sk-ant-…", show="•",
                                        width=320, **Styles.ENTRY, height=36)
        # Cargar key guardada
        saved = self._db.get_config("claude_api_key")
        if saved: self._entry_key.insert(0, saved)
        self._entry_key.pack(side="left", padx=(8, 0))

        self._lbl_msg = ctk.CTkLabel(card, text="", font=Fonts.BODY_SM,
                                      text_color=Colors.GREEN, fg_color="transparent")
        self._lbl_msg.pack()

        ctk.CTkButton(card, text="Guardar y aplicar", command=self._guardar,
                      **Styles.BTN_PRIMARY, width=180, height=38).pack(pady=(8, 24))

    def _guardar(self):
        key = self._entry_key.get().strip()
        if not key:
            self._lbl_msg.configure(text="Ingresa la API key.", text_color=Colors.RED); return
        self._db.set_config("claude_api_key", key)
        try:
            self._agent.set_api_key(key)
            self._lbl_msg.configure(text="✓ API key configurada correctamente.", text_color=Colors.GREEN)
        except Exception as e:
            self._lbl_msg.configure(text=str(e), text_color=Colors.RED)
