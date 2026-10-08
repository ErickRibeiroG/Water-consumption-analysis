"""Leitura, limpeza, validação e engenharia de atributos da base de consumo de água."""

from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_CSV = RAIZ / "dados" / "simulacao_consumo_agua_brasil.csv"

COLUNAS_OBRIGATORIAS = [
    "ano", "mes", "data", "regiao", "uf", "setor_consumo",
    "consumo_milhoes_litros", "desperdicio_percentual", "reservatorios_percentual",
    "chuva_mm", "temperatura_media", "populacao", "consumo_per_capita", "nivel_alerta",
]

ORDEM_REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
ORDEM_SETORES = ["Residencial", "Comercial", "Industrial", "Agrícola", "Público"]
ORDEM_ALERTA = ["Baixo", "Médio", "Alto", "Crítico"]
ORDEM_ESTACOES = ["Verão", "Outono", "Inverno", "Primavera"]
ORDEM_FAIXA_RESERVATORIO = ["Crítico (<30%)", "Atenção (30–50%)", "Moderado (50–70%)", "Confortável (≥70%)"]

# Estações do ano no hemisfério sul (meteorológicas).
ESTACAO_POR_MES = {
    12: "Verão", 1: "Verão", 2: "Verão",
    3: "Outono", 4: "Outono", 5: "Outono",
    6: "Inverno", 7: "Inverno", 8: "Inverno",
    9: "Primavera", 10: "Primavera", 11: "Primavera",
}

# Faixas válidas usadas na validação de domínio.
LIMITES = {
    "consumo_milhoes_litros": (0, None),
    "desperdicio_percentual": (0, 100),
    "reservatorios_percentual": (0, 100),
    "chuva_mm": (0, None),
    "temperatura_media": (-10, 50),
    "populacao": (1, None),
    "consumo_per_capita": (0, None),
    "mes": (1, 12),
}

COLUNAS_NUMERICAS = [
    "consumo_milhoes_litros", "desperdicio_percentual", "reservatorios_percentual",
    "chuva_mm", "temperatura_media", "populacao", "consumo_per_capita",
]

ROTULOS = {
    "consumo_milhoes_litros": "Consumo (mi L)",
    "desperdicio_percentual": "Desperdício (%)",
    "reservatorios_percentual": "Reservatórios (%)",
    "chuva_mm": "Chuva (mm)",
    "temperatura_media": "Temperatura (°C)",
    "populacao": "População",
    "consumo_per_capita": "Per capita (L/hab/dia)",
    "volume_desperdicado_ml": "Volume desperdiçado (mi L)",
    "consumo_efetivo_ml": "Consumo efetivo (mi L)",
    "score_alerta": "Score de alerta (1–4)",
}


def ler_csv(origem=CAMINHO_CSV) -> pd.DataFrame:
    """Lê o CSV bruto (caminho ou arquivo enviado por upload)."""
    return pd.read_csv(origem, encoding="utf-8")


def validar_esquema(df: pd.DataFrame) -> list[str]:
    """Retorna a lista de colunas obrigatórias ausentes (vazia se o esquema estiver ok)."""
    return [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]


def limpar(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Padroniza tipos e textos, remove duplicatas e registros fora do domínio.

    Retorna o DataFrame limpo e um relatório com o que foi feito em cada etapa.
    """
    rel = {"linhas_originais": len(df)}
    df = df.copy()

    # Textos: remove espaços e padroniza caixa.
    for col in ["regiao", "setor_consumo", "nivel_alerta"]:
        df[col] = df[col].astype("string").str.strip().str.title()
    df["uf"] = df["uf"].astype("string").str.strip().str.upper()

    # Tipos numéricos (valores não numéricos viram NaN).
    for col in COLUNAS_NUMERICAS + ["ano", "mes"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["data"] = pd.to_datetime(df["data"], errors="coerce")

    rel["nulos_por_coluna"] = df.isna().sum()[lambda s: s > 0].to_dict()
    df = df.dropna(subset=COLUNAS_OBRIGATORIAS)
    rel["removidas_nulos"] = rel["linhas_originais"] - len(df)

    antes = len(df)
    df = df.drop_duplicates()
    rel["removidas_duplicadas"] = antes - len(df)

    # Validação de domínio.
    fora = pd.Series(False, index=df.index)
    rel["fora_do_dominio"] = {}
    for col, (mn, mx) in LIMITES.items():
        mask = pd.Series(False, index=df.index)
        if mn is not None:
            mask |= df[col] < mn
        if mx is not None:
            mask |= df[col] > mx
        if mask.any():
            rel["fora_do_dominio"][col] = int(mask.sum())
        fora |= mask
    # Consistência entre data e colunas ano/mes.
    inconsistente_data = (df["data"].dt.year != df["ano"]) | (df["data"].dt.month != df["mes"])
    rel["data_inconsistente"] = int(inconsistente_data.sum())
    fora |= inconsistente_data
    df = df[~fora]
    rel["removidas_dominio"] = int(fora.sum())

    df["ano"] = df["ano"].astype(int)
    df["mes"] = df["mes"].astype(int)
    df["populacao"] = df["populacao"].astype(int)

    # Categorias ordenadas (facilitam ordenação e gráficos).
    df["regiao"] = pd.Categorical(df["regiao"], categories=ORDEM_REGIOES, ordered=True)
    df["setor_consumo"] = pd.Categorical(df["setor_consumo"], categories=ORDEM_SETORES, ordered=True)
    df["nivel_alerta"] = pd.Categorical(df["nivel_alerta"], categories=ORDEM_ALERTA, ordered=True)
    # Valores fora das categorias conhecidas viram NaN e são descartados.
    invalidas = df[["regiao", "setor_consumo", "nivel_alerta"]].isna().any(axis=1)
    rel["removidas_categoria_invalida"] = int(invalidas.sum())
    df = df[~invalidas]

    rel["linhas_finais"] = len(df)
    return df.reset_index(drop=True), rel


def criar_atributos(df: pd.DataFrame) -> pd.DataFrame:
    """Engenharia de atributos: métricas derivadas, calendário e faixas."""
    df = df.copy()
    df["volume_desperdicado_ml"] = (df["consumo_milhoes_litros"] * df["desperdicio_percentual"] / 100).round(3)
    df["consumo_efetivo_ml"] = (df["consumo_milhoes_litros"] - df["volume_desperdicado_ml"]).round(3)
    df["trimestre"] = df["data"].dt.quarter
    df["ano_mes"] = df["data"].dt.to_period("M").astype(str)
    df["estacao"] = pd.Categorical(df["mes"].map(ESTACAO_POR_MES), categories=ORDEM_ESTACOES, ordered=True)
    df["periodo_chuvoso"] = df["mes"].isin([10, 11, 12, 1, 2, 3])
    df["faixa_reservatorio"] = pd.cut(
        df["reservatorios_percentual"], bins=[0, 30, 50, 70, 100.01],
        labels=ORDEM_FAIXA_RESERVATORIO, right=False, include_lowest=True,
    )
    df["score_alerta"] = df["nivel_alerta"].cat.codes + 1
    df["alerta_elevado"] = df["nivel_alerta"].isin(["Alto", "Crítico"])
    df["reservatorio_critico"] = df["reservatorios_percentual"] < 30

    # Outliers de chuva pelo critério do intervalo interquartil (IQR).
    q1, q3 = df["chuva_mm"].quantile([0.25, 0.75])
    df["chuva_outlier"] = df["chuva_mm"] > q3 + 1.5 * (q3 - q1)

    # Per capita recalculado a partir de consumo e população (para auditoria de consistência).
    dias = df["data"].dt.days_in_month
    df["per_capita_recalculado"] = (df["consumo_milhoes_litros"] * 1e6 / df["populacao"] / dias).round(2)
    return df


def preparar(origem=CAMINHO_CSV) -> tuple[pd.DataFrame, dict]:
    """Pipeline completo: leitura → limpeza → atributos."""
    bruto = ler_csv(origem)
    faltando = validar_esquema(bruto)
    if faltando:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(faltando)}")
    limpo, rel = limpar(bruto)
    return criar_atributos(limpo), rel


def auditoria_consistencia(df: pd.DataFrame) -> pd.DataFrame:
    """Testes de coerência entre variáveis que deveriam estar relacionadas."""
    n = len(df)
    r_critico = 1.96 / np.sqrt(n) if n else np.nan
    corr = lambda a, b: df[a].corr(df[b]) if n > 2 else np.nan  # noqa: E731
    reserv_por_alerta = df.groupby("nivel_alerta", observed=True)["reservatorios_percentual"].mean()
    amplitude = reserv_por_alerta.max() - reserv_por_alerta.min() if len(reserv_por_alerta) else np.nan
    linhas = [
        ("Alerta × reservatórios",
         "Alertas mais graves deveriam ocorrer com reservatórios mais baixos.",
         f"Amplitude da média de reservatório entre níveis de alerta: {amplitude:.1f} p.p.",
         amplitude > 10),
        ("Chuva × reservatórios",
         "Mais chuva deveria elevar o nível dos reservatórios.",
         f"r de Pearson = {corr('chuva_mm', 'reservatorios_percentual'):+.3f} (limite de significância ≈ ±{r_critico:.3f})",
         abs(corr("chuva_mm", "reservatorios_percentual")) > r_critico),
        ("Temperatura × consumo",
         "Dias mais quentes costumam elevar o consumo.",
         f"r de Pearson = {corr('temperatura_media', 'consumo_milhoes_litros'):+.3f}",
         abs(corr("temperatura_media", "consumo_milhoes_litros")) > r_critico),
        ("Per capita informado × recalculado",
         "consumo ÷ população ÷ dias deveria reproduzir o per capita.",
         f"r de Pearson = {corr('consumo_per_capita', 'per_capita_recalculado'):+.3f}; "
         f"mediana recalculada = {df['per_capita_recalculado'].median():.2f} L/hab/dia",
         abs(corr("consumo_per_capita", "per_capita_recalculado")) > 0.5),
        ("População estável por UF",
         "A população de um estado deveria variar pouco entre meses.",
         f"Coeficiente de variação médio por UF = {(df.groupby('uf')['populacao'].std() / df.groupby('uf')['populacao'].mean()).mean():.0%}",
         (df.groupby("uf")["populacao"].std() / df.groupby("uf")["populacao"].mean()).mean() < 0.1),
    ]
    return pd.DataFrame(linhas, columns=["Teste", "Expectativa", "Resultado", "Coerente"])


def calcular_kpis(df: pd.DataFrame) -> dict:
    """KPIs principais do recorte informado."""
    if df.empty:
        return {k: np.nan for k in [
            "consumo_total", "volume_desperdicado", "desperdicio_ponderado", "reservatorio_medio",
            "per_capita_medio", "pct_alerta_elevado", "pct_reservatorio_critico", "chuva_media", "registros"]}
    consumo = df["consumo_milhoes_litros"].sum()
    desperd = df["volume_desperdicado_ml"].sum()
    return {
        "consumo_total": consumo,
        "volume_desperdicado": desperd,
        "desperdicio_ponderado": desperd / consumo * 100,
        "reservatorio_medio": df["reservatorios_percentual"].mean(),
        "per_capita_medio": df["consumo_per_capita"].mean(),
        "pct_alerta_elevado": df["alerta_elevado"].mean() * 100,
        "pct_reservatorio_critico": df["reservatorio_critico"].mean() * 100,
        "chuva_media": df["chuva_mm"].mean(),
        "registros": len(df),
    }


def serie_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega o recorte por mês e calcula média móvel, variação anual e tendência."""
    m = (df.groupby("data")
           .agg(consumo=("consumo_milhoes_litros", "sum"),
                desperdicado=("volume_desperdicado_ml", "sum"),
                reservatorio=("reservatorios_percentual", "mean"),
                chuva=("chuva_mm", "mean"),
                temperatura=("temperatura_media", "mean"))
           .sort_index())
    if m.empty:
        return m
    # Garante meses contínuos para que rolling/pct_change usem a janela correta.
    m = m.asfreq("MS")
    m["desperdicio_pct"] = m["desperdicado"] / m["consumo"] * 100
    m["consumo_mm12"] = m["consumo"].rolling(12, min_periods=12).mean()
    m["reservatorio_mm12"] = m["reservatorio"].rolling(12, min_periods=12).mean()
    m["consumo_var_anual"] = m["consumo"].pct_change(12) * 100
    validos = m["consumo"].notna()
    if validos.sum() >= 2:
        x = np.arange(len(m))[validos]
        coef = np.polyfit(x, m.loc[validos, "consumo"], 1)
        m["consumo_tendencia"] = np.polyval(coef, np.arange(len(m)))
        m.attrs["inclinacao_mensal"] = coef[0]
    return m


def formatar_num(valor, casas=1, sufixo="") -> str:
    """Formata número no padrão brasileiro (1.234,5)."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    txt = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{txt}{sufixo}"
