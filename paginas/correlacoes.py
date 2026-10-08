import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import seaborn as sns
import streamlit as st

from utils import app_comum, dados, estilo
from utils.dados import ROTULOS
from utils.dados import formatar_num as fmt

df, base, f = app_comum.obter_contexto()
pal = estilo.paleta()  # cores do tema ativo (claro/escuro)
estilo.aplicar_estilo_mpl(pal)

st.title("Correlações e distribuições")
st.markdown("O clima explica o consumo? O nível de alerta reflete os reservatórios? Aqui as relações entre as "
            "variáveis são medidas estatisticamente.")
st.caption(app_comum.descrever_filtros(f, base))
if app_comum.aviso_vazio(df) or len(df) < 10:
    st.stop()

VARS = ["consumo_milhoes_litros", "desperdicio_percentual", "reservatorios_percentual", "chuva_mm",
        "temperatura_media", "populacao", "consumo_per_capita", "score_alerta"]


def p_valor(r: float, n: int) -> float:
    """p-valor bicaudal do teste t para correlação (aproximação normal, adequada para n grande)."""
    if n < 3 or abs(r) >= 1:
        return 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    return math.erfc(abs(t) / math.sqrt(2))


# ---------------------------------------------------------------- matriz de correlação
c1, c2 = st.columns([1, 3])
with c1:
    metodo = st.radio("Método", ["Pearson", "Spearman"], horizontal=True, key="corr_metodo",
                      help="Pearson mede relação linear. Spearman mede relação monotônica (baseada em postos).")
    selecionadas = st.multiselect("Variáveis", VARS, default=VARS, format_func=lambda c: ROTULOS.get(c, c),
                                  key="corr_vars")
    n = len(df)
    limite = 1.96 / math.sqrt(n)
    st.metric("Registros (n)", fmt(n, 0), border=True)
    st.metric("|r| mínimo para significância (5%)", fmt(limite, 3), border=True,
              help="Com n observações, |r| > 1,96/√n é estatisticamente diferente de zero a 5%.")

if len(selecionadas) < 2:
    c2.info("Selecione pelo menos duas variáveis.")
    st.stop()

corr = df[selecionadas].astype(float).corr(method=metodo.lower())
rotulos = [ROTULOS.get(c, c) for c in selecionadas]
with c2:
    fig, ax = plt.subplots(figsize=(9, 6.5))
    mascara = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(corr, mask=mascara, cmap=pal.CMAP_DIV, vmin=-1, vmax=1, center=0, annot=True, fmt=".2f",
                linewidths=2, linecolor=pal.SUPERFICIE, square=True, xticklabels=rotulos, yticklabels=rotulos,
                cbar_kws={"label": f"Correlação de {metodo}", "shrink": 0.75}, annot_kws={"size": 9}, ax=ax)
    ax.set_title(f"Matriz de correlação ({metodo})")
    ax.tick_params(axis="x", rotation=40)
    plt.setp(ax.get_xticklabels(), ha="right")
    st.pyplot(fig, width="stretch")
    estilo.fechar(fig)

pares = (corr.where(np.tril(np.ones_like(corr, dtype=bool), k=-1)).stack().dropna()
             .rename("r").reset_index().rename(columns={"level_0": "var_a", "level_1": "var_b"}))
pares["abs_r"] = pares["r"].abs()
pares["p_valor"] = pares["r"].map(lambda r: p_valor(r, n))
pares["significativa"] = pares["p_valor"] < 0.05
pares["var_a"] = pares["var_a"].map(lambda c: ROTULOS.get(c, c))
pares["var_b"] = pares["var_b"].map(lambda c: ROTULOS.get(c, c))
pares = pares.sort_values("abs_r", ascending=False)

st.markdown("##### Pares ordenados pela força da relação")
st.dataframe(pares.drop(columns="abs_r").head(10), hide_index=True, width="stretch", column_config={
    "var_a": "Variável A", "var_b": "Variável B",
    "r": st.column_config.NumberColumn("r", format="%+.3f"),
    "p_valor": st.column_config.NumberColumn("p-valor", format="%.3f"),
    "significativa": st.column_config.CheckboxColumn("Significativa (5%)"),
})

mais_forte = pares.iloc[0]
n_sig = int(pares["significativa"].sum())
app_comum.interpretacao(f"""
- A correlação mais forte do recorte é entre **{mais_forte['var_a']}** e **{mais_forte['var_b']}**, com
  r = {mais_forte['r']:+.3f}. Isso equivale a **{fmt(mais_forte['r'] ** 2 * 100, 2, '%')}** de variância explicada (r²):
  uma relação **desprezível**.
- Dos {len(pares)} pares testados, **{n_sig}** passam do limiar de significância de 5%. Com tantos testes, cerca de
  {len(pares) * 0.05:.1f} "falsos positivos" já seriam esperados por acaso.
- Conclusão: as variáveis são **praticamente independentes**. Chuva não eleva os reservatórios, temperatura não aumenta
  o consumo e o score de alerta não acompanha o nível dos reservatórios. No mundo real essas relações existem, o que reforça
  que a base foi **gerada aleatoriamente, variável a variável**.
""")

# ---------------------------------------------------------------- dispersão
st.divider()
st.subheader("Dispersão entre duas variáveis")
d1, d2, d3 = st.columns(3)
x = d1.selectbox("Eixo X", VARS, index=VARS.index("chuva_mm"), format_func=lambda c: ROTULOS.get(c, c), key="disp_x")
y = d2.selectbox("Eixo Y", VARS, index=VARS.index("reservatorios_percentual"),
                 format_func=lambda c: ROTULOS.get(c, c), key="disp_y")
amostra = d3.slider("Pontos exibidos", 200, min(4000, len(df)), min(1500, len(df)), step=100, key="disp_n",
                    help="Amostra aleatória para manter o gráfico legível. A reta usa todos os pontos.")

pts = df.sample(min(amostra, len(df)), random_state=42)
coef = np.polyfit(df[x].astype(float), df[y].astype(float), 1)
r_xy = df[x].astype(float).corr(df[y].astype(float))
xs = np.linspace(df[x].min(), df[x].max(), 50)
fig = go.Figure()
fig.add_scatter(x=pts[x], y=pts[y], mode="markers", name="Registros",
                marker=dict(color=pal.PRIMARIA, size=8, opacity=0.35, line=dict(color=pal.SUPERFICIE, width=1)),
                customdata=np.stack([pts["uf"], pts["ano_mes"]], axis=1),
                hovertemplate="%{customdata[0]} · %{customdata[1]}<br>X: %{x:,.2f}<br>Y: %{y:,.2f}<extra></extra>")
fig.add_scatter(x=xs, y=np.polyval(coef, xs), mode="lines", name=f"Regressão linear (r = {r_xy:+.3f})",
                line=dict(color=pal.CATEGORICA[1], width=2.5), hoverinfo="skip")
fig.update_layout(xaxis_title=ROTULOS.get(x, x), yaxis_title=ROTULOS.get(y, y))
st.plotly_chart(estilo.estilizar_plotly(fig, 440), width="stretch")
st.caption(f"Reta: y = {coef[0]:+.4f}·x {coef[1]:+.2f}  ·  r² = {r_xy ** 2:.4f}  ·  "
           f"p-valor = {p_valor(r_xy, n):.3f}")

# ---------------------------------------------------------------- alerta × reservatório
st.divider()
st.subheader("O nível de alerta reflete os reservatórios?")
b1, b2 = st.columns([3, 2])
with b1:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ordem = [a for a in dados.ORDEM_ALERTA if a in set(df["nivel_alerta"])]
    sns.boxplot(data=df, x="nivel_alerta", y="reservatorios_percentual", order=ordem, hue="nivel_alerta",
                hue_order=ordem, palette=pal.CORES_ALERTA, legend=False, width=0.55, linewidth=1.2,
                fliersize=3, ax=ax)
    ax.axhline(30, color=pal.CORES_ALERTA["Crítico"], linewidth=1)
    ax.text(1.01, 30, "30%\ncrítico", transform=ax.get_yaxis_transform(), va="center", fontsize=8,
            color=pal.TINTA_SEC)
    ax.set_xlabel("Nível de alerta informado")
    ax.set_ylabel("Reservatórios (%)")
    ax.set_title("Distribuição do nível dos reservatórios por nível de alerta")
    st.pyplot(fig, width="stretch")
    estilo.fechar(fig)
with b2:
    cruz = pd.crosstab(df["nivel_alerta"], df["faixa_reservatorio"], normalize="index") * 100
    st.markdown("**% dos registros por faixa de reservatório**")
    st.dataframe(cruz.style.format("{:.0f}%").background_gradient(cmap=pal.CMAP_SEQ, axis=None),
                 width="stretch")
    st.caption("Cada linha soma 100%. Se o alerta fosse coerente, a linha *Crítico* se concentraria na coluna "
               "*Crítico (<30%)*.")

medias = df.groupby("nivel_alerta", observed=True)["reservatorios_percentual"].median()
app_comum.interpretacao(f"""
- A mediana do reservatório é **praticamente a mesma** em todos os níveis de alerta
  ({', '.join(f'{k}: {fmt(v, 0)}%' for k, v in medias.items())}).
- Em todos os níveis aparecem registros com reservatório quase cheio e quase vazio. O **alerta não é derivado do
  nível dos reservatórios**. Na prática, um indicador assim **perderia a credibilidade**. A recomendação é
  recalcular o alerta a partir de regras objetivas, como o atributo `faixa_reservatorio` criado na engenharia de atributos.
""")

# ---------------------------------------------------------------- distribuição
st.divider()
st.subheader("Distribuição de uma variável")
v = st.selectbox("Variável", VARS[:-1], format_func=lambda c: ROTULOS.get(c, c), key="dist_var")
h1, h2 = st.columns([3, 2])
with h1:
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.histplot(df[v], bins=40, kde=True, color=pal.PRIMARIA, edgecolor=pal.SUPERFICIE, linewidth=1.5, ax=ax)
    ax.axvline(df[v].mean(), color=pal.CATEGORICA[1], linewidth=1.5, label=f"média = {fmt(df[v].mean(), 1)}")
    ax.axvline(df[v].median(), color=pal.TINTA, linewidth=1.5, label=f"mediana = {fmt(df[v].median(), 1)}")
    ax.legend()
    ax.set_xlabel(ROTULOS.get(v, v))
    ax.set_ylabel("Frequência")
    ax.set_title(f"Histograma — {ROTULOS.get(v, v)}")
    st.pyplot(fig, width="stretch")
    estilo.fechar(fig)
with h2:
    desc = df[v].describe().rename({"count": "n", "mean": "média", "std": "desvio-padrão", "min": "mínimo",
                                    "25%": "1º quartil", "50%": "mediana", "75%": "3º quartil", "max": "máximo"})
    desc["assimetria"] = df[v].skew()
    desc["curtose"] = df[v].kurt()
    st.dataframe(desc.rename("valor").to_frame().style.format("{:,.2f}"), width="stretch")
    st.caption("Assimetria perto de 0 e curtose perto de −1,2 indicam distribuição **uniforme** (consumo, "
               "desperdício, reservatórios, per capita). A chuva tem cauda à direita (assimetria positiva) e a "
               "temperatura é aproximadamente **normal** (curtose perto de 0).")
