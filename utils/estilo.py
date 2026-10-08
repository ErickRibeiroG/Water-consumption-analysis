"""Identidade visual compartilhada por Matplotlib/Seaborn e Plotly."""

import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

# Tinta e superfícies
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_SEC = "#52514e"
TINTA_MUTED = "#898781"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"

# Paleta categórica (ordem fixa, validada para daltonismo nos pares adjacentes).
CATEGORICA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
PRIMARIA = CATEGORICA[0]

# A cor segue a entidade: cada região tem sempre a mesma cor.
CORES_REGIAO = dict(zip(["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"], CATEGORICA))

# Status (reservado para o nível de alerta; sempre acompanhado de rótulo).
CORES_ALERTA = {"Baixo": "#0ca30c", "Médio": "#fab219", "Alto": "#ec835a", "Crítico": "#d03b3b"}

# Sequencial (azul, claro → escuro) e divergente (vermelho ↔ cinza ↔ azul).
SEQUENCIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGENTE = ["#b02a2a", "#d03b3b", "#e88a8a", "#f0efec", "#86b6ef", "#2a78d6", "#184f95"]
CMAP_SEQ = LinearSegmentedColormap.from_list("agua_seq", SEQUENCIAL)
CMAP_DIV = LinearSegmentedColormap.from_list("agua_div", DIVERGENTE)
ESCALA_SEQ_PLOTLY = [[i / (len(SEQUENCIAL) - 1), c] for i, c in enumerate(SEQUENCIAL)]

FONTE = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"


def aplicar_estilo_mpl():
    """Tema do Seaborn/Matplotlib: grade discreta, eixos leves, sem bordas superiores."""
    sns.set_theme(style="whitegrid", palette=CATEGORICA, rc={
        "figure.facecolor": SUPERFICIE,
        "axes.facecolor": SUPERFICIE,
        "axes.edgecolor": EIXO,
        "axes.labelcolor": TINTA_SEC,
        "axes.titlecolor": TINTA,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRADE,
        "grid.linewidth": 0.8,
        "xtick.color": TINTA_MUTED,
        "ytick.color": TINTA_MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "lines.linewidth": 2,
        "font.family": "sans-serif",
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.facecolor": SUPERFICIE,
    })
    mpl.rcParams["axes.formatter.use_locale"] = False


def fmt_milhar(x, _pos=None):
    """Formatador de eixo no padrão brasileiro."""
    return f"{x:,.0f}".replace(",", ".")


def estilizar_plotly(fig, altura=380, legenda=True, titulo=None):
    """Aplica layout padrão a uma figura Plotly."""
    fig.update_layout(
        height=altura,
        template="plotly_white",
        font=dict(family=FONTE, color=TINTA_SEC, size=12),
        title=dict(text=titulo, font=dict(size=15, color=TINTA), x=0, xanchor="left",
                   y=1, yref="container", yanchor="top", pad=dict(t=12)) if titulo else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=CATEGORICA,
        # Espaço no topo para título e legenda não se sobreporem.
        margin=dict(l=10, r=10, t=(45 if titulo else 0) + (35 if legenda else 15), b=10),
        hoverlabel=dict(bgcolor="white", font=dict(family=FONTE, color=TINTA)),
        showlegend=legenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        bargap=0.25,
        separators=",.",  # padrão brasileiro: vírgula decimal, ponto de milhar
    )
    fig.update_xaxes(showgrid=False, linecolor=EIXO, tickfont=dict(color=TINTA_MUTED), title_font=dict(color=TINTA_SEC))
    fig.update_yaxes(gridcolor=GRADE, zeroline=False, linecolor=EIXO, tickfont=dict(color=TINTA_MUTED),
                     title_font=dict(color=TINTA_SEC))
    return fig


def fechar(fig):
    """Fecha a figura Matplotlib após exibi-la (evita vazamento de memória no Streamlit)."""
    plt.close(fig)
