"""Aplicação desktop (tkinter) que consome a API Flask do backend via HTTP.

Execução:
    python app_desktop.py                      # usa http://localhost:8000
    API_URL=http://servidor:8000 python app_desktop.py

Compilação (executável único):
    pip install pyinstaller
    pyinstaller --onefile --windowed --name ServidoresFederais app_desktop.py
    # o executável fica em dist/
"""
import json
import os
import threading
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from tkinter import messagebox, ttk

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
UFS = ["", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
       "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]


def chamar_api(caminho: str, params: dict | None = None) -> dict:
    """GET na API; levanta RuntimeError com a mensagem de erro da API."""
    url = f"{API_URL}/api{caminho}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            corpo = json.loads(e.read().decode("utf-8"))
            msg = corpo.get("erro", f"Erro HTTP {e.code}")
            dica = (corpo.get("detalhes") or {}).get("dica")
            raise RuntimeError(f"{msg}\n{dica}" if dica else msg) from None
        except ValueError:
            raise RuntimeError(f"Erro HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Não foi possível conectar à API em {API_URL}.\n{e.reason}") from None


def titulo(s):
    return " ".join(p.capitalize() for p in str(s or "").lower().split())


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Servidores do Executivo Federal")
        self.geometry("1100x680")
        self.minsize(900, 560)
        self.page = 1
        self.total_paginas = 1
        self.filtros: dict = {}
        self._montar()
        self.after(100, self._status)

    # ---------------------------------------------------------------- layout
    def _montar(self):
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 16, "bold"))
        estilo.configure("Treeview", rowheight=26)

        topo = ttk.Frame(self, padding=(14, 12))
        topo.pack(fill="x")
        ttk.Label(topo, text="Servidores do Executivo Federal", style="Titulo.TLabel").pack(side="left")
        self.lbl_status = ttk.Label(topo, text="conectando…", foreground="#b45309")
        self.lbl_status.pack(side="right")

        f = ttk.LabelFrame(self, text="Busca", padding=12)
        f.pack(fill="x", padx=14)

        self.modo = tk.StringVar(value="exata")
        ttk.Radiobutton(f, text="Nome exato", variable=self.modo, value="exata").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(f, text="Nome similar (use %)", variable=self.modo, value="similar").grid(row=0, column=1, sticky="w")

        self.e_nome = self._campo(f, "Nome", 1, 0, largura=42)
        self.e_limit = self._campo(f, "Limite (similar)", 1, 2, largura=8)
        self.e_limit.insert(0, "100")
        self.e_cargo = self._campo(f, "Cargo / profissão", 2, 0, largura=42)
        ttk.Label(f, text="UF").grid(row=2, column=2, sticky="w", padx=(12, 4))
        self.c_uf = ttk.Combobox(f, values=UFS, width=6, state="readonly")
        self.c_uf.grid(row=2, column=3, sticky="w")
        self.e_orgao = self._campo(f, "Instituição / órgão", 3, 0, largura=42)
        ttk.Label(f, text="Situação").grid(row=3, column=2, sticky="w", padx=(12, 4))
        self.c_sit = ttk.Combobox(f, values=["", "ATIVO", "APOSENTADO"], width=12, state="readonly")
        self.c_sit.grid(row=3, column=3, sticky="w")

        botoes = ttk.Frame(f)
        botoes.grid(row=4, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self.b_buscar = ttk.Button(botoes, text="Buscar", command=self.buscar)
        self.b_buscar.pack(side="left")
        ttk.Button(botoes, text="Limpar", command=self.limpar).pack(side="left", padx=6)
        self.bind("<Return>", lambda _e: self.buscar())

        # resultados
        r = ttk.Frame(self, padding=(14, 10))
        r.pack(fill="both", expand=True)
        cols = ("nome", "cargo", "orgao", "uf", "situacao", "valor")
        self.tv = ttk.Treeview(r, columns=cols, show="headings", selectmode="browse")
        for c, t, w, anc in (("nome", "Nome", 280, "w"), ("cargo", "Cargo", 220, "w"), ("orgao", "Órgão", 260, "w"),
                             ("uf", "UF", 50, "center"), ("situacao", "Situação", 100, "center"), ("valor", "Valor (R$)", 110, "e")):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor=anc, stretch=(c in ("nome", "cargo", "orgao")))
        sb = ttk.Scrollbar(r, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", self.detalhes)
        self._ids: dict[str, int] = {}

        pg = ttk.Frame(self, padding=(14, 0, 14, 12))
        pg.pack(fill="x")
        self.b_ant = ttk.Button(pg, text="‹ Anterior", command=lambda: self.ir(self.page - 1), state="disabled")
        self.b_ant.pack(side="left")
        self.lbl_pg = ttk.Label(pg, text="")
        self.lbl_pg.pack(side="left", padx=12)
        self.b_prox = ttk.Button(pg, text="Próxima ›", command=lambda: self.ir(self.page + 1), state="disabled")
        self.b_prox.pack(side="left")
        self.lbl_resumo = ttk.Label(pg, text="", foreground="#555")
        self.lbl_resumo.pack(side="right")
        ttk.Label(pg, text="Duplo clique em uma linha para ver os detalhes", foreground="#888").pack(side="right", padx=12)

    def _campo(self, pai, rotulo, linha, col, largura=30):
        ttk.Label(pai, text=rotulo).grid(row=linha, column=col, sticky="w", pady=3)
        e = ttk.Entry(pai, width=largura)
        e.grid(row=linha, column=col + 1, sticky="w", padx=(6, 0))
        return e

    # ---------------------------------------------------------------- ações
    def _status(self):
        def tarefa():
            try:
                h = chamar_api("/health")
                self.after(0, lambda: self.lbl_status.config(text=f"API online · {h['total_servidores']:,} registros".replace(",", "."), foreground="#047857"))
            except RuntimeError:
                self.after(0, lambda: self.lbl_status.config(text="API indisponível", foreground="#b91c1c"))
        threading.Thread(target=tarefa, daemon=True).start()

    def limpar(self):
        for e in (self.e_nome, self.e_cargo, self.e_orgao):
            e.delete(0, "end")
        self.c_uf.set("")
        self.c_sit.set("")
        self.tv.delete(*self.tv.get_children())
        self.lbl_pg.config(text="")
        self.lbl_resumo.config(text="")

    def buscar(self):
        f = {
            "cargo": self.e_cargo.get().strip(), "uf": self.c_uf.get(), "orgao": self.e_orgao.get().strip(),
            "situacao": self.c_sit.get(), "per_page": 50,
        }
        nome = self.e_nome.get().strip()
        if self.modo.get() == "similar":
            f["similar"], f["limit"] = nome, self.e_limit.get().strip() or "100"
        else:
            f["nome"] = nome
        if not any(f.get(k) for k in ("nome", "similar", "cargo", "uf", "orgao", "situacao")):
            messagebox.showwarning("Busca", "Informe pelo menos um critério de busca.")
            return
        self.filtros, self.page = f, 1
        self._executar()

    def ir(self, p):
        if 1 <= p <= self.total_paginas:
            self.page = p
            self._executar()

    def _executar(self):
        self.b_buscar.config(state="disabled")
        params = {**self.filtros, "page": self.page}

        def tarefa():
            try:
                d = chamar_api("/servidores", params)
                self.after(0, lambda: self._render(d))
            except RuntimeError as e:
                # Guarda a mensagem antes: a variável `e` deixa de existir ao sair
                # do except, e a lambda só roda depois, na thread da interface.
                msg = str(e)
                self.after(0, lambda: self._erro_busca(msg))
        threading.Thread(target=tarefa, daemon=True).start()

    def _erro_busca(self, msg):
        self.b_buscar.config(state="normal")
        messagebox.showerror("Busca", msg)

    def _render(self, d):
        self.b_buscar.config(state="normal")
        self.tv.delete(*self.tv.get_children())
        self._ids.clear()
        for s in d["itens"]:
            valor = f"{s['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if s.get("valor") is not None else "—"
            iid = self.tv.insert("", "end", values=(titulo(s["nome"]), titulo(s.get("cargo")), titulo(s.get("orgao")),
                                                   s.get("uf") or "—", titulo(s["situacao"]), valor))
            self._ids[iid] = s["id"]
        self.total_paginas = d["total_paginas"]
        self.lbl_pg.config(text=f"Página {d['page']} de {d['total_paginas']}")
        self.lbl_resumo.config(text=f"{d['total']:,} registro(s)".replace(",", "."))
        self.b_ant.config(state="normal" if d["page"] > 1 else "disabled")
        self.b_prox.config(state="normal" if d["page"] < d["total_paginas"] else "disabled")
        if d.get("registro_unico"):
            self._mostrar_detalhes(d["itens"][0])

    def detalhes(self, _ev=None):
        sel = self.tv.selection()
        if not sel:
            return
        id_servidor = self._ids[sel[0]]

        def tarefa():  # em thread, para a janela não travar enquanto a API responde
            try:
                s = chamar_api(f"/servidores/{id_servidor}")
                self.after(0, lambda: self._mostrar_detalhes(s))
            except RuntimeError as e:
                msg = str(e)
                self.after(0, lambda: messagebox.showerror("Detalhes", msg))
        threading.Thread(target=tarefa, daemon=True).start()

    def _mostrar_detalhes(self, s):
        win = tk.Toplevel(self)
        win.title(titulo(s["nome"]))
        win.geometry("560x520")
        txt = tk.Text(win, wrap="word", padx=12, pady=10, font=("Segoe UI", 10))
        txt.pack(fill="both", expand=True)
        rotulos = [("Nome", "nome"), ("CPF", "cpf"), ("Matrícula", "matricula"), ("Situação", "situacao"),
                   ("Cargo", "cargo"), ("Órgão", "orgao"), ("Sigla do órgão", "orgao_sigla"), ("UF", "uf"),
                   ("Código da carreira", "codigo_carreira"), ("Classe", "classe"), ("Padrão", "padrao"),
                   ("Referência", "referencia"), ("Nível", "nivel"), ("Tipo de aposentadoria", "tipo_aposentadoria"),
                   ("Fundamento legal", "fundamento_legal"), ("Diploma legal", "diploma_legal"),
                   ("Data da inatividade", "data_inatividade"), ("Ingresso", "ocorrencia_ingresso"),
                   ("Data de ingresso", "data_ingresso"), ("Valor (R$)", "valor"), ("Mês de referência", "mes_referencia")]
        for rot, k in rotulos:
            if s.get(k) not in (None, ""):
                txt.insert("end", f"{rot}: ", ("b",))
                txt.insert("end", f"{s[k]}\n")
        txt.tag_configure("b", font=("Segoe UI", 10, "bold"))
        txt.config(state="disabled")


if __name__ == "__main__":
    App().mainloop()
