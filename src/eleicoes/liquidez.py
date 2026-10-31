"""As ações mais negociadas antes de cada eleição, por empresa.

Período: 365 dias corridos terminando no último pregão antes do 1º turno. Em 1994 começa em
01/07/1994, quando o Real passou a valer: o volume de antes está em cruzeiro real e não se
compara com o de depois.

Empresa = raiz do ticker (`PETR`, `VALE`). Por raiz soma-se o volume de todos os papéis (ON, PN,
unit); o representante é o ticker com mais volume. A tabela tem as `TOP` raízes de maior volume
financeiro e serve de matéria-prima para classificar à mão por setor e por estatal ou privada.

O volume é nominal e fica na moeda da época: serve para ordenar dentro de uma eleição, não para
comparar uma eleição com outra.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from eleicoes import acoes, calendario, caminhos
from eleicoes.calendario import Eleicao

TOP = 60
DIAS_DO_PERIODO = 365

COLUNAS = [
    "ano",
    "posicao",
    "raiz",
    "ticker",
    "nomres",
    "especi",
    "volume_milhoes",
    "pregoes_com_negocio",
    "pregoes_no_periodo",
]


def periodo(eleicao: Eleicao, pregoes: pd.DatetimeIndex) -> tuple[date, date]:
    """(início, fim) do período de liquidez, os dois dias inclusive.

    O fim é o último pregão antes do 1º turno; o início, 364 dias antes (365 dias corridos no
    total), nunca antes de 01/07/1994.
    """
    ultimo = calendario.ultimo_pregao_antes(eleicao.primeiro_turno.data, pregoes)
    if ultimo is None:
        raise ValueError(f"sem pregão antes do 1º turno de {eleicao.ano}")
    fim = ultimo.date()
    inicio = fim - timedelta(days=DIAS_DO_PERIODO - 1)
    return max(inicio, acoes.INICIO_REAL), fim


def ranking(precos: pd.DataFrame, ano: int, top: int = TOP) -> pd.DataFrame:
    """As `top` raízes de maior volume nos `precos` (já cortados no período) de uma eleição."""
    if precos.empty:
        return pd.DataFrame(columns=COLUNAS)
    no_periodo = precos["data"].nunique()
    com_negocio = precos[precos["volume"] > 0]

    # Representante: o ticker de maior volume da raiz, com o nome e a espécie das linhas dele.
    por_ticker = com_negocio.groupby(["raiz", "ticker"], as_index=False)["volume"].sum()
    representante = por_ticker.sort_values(
        ["raiz", "volume", "ticker"], ascending=[True, False, True]
    ).drop_duplicates("raiz")[["raiz", "ticker"]]
    # nomres e especi do representante: os da linha mais recente dele.
    ultimas = com_negocio.sort_values("data").drop_duplicates("ticker", keep="last")[
        ["ticker", "nomres", "especi"]
    ]
    por_raiz = com_negocio.groupby("raiz").agg(
        volume=("volume", "sum"), pregoes_com_negocio=("data", "nunique")
    )
    tabela = por_raiz.join(representante.set_index("raiz")).reset_index()
    tabela = tabela.merge(ultimas, on="ticker", how="left")
    tabela = tabela.sort_values(["volume", "raiz"], ascending=[False, True]).head(top)
    tabela["ano"] = ano
    tabela["posicao"] = range(1, len(tabela) + 1)
    tabela["volume_milhoes"] = tabela["volume"] / 1e6
    tabela["pregoes_no_periodo"] = no_periodo
    return tabela[COLUNAS].reset_index(drop=True)


def calcular_liquidez(
    eleicoes: list[Eleicao], pregoes: pd.DatetimeIndex, ler=acoes.ler_precos
) -> pd.DataFrame:
    """A tabela de liquidez de todas as eleições, ordenada por ano e posição."""
    partes = []
    for eleicao in eleicoes:
        inicio, fim = periodo(eleicao, pregoes)
        partes.append(ranking(ler(inicio, fim), eleicao.ano))
    return pd.concat(partes, ignore_index=True).sort_values(["ano", "posicao"], ignore_index=True)


def gravar_liquidez(tabela: pd.DataFrame) -> Path:
    caminho = caminhos.RESULTADOS / "liquidez.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tabela.to_csv(caminho, index=False, float_format="%.3f")
    return caminho
