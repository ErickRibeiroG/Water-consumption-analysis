"""Funções compartilhadas pelas páginas do Streamlit: carga em cache, filtros e componentes."""

import pandas as pd
import streamlit as st

from utils import api_ibge, banco, dados

ANO_PADRAO_IBGE = 2021


@st.cache_data(show_spinner="Carregando dados do banco SQLite…")
def carregar_base() -> pd.DataFrame:
    return banco.carregar_do_banco()


@st.cache_data(show_spinner="Processando arquivo enviado…")
def carregar_upload(conteudo: bytes, nome: str) -> tuple[pd.DataFrame, dict]:
    import io
    df, rel = dados.preparar(io.BytesIO(conteudo))
    # Enriquece com nome da UF e população oficial (mesma integração feita no banco).
    ibge, _ = api_ibge.dados_ibge()
    df = df.merge(ibge[["uf", "nome_uf", "populacao_ibge"]], on="uf", how="left")
    df["nome_uf"] = df["nome_uf"].fillna(df["uf"])
    return df, rel


@st.cache_data(show_spinner=False)
def relatorio_tratamento() -> dict:
    _, rel = dados.preparar()
    return rel


@st.cache_data(show_spinner="Consultando API do IBGE…", ttl=60 * 60 * 24)
def carregar_ibge(atualizar: bool = False):
    tabela, info = api_ibge.dados_ibge(atualizar=atualizar)
    geo, origem_malha = api_ibge.buscar_malha_ufs(atualizar=atualizar)
    info["malha"] = origem_malha
    return tabela, geo, info


@st.cache_data(show_spinner=False)
def logo_ibge_html(modo: str = "light", altura: str = "0.82em") -> str:
    """<img> inline (base64) do logo do IBGE, na versão adequada ao tema."""
    import base64
    from pathlib import Path

    arquivo = "logo_ibge_dark.png" if modo == "dark" else "logo_ibge.png"
    caminho = Path(__file__).resolve().parent.parent / "imagens" / arquivo
    b64 = base64.b64encode(caminho.read_bytes()).decode()
    return (f'<img src="data:image/png;base64,{b64}" alt="IBGE" '
            f'style="height:{altura}; vertical-align:baseline; margin-left:0.15em;">')


def aplicar_filtros(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    mask = (
        df["ano"].between(*f["anos"])
        & df["regiao"].isin(f["regioes"])
        & df["uf"].isin(f["ufs"])
        & df["setor_consumo"].isin(f["setores"])
        & df["nivel_alerta"].isin(f["alertas"])
    )
    return df[mask]


def descrever_filtros(f: dict, base: pd.DataFrame) -> str:
    def lista(sel, total):
        return "todos" if len(sel) == total else ", ".join(map(str, sel))
    return (f"Período {f['anos'][0]}–{f['anos'][1]} · Regiões: {lista(f['regioes'], base['regiao'].nunique())} · "
            f"Setores: {lista(f['setores'], base['setor_consumo'].nunique())} · "
            f"Alerta: {lista(f['alertas'], base['nivel_alerta'].nunique())}")


def obter_contexto():
    """Retorna (df_filtrado, df_base, filtros) definidos pelo app.py."""
    return st.session_state["df_filtrado"], st.session_state["df_base"], st.session_state["filtros"]


def aviso_vazio(df: pd.DataFrame) -> bool:
    if df.empty:
        st.warning("Nenhum registro corresponde aos filtros selecionados. Ajuste os filtros na barra lateral.")
        return True
    return False


def interpretacao(texto: str, titulo: str = "Interpretação"):
    """Bloco padronizado de interpretação textual."""
    with st.container(border=True):
        st.markdown(f"**:material/lightbulb: {titulo}**")
        st.markdown(texto)


def delta_anual(df: pd.DataFrame, f: dict, chave: str):
    """Variação de um KPI entre o último ano do filtro e o ano anterior (pontos ou %)."""
    ano_fim = f["anos"][1]
    if f["anos"][0] == ano_fim:
        return None
    atual = dados.calcular_kpis(df[df["ano"] == ano_fim])[chave]
    anterior = dados.calcular_kpis(df[df["ano"] == ano_fim - 1])[chave]
    if pd.isna(atual) or pd.isna(anterior) or anterior == 0:
        return None
    return atual, anterior
