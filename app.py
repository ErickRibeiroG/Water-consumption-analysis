"""Dashboard Streamlit — Consumo de Água no Brasil.

Ponto de entrada: define a navegação multipágina, a origem dos dados (banco SQLite
ou upload de CSV) e os filtros globais compartilhados por todas as páginas.

Execução local:  streamlit run app.py
"""

import streamlit as st

from utils import app_comum, dados

st.set_page_config(
    page_title="Consumo de Água no Brasil",
    page_icon=":material/water_drop:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------- origem dos dados
with st.sidebar:
    st.markdown("### :material/water_drop: Consumo de Água")
    st.caption("Sistemas de Informação · Linguagens de Programação")

    with st.expander(":material/upload_file: Enviar outra base (CSV)", expanded=False):
        arquivo = st.file_uploader(
            "CSV com o mesmo layout da base original", type=["csv"], label_visibility="collapsed"
        )
        st.caption("Sem envio, os dados vêm do banco SQLite `database/agua.db`.")

if arquivo is not None:
    try:
        base, _ = app_comum.carregar_upload(arquivo.getvalue(), arquivo.name)
        origem = f"Upload: {arquivo.name}"
    except ValueError as erro:
        st.sidebar.error(f"Arquivo inválido. {erro}")
        base, origem = app_comum.carregar_base(), "Banco SQLite"
else:
    base, origem = app_comum.carregar_base(), "Banco SQLite"

# ---------------------------------------------------------------- filtros globais
anos_disp = sorted(base["ano"].unique())
regioes_disp = [r for r in dados.ORDEM_REGIOES if r in set(base["regiao"])]
setores_disp = [s for s in dados.ORDEM_SETORES if s in set(base["setor_consumo"])]
alertas_disp = [a for a in dados.ORDEM_ALERTA if a in set(base["nivel_alerta"])]


CHAVES_FILTRO = ["f_anos", "f_regioes", "f_ufs", "f_setores", "f_alertas", "_regioes_prev", "_origem_prev"]


def limpar_filtros():
    for chave in CHAVES_FILTRO:
        st.session_state.pop(chave, None)


# Uma nova base (upload) pode ter outros valores possíveis: reinicia os filtros.
if st.session_state.get("_origem_prev") != origem:
    limpar_filtros()
    st.session_state["_origem_prev"] = origem

ss = st.session_state
ss.setdefault("f_anos", (int(anos_disp[0]), int(anos_disp[-1])))
ss.setdefault("f_regioes", regioes_disp)
ss.setdefault("f_setores", setores_disp)
ss.setdefault("f_alertas", alertas_disp)

with st.sidebar:
    st.markdown("#### :material/filter_alt: Filtros")
    if len(anos_disp) > 1:
        anos = st.slider("Período", min_value=int(anos_disp[0]), max_value=int(anos_disp[-1]), key="f_anos")
    else:
        anos = ss["f_anos"]
    regioes = st.multiselect("Regiões", regioes_disp, key="f_regioes", placeholder="Selecione as regiões")

    # Estados dependem das regiões: ao mudar as regiões, todos os estados delas são selecionados.
    ufs_disp = sorted(base.loc[base["regiao"].isin(regioes), "uf"].unique())
    if ss.get("_regioes_prev") != regioes or "f_ufs" not in ss:
        ss["f_ufs"] = ufs_disp
        ss["_regioes_prev"] = regioes
    ufs = st.multiselect("Estados (UF)", ufs_disp, key="f_ufs", placeholder="Selecione os estados")

    setores = st.multiselect("Setores de consumo", setores_disp, key="f_setores", placeholder="Selecione os setores")
    alertas = st.multiselect("Nível de alerta", alertas_disp, key="f_alertas", placeholder="Selecione os níveis")
    st.button("Limpar filtros", icon=":material/restart_alt:", on_click=limpar_filtros, width="stretch")

filtros = {"anos": anos, "regioes": regioes, "ufs": ufs, "setores": setores, "alertas": alertas}
filtrado = app_comum.aplicar_filtros(base, filtros)

st.session_state["df_base"] = base
st.session_state["df_filtrado"] = filtrado
st.session_state["filtros"] = filtros

with st.sidebar:
    st.divider()
    st.caption(f"**Fonte:** {origem}  \n**Registros no recorte:** {dados.formatar_num(len(filtrado), 0)} "
               f"de {dados.formatar_num(len(base), 0)}")

# ---------------------------------------------------------------- navegação
paginas = {
    "Painel": [
        st.Page("paginas/visao_geral.py", title="Visão geral", icon=":material/dashboard:", default=True),
        st.Page("paginas/analise_temporal.py", title="Análise temporal", icon=":material/timeline:"),
        st.Page("paginas/mapa.py", title="Mapa e IBGE", icon=":material/map:"),
    ],
    "Análises": [
        st.Page("paginas/correlacoes.py", title="Correlações", icon=":material/scatter_plot:"),
        st.Page("paginas/dados_banco.py", title="Dados e banco", icon=":material/database:"),
    ],
    "Fechamento": [
        st.Page("paginas/conclusoes.py", title="Conclusões", icon=":material/task_alt:"),
    ],
}
st.navigation(paginas).run()
