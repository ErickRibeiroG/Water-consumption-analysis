"""Identidade visual compartilhada por Matplotlib/Seaborn e Plotly, com tema claro e escuro.

- No dashboard, `paleta()` escolhe o tema ativo do Streamlit (`st.context.theme.type`).
- No notebook, o tema vem da variável de ambiente TEMA_GRAFICOS ("light" por padrão), o que
  permite exportar as imagens nas duas versões (imagens/ e imagens/dark/).
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]

# Status (reservado para o nível de alerta; sempre acompanhado de rótulo). Igual nos dois temas.
CORES_ALERTA = {"Baixo": "#0ca30c", "Médio": "#fab219", "Alto": "#ec835a", "Crítico": "#d03b3b"}

# Cada tema tem seus próprios tons, validados contra a sua superfície (não é uma simples inversão).
_TEMAS = {
    "light": dict(
        SUPERFICIE="#fcfcfb", TINTA="#0b0b0b", TINTA_SEC="#52514e", TINTA_MUTED="#898781",
        GRADE="#e1e0d9", EIXO="#c3c2b7", SEM_DADOS="#ecebe7",
        CATEGORICA=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
        # Sequencial: claro (pouco) → escuro (muito).
        SEQUENCIAL=["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
        # Divergente: vermelho ↔ cinza neutro ↔ azul.
        DIVERGENTE=["#b02a2a", "#d03b3b", "#e88a8a", "#f0efec", "#86b6ef", "#2a78d6", "#184f95"],
    ),
    "dark": dict(
        SUPERFICIE="#1a1a19", TINTA="#ffffff", TINTA_SEC="#c3c2b7", TINTA_MUTED="#898781",
        GRADE="#2c2c2a", EIXO="#383835", SEM_DADOS="#2c2c2a",
        CATEGORICA=["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
        # No escuro, "pouco" se funde com a superfície (escuro) e "muito" se destaca (claro).
        SEQUENCIAL=["#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"],
        DIVERGENTE=["#f08a8a", "#d03b3b", "#6e2f2e", "#383835", "#1c4a80", "#3987e5", "#9ec5f4"],
    ),
}

FONTE = "Comfortaa, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
PASTA_FONTES = Path(__file__).resolve().parent.parent / "fontes"


def montar_paleta(modo: str = "light") -> SimpleNamespace:
    """Paleta completa de um tema ("light" ou "dark")."""
    base = _TEMAS["dark" if modo == "dark" else "light"]
    p = SimpleNamespace(MODO=modo, CORES_ALERTA=CORES_ALERTA, FONTE=FONTE, **base)
    p.PRIMARIA = p.CATEGORICA[0]
    # A cor segue a entidade: cada região tem sempre a mesma cor.
    p.CORES_REGIAO = dict(zip(REGIOES, p.CATEGORICA))
    p.CMAP_SEQ = LinearSegmentedColormap.from_list(f"agua_seq_{modo}", p.SEQUENCIAL)
    p.CMAP_DIV = LinearSegmentedColormap.from_list(f"agua_div_{modo}", p.DIVERGENTE)
    p.ESCALA_SEQ_PLOTLY = [[i / (len(p.SEQUENCIAL) - 1), c] for i, c in enumerate(p.SEQUENCIAL)]
    return p


def modo_atual() -> str:
    """Tema ativo: o do Streamlit, se houver sessão; senão, TEMA_GRAFICOS (padrão "light")."""
    if "streamlit" in sys.modules:
        try:
            import streamlit as st
            from streamlit.runtime.scriptrunner import get_script_run_ctx

            if get_script_run_ctx(suppress_warning=True) is not None:
                tipo = st.context.theme.type
                if tipo in ("light", "dark"):
                    return tipo
        except Exception:  # noqa: BLE001 — API indisponível: cai no padrão
            pass
    return "dark" if os.environ.get("TEMA_GRAFICOS", "light").lower() == "dark" else "light"


def paleta() -> SimpleNamespace:
    return montar_paleta(modo_atual())


# Constantes de módulo (usadas pelo notebook): seguem TEMA_GRAFICOS.
_PADRAO = montar_paleta(modo_atual())
MODO = _PADRAO.MODO
SUPERFICIE, TINTA, TINTA_SEC, TINTA_MUTED = _PADRAO.SUPERFICIE, _PADRAO.TINTA, _PADRAO.TINTA_SEC, _PADRAO.TINTA_MUTED
GRADE, EIXO = _PADRAO.GRADE, _PADRAO.EIXO
CATEGORICA, PRIMARIA, CORES_REGIAO = _PADRAO.CATEGORICA, _PADRAO.PRIMARIA, _PADRAO.CORES_REGIAO
CMAP_SEQ, CMAP_DIV, ESCALA_SEQ_PLOTLY = _PADRAO.CMAP_SEQ, _PADRAO.CMAP_DIV, _PADRAO.ESCALA_SEQ_PLOTLY


def registrar_fontes() -> str:
    """Registra os .ttf da Comfortaa no Matplotlib. Retorna a família a usar (com fallback)."""
    arquivos = sorted(PASTA_FONTES.glob("Comfortaa-*.ttf"))
    for arquivo in arquivos:
        font_manager.fontManager.addfont(str(arquivo))
    return "Comfortaa" if arquivos else "sans-serif"


def aplicar_estilo_mpl(p: SimpleNamespace | None = None):
    """Tema do Seaborn/Matplotlib: grade discreta, eixos leves, sem bordas superiores."""
    p = p or _PADRAO
    familia = registrar_fontes()
    sns.set_theme(font=familia, style="darkgrid" if p.MODO == "dark" else "whitegrid", palette=p.CATEGORICA, rc={
        "figure.facecolor": p.SUPERFICIE,
        "axes.facecolor": p.SUPERFICIE,
        "axes.edgecolor": p.EIXO,
        "axes.labelcolor": p.TINTA_SEC,
        "axes.titlecolor": p.TINTA,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": p.GRADE,
        "grid.linewidth": 0.8,
        "text.color": p.TINTA_SEC,
        "xtick.color": p.TINTA_MUTED,
        "ytick.color": p.TINTA_MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "legend.labelcolor": p.TINTA_SEC,
        "lines.linewidth": 2,
        "patch.edgecolor": p.SUPERFICIE,
        "boxplot.boxprops.color": p.TINTA_SEC,
        "boxplot.whiskerprops.color": p.TINTA_SEC,
        "boxplot.capprops.color": p.TINTA_SEC,
        "boxplot.medianprops.color": p.TINTA,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.facecolor": p.SUPERFICIE,
    })
    mpl.rcParams["axes.formatter.use_locale"] = False


def fmt_milhar(x, _pos=None):
    """Formatador de eixo no padrão brasileiro."""
    return f"{x:,.0f}".replace(",", ".")


def estilizar_plotly(fig, altura=380, legenda=True, titulo=None):
    """Layout padrão Plotly.

    Cores de texto, grade, eixos e tooltip ficam a cargo do tema do Streamlit, que as adapta no
    navegador na hora em que o usuário troca entre claro e escuro.
    """
    fig.update_layout(
        height=altura,
        font=dict(family=FONTE, size=12),
        title=dict(text=titulo, font=dict(size=15), x=0, xanchor="left",
                   y=1, yref="container", yanchor="top", pad=dict(t=12)) if titulo else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=paleta().CATEGORICA,
        # Espaço no topo para título e legenda não se sobreporem.
        margin=dict(l=10, r=10, t=(45 if titulo else 0) + (35 if legenda else 15), b=10),
        hoverlabel=dict(font=dict(family=FONTE)),
        showlegend=legenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        bargap=0.25,
        separators=",.",  # padrão brasileiro: vírgula decimal, ponto de milhar
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(zeroline=False)
    return fig


def fechar(fig):
    """Fecha a figura Matplotlib após exibi-la (evita vazamento de memória no Streamlit)."""
    plt.close(fig)
