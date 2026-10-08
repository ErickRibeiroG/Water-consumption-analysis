"""Modelagem relacional e persistência em SQLite com SQLAlchemy.

Modelo (esquema estrela):

    regioes 1──N estados 1──N medicoes N──1 setores
                                   │
                                   N──1 niveis_alerta

Execute `python -m utils.banco` para (re)criar `database/agua.db` a partir do CSV.
"""

from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import Date, Float, ForeignKey, Integer, String, create_engine, func, insert, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from utils import api_ibge, dados

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_DB = RAIZ / "database" / "agua.db"


class Base(DeclarativeBase):
    pass


class Regiao(Base):
    __tablename__ = "regioes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(20), unique=True)
    estados: Mapped[list["Estado"]] = relationship(back_populates="regiao")


class Estado(Base):
    __tablename__ = "estados"
    id: Mapped[int] = mapped_column(primary_key=True)  # código IBGE da UF
    sigla: Mapped[str] = mapped_column(String(2), unique=True)
    nome: Mapped[str] = mapped_column(String(40))
    populacao_ibge: Mapped[int | None] = mapped_column(Integer)
    regiao_id: Mapped[int] = mapped_column(ForeignKey("regioes.id"))
    regiao: Mapped[Regiao] = relationship(back_populates="estados")


class Setor(Base):
    __tablename__ = "setores"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(20), unique=True)


class NivelAlerta(Base):
    __tablename__ = "niveis_alerta"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(10), unique=True)
    score: Mapped[int] = mapped_column(Integer)


class Medicao(Base):
    __tablename__ = "medicoes"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    estado_id: Mapped[int] = mapped_column(ForeignKey("estados.id"), index=True)
    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id"))
    nivel_alerta_id: Mapped[int] = mapped_column(ForeignKey("niveis_alerta.id"))
    consumo_milhoes_litros: Mapped[float] = mapped_column(Float)
    desperdicio_percentual: Mapped[float] = mapped_column(Float)
    reservatorios_percentual: Mapped[float] = mapped_column(Float)
    chuva_mm: Mapped[float] = mapped_column(Float)
    temperatura_media: Mapped[float] = mapped_column(Float)
    populacao: Mapped[int] = mapped_column(Integer)
    consumo_per_capita: Mapped[float] = mapped_column(Float)


def obter_engine(caminho: Path = CAMINHO_DB):
    return create_engine(f"sqlite:///{caminho.as_posix()}")


def criar_banco(caminho: Path = CAMINHO_DB) -> dict:
    """Recria o banco a partir do CSV tratado + dados do IBGE. Retorna contagens por tabela."""
    df, _ = dados.preparar()
    ibge, _ = api_ibge.dados_ibge()

    # Integração CSV × IBGE: a região informada no CSV deve bater com a oficial.
    regiao_csv = df.groupby("uf", observed=True)["regiao"].first().astype(str)
    oficial = ibge.set_index("uf")["regiao_ibge"]
    divergentes = [uf for uf, r in regiao_csv.items() if oficial.get(uf) != r]
    if divergentes:
        raise ValueError(f"UFs com região divergente do IBGE: {divergentes}")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    engine = obter_engine(caminho)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as s:
        id_regiao = {nome: i for i, nome in enumerate(dados.ORDEM_REGIOES, start=1)}
        s.execute(insert(Regiao), [{"id": i, "nome": n} for n, i in id_regiao.items()])
        s.execute(insert(Estado), [{
            "id": int(r.codigo_ibge), "sigla": r.uf, "nome": r.nome_uf,
            "populacao_ibge": None if pd.isna(r.populacao_ibge) else int(r.populacao_ibge),
            "regiao_id": id_regiao[r.regiao_ibge],
        } for r in ibge.itertuples()])
        id_setor = {nome: i for i, nome in enumerate(dados.ORDEM_SETORES, start=1)}
        s.execute(insert(Setor), [{"id": i, "nome": n} for n, i in id_setor.items()])
        id_alerta = {nome: i for i, nome in enumerate(dados.ORDEM_ALERTA, start=1)}
        s.execute(insert(NivelAlerta), [{"id": i, "nome": n, "score": i} for n, i in id_alerta.items()])

        id_estado = dict(zip(ibge["uf"], ibge["codigo_ibge"].astype(int)))
        registros = [{
            "data": r.data.date(),
            "estado_id": id_estado[r.uf],
            "setor_id": id_setor[r.setor_consumo],
            "nivel_alerta_id": id_alerta[r.nivel_alerta],
            "consumo_milhoes_litros": r.consumo_milhoes_litros,
            "desperdicio_percentual": r.desperdicio_percentual,
            "reservatorios_percentual": r.reservatorios_percentual,
            "chuva_mm": r.chuva_mm,
            "temperatura_media": r.temperatura_media,
            "populacao": int(r.populacao),
            "consumo_per_capita": r.consumo_per_capita,
        } for r in df.itertuples()]
        s.execute(insert(Medicao), registros)
        s.commit()
    return contar_registros(engine)


def contar_registros(engine) -> dict:
    with Session(engine) as s:
        return {m.__tablename__: s.scalar(select(func.count()).select_from(m))
                for m in [Regiao, Estado, Setor, NivelAlerta, Medicao]}


def consulta_medicoes():
    """SELECT com JOINs que reconstrói a tabela analítica a partir do modelo relacional."""
    return (
        select(
            Medicao.data,
            Regiao.nome.label("regiao"),
            Estado.sigla.label("uf"),
            Estado.nome.label("nome_uf"),
            Estado.populacao_ibge,
            Setor.nome.label("setor_consumo"),
            Medicao.consumo_milhoes_litros,
            Medicao.desperdicio_percentual,
            Medicao.reservatorios_percentual,
            Medicao.chuva_mm,
            Medicao.temperatura_media,
            Medicao.populacao,
            Medicao.consumo_per_capita,
            NivelAlerta.nome.label("nivel_alerta"),
        )
        .join(Estado, Medicao.estado_id == Estado.id)
        .join(Regiao, Estado.regiao_id == Regiao.id)
        .join(Setor, Medicao.setor_id == Setor.id)
        .join(NivelAlerta, Medicao.nivel_alerta_id == NivelAlerta.id)
        .order_by(Medicao.data, Medicao.id)
    )


def carregar_do_banco(caminho: Path = CAMINHO_DB) -> pd.DataFrame:
    """Lê as medições do SQLite (criando o banco se necessário) e aplica a engenharia de atributos."""
    if not caminho.exists():
        criar_banco(caminho)
    engine = obter_engine(caminho)
    with engine.connect() as con:
        df = pd.read_sql(consulta_medicoes(), con, parse_dates=["data"])
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.month
    for col, ordem in [("regiao", dados.ORDEM_REGIOES), ("setor_consumo", dados.ORDEM_SETORES),
                       ("nivel_alerta", dados.ORDEM_ALERTA)]:
        df[col] = pd.Categorical(df[col], categories=ordem, ordered=True)
    return dados.criar_atributos(df)


def executar_sql(sql: str, caminho: Path = CAMINHO_DB) -> pd.DataFrame:
    """Executa uma consulta SQL somente leitura (usada na página de dados)."""
    engine = create_engine(f"sqlite:///file:{caminho.as_posix()}?mode=ro&uri=true")
    with engine.connect() as con:
        return pd.read_sql_query(sql, con)


if __name__ == "__main__":
    print(criar_banco())
