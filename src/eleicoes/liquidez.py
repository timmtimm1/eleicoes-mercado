"""As ações mais negociadas antes de cada eleição, por empresa.

Período: 365 dias corridos terminando no último pregão antes do 1º turno. Em 1994 começa em
01/07/1994, quando o Real passou a valer: o volume de antes está em cruzeiro real e não se
compara com o de depois.

Empresa = raiz do ticker (`PETR`, `VALE`), com as raízes da mesma empresa juntas pela tabela
de sucessões (`ABEV` e `AMBV`). Soma-se o volume de todos os papéis (ON, PN, unit) da família;
o representante é o ticker com mais volume, e a classificação (setor, estatal) é a da raiz
dele. A tabela tem as `TOP` empresas de maior volume financeiro.

O volume é nominal e fica na moeda da época: serve para ordenar dentro de uma eleição, não para
comparar uma eleição com outra.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from eleicoes import acoes, calendario, caminhos
from eleicoes.calendario import Eleicao
from eleicoes.empresas import SETOR_SEM_CLASSIFICACAO, Empresa, Sucessao, e_estatal
from eleicoes.empresas import familias as _familias

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
    "raizes_somadas",
    "empresa",
    "setor",
    "estatal",
    "excluida",
]
COLUNAS_DO_RANKING = [*COLUNAS[:9], "raizes_somadas"]


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


def ranking(
    precos: pd.DataFrame, ano: int, top: int = TOP, familias: dict[str, str] | None = None
) -> pd.DataFrame:
    """As `top` empresas de maior volume nos `precos` (já cortados no período) de uma eleição.

    `familias` junta raízes da mesma empresa (ver `empresas.familias`): o volume é somado e a
    raiz que aparece é a do ticker representante, o de maior volume da família inteira.
    """
    if precos.empty:
        return pd.DataFrame(columns=COLUNAS_DO_RANKING)
    familias = familias or {}
    no_periodo = precos["data"].nunique()
    com_negocio = precos[precos["volume"] > 0].copy()
    com_negocio["familia"] = com_negocio["raiz"].map(lambda raiz: familias.get(raiz, raiz))

    # Representante: o ticker de maior volume da família.
    por_ticker = com_negocio.groupby(["familia", "ticker"], as_index=False)["volume"].sum()
    representante = por_ticker.sort_values(
        ["familia", "volume", "ticker"], ascending=[True, False, True]
    ).drop_duplicates("familia")[["familia", "ticker"]]
    # nomres, especi e raiz do representante: os da linha mais recente dele.
    ultimas = com_negocio.sort_values("data").drop_duplicates("ticker", keep="last")[
        ["ticker", "raiz", "nomres", "especi"]
    ]
    por_familia = com_negocio.groupby("familia").agg(
        volume=("volume", "sum"),
        pregoes_com_negocio=("data", "nunique"),
        raizes_somadas=("raiz", lambda raizes: ";".join(sorted(set(raizes)))),
    )
    tabela = por_familia.join(representante.set_index("familia")).reset_index()
    tabela = tabela.merge(ultimas, on="ticker", how="left")
    tabela = tabela.sort_values(["volume", "raiz"], ascending=[False, True]).head(top)
    tabela["ano"] = ano
    tabela["posicao"] = range(1, len(tabela) + 1)
    tabela["volume_milhoes"] = tabela["volume"] / 1e6
    tabela["pregoes_no_periodo"] = no_periodo
    return tabela[COLUNAS_DO_RANKING].reset_index(drop=True)


def classificar(
    tabela: pd.DataFrame,
    eleicao: Eleicao,
    empresas: dict[str, Empresa],
    exclusoes: set[tuple[int, str]],
) -> pd.DataFrame:
    """Acrescenta empresa, setor, estatal e excluida, pela raiz do representante.

    Raiz fora de `empresas.csv` fica com setor `sem_classificacao`: entra só na carteira
    `todas`. Está excluída a empresa cuja raiz (ou qualquer raiz somada) consta das exclusões.
    """
    saida = tabela.copy()
    linhas = [empresas.get(raiz) for raiz in saida["raiz"]]
    saida["empresa"] = [
        e.empresa if e else nomres for e, nomres in zip(linhas, saida["nomres"], strict=True)
    ]
    saida["setor"] = [e.setor if e else SETOR_SEM_CLASSIFICACAO for e in linhas]
    saida["estatal"] = [e_estatal(e, eleicao.primeiro_turno.data) for e in linhas]
    saida["excluida"] = [
        any((eleicao.ano, raiz) in exclusoes for raiz in somadas.split(";"))
        for somadas in saida["raizes_somadas"]
    ]
    return saida[COLUNAS]


def calcular_liquidez(
    eleicoes: list[Eleicao],
    pregoes: pd.DatetimeIndex,
    ler=acoes.ler_precos,
    empresas: dict[str, Empresa] | None = None,
    sucessoes: list[Sucessao] | None = None,
    exclusoes: set[tuple[int, str]] | None = None,
) -> pd.DataFrame:
    """A tabela de liquidez de todas as eleições, ordenada por ano e posição."""
    empresas = {} if empresas is None else empresas
    familias = _familias(sucessoes or [])
    exclusoes = exclusoes or set()
    partes = []
    for eleicao in eleicoes:
        inicio, fim = periodo(eleicao, pregoes)
        do_ano = ranking(ler(inicio, fim), eleicao.ano, familias=familias)
        partes.append(classificar(do_ano, eleicao, empresas, exclusoes))
    return pd.concat(partes, ignore_index=True).sort_values(["ano", "posicao"], ignore_index=True)


def gravar_liquidez(tabela: pd.DataFrame) -> Path:
    caminho = caminhos.RESULTADOS / "liquidez.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tabela.to_csv(caminho, index=False, float_format="%.3f")
    return caminho
