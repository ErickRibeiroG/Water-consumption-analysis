"""Consumo das APIs públicas do IBGE com cache local em `dados/ibge/`.

- Localidades: nomes, siglas e regiões das 27 UFs.
- Malhas: GeoJSON com o contorno das UFs (usado no mapa).
- Agregados (SIDRA, tabela 6579): estimativa oficial de população por UF.

Se a API estiver indisponível, os arquivos em cache são usados, garantindo que o
dashboard continue funcionando no Streamlit Cloud.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parent.parent
PASTA_CACHE = RAIZ / "dados" / "ibge"
BASE = "https://servicodados.ibge.gov.br/api"
TIMEOUT = 20

URL_ESTADOS = f"{BASE}/v1/localidades/estados"
URL_MALHA = f"{BASE}/v3/malhas/paises/BR"
URL_POPULACAO = f"{BASE}/v3/agregados/6579/periodos/{{ano}}/variaveis/9324"


def _buscar_json(url: str, params: dict | None, arquivo: str, atualizar: bool) -> tuple[object, str]:
    """Busca JSON na API (ou no cache). Retorna (dados, origem)."""
    caminho = PASTA_CACHE / arquivo
    if caminho.exists() and not atualizar:
        return json.loads(caminho.read_text(encoding="utf-8")), "cache"
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        dados = resp.json()
        PASTA_CACHE.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        return dados, "api"
    except (requests.RequestException, ValueError):
        if caminho.exists():
            return json.loads(caminho.read_text(encoding="utf-8")), "cache (API indisponível)"
        raise


def buscar_estados(atualizar: bool = False) -> tuple[pd.DataFrame, str]:
    """DataFrame com código IBGE, sigla, nome e região de cada UF."""
    dados, origem = _buscar_json(URL_ESTADOS, None, "estados.json", atualizar)
    df = pd.DataFrame([{
        "codigo_ibge": int(e["id"]),
        "uf": e["sigla"],
        "nome_uf": e["nome"],
        "regiao_ibge": e["regiao"]["nome"],
    } for e in dados]).sort_values("uf").reset_index(drop=True)
    return df, origem


def _area_assinada(anel: list) -> float:
    """Fórmula do laço (shoelace): positiva = sentido anti-horário."""
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1])) / 2


def _reorientar(geometria: dict) -> None:
    """Ajusta o sentido dos anéis para o padrão do d3-geo/Plotly.

    O IBGE segue a RFC 7946 (anel externo anti-horário), mas o Plotly espera o anel externo
    no sentido horário; sem o ajuste, cada estado é desenhado como "o mundo menos o estado".
    """
    poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    for poligono in poligonos:
        for i, anel in enumerate(poligono):
            externo = i == 0
            if (_area_assinada(anel) > 0) == externo:  # externo anti-horário ou buraco horário
                anel.reverse()


def buscar_malha_ufs(atualizar: bool = False) -> tuple[dict, str]:
    """GeoJSON das UFs; cada feature recebe a propriedade `uf` (sigla)."""
    params = {"formato": "application/vnd.geo+json", "qualidade": "minima", "intrarregiao": "UF"}
    geo, origem = _buscar_json(URL_MALHA, params, "malha_ufs.geojson", atualizar)
    estados, _ = buscar_estados(atualizar=False)
    sigla_por_codigo = dict(zip(estados["codigo_ibge"].astype(str), estados["uf"]))
    for f in geo["features"]:
        f["properties"]["uf"] = sigla_por_codigo.get(str(f["properties"]["codarea"]))
        _reorientar(f["geometry"])
    return geo, origem


def buscar_populacao(ano: int = 2021, atualizar: bool = False) -> tuple[pd.DataFrame, str]:
    """Estimativa de população residente por UF (IBGE/SIDRA, tabela 6579)."""
    dados, origem = _buscar_json(
        URL_POPULACAO.format(ano=ano), {"localidades": "N3[all]"}, f"populacao_{ano}.json", atualizar
    )
    series = dados[0]["resultados"][0]["series"]
    df = pd.DataFrame([{
        "codigo_ibge": int(s["localidade"]["id"]),
        "populacao_ibge": int(s["serie"][str(ano)]),
    } for s in series])
    return df, origem


def dados_ibge(atualizar: bool = False) -> tuple[pd.DataFrame, dict]:
    """Integra localidades + população em uma tabela única por UF."""
    estados, o1 = buscar_estados(atualizar)
    pop, o2 = buscar_populacao(atualizar=atualizar)
    tabela = estados.merge(pop, on="codigo_ibge", how="left")
    info = {"estados": o1, "populacao": o2, "consultado_em": datetime.now().strftime("%d/%m/%Y %H:%M")}
    return tabela, info


if __name__ == "__main__":
    tabela, info = dados_ibge(atualizar=True)
    buscar_malha_ufs(atualizar=True)
    print(tabela.head(), info, sep="\n")
