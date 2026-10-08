import re
import textwrap

import pandas as pd
import streamlit as st

from utils import app_comum, banco, dados
from utils.dados import formatar_num as fmt

df, base, f = app_comum.obter_contexto()

st.title("Dados, tratamento e banco")
st.markdown("Como a base foi preparada, quais problemas de qualidade existem e como os dados estão modelados no "
            "SQLite.")


def mostrar_auditoria(df):
    aud = dados.auditoria_consistencia(df)
    aud["Situação"] = aud["Coerente"].map({True: "✅ Coerente", False: "⚠️ Incoerente"})
    st.dataframe(aud[["Situação", "Teste", "Resultado", "Expectativa"]], hide_index=True, width="stretch",
                 column_config={"Situação": st.column_config.TextColumn(width="small"),
                                "Resultado": st.column_config.TextColumn(width="large")})
    incoerentes = int((~aud["Coerente"]).sum())
    app_comum.interpretacao(textwrap.dedent(f"""
    **{incoerentes} de {len(aud)} testes falharam.** Todas as colunas são válidas isoladamente, mas **não se relacionam entre si**
    como na realidade. É o padrão de dados **sintéticos gerados de forma independente** (cada coluna sorteada
    de uma distribuição uniforme).

    **Consequências para a análise:**
    - Os KPIs descritivos (totais, médias, percentuais) são **válidos como exercício**, mas não descrevem o Brasil real.
    - Correlações, tendências e sazonalidade **ausentes** são o resultado esperado, não falhas do método.
    - O per capita informado (80–450 L/hab/dia) é plausível, mas é **incompatível** com o consumo e a população da mesma
      linha, que resultam em menos de 1 L/hab/dia.

    **Recomendação:** repetir a análise com dados oficiais (SNIS, ANA e IBGE). Pipeline, banco e dashboard já estão
    prontos para receber uma nova base pelo upload.
    """), titulo="Diagnóstico de qualidade")


tab1, tab2, tab3, tab4 = st.tabs([":material/cleaning_services: Tratamento", ":material/fact_check: Auditoria",
                                  ":material/schema: Banco SQL", ":material/table: Dados filtrados"])

# ---------------------------------------------------------------- tratamento
with tab1:
    rel = app_comum.relatorio_tratamento()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Linhas no CSV original", fmt(rel["linhas_originais"], 0), border=True)
    m2.metric("Removidas (nulos/duplicatas)", fmt(rel["removidas_nulos"] + rel["removidas_duplicadas"], 0),
              border=True)
    m3.metric("Removidas (domínio/categoria)",
              fmt(rel["removidas_dominio"] + rel["removidas_categoria_invalida"], 0), border=True)
    m4.metric("Linhas finais", fmt(rel["linhas_finais"], 0), border=True)

    st.markdown("""
##### Etapas do pipeline (`utils/dados.py`)
1. **Leitura** do CSV (UTF-8) e **validação do esquema**: as 14 colunas obrigatórias precisam existir. O mesmo teste vale
   para arquivos enviados por upload.
2. **Padronização de textos**: remoção de espaços, caixa título em região, setor e alerta e caixa alta em UF.
3. **Conversão de tipos**: números com `to_numeric(errors="coerce")` e datas com `to_datetime`.
4. **Nulos e duplicatas**: remoção de registros incompletos e de linhas repetidas.
5. **Validação de domínio**: percentuais entre 0 e 100, chuva e consumo ≥ 0, mês entre 1 e 12, temperatura plausível e
   coerência entre `data` e as colunas `ano`/`mes`.
6. **Categorias ordenadas**: região, setor e alerta (Baixo < Médio < Alto < Crítico), o que garante ordenação correta.
7. **Engenharia de atributos** (tabela abaixo).
8. **Persistência** no SQLite (`database/agua.db`) em modelo relacional, enriquecida com dados do IBGE.
    """)
    st.success(f"Resultado: a base original já estava íntegra. Sem nulos ({len(rel['nulos_por_coluna'])} colunas "
               f"afetadas), sem duplicatas ({rel['removidas_duplicadas']}) e sem valores fora do domínio "
               f"({rel['removidas_dominio']}). As validações continuam no pipeline para proteger o dashboard "
               "contra arquivos enviados por upload.", icon=":material/verified:")

    st.markdown("##### Atributos criados")
    st.dataframe(pd.DataFrame([
        ("volume_desperdicado_ml", "consumo × desperdício% ÷ 100", "Volume perdido em milhões de litros"),
        ("consumo_efetivo_ml", "consumo − volume desperdiçado", "Água efetivamente aproveitada"),
        ("trimestre / ano_mes", "derivados da coluna data", "Agregações temporais"),
        ("estacao", "mês → estação (hemisfério sul)", "Análise sazonal"),
        ("periodo_chuvoso", "mês entre outubro e março", "Comparar período chuvoso com estiagem"),
        ("faixa_reservatorio", "pd.cut em 30/50/70%", "Classificação objetiva do risco hídrico"),
        ("score_alerta", "Baixo=1 … Crítico=4", "Permite correlacionar o alerta com variáveis numéricas"),
        ("alerta_elevado", "alerta ∈ {Alto, Crítico}", "KPI: % de registros em alerta elevado"),
        ("reservatorio_critico", "reservatório < 30%", "KPI: % de registros críticos"),
        ("chuva_outlier", "chuva > Q3 + 1,5·IQR", "Marca eventos extremos de chuva"),
        ("per_capita_recalculado", "consumo·10⁶ ÷ população ÷ dias do mês", "Auditoria de consistência"),
    ], columns=["Atributo", "Regra", "Uso"]), hide_index=True, width="stretch")

    n_out = int(df["chuva_outlier"].sum()) if not df.empty else 0
    st.caption(f"Outliers de chuva no recorte atual: {fmt(n_out, 0)} registros ({fmt(n_out / max(len(df), 1) * 100, 1, '%')}). "
               "Eles foram **mantidos**, porque chuvas extremas são eventos reais e relevantes, apenas sinalizados.")

# ---------------------------------------------------------------- auditoria
with tab2:
    st.markdown("Testes de **coerência entre variáveis** que, numa base real, deveriam estar relacionadas. "
                "Eles verificam se os números fazem sentido juntos, não só se cada coluna é válida isoladamente.")
    if not app_comum.aviso_vazio(df):
        mostrar_auditoria(df)

# ---------------------------------------------------------------- banco
with tab3:
    st.markdown("##### Modelo relacional (SQLAlchemy ORM → SQLite)")
    st.graphviz_chart("""
digraph {
  rankdir=LR; bgcolor="transparent"; size="9,4.2";
  node [shape=plain, fontname="Comfortaa", fontsize=10];
  edge [color="#898781", arrowhead=crow, arrowtail=none];
  regioes [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td width="130" bgcolor="#2a78d6"><font color="white"><b>regioes</b></font></td></tr>
    <tr><td align="left">🔑 id</td></tr><tr><td align="left">nome</td></tr></table>>];
  estados [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td width="210" bgcolor="#2a78d6"><font color="white"><b>estados</b></font></td></tr>
    <tr><td align="left">🔑 id (código IBGE)</td></tr><tr><td align="left">sigla</td></tr>
    <tr><td align="left">nome</td></tr><tr><td align="left">populacao_ibge</td></tr>
    <tr><td align="left">🔗 regiao_id</td></tr></table>>];
  setores [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td width="130" bgcolor="#2a78d6"><font color="white"><b>setores</b></font></td></tr>
    <tr><td align="left">🔑 id</td></tr><tr><td align="left">nome</td></tr></table>>];
  niveis_alerta [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td width="170" bgcolor="#2a78d6"><font color="white"><b>niveis_alerta</b></font></td></tr>
    <tr><td align="left">🔑 id</td></tr><tr><td align="left">nome</td></tr><tr><td align="left">score</td></tr></table>>];
  medicoes [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4" bgcolor="white">
    <tr><td width="290" bgcolor="#0d366b"><font color="white"><b>medicoes (fato)</b></font></td></tr>
    <tr><td align="left">🔑 id</td></tr><tr><td align="left">data</td></tr>
    <tr><td align="left">🔗 estado_id</td></tr><tr><td align="left">🔗 setor_id</td></tr>
    <tr><td align="left">🔗 nivel_alerta_id</td></tr><tr><td align="left">consumo_milhoes_litros</td></tr>
    <tr><td align="left">desperdicio_percentual</td></tr><tr><td align="left">reservatorios_percentual</td></tr>
    <tr><td align="left">chuva_mm · temperatura_media</td></tr><tr><td align="left">populacao · consumo_per_capita</td></tr>
    </table>>];
  regioes -> estados; estados -> medicoes; setores -> medicoes; niveis_alerta -> medicoes;
}
""", width="stretch")

    contagem = banco.contar_registros(banco.obter_engine())
    st.caption("Registros por tabela: " + " · ".join(f"`{t}` = {fmt(n, 0)}" for t, n in contagem.items()))

    st.markdown("##### Consultas SQL")
    consultas = {
        "Consumo e desperdício por região": """SELECT r.nome AS regiao,
       ROUND(SUM(m.consumo_milhoes_litros), 1) AS consumo_total_mi_l,
       ROUND(SUM(m.consumo_milhoes_litros * m.desperdicio_percentual / 100), 1) AS desperdicado_mi_l,
       ROUND(AVG(m.reservatorios_percentual), 1) AS reservatorio_medio
FROM medicoes m
JOIN estados e ON e.id = m.estado_id
JOIN regioes r ON r.id = e.regiao_id
GROUP BY r.nome
ORDER BY consumo_total_mi_l DESC;""",
        "Ranking de estados com alerta Crítico": """SELECT e.sigla, e.nome, COUNT(*) AS meses_criticos,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM medicoes m2 WHERE m2.estado_id = e.id), 1) AS pct
FROM medicoes m
JOIN estados e ON e.id = m.estado_id
JOIN niveis_alerta n ON n.id = m.nivel_alerta_id
WHERE n.nome = 'Crítico'
GROUP BY e.id
ORDER BY pct DESC;""",
        "Consumo anual por setor": """SELECT strftime('%Y', m.data) AS ano, s.nome AS setor,
       ROUND(SUM(m.consumo_milhoes_litros), 1) AS consumo_mi_l
FROM medicoes m
JOIN setores s ON s.id = m.setor_id
GROUP BY ano, s.nome
ORDER BY ano, consumo_mi_l DESC;""",
        "População da base × IBGE": """SELECT e.sigla, e.populacao_ibge,
       CAST(AVG(m.populacao) AS INTEGER) AS populacao_media_base,
       ROUND(AVG(m.populacao) * 1.0 / e.populacao_ibge, 2) AS razao
FROM medicoes m
JOIN estados e ON e.id = m.estado_id
GROUP BY e.id
ORDER BY e.populacao_ibge DESC;""",
        "UFs do IBGE sem registros na base (LEFT JOIN)": """SELECT e.sigla, e.nome, r.nome AS regiao
FROM estados e
JOIN regioes r ON r.id = e.regiao_id
LEFT JOIN medicoes m ON m.estado_id = e.id
WHERE m.id IS NULL
ORDER BY r.nome, e.sigla;""",
    }
    nome = st.selectbox("Consulta pronta", list(consultas), key="sql_pronta")
    sql = st.text_area("SQL (somente leitura, apenas SELECT)", consultas[nome], height=210, key=f"sql_{nome}")
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, flags=re.IGNORECASE):
        st.error("Apenas consultas SELECT são permitidas.")
    else:
        try:
            st.dataframe(banco.executar_sql(sql), hide_index=True, width="stretch")
        except Exception as erro:  # noqa: BLE001 — mostra o erro de SQL ao usuário
            st.error(f"Erro na consulta: {erro}")
    st.caption("As consultas usam o banco original. Filtros e uploads da barra lateral não se aplicam aqui. "
               "A conexão é aberta em modo somente leitura (`mode=ro`).")

# ---------------------------------------------------------------- dados filtrados
with tab4:
    st.caption(app_comum.descrever_filtros(f, base))
    colunas = st.multiselect("Colunas", list(df.columns), default=[
        "data", "regiao", "uf", "setor_consumo", "consumo_milhoes_litros", "desperdicio_percentual",
        "volume_desperdicado_ml", "reservatorios_percentual", "faixa_reservatorio", "chuva_mm",
        "temperatura_media", "consumo_per_capita", "nivel_alerta"], key="tab_cols")
    exibir = df[colunas] if colunas else df
    st.dataframe(exibir, hide_index=True, width="stretch", height=480,
                 column_config={"data": st.column_config.DateColumn("data", format="MM/YYYY")})
    st.download_button("Baixar recorte em CSV", exibir.to_csv(index=False).encode("utf-8-sig"),
                       file_name="consumo_agua_recorte.csv", mime="text/csv", icon=":material/download:")
