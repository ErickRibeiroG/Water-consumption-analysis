import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import app_comum, dados, estilo
from utils.dados import formatar_num as fmt

df, base, f = app_comum.obter_contexto()
pal = estilo.paleta()  # cores do tema ativo (claro/escuro)

st.title("Consumo de Água no Brasil")
st.markdown(
    "**Painel analítico de consumo, desperdício e segurança hídrica por região, estado e setor (2015–2024).**"
)

with st.expander(":material/help: Qual é o problema?", expanded=True):
    st.markdown(
        """
A gestão da água no Brasil precisa equilibrar **demanda crescente**, **perdas na distribuição** e
**níveis de reservatórios** sujeitos à variação climática. Este painel organiza 10 anos de registros
mensais de 20 estados e 5 setores para responder:

1. **Onde** e **em que setor** se concentra o consumo de água?
2. Qual é o tamanho do **desperdício** e onde ele é mais grave?
3. Como estão os **reservatórios** e com que frequência há **alertas elevados**?
4. Existe **tendência** ou **sazonalidade** no consumo? O clima (chuva e temperatura) explica o comportamento?

Use os **filtros da barra lateral**. Eles valem para todas as páginas.
        """
    )

st.caption(app_comum.descrever_filtros(f, base))
if app_comum.aviso_vazio(df):
    st.stop()

# ---------------------------------------------------------------- KPIs
k = dados.calcular_kpis(df)


def delta(chave, modo):
    par = app_comum.delta_anual(df, f, chave)
    if par is None:
        return None
    atual, anterior = par
    if modo == "pct":
        return f"{(atual / anterior - 1) * 100:+.1f}".replace(".", ",") + f"% vs {f['anos'][1] - 1}"
    return f"{atual - anterior:+.1f}".replace(".", ",") + f" p.p. vs {f['anos'][1] - 1}"


st.subheader("Indicadores-chave")
st.caption("A variação compara o último ano do período filtrado com o ano anterior.")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Consumo total", f"{fmt(k['consumo_total'] / 1000, 1)} bi L", delta("consumo_total", "pct"),
          delta_color="off", border=True, help="Soma de `consumo_milhoes_litros` no recorte.")
c2.metric("Volume desperdiçado", f"{fmt(k['volume_desperdicado'] / 1000, 1)} bi L",
          delta("volume_desperdicado", "pct"), delta_color="inverse", border=True,
          help="Σ consumo × desperdício% — estimativa de água perdida.")
c3.metric("Taxa de desperdício", fmt(k["desperdicio_ponderado"], 1, "%"), delta("desperdicio_ponderado", "pp"),
          delta_color="inverse", border=True, help="Volume desperdiçado ÷ consumo total (média ponderada).")
c4.metric("Per capita (L/hab/dia)", fmt(k["per_capita_medio"], 0), delta("per_capita_medio", "pct"),
          delta_color="inverse", border=True, help="Média de `consumo_per_capita`. Referência ONU: 110 L/hab/dia.")
c5, c6, c7, c8 = st.columns(4)
c5.metric("Reservatório médio", fmt(k["reservatorio_medio"], 1, "%"), delta("reservatorio_medio", "pp"),
          border=True)
c6.metric("Reservatório < 30%", fmt(k["pct_reservatorio_critico"], 1, "%"),
          delta("pct_reservatorio_critico", "pp"), delta_color="inverse", border=True,
          help="% dos registros com reservatório abaixo de 30% da capacidade.")
c7.metric("Alerta Alto/Crítico", fmt(k["pct_alerta_elevado"], 1, "%"),
          delta("pct_alerta_elevado", "pp"), delta_color="inverse", border=True,
          help="% dos registros com nível de alerta Alto ou Crítico.")
c8.metric("Chuva média", fmt(k["chuva_media"], 0, " mm"), delta("chuva_media", "pct"),
          delta_color="normal", border=True)

# ---------------------------------------------------------------- distribuição
st.divider()
st.subheader("Onde a água é consumida")

metricas = {
    "Consumo total (mi L)": ("consumo_milhoes_litros", "sum"),
    "Consumo médio por registro (mi L)": ("consumo_milhoes_litros", "mean"),
    "Desperdício médio (%)": ("desperdicio_percentual", "mean"),
    "Per capita médio (L/hab/dia)": ("consumo_per_capita", "mean"),
    "Reservatório médio (%)": ("reservatorios_percentual", "mean"),
}
escolha = st.segmented_control("Métrica dos gráficos", list(metricas), default="Consumo total (mi L)",
                               key="vg_metrica")
escolha = escolha or "Consumo total (mi L)"
col, agg = metricas[escolha]

g1, g2 = st.columns(2)
por_regiao = df.groupby("regiao", observed=True)[col].agg(agg).reset_index()
fig = px.bar(por_regiao, x=col, y="regiao", orientation="h", color="regiao",
             color_discrete_map=pal.CORES_REGIAO, text_auto=",.1f",
             labels={col: escolha, "regiao": ""})
fig.update_traces(textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x:,.2f}<extra></extra>")
fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(dados.ORDEM_REGIOES)))
fig.update_xaxes(range=[0, por_regiao[col].max() * 1.22])
g1.plotly_chart(estilo.estilizar_plotly(fig, 340, legenda=False, titulo=f"{escolha} por região"), width="stretch")

por_setor = df.groupby("setor_consumo", observed=True)[col].agg(agg).reset_index().sort_values(col)
fig = px.bar(por_setor, x=col, y="setor_consumo", orientation="h", text_auto=",.1f",
             labels={col: escolha, "setor_consumo": ""})
fig.update_traces(marker_color=pal.PRIMARIA, textposition="outside", cliponaxis=False,
                  hovertemplate="%{y}: %{x:,.2f}<extra></extra>")
fig.update_xaxes(range=[0, por_setor[col].max() * 1.22])
g2.plotly_chart(estilo.estilizar_plotly(fig, 340, legenda=False, titulo=f"{escolha} por setor"), width="stretch")

# ---------------------------------------------------------------- alertas
st.subheader("Nível de alerta por região")
alerta = (df.groupby(["regiao", "nivel_alerta"], observed=True).size()
            .groupby(level=0, observed=True).transform(lambda s: s / s.sum() * 100)
            .rename("pct").reset_index())
fig = go.Figure()
for nivel in dados.ORDEM_ALERTA:
    sub = alerta[alerta["nivel_alerta"] == nivel]
    fig.add_bar(y=sub["regiao"], x=sub["pct"], name=nivel, orientation="h",
                marker=dict(color=pal.CORES_ALERTA[nivel], line=dict(color=pal.SUPERFICIE, width=2)),
                text=sub["pct"].map(lambda v: f"{v:.0f}%"), textposition="inside",
                insidetextanchor="middle", textfont=dict(color="white"),
                hovertemplate="%{y} · " + nivel + ": %{x:.1f}%<extra></extra>")
fig.update_layout(barmode="stack", xaxis=dict(title="% dos registros", range=[0, 100], ticksuffix="%"),
                  legend_traceorder="normal")
fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(dados.ORDEM_REGIOES)))
st.plotly_chart(estilo.estilizar_plotly(fig, 300), width="stretch")

# ---------------------------------------------------------------- tabela
st.subheader("Ranking de estados")
ranking = (df.groupby(["uf", "nome_uf", "regiao"], observed=True)
             .agg(consumo=("consumo_milhoes_litros", "sum"),
                  desperdicio=("desperdicio_percentual", "mean"),
                  reservatorio=("reservatorios_percentual", "mean"),
                  per_capita=("consumo_per_capita", "mean"),
                  alerta=("alerta_elevado", "mean"),
                  registros=("uf", "size"))
             .reset_index().sort_values("consumo", ascending=False))
ranking["alerta"] *= 100
ranking["regiao"] = ranking["regiao"].astype(str)
st.dataframe(
    ranking, hide_index=True, width="stretch",
    column_config={
        "uf": "UF", "nome_uf": "Estado", "regiao": "Região",
        "consumo": st.column_config.ProgressColumn("Consumo (mi L)", format="%.0f",
                                                   min_value=0, max_value=float(ranking["consumo"].max())),
        "desperdicio": st.column_config.NumberColumn("Desperdício médio", format="%.1f%%"),
        "reservatorio": st.column_config.ProgressColumn("Reservatório médio", format="%.1f%%",
                                                        min_value=0, max_value=100),
        "per_capita": st.column_config.NumberColumn("Per capita (L/hab/dia)", format="%.0f"),
        "alerta": st.column_config.NumberColumn("% alerta Alto/Crítico", format="%.1f%%"),
        "registros": st.column_config.NumberColumn("Registros"),
    },
)

# ---------------------------------------------------------------- interpretação
part = df.groupby("regiao", observed=True).agg(consumo=("consumo_milhoes_litros", "sum"), n=("uf", "size"))
part["pct_consumo"] = part["consumo"] / part["consumo"].sum() * 100
part["pct_registros"] = part["n"] / part["n"].sum() * 100
lider = part["pct_consumo"].idxmax()
media_reg = df.groupby("regiao", observed=True)["consumo_milhoes_litros"].mean()
setor_desp = df.groupby("setor_consumo", observed=True)["desperdicio_percentual"].mean()
amplitude_setor = setor_desp.max() - setor_desp.min()
dispersao_alerta = alerta.groupby("nivel_alerta", observed=True)["pct"].agg(lambda s: s.max() - s.min()).max()
frase_alerta = ("Os níveis de alerta aparecem em proporções parecidas em todas as regiões "
                f"(diferença máxima de {fmt(dispersao_alerta, 1)} p.p.)." if dispersao_alerta < 8 else
                f"A composição dos alertas difere entre regiões (até {fmt(dispersao_alerta, 1)} p.p.), "
                "o que merece investigação regional.")

app_comum.interpretacao(f"""
- **{lider}** concentra **{fmt(part.loc[lider, 'pct_consumo'], 1, '%')}** do consumo do recorte, mas também responde por
  **{fmt(part.loc[lider, 'pct_registros'], 1, '%')}** dos registros. O volume total reflete principalmente
  **quantos estados e meses** cada região tem na base, não uma intensidade maior de uso.
- Por registro, o consumo médio varia só de **{fmt(media_reg.min(), 1)}** a **{fmt(media_reg.max(), 1)} mi L** entre as regiões.
  Para comparar regiões de forma justa, use a métrica *Consumo médio por registro*.
- A taxa de desperdício está em **{fmt(k['desperdicio_ponderado'], 1, '%')}**: cerca de **1 em cada {100 / k['desperdicio_ponderado']:.0f} litros** se perde.
  Entre os setores, a diferença é pequena ({fmt(amplitude_setor, 1)} p.p. entre o maior, **{setor_desp.idxmax()}**,
  e o menor, **{setor_desp.idxmin()}**). O problema é **sistêmico**, não de um setor específico.
- **{fmt(k['pct_alerta_elevado'], 0, '%')}** dos registros estão em alerta Alto ou Crítico, e
  **{fmt(k['pct_reservatorio_critico'], 0, '%')}** têm reservatórios abaixo de 30%. {frase_alerta}
""")

with st.container(border=True):
    st.markdown("**:material/flag: Conclusão executiva**")
    st.markdown(
        f"O desperdício (~{fmt(k['desperdicio_ponderado'], 0, '%')}) é o principal ponto de ação: ele é alto e uniforme entre "
        "regiões e setores, o que pede **programas estruturais de redução de perdas**. A frequência de alertas elevados "
        "e de reservatórios críticos justifica **monitoramento contínuo**. A análise completa, com limitações e "
        "recomendações, está na página **Conclusões**."
    )
