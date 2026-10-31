"""Uma função por fonte de dados; todas devolvem `pd.Series` diária e ordenada."""

import pandas as pd


def limpar(valores: pd.Series, nome: str) -> pd.Series:
    """Deixa a série no formato padrão: float, índice de datas sem repetição e ordenado, sem NaN."""
    serie = pd.Series(valores, dtype="float64").dropna()
    serie.index = pd.DatetimeIndex(serie.index).normalize()
    serie = serie[~serie.index.duplicated(keep="last")].sort_index()
    serie.index.name = "data"
    serie.name = nome
    return serie
