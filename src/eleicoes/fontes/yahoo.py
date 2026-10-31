"""Fechamentos do Yahoo Finance."""

import re

import pandas as pd
import yfinance as yf

from eleicoes import caminhos
from eleicoes.fontes import limpar


def _arquivo(ticker: str):
    seguro = re.sub(r"[^A-Za-z0-9]+", "_", ticker).strip("_")
    return caminhos.CACHE / "yahoo" / f"{seguro}.csv"


def fechamento(ticker: str, atualizar: bool) -> pd.Series:
    """Fechamento diário sem ajuste de dividendos, histórico inteiro."""
    arquivo = _arquivo(ticker)
    if atualizar or not arquivo.exists():
        historico = yf.Ticker(ticker).history(period="max", auto_adjust=False)["Close"]
        if historico.empty:
            raise RuntimeError(f"Yahoo não devolveu dados para {ticker}")
        # O índice vem com fuso (hora local da bolsa): fica só a data.
        historico.index = pd.DatetimeIndex(historico.index).tz_localize(None).normalize()
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        historico.rename("fechamento").rename_axis("data").to_csv(arquivo)
    lido = pd.read_csv(arquivo, index_col="data", parse_dates=["data"])["fechamento"]
    return limpar(lido, ticker)
