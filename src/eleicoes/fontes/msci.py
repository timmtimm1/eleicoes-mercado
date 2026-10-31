"""MSCI Emerging Markets em dólar, pela API pública de gráficos do site da MSCI."""

import json
from datetime import date

import pandas as pd

from eleicoes.baixar import baixar
from eleicoes.fontes import limpar

CODIGO = "891800"
# A data mínima que a API aceita.
PRIMEIRO_DIA = date(1997, 1, 1)
URL = (
    "https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph"
    "?currency_symbol=USD&index_variant=STRD&start_date={inicio:%Y%m%d}&end_date={fim}"
    "&data_frequency=DAILY&index_codes=" + CODIGO
)


def ler(texto: str, nome: str = "msci_em") -> pd.Series:
    """Converte a resposta (`level_eod`, `calc_date` aaaammdd) em série diária."""
    niveis = json.loads(texto)["indexes"]["INDEX_LEVELS"]
    datas = [pd.to_datetime(str(n["calc_date"]), format="%Y%m%d") for n in niveis]
    valores = [n["level_eod"] for n in niveis]
    return limpar(pd.Series(valores, index=datas, dtype="float64"), nome)


def emergentes_usd(atualizar: bool) -> pd.Series:
    """Nível diário do índice, de 01/01/1997 até hoje, num pedido só."""
    hoje = date.today()
    # A data de fim entra no nome: um dia novo pede os dados de novo.
    caminho = baixar(
        URL.format(inicio=PRIMEIRO_DIA, fim=f"{hoje:%Y%m%d}"),
        f"msci/emergentes_usd_{hoje:%Y%m%d}.json",
        atualizar,
        cabecalhos={"User-Agent": "Mozilla/5.0"},
    )
    return ler(caminho.read_text(encoding="utf-8"))
