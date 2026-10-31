"""Confere a variação de cada empresa em cada janela com a do Yahoo Finance.

O Yahoo não entra no cálculo, só na conferência. O `Close` dele (`auto_adjust=False`) já vem
ajustado por desdobramento e grupamento, não por dividendo, como a nossa série. Comparamos
só as janelas em que a empresa usa um único ticker (sem emenda) e que começam em 2000 ou
depois; antes disso o Yahoo não tem dado.
"""

import pandas as pd

from eleicoes import caminhos, janelas
from eleicoes.calendario import Eleicao
from eleicoes.carteiras import OK, preco_asof
from eleicoes.fontes import yahoo
from eleicoes.janelas import gravar_tabela

PRIMEIRO_DIA_DO_YAHOO = pd.Timestamp("2000-01-01")
LIMITE_DIFERENCA = 2.0  # pontos percentuais

COLUNAS = [
    "ano",
    "janela",
    "raiz",
    "ticker",
    "inicio",
    "fim",
    "variacao",
    "variacao_yahoo",
    "diferenca",
    "ajustes",
]


def conferir(
    eleicoes: list[Eleicao],
    empresas: pd.DataFrame,
    pregoes: pd.DatetimeIndex,
    atualizar: bool = False,
    buscar=yahoo.fechamento,
) -> tuple[pd.DataFrame, list[str]]:
    """(comparação, tickers que o Yahoo não tem). `empresas` é o `carteiras_empresas.csv`."""
    datas = {
        (e.ano, janela): (inicio, fim)
        for e in eleicoes
        for janela, inicio, fim in janelas.datas_das_janelas(e, pregoes)
    }
    candidatos = empresas[
        (empresas["status"] == OK) & ~empresas["tickers_usados"].fillna("").str.contains(";")
    ]
    yahoo_por_ticker: dict[str, pd.Series | None] = {}
    linhas = []
    for linha in candidatos.itertuples(index=False):
        inicio, fim = datas[(linha.ano, linha.janela)]
        if inicio < PRIMEIRO_DIA_DO_YAHOO:
            continue
        ticker = linha.tickers_usados
        if ticker not in yahoo_por_ticker:
            try:
                yahoo_por_ticker[ticker] = buscar(f"{ticker}.SA", atualizar)
            except Exception:
                yahoo_por_ticker[ticker] = None
        serie = yahoo_por_ticker[ticker]
        if serie is None:
            continue
        p0, p1 = preco_asof(serie, inicio), preco_asof(serie, fim)
        if pd.isna(p0) or pd.isna(p1):
            continue
        variacao_yahoo = (p1 / p0 - 1) * 100
        linhas.append(
            {
                "ano": linha.ano,
                "janela": linha.janela,
                "raiz": linha.raiz,
                "ticker": ticker,
                "inicio": inicio.strftime("%Y-%m-%d"),
                "fim": fim.strftime("%Y-%m-%d"),
                "variacao": linha.variacao,
                "variacao_yahoo": variacao_yahoo,
                "diferenca": linha.variacao - variacao_yahoo,
                "ajustes": "" if pd.isna(linha.ajustes) else linha.ajustes,
            }
        )
    ausentes = sorted(t for t, s in yahoo_por_ticker.items() if s is None)
    return pd.DataFrame(linhas, columns=COLUNAS), ausentes


def gravar(tabela: pd.DataFrame) -> str:
    caminho = caminhos.RESULTADOS / "conferencia_acoes.csv"
    gravar_tabela(tabela, caminho)
    return str(caminho)
