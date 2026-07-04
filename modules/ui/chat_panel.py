"""Chat panel + Config panel — DeepCore Agent."""
import sys, os, threading
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

import customtkinter as ctk
from tkinter import filedialog
from datetime import datetime
from deepcore_shared.theme import Colors, Fonts, Sizes, Styles
from deepcore_shared.components import Topbar

try:
    from deepcore_shared.utils.exporters import abrir_archivo
except ImportError:
    abrir_archivo = None


class ChatPanel(ctk.CTkFrame):
    def __init__(self, master, agent, db, conversation_id: int, on_title_change=None):
        super().__init__(master, fg_color=Colors.BG2, corner_radius=0)
        self._agent  = agent
        self._db     = db
        self._cid    = conversation_id
        self._on_title_change = on_title_change
        self._msg_count  = 0
        self._streaming  = False
        self._resp_label = None
        self._full_resp  = []
        self._build_ui()
        self._cargar_historial()

    def _build_ui(self):
        bar = Topbar(self, title="Chat con Aria")
        bar.add_button("↓ Exportar", self._exportar_txt)
        bar.pack(fill="x")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=Colors.BG2, corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=Sizes.PAD_LG, pady=(Sizes.PAD, 0))

        # Footer
        foot = ctk.CTkFrame(self, fg_color=Colors.CARD, corner_radius=0)
        foot.pack(fill="x", side="bottom")

        inner = ctk.CTkFrame(foot, fg_color="transparent")
        inner.pack(fill="x", padx=Sizes.PAD_LG, pady=(10, 6))

        ctk.CTkButton(inner, text="📎", command=self._adjuntar_doc,
                      fg_color="transparent", hover_color=Colors.CARD_HOVER,
                      text_color=Colors.TEXT_DIM, font=("Segoe UI Emoji", 15),
                      width=36, height=36, corner_radius=6).pack(side="left", padx=(0, 6))

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

        self._lbl_status = ctk.CTkLabel(foot, text="", font=Fonts.BODY_SM,
                                         text_color=Colors.TEXT_DIM, fg_color="transparent")
        self._lbl_status.pack(anchor="w", padx=Sizes.PAD_LG, pady=(0, 8))

    # ── Burbujas ──────────────────────────────────────────────────────────────

    def _add_bubble(self, role: str, text: str = "") -> ctk.CTkLabel:
        is_user = role == "user"
        outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        outer.pack(fill="x", pady=3, padx=4)

        bg    = Colors.GREEN_DIM if is_user else Colors.SURFACE
        color = Colors.GREEN     if is_user else Colors.TEXT

        lbl = ctk.CTkLabel(outer, text=text or " ",
                            fg_color=bg, text_color=color, font=Fonts.BODY,
                            wraplength=580, anchor="nw", justify="left",
                            corner_radius=10, padx=14, pady=10)
        lbl.pack(side="right" if is_user else "left", padx=4, anchor="n")

        if not is_user and text:
            self._attach_copy_btn(outer, text)

        self._scroll.after(60, lambda: self._scroll._parent_canvas.yview_moveto(1))
        return lbl

    def _attach_copy_btn(self, outer, texto: str):
        ctk.CTkButton(outer, text="⎘", width=26, height=22,
                      fg_color="transparent", hover_color=Colors.CARD_HOVER,
                      text_color=Colors.TEXT_DIM, font=("Segoe UI", 11),
                      corner_radius=4,
                      command=lambda t=texto: self._copiar(t)
                      ).pack(side="left", anchor="s", padx=(2, 0))

    def _copiar(self, texto: str):
        self.clipboard_clear()
        self.clipboard_append(texto.strip())

    def _cargar_historial(self):
        msgs = self._db.get_messages(self._cid)
        for m in msgs:
            self._add_bubble(m["role"], m["content"])
        self._msg_count = len(msgs)

    # ── Enviar ────────────────────────────────────────────────────────────────

    def _enviar(self, _=None):
        if self._streaming:
            return
        texto = self._entry.get().strip()
        if not texto:
            return
        self._entry.delete(0, "end")
        self._btn_send.configure(state="disabled")
        self._streaming = True
        self._full_resp = []

        self._add_bubble("user", texto)
        self._db.save_message(self._cid, "user", texto)

        if self._msg_count == 0:
            titulo = texto[:40]
            self._db.update_titulo(self._cid, titulo)
            if self._on_title_change:
                self._on_title_change(titulo)
        self._msg_count += 1

        self._lbl_status.configure(text="Aria está escribiendo…", text_color=Colors.TEXT_DIM)
        self._resp_label = self._add_bubble("assistant", "")

        self._agent.chat(
            texto,
            on_token=lambda d: self.after(0, lambda dt=d: self._on_token(dt)),
            on_done=lambda f, ok: self.after(0, lambda: self._on_done(f, ok)))

    def _on_token(self, delta: str):
        self._full_resp.append(delta)
        acum = "".join(self._full_resp)
        self._resp_label.configure(text=acum)
        self._scroll._parent_canvas.yview_moveto(1)

    def _on_done(self, full: str, ok: bool):
        self._streaming = False
        self._lbl_status.configure(text="")
        if ok:
            self._db.save_message(self._cid, "assistant", full)
            if self._resp_label:
                self._attach_copy_btn(self._resp_label.master, full)
        else:
            if self._resp_label:
                self._resp_label.configure(text=f"Error: {full}", text_color=Colors.RED)
        self._btn_send.configure(state="normal")

    def _limpiar(self):
        if self._streaming:
            return
        for w in self._scroll.winfo_children():
            w.destroy()
        self._agent.clear_history()
        self._lbl_status.configure(text="")

    # ── Adjuntar documentos para RAG ──────────────────────────────────────────

    def _adjuntar_doc(self):
        if self._streaming:
            return
        rutas = filedialog.askopenfilenames(
            title="Seleccionar documentos para indexar",
            filetypes=[("Documentos", "*.txt *.pdf *.md *.csv"),
                       ("Texto plano", "*.txt *.md *.csv"),
                       ("PDF", "*.pdf")])
        if not rutas:
            return
        threading.Thread(target=self._procesar_docs, args=(rutas,), daemon=True).start()

    def _procesar_docs(self, rutas):
        self.after(0, lambda: self._lbl_status.configure(
            text="Indexando documentos…", text_color=Colors.AMBER))
        for ruta in rutas:
            nombre = os.path.basename(ruta)
            try:
                texto = self._leer_archivo(ruta)
                if texto.strip():
                    self._agent.add_document(texto, nombre, {"fuente": nombre})
                    self.after(0, lambda n=nombre: self._add_bubble(
                        "assistant", f"✓ Documento indexado: {n}\n"
                        "Ahora puedes preguntarme sobre su contenido."))
                else:
                    self.after(0, lambda n=nombre: self._add_bubble(
                        "assistant", f"El archivo {n} está vacío o no pudo leerse."))
            except Exception as e:
                self.after(0, lambda err=str(e), n=nombre: self._add_bubble(
                    "assistant", f"Error al indexar {n}: {err}"))
        self.after(0, lambda: self._lbl_status.configure(text=""))

    def _leer_archivo(self, ruta: str) -> str:
        ext = os.path.splitext(ruta)[1].lower()
        if ext == ".pdf":
            # Intentar con pypdf (incluido en muchos entornos)
            try:
                import pypdf
                reader = pypdf.PdfReader(ruta)
                return "\n".join(p.extract_text() or "" for p in reader.pages)
            except ImportError:
                pass
            # Fallback PyMuPDF
            try:
                import fitz
                doc = fitz.open(ruta)
                return "\n".join(p.get_text() for p in doc)
            except ImportError:
                pass
            return ""
        else:
            with open(ruta, encoding="utf-8", errors="ignore") as f:
                return f.read()

    # ── Exportar conversación ─────────────────────────────────────────────────

    def _exportar_txt(self):
        msgs = self._db.get_messages(self._cid)
        if not msgs:
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            title="Guardar conversación")
        if not ruta:
            return
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(f"DeepCore Agent — Conversación exportada {datetime.now():%Y-%m-%d %H:%M}\n")
            f.write("=" * 60 + "\n\n")
            for m in msgs:
                prefijo = "Tú" if m["role"] == "user" else "Aria"
                f.write(f"[{prefijo}]\n{m['content']}\n\n")
        if abrir_archivo:
            abrir_archivo(ruta)


# ─── Panel de Configuración ───────────────────────────────────────────────────

class ConfigPanel(ctk.CTkFrame):
    def __init__(self, master, agent, db):
        super().__init__(master, fg_color=Colors.BG2, corner_radius=0)
        self._agent = agent
        self._db    = db
        self._build_ui()

    def _build_ui(self):
        Topbar(self, title="Configuración — DeepCore Agent").pack(fill="x")

        scroll = ctk.CTkScrollableFrame(self, fg_color=Colors.BG2, corner_radius=0,
                                         scrollbar_button_color=Colors.BORDER)
        scroll.pack(fill="both", expand=True, padx=Sizes.PAD_LG, pady=Sizes.PAD_LG)

        # ── Tarjeta API Key ──
        card = ctk.CTkFrame(scroll, **Styles.CARD)
        card.pack(fill="x", pady=(0, Sizes.PAD))

        ctk.CTkLabel(card, text="CLAUDE API KEY", font=("Segoe UI", 10, "bold"),
                     text_color=Colors.TEXT_DIM, fg_color="transparent").pack(
            anchor="w", padx=Sizes.PAD, pady=(Sizes.PAD, 4))
        ctk.CTkLabel(card,
                     text="Obtén tu key en console.anthropic.com  •  Se almacena encriptada localmente.",
                     font=Fonts.BODY_SM, text_color=Colors.TEXT_MUTED,
                     fg_color="transparent").pack(anchor="w", padx=Sizes.PAD, pady=(0, 10))

        row_key = ctk.CTkFrame(card, fg_color="transparent")
        row_key.pack(fill="x", padx=Sizes.PAD, pady=(0, 4))
        row_key.columnconfigure(1, weight=1)

        ctk.CTkLabel(row_key, text="API Key:", font=Fonts.BODY,
                     text_color=Colors.TEXT_MUTED, fg_color="transparent",
                     width=70).grid(row=0, column=0, sticky="w")

        self._entry_key = ctk.CTkEntry(row_key, placeholder_text="sk-ant-…", show="•",
                                        **Styles.ENTRY, height=36)
        saved = self._db.get_config("claude_api_key")
        if saved:
            self._entry_key.insert(0, saved)
        self._entry_key.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self._lbl_key_msg = ctk.CTkLabel(card, text="", font=Fonts.BODY_SM,
                                          text_color=Colors.GREEN, fg_color="transparent")
        self._lbl_key_msg.pack()

        ctk.CTkButton(card, text="Guardar API key", command=self._guardar_key,
                      **Styles.BTN_PRIMARY, width=160, height=36).pack(pady=(0, Sizes.PAD))

        # ── Tarjeta modelo ──
        card2 = ctk.CTkFrame(scroll, **Styles.CARD)
        card2.pack(fill="x", pady=(0, Sizes.PAD))

        ctk.CTkLabel(card2, text="MODELO", font=("Segoe UI", 10, "bold"),
                     text_color=Colors.TEXT_DIM, fg_color="transparent").pack(
            anchor="w", padx=Sizes.PAD, pady=(Sizes.PAD, 4))

        row_modelo = ctk.CTkFrame(card2, fg_color="transparent")
        row_modelo.pack(fill="x", padx=Sizes.PAD, pady=(0, Sizes.PAD))

        MODELOS = {
            "Haiku 4.5 (rápido, económico)":  "claude-haiku-4-5-20251001",
            "Sonnet 4.6 (balanceado)":          "claude-sonnet-4-6",
            "Opus 4.8 (máximo razonamiento)":   "claude-opus-4-8",
        }
        modelo_actual = self._db.get_config("modelo") or "claude-haiku-4-5-20251001"
        nombre_actual = next((k for k, v in MODELOS.items() if v == modelo_actual),
                             list(MODELOS.keys())[0])

        self._combo_modelo = ctk.CTkComboBox(row_modelo, values=list(MODELOS.keys()),
                                              font=Fonts.BODY, height=36,
                                              fg_color=Colors.SURFACE,
                                              button_color=Colors.BORDER,
                                              dropdown_fg_color=Colors.CARD,
                                              text_color=Colors.TEXT)
        self._combo_modelo.set(nombre_actual)
        self._combo_modelo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row_modelo, text="Aplicar", command=lambda: self._guardar_modelo(MODELOS),
                      **Styles.BTN_PRIMARY, width=90, height=36).pack(side="left")

        self._lbl_modelo_msg = ctk.CTkLabel(card2, text="", font=Fonts.BODY_SM,
                                             text_color=Colors.GREEN, fg_color="transparent")
        self._lbl_modelo_msg.pack(pady=(0, Sizes.PAD_SM))

        # ── Tarjeta RAG ──
        card3 = ctk.CTkFrame(scroll, **Styles.CARD)
        card3.pack(fill="x", pady=(0, Sizes.PAD))

        ctk.CTkLabel(card3, text="DOCUMENTOS INDEXADOS (RAG)", font=("Segoe UI", 10, "bold"),
                     text_color=Colors.TEXT_DIM, fg_color="transparent").pack(
            anchor="w", padx=Sizes.PAD, pady=(Sizes.PAD, 4))
        ctk.CTkLabel(card3,
                     text="Los documentos indexados se usan como contexto al responder.",
                     font=Fonts.BODY_SM, text_color=Colors.TEXT_MUTED,
                     fg_color="transparent").pack(anchor="w", padx=Sizes.PAD, pady=(0, 8))

        btn_row = ctk.CTkFrame(card3, fg_color="transparent")
        btn_row.pack(fill="x", padx=Sizes.PAD, pady=(0, 8))
        ctk.CTkButton(btn_row, text="+ Añadir documento", command=self._agregar_doc,
                      **Styles.BTN_PRIMARY, height=34).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Limpiar todos", command=self._limpiar_docs,
                      **Styles.BTN_SECONDARY, height=34).pack(side="left")

        self._lbl_docs = ctk.CTkLabel(card3, text="", font=Fonts.BODY_SM,
                                       text_color=Colors.TEXT_MUTED, fg_color="transparent",
                                       justify="left", anchor="w")
        self._lbl_docs.pack(anchor="w", padx=Sizes.PAD, pady=(0, Sizes.PAD))

        self._refresh_docs()

    def _guardar_key(self):
        key = self._entry_key.get().strip()
        if not key:
            self._lbl_key_msg.configure(text="Ingresa la API key.", text_color=Colors.RED)
            return
        self._db.set_config("claude_api_key", key)
        try:
            self._agent.set_api_key(key)
            self._lbl_key_msg.configure(text="✓ API key configurada.", text_color=Colors.GREEN)
        except Exception as e:
            self._lbl_key_msg.configure(text=str(e), text_color=Colors.RED)

    def _guardar_modelo(self, modelos: dict):
        nombre = self._combo_modelo.get()
        model_id = modelos.get(nombre, "claude-haiku-4-5-20251001")
        self._db.set_config("modelo", model_id)
        self._agent.set_model(model_id)
        self._lbl_modelo_msg.configure(text=f"✓ Modelo: {model_id}", text_color=Colors.GREEN)

    def _refresh_docs(self):
        docs = self._agent.list_docs()
        if docs:
            texto = "\n".join(f"• {d}" for d in docs)
        else:
            texto = "No hay documentos indexados."
        self._lbl_docs.configure(text=texto)

    def _agregar_doc(self):
        rutas = filedialog.askopenfilenames(
            title="Seleccionar documentos",
            filetypes=[("Documentos", "*.txt *.pdf *.md *.csv")])
        if not rutas:
            return
        threading.Thread(target=self._indexar_docs, args=(rutas,), daemon=True).start()

    def _indexar_docs(self, rutas):
        for ruta in rutas:
            nombre = os.path.basename(ruta)
            try:
                ext = os.path.splitext(ruta)[1].lower()
                if ext == ".pdf":
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(ruta)
                        texto = "\n".join(p.extract_text() or "" for p in reader.pages)
                    except ImportError:
                        texto = ""
                else:
                    with open(ruta, encoding="utf-8", errors="ignore") as f:
                        texto = f.read()
                if texto.strip():
                    self._agent.add_document(texto, nombre, {"fuente": nombre})
            except Exception:
                pass
        self.after(0, self._refresh_docs)

    def _limpiar_docs(self):
        for doc_id in self._agent.list_docs():
            self._agent.delete_doc(doc_id)
        self._refresh_docs()
