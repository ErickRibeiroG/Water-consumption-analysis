import streamlit as st

from utils import app_comum, dados, estilo
from utils.dados import formatar_num as fmt

df, base, f = app_comum.obter_contexto()
pal = estilo.paleta()  # cores do tema ativo (claro/escuro)

# Selos de prioridade: tom suave da cor de status (fundo translúcido + borda leve + texto no mesmo matiz).
_SELOS = {
    #          RGB do status     texto (claro)  texto (escuro)
    "Alta":  ((208, 59, 59),   "#9b2a2a",     "#f3a5a5"),
    "Média": ((250, 178, 25),  "#7a5200",     "#f5cd73"),
    "Baixa": ((12, 163, 12),   "#1d6b1d",     "#8fd68f"),
}


def selo(nivel: str) -> str:
    (r, g, b), texto_claro, texto_escuro = _SELOS[nivel]
    escuro = pal.MODO == "dark"
    fundo = f"rgba({r},{g},{b},{0.16 if escuro else 0.10})"
    borda = f"rgba({r},{g},{b},{0.35 if escuro else 0.30})"
    return (f'<span style="display:inline-block; padding:2px 12px; border-radius:999px; background:{fundo}; '
            f'border:1px solid {borda}; color:{texto_escuro if escuro else texto_claro}; font-size:0.85em; '
            f'font-weight:600; white-space:nowrap;">{nivel}</span>')


st.title("Conclusão executiva")
st.caption(app_comum.descrever_filtros(f, base))
if app_comum.aviso_vazio(df):
    st.stop()

k = dados.calcular_kpis(df)
m = dados.serie_mensal(df)
aud = dados.auditoria_consistencia(df)
tend_pct = m.attrs.get("inclinacao_mensal", 0) * 12 / m["consumo"].mean() * 100
setor_desp = df.groupby("setor_consumo", observed=True)["desperdicio_percentual"].mean()
lider = df.groupby("regiao", observed=True)["consumo_milhoes_litros"].sum().idxmax()
num = ["consumo_milhoes_litros", "desperdicio_percentual", "reservatorios_percentual", "chuva_mm",
       "temperatura_media", "consumo_per_capita", "score_alerta"]
corr = df[num].astype(float).corr().abs()
max_r = corr.where(~(corr == 1)).max().max()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Consumo total", f"{fmt(k['consumo_total'] / 1000, 1)} bi L", border=True)
c2.metric("Perdido com desperdício", f"{fmt(k['volume_desperdicado'] / 1000, 1)} bi L", border=True)
c3.metric("Alerta Alto/Crítico", fmt(k["pct_alerta_elevado"], 1, "%"), border=True)
c4.metric("Testes de coerência", f"{int(aud['Coerente'].sum())} de {len(aud)}", border=True)

st.markdown(f"""
### Principais achados

1. **Desperdício é o maior problema e é sistêmico.** {fmt(k['desperdicio_ponderado'], 1, '%')} da água consumida se perde,
   o que soma **{fmt(k['volume_desperdicado'] / 1000, 1)} bilhões de litros** no recorte. A diferença entre setores é de
   apenas {fmt(setor_desp.max() - setor_desp.min(), 1)} p.p., e a dispersão entre regiões é igualmente pequena. Não há um
   "vilão" isolado: as perdas estão espalhadas por todo o sistema.
2. **Segurança hídrica merece atenção constante.** {fmt(k['pct_reservatorio_critico'], 0, '%')} dos registros têm reservatórios
   abaixo de 30%, e {fmt(k['pct_alerta_elevado'], 0, '%')} estão em alerta Alto ou Crítico.
3. **O consumo é estável.** A tendência linear é de {fmt(tend_pct, 2, '%')} ao ano e não há sazonalidade estatisticamente
   relevante. As variações mensais e anuais parecem ruído.
4. **Diferenças regionais refletem o volume de registros, não intensidade de uso.** **{lider}** lidera o consumo total porque
   tem mais estados e séries na base. Com métricas normalizadas (média por registro, per capita), as regiões ficam equivalentes.
5. **O clima não explica o consumo nem os reservatórios.** A maior correlação entre as variáveis numéricas é
   |r| = {fmt(max_r, 3)}, sem poder explicativo prático.
6. **A base tem problemas estruturais de qualidade.** O alerta não segue o reservatório, a população não bate com o IBGE
   e o per capita não fecha com consumo ÷ população. A auditoria indica **dados sintéticos com variáveis independentes**.

### Recomendações

| Prioridade | Ação | Indicador de acompanhamento |
|---|---|---|
| {selo('Alta')} | Programa de **redução de perdas** (detecção de vazamentos, setorização, troca de redes antigas) | Taxa de desperdício (meta: < 25%) |
| {selo('Alta')} | **Recalcular o nível de alerta** com regras objetivas a partir do reservatório (`faixa_reservatorio`) | Coerência alerta × reservatório |
| {selo('Média')} | **Monitoramento contínuo** dos estados com mais meses em reservatório crítico | % de registros com reservatório < 30% |
| {selo('Média')} | **Governança de dados**: validar população (IBGE), per capita e alertas na origem | Testes de coerência aprovados |
| {selo('Baixa')} | Ampliar a cobertura para as 27 UFs e integrar fontes oficiais (SNIS/ANA) | Nº de UFs cobertas |

### Limitações
- A base é **simulada**: as conclusões quantitativas ilustram o método e não devem embasar decisões reais.
- Cobertura parcial: **{base['uf'].nunique()} de 27 UFs**, com número desigual de séries por estado.
- A população de referência do IBGE é de 2021 e foi usada só como comparação.

### O que este projeto demonstra
Um **pipeline completo e reutilizável**: leitura e validação → limpeza → engenharia de atributos → persistência relacional
(SQLAlchemy + SQLite) → integração com API (IBGE) → análise exploratória e estatística → dashboard interativo
multipágina. Basta enviar uma base real pelo **upload** na barra lateral para que todas as páginas, KPIs e interpretações
sejam recalculados.
""", unsafe_allow_html=True)
