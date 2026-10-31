"""Conferência dos dados brutos contra números publicados na imprensa.

Lê só os CSVs de `dados/series/`; não baixa nada. Se uma checagem falhar, o esperado e a
tolerância ficam como estão: o desacordo é o resultado.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from eleicoes.series import ler

ANOS_DE_ELEICAO = range(1994, 2027, 4)
COLUNAS = [
    "checagem",
    "serie",
    "data",
    "esperado",
    "obtido",
    "diferenca",
    "tolerancia",
    "ok",
    "fonte",
]


@dataclass(frozen=True)
class Checagem:
    """Um número da imprensa e a série onde ele deve aparecer.

    Em `variacao`, o valor é a mudança percentual contra o pregão anterior e a tolerância
    é em pontos percentuais. Em `nivel`, a tolerância é absoluta, na unidade da série.
    """

    texto: str
    serie: str
    data: str
    esperado: float
    tolerancia: float
    fonte: str
    variacao: bool = False


def _fechamento(esperado: float, percentual: float) -> float:
    """Tolerância absoluta equivalente a `percentual` % do valor esperado."""
    return abs(esperado) * percentual / 100


FECHAMENTO_1T_2026 = 206911.89
FECHAMENTO_2T_2026 = 176608.0
FECHAMENTO_OUTUBRO_2026 = 167921.80

CHECAGENS = [
    Checagem(
        "Ibovespa no pregão após o 1º turno de 2026 (fechamento)",
        "ibov",
        "2026-10-05",
        FECHAMENTO_1T_2026,
        _fechamento(FECHAMENTO_1T_2026, 0.1),
        "Times Brasil e Correio do Estado, 05/10/2026",
    ),
    Checagem(
        "Ibovespa: variação em 05/10/2026",
        "ibov",
        "2026-10-05",
        7.70,
        0.05,
        "Times Brasil e Correio do Estado, 05/10/2026",
        variacao=True,
    ),
    Checagem(
        "Ibovespa no pregão após o 2º turno de 2026 (fechamento)",
        "ibov",
        "2026-10-26",
        FECHAMENTO_2T_2026,
        _fechamento(FECHAMENTO_2T_2026, 0.1),
        "InfoMoney, 26/10/2026",
    ),
    Checagem(
        "Ibovespa: variação em 26/10/2026",
        "ibov",
        "2026-10-26",
        -13.88,
        0.05,
        "InfoMoney, 26/10/2026",
        variacao=True,
    ),
    Checagem(
        "Ibovespa: fechamento de outubro de 2026",
        "ibov",
        "2026-10-30",
        FECHAMENTO_OUTUBRO_2026,
        _fechamento(FECHAMENTO_OUTUBRO_2026, 0.1),
        "Gazeta Mercantil, 31/10/2026",
    ),
    Checagem(
        "Dólar BCB em 26/10/2026",
        "dolar",
        "2026-10-26",
        5.5007,
        0.0001,
        "BCB, consulta de 31/10/2026",
    ),
    Checagem(
        "Dólar: variação em 26/10/2026",
        "dolar",
        "2026-10-26",
        9.19,
        0.05,
        "Imprensa (alta de 9,2% pela PTAX), 26/10/2026",
        variacao=True,
    ),
    Checagem(
        "Ibovespa: variação após o 1º turno de 2022",
        "ibov",
        "2022-10-03",
        5.54,
        0.05,
        "Elos Ayta via Times Brasil, 05/10/2026",
        variacao=True,
    ),
    Checagem(
        "Tesouro prefixado ~10 anos antes do 2º turno de 2026",
        "prefixado_10a",
        "2026-10-23",
        12.90,
        0.05,
        "projeto valuation-seguradoras, 30/10/2026",
    ),
    Checagem(
        "Tesouro prefixado ~10 anos após o 2º turno de 2026",
        "prefixado_10a",
        "2026-10-26",
        15.42,
        0.05,
        "projeto valuation-seguradoras, 30/10/2026",
    ),
]


def variacao_percentual(serie: pd.Series, data: pd.Timestamp) -> float:
    """Variação do fechamento de `data` sobre o pregão anterior que existe na série."""
    if data not in serie.index:
        return np.nan
    posicao = serie.index.get_loc(data)
    if posicao == 0:
        return np.nan
    return (serie.iloc[posicao] / serie.iloc[posicao - 1] - 1) * 100


def avaliar(checagem: Checagem, serie: pd.Series) -> dict:
    """Compara um número da imprensa com a série e devolve a linha da tabela."""
    data = pd.Timestamp(checagem.data)
    if checagem.variacao:
        obtido = variacao_percentual(serie, data)
    else:
        obtido = float(serie.get(data, np.nan))
    diferenca = obtido - checagem.esperado
    return {
        "checagem": checagem.texto,
        "serie": checagem.serie,
        "data": checagem.data,
        "esperado": checagem.esperado,
        "obtido": obtido,
        "diferenca": diferenca,
        "tolerancia": checagem.tolerancia,
        # Com dado ausente, `diferenca` é NaN e a comparação dá falso.
        "ok": bool(abs(diferenca) <= checagem.tolerancia),
        "fonte": checagem.fonte,
    }


def conferir(checagens: list[Checagem] | None = None) -> pd.DataFrame:
    """Tabela com uma linha por checagem."""
    series = {}
    linhas = []
    for checagem in checagens or CHECAGENS:
        if checagem.serie not in series:
            series[checagem.serie] = ler(checagem.serie)
        linhas.append(avaliar(checagem, series[checagem.serie]))
    return pd.DataFrame(linhas, columns=COLUNAS)


def comparar_series(
    principal: pd.Series, outra: pd.Series, inicio: str, fim: str
) -> dict[str, object]:
    """Compara duas séries nas datas que as duas têm, dentro de [inicio, fim]."""
    recorte = slice(pd.Timestamp(inicio), pd.Timestamp(fim))
    a, b = principal.loc[recorte], outra.loc[recorte]
    comuns = a.index.intersection(b.index)
    diferenca = ((a.loc[comuns] / b.loc[comuns] - 1) * 100).abs()
    return {
        "datas_comuns": len(comuns),
        "maior_diferenca_pct": diferenca.max() if len(comuns) else np.nan,
        "mediana_diferenca_pct": diferenca.median() if len(comuns) else np.nan,
        "so_yahoo": list(a.index.difference(b.index)),
        "so_ipeadata": list(b.index.difference(a.index)),
    }


def _resumir_datas(datas: list[pd.Timestamp], limite: int = 3) -> str:
    """ "12 (1994-07-04, 1994-07-05, ...)": quantas são e as primeiras."""
    if not datas:
        return "0"
    exemplos = ", ".join(d.strftime("%Y-%m-%d") for d in datas[:limite])
    return f"{len(datas)} ({exemplos}{', ...' if len(datas) > limite else ''})"


def comparar_ibov() -> pd.DataFrame:
    """Yahoo × Ipeadata no Ibovespa, de 1º de julho do ano da eleição a 31/12 do ano seguinte.

    A diferença é `|yahoo / ipeadata − 1|` em %, só nas datas que as duas séries têm.
    """
    yahoo, ipeadata = ler("ibov"), ler("ibov_ipea")
    linhas = []
    for ano in ANOS_DE_ELEICAO:
        resultado = comparar_series(yahoo, ipeadata, f"{ano}-07-01", f"{ano + 1}-12-31")
        linhas.append(
            {
                "ano": ano,
                "datas_comuns": resultado["datas_comuns"],
                "maior_diferenca_pct": resultado["maior_diferenca_pct"],
                "mediana_diferenca_pct": resultado["mediana_diferenca_pct"],
                "so_yahoo": _resumir_datas(resultado["so_yahoo"]),
                "so_ipeadata": _resumir_datas(resultado["so_ipeadata"]),
            }
        )
    return pd.DataFrame(linhas)
