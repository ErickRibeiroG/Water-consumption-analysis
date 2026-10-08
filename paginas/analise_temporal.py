import matplotlib.pyplot as plt
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import streamlit as st

from utils import app_comum, dados, estilo
from utils.dados import formatar_num as fmt

df, base, f = app_comum.obter_contexto()
estilo.aplicar_estilo_mpl()
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

st.title("Análise temporal")
st.markdown("Evolução mensal, tendência, variação anual e sazonalidade do consumo e das variáveis climáticas.")
st.caption(app_comum.descrever_filtros(f, base))
if app_comum.aviso_vazio(df):
    st.stop()

m = dados.serie_mensal(df)

tab1, tab2, tab3 = st.tabs([":material/show_chart: Série e tendência", ":material/calendar_month: Sazonalidade",
                            ":material/compare_arrows: Comparação regional"])

# ---------------------------------------------------------------- série e tendência
with tab1:
    fig = go.Figure()
    fig.add_scatter(x=m.index, y=m["consumo"], name="Consumo mensal", mode="lines",
                    line=dict(color="#9ec5f4", width=1.5),
                    hovertemplate="%{x|%b/%Y}: %{y:,.1f} mi L<extra></extra>")
    fig.add_scatter(x=m.index, y=m["consumo_mm12"], name="Média móvel 12 meses", mode="lines",
                    line=dict(color=estilo.PRIMARIA, width=2.5),
                    hovertemplate="%{x|%b/%Y}: %{y:,.1f} mi L<extra></extra>")
    if "consumo_tendencia" in m:
        fig.add_scatter(x=m.index, y=m["consumo_tendencia"], name="Tendência linear", mode="lines",
                        line=dict(color=estilo.TINTA_SEC, width=1.5, dash="dash"),
                        hovertemplate="%{x|%b/%Y}: %{y:,.1f} mi L<extra></extra>")
    fig.update_layout(hovermode="x unified", yaxis_title="Consumo (milhões de litros)")
    st.plotly_chart(estilo.estilizar_plotly(fig, 400, titulo="Consumo mensal, média móvel e tendência"),
                    width="stretch")

    anual = (df.groupby("ano").agg(consumo=("consumo_milhoes_litros", "sum"),
                                   desperdicio=("volume_desperdicado_ml", "sum")).reset_index())
    anual["var"] = anual["consumo"].pct_change() * 100
    c1, c2 = st.columns([3, 2])
    fig = px.bar(anual, x="ano", y="consumo", labels={"ano": "", "consumo": "Consumo (mi L)"},
                 text=anual["var"].map(lambda v: "" if np.isnan(v) else f"{v:+.1f}%"))
    fig.update_traces(marker_color=estilo.PRIMARIA, textposition="outside", cliponaxis=False,
                      hovertemplate="%{x}: %{y:,.0f} mi L<extra></extra>")
    fig.update_xaxes(dtick=1)
    c1.plotly_chart(estilo.estilizar_plotly(fig, 340, legenda=False,
                                            titulo="Consumo anual (rótulo = variação vs ano anterior)"),
                    width="stretch")

    tabela_anual = anual.assign(taxa=lambda d: d["desperdicio"] / d["consumo"] * 100)
    c2.dataframe(tabela_anual, hide_index=True, width="stretch", height=340, column_config={
        "ano": st.column_config.NumberColumn("Ano", format="%d"),
        "consumo": st.column_config.NumberColumn("Consumo (mi L)", format="%.0f"),
        "desperdicio": st.column_config.NumberColumn("Desperdiçado (mi L)", format="%.0f"),
        "var": st.column_config.NumberColumn("Var. anual", format="%+.1f%%"),
        "taxa": st.column_config.NumberColumn("Desperdício", format="%.1f%%"),
    })

    st.markdown("##### Mapa de calor: consumo por ano e mês")
    pivo = df.pivot_table(index="ano", columns="mes", values="consumo_milhoes_litros", aggfunc="sum")
    pivo.columns = [MESES[c - 1] for c in pivo.columns]
    fig_hm, ax = plt.subplots(figsize=(12, 0.45 * len(pivo) + 1.2))
    sns.heatmap(pivo, cmap=estilo.CMAP_SEQ, annot=True, fmt=".0f", linewidths=2, linecolor=estilo.SUPERFICIE,
                cbar_kws={"label": "Consumo (mi L)", "shrink": 0.8}, annot_kws={"size": 8}, ax=ax)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(axis="y", rotation=0)
    st.pyplot(fig_hm, width="stretch")
    estilo.fechar(fig_hm)

    inclinacao_ano = m.attrs.get("inclinacao_mensal", np.nan) * 12
    media_mensal = m["consumo"].mean()
    cv = m["consumo"].std() / media_mensal * 100
    var_valida = anual["var"].dropna()
    texto_var = (f"As variações anuais ficaram entre **{fmt(var_valida.min(), 1, '%')}** e "
                 f"**{fmt(var_valida.max(), 1, '%')}**, sem sequência persistente de alta ou queda."
                 if len(var_valida) else "Selecione mais de um ano para ver as variações anuais.")
    tend_pct = inclinacao_ano / media_mensal * 100
    leitura_tend = ("Na prática, o consumo está **estável** no período." if abs(tend_pct) < 2 else
                    f"Há tendência de **{'alta' if tend_pct > 0 else 'queda'}** que merece acompanhamento.")
    app_comum.interpretacao(f"""
- A tendência linear aponta variação de **{fmt(inclinacao_ano, 1)} mi L/ano**, o que equivale a
  **{fmt(tend_pct, 2, '%')}** do consumo médio mensal ({fmt(media_mensal, 0)} mi L). {leitura_tend}
- O consumo mensal oscila bastante em torno da média (coeficiente de variação de **{fmt(cv, 1, '%')}**).
  A média móvel de 12 meses suaviza esse ruído e confirma o nível estável.
- {texto_var}
- No mapa de calor não aparece nenhum padrão repetido de meses mais escuros: os picos mudam de lugar a cada ano.
""")

# ---------------------------------------------------------------- sazonalidade
with tab2:
    st.markdown("Perfil médio de cada mês do ano. A faixa sombreada é o intervalo de confiança de 95% da média.")
    variaveis = [("consumo_milhoes_litros", "Consumo médio por registro (mi L)"),
                 ("chuva_mm", "Chuva (mm)"),
                 ("reservatorios_percentual", "Reservatórios (%)"),
                 ("temperatura_media", "Temperatura (°C)")]
    fig_s, eixos = plt.subplots(2, 2, figsize=(12, 7), sharex=True)
    for ax, (col, rotulo) in zip(eixos.flat, variaveis):
        sns.lineplot(data=df, x="mes", y=col, estimator="mean", errorbar=("ci", 95), color=estilo.PRIMARIA,
                     marker="o", markersize=5, ax=ax)
        ax.axhline(df[col].mean(), color=estilo.TINTA_MUTED, linewidth=1)
        ax.set_title(rotulo, fontsize=11)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_xticks(range(1, 13), MESES)
    fig_s.tight_layout()
    st.pyplot(fig_s, width="stretch")
    estilo.fechar(fig_s)

    por_estacao = (df.groupby("estacao", observed=True)
                     .agg(consumo=("consumo_milhoes_litros", "mean"), chuva=("chuva_mm", "mean"),
                          reservatorio=("reservatorios_percentual", "mean"),
                          temperatura=("temperatura_media", "mean"), alerta=("alerta_elevado", "mean"))
                     .reset_index())
    por_estacao["alerta"] *= 100
    por_estacao["estacao"] = por_estacao["estacao"].astype(str)
    st.dataframe(por_estacao, hide_index=True, width="stretch", column_config={
        "estacao": "Estação",
        "consumo": st.column_config.NumberColumn("Consumo médio (mi L)", format="%.2f"),
        "chuva": st.column_config.NumberColumn("Chuva média (mm)", format="%.1f"),
        "reservatorio": st.column_config.NumberColumn("Reservatório médio", format="%.1f%%"),
        "temperatura": st.column_config.NumberColumn("Temperatura média", format="%.1f °C"),
        "alerta": st.column_config.NumberColumn("% alerta elevado", format="%.1f%%"),
    })

    perfil = df.groupby("mes")[["consumo_milhoes_litros", "chuva_mm"]].mean()
    amp_consumo = (perfil["consumo_milhoes_litros"].max() / perfil["consumo_milhoes_litros"].min() - 1) * 100
    amp_chuva = (perfil["chuva_mm"].max() / perfil["chuva_mm"].min() - 1) * 100
    app_comum.interpretacao(f"""
- O perfil mensal do consumo varia só **{fmt(amp_consumo, 1, '%')}** entre o mês de maior e o de menor média
  (pico em **{MESES[perfil['consumo_milhoes_litros'].idxmax() - 1]}**).
  Os intervalos de confiança se sobrepõem, então **não há sazonalidade estatisticamente clara**.
- A chuva também é quase plana ao longo do ano (amplitude de {fmt(amp_chuva, 1, '%')}). Isso **contraria o regime real
  brasileiro**, em que o período chuvoso (out–mar) chega a ter várias vezes mais chuva que a estiagem. É mais um indício
  de que a base é **simulada sem estrutura sazonal** (veja *Dados e banco → Auditoria*).
- Por isso, o planejamento não deve se apoiar em sazonalidade a partir desta base. Com dados reais (por exemplo, SNIS e ANA),
  a análise sazonal passaria a ser central.
""")

# ---------------------------------------------------------------- comparação regional
with tab3:
    opcoes = {
        "Consumo médio por registro (mi L)": "consumo_milhoes_litros",
        "Desperdício médio (%)": "desperdicio_percentual",
        "Reservatório médio (%)": "reservatorios_percentual",
        "Per capita médio (L/hab/dia)": "consumo_per_capita",
        "Chuva média (mm)": "chuva_mm",
    }
    escolha = st.selectbox("Métrica", list(opcoes), key="temp_regional")
    col = opcoes[escolha]
    reg = df.groupby(["ano", "regiao"], observed=True)[col].mean().reset_index()
    reg["regiao"] = reg["regiao"].astype(str)
    fig = px.line(reg, x="ano", y=col, color="regiao", markers=True, color_discrete_map=estilo.CORES_REGIAO,
                  category_orders={"regiao": dados.ORDEM_REGIOES}, labels={"ano": "", col: escolha})
    fig.update_traces(line=dict(width=2), marker=dict(size=8, line=dict(color=estilo.SUPERFICIE, width=2)),
                      hovertemplate="%{x}: %{y:,.2f}<extra>%{fullData.name}</extra>")
    fig.update_xaxes(dtick=1)
    st.plotly_chart(estilo.estilizar_plotly(fig, 420, titulo=f"{escolha} por região e ano"), width="stretch")

    tabela = reg.pivot(index="ano", columns="regiao", values=col)
    tabela = tabela[[r for r in dados.ORDEM_REGIOES if r in tabela.columns]]
    with st.expander("Ver tabela"):
        st.dataframe(tabela.style.format("{:.2f}").background_gradient(cmap=estilo.CMAP_SEQ, axis=None),
                     width="stretch")

    if not tabela.empty and tabela.shape[1] > 1:
        lideres = tabela.idxmax(axis=1).value_counts()
        app_comum.interpretacao(f"""
- A região com maior **{escolha.lower()}** muda de um ano para outro. **{lideres.index[0]}** liderou em
  {lideres.iloc[0]} de {len(tabela)} anos.
- As linhas se cruzam com frequência e ficam dentro de uma faixa estreita
  ({fmt(tabela.min().min(), 1)} a {fmt(tabela.max().max(), 1)}). **Nenhuma região se destaca de forma persistente**,
  então as diferenças anuais parecem ser **variação aleatória**, não desempenho estrutural.
""")
