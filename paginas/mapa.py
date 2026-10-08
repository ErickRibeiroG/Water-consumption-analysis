import plotly.graph_objects as go
import streamlit as st

from utils import app_comum, estilo
from utils.dados import formatar_num as fmt

df, base, f = app_comum.obter_contexto()

st.title("Mapa e integração com o IBGE")
st.markdown(
    "Distribuição geográfica dos indicadores e cruzamento da base com dados oficiais obtidos **em tempo real** "
    "pelas APIs públicas do IBGE: localidades, malha territorial (GeoJSON) e estimativas de população."
)
st.caption(app_comum.descrever_filtros(f, base))
if app_comum.aviso_vazio(df):
    st.stop()

# ---------------------------------------------------------------- dados do IBGE
topo1, topo2 = st.columns([3, 1], vertical_alignment="bottom")
with topo2:
    if st.button("Atualizar dados do IBGE", icon=":material/sync:", width="stretch",
                 help="Consulta novamente as APIs do IBGE e atualiza o cache local."):
        app_comum.carregar_ibge.clear()
        st.session_state["ibge_forcar"] = True
forcar = st.session_state.pop("ibge_forcar", False)
try:
    ibge, geo, info = app_comum.carregar_ibge(atualizar=forcar)
except Exception as erro:  # noqa: BLE001 — sem API e sem cache, a página não tem como seguir
    st.error(f"Não foi possível obter dados do IBGE: {erro}")
    st.stop()
with topo1:
    st.caption(f":material/cloud_done: IBGE: estados via **{info['estados']}**, malha via **{info['malha']}**, "
               f"população via **{info['populacao']}**. Consulta: {info['consultado_em']}.")

# ---------------------------------------------------------------- mapa
metricas = {
    "Consumo total (mi L)": ("consumo_milhoes_litros", "sum"),
    "Desperdício médio (%)": ("desperdicio_percentual", "mean"),
    "Reservatório médio (%)": ("reservatorios_percentual", "mean"),
    "Per capita médio (L/hab/dia)": ("consumo_per_capita", "mean"),
    "% registros em alerta Alto/Crítico": ("alerta_elevado", "mean"),
    "Chuva média (mm)": ("chuva_mm", "mean"),
}
escolha = st.selectbox("Indicador do mapa", list(metricas), key="mapa_metrica")
col, agg = metricas[escolha]
por_uf = df.groupby("uf", observed=True)[col].agg(agg).rename("valor").reset_index()
if col == "alerta_elevado":
    por_uf["valor"] *= 100
por_uf = por_uf.merge(ibge[["uf", "nome_uf"]], on="uf", how="left")

todas = ibge[["uf", "nome_uf"]]
fig = go.Figure()
# Camada base: todas as UFs em cinza (inclusive as que não estão na base).
fig.add_choropleth(geojson=geo, featureidkey="properties.uf", locations=todas["uf"], z=[0] * len(todas),
                   colorscale=[[0, "#ecebe7"], [1, "#ecebe7"]], showscale=False,
                   marker_line_color="white", marker_line_width=0.8,
                   customdata=todas["nome_uf"], hovertemplate="%{customdata}: sem dados no recorte<extra></extra>")
fig.add_choropleth(geojson=geo, featureidkey="properties.uf", locations=por_uf["uf"], z=por_uf["valor"],
                   colorscale=estilo.ESCALA_SEQ_PLOTLY, marker_line_color="white", marker_line_width=0.8,
                   colorbar=dict(title=dict(text=escolha, side="top"), orientation="h", thickness=10, len=0.6,
                                 x=0.5, xanchor="center", y=-0.02, yanchor="top"),
                   customdata=por_uf["nome_uf"], hovertemplate="<b>%{customdata}</b><br>" + escolha +
                   ": %{z:,.2f}<extra></extra>")
fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)", projection_type="mercator")
fig.update_layout(height=600, margin=dict(l=0, r=0, t=10, b=60), paper_bgcolor="rgba(0,0,0,0)", separators=",.",
                  font=dict(family=estilo.FONTE, color=estilo.TINTA_SEC))

c_mapa, c_rank = st.columns([3, 2])
c_mapa.plotly_chart(fig, width="stretch")
with c_rank:
    st.markdown(f"**Ranking — {escolha}**")
    st.dataframe(por_uf.sort_values("valor", ascending=False)[["uf", "nome_uf", "valor"]],
                 hide_index=True, width="stretch", height=520, column_config={
                     "uf": "UF", "nome_uf": "Estado",
                     "valor": st.column_config.ProgressColumn(escolha, format="%.1f", min_value=0,
                                                              max_value=float(por_uf["valor"].max()))})

faltam = sorted(set(ibge["uf"]) - set(base["uf"]))
topo, fundo = por_uf.nlargest(1, "valor").iloc[0], por_uf.nsmallest(1, "valor").iloc[0]
n_uf = df["uf"].value_counts()
app_comum.interpretacao(f"""
- Em **{escolha.lower()}**, **{topo['nome_uf']}** lidera ({fmt(topo['valor'], 1)}) e **{fundo['nome_uf']}** tem o menor valor
  ({fmt(fundo['valor'], 1)}).
- Nos indicadores de **média** (desperdício, reservatório, per capita), os estados ficam numa faixa estreita e
  **não formam um padrão regional contínuo** no mapa. Já o **consumo total** acompanha o número de registros de cada
  UF: **{n_uf.idxmax()}** tem {n_uf.max()} registros no recorte, enquanto **{n_uf.idxmin()}** tem {n_uf.min()}.
- A base cobre **{base['uf'].nunique()} das 27 UFs**. Ficam de fora: {', '.join(faltam) if faltam else 'nenhuma'}
  (em cinza no mapa).
""")

# ---------------------------------------------------------------- população: base × IBGE
st.divider()
st.subheader("População da base × estimativa oficial do IBGE")
st.markdown("Compara a população informada na base (média por UF) com a estimativa do IBGE para 2021 "
            "(API SIDRA, tabela 6579). É um teste de **integração de múltiplas fontes** e de **qualidade dos dados**.")
pop = (df.groupby("uf", observed=True)
         .agg(pop_base_media=("populacao", "mean"), pop_base_min=("populacao", "min"),
              pop_base_max=("populacao", "max"))
         .reset_index().merge(ibge, on="uf", how="left"))
pop["razao"] = pop["pop_base_media"] / pop["populacao_ibge"]
pop = pop.sort_values("populacao_ibge", ascending=False)

fig = go.Figure()
fig.add_bar(x=pop["uf"], y=pop["populacao_ibge"] / 1e6, name="IBGE 2021 (oficial)",
            marker=dict(color=estilo.PRIMARIA, line=dict(color=estilo.SUPERFICIE, width=2)),
            hovertemplate="%{x}: %{y:.2f} mi hab.<extra>IBGE</extra>")
fig.add_bar(x=pop["uf"], y=pop["pop_base_media"] / 1e6, name="Base simulada (média)",
            marker=dict(color=estilo.CATEGORICA[1], line=dict(color=estilo.SUPERFICIE, width=2)),
            hovertemplate="%{x}: %{y:.2f} mi hab.<extra>Base</extra>")
fig.update_layout(barmode="group", yaxis_title="Milhões de habitantes")
st.plotly_chart(estilo.estilizar_plotly(fig, 380), width="stretch")

with st.expander("Ver tabela comparativa"):
    st.dataframe(pop[["uf", "nome_uf", "regiao_ibge", "populacao_ibge", "pop_base_media", "pop_base_min",
                      "pop_base_max", "razao"]], hide_index=True, width="stretch", column_config={
        "uf": "UF", "nome_uf": "Estado", "regiao_ibge": "Região (IBGE)",
        "populacao_ibge": st.column_config.NumberColumn("IBGE 2021", format="%d"),
        "pop_base_media": st.column_config.NumberColumn("Base: média", format="%.0f"),
        "pop_base_min": st.column_config.NumberColumn("Base: mínimo", format="%d"),
        "pop_base_max": st.column_config.NumberColumn("Base: máximo", format="%d"),
        "razao": st.column_config.NumberColumn("Base ÷ IBGE", format="%.2f×"),
    })

sp = pop[pop["uf"] == "SP"]
texto_sp = (f"Em São Paulo, a base indica em média {fmt(sp['pop_base_media'].iloc[0] / 1e6, 1)} mi de habitantes, "
            f"contra {fmt(sp['populacao_ibge'].iloc[0] / 1e6, 1)} mi do IBGE." if not sp.empty else "")
app_comum.interpretacao(f"""
- A população da base **não corresponde à realidade**: os valores vão de {fmt(pop['pop_base_min'].min() / 1e6, 1)} a
  {fmt(pop['pop_base_max'].max() / 1e6, 1)} milhões, em faixas parecidas para estados pequenos e grandes, e mudam a cada mês.
  {texto_sp}
- A razão base ÷ IBGE vai de **{fmt(pop['razao'].min(), 2)}×** a **{fmt(pop['razao'].max(), 2)}×**. Por isso, KPIs que
  dependem da população (como o per capita) devem ser lidos como **ilustrativos**.
- A integração com o IBGE serviu para três coisas: **validar** a região de cada UF (todas conferem), **enriquecer** a base
  com nomes oficiais e geometria para o mapa e **detectar** esta inconsistência.
""", titulo="Interpretação — qualidade da população")
