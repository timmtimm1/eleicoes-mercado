"""Séries do Ipeadata (API OData)."""

import json

import pandas as pd

from eleicoes.baixar import baixar
from eleicoes.fontes import limpar

URL = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo}')"


def ler(texto: str, nome: str) -> pd.Series:
    """Converte a resposta JSON (`VALDATA` com fuso, `VALVALOR`) em série diária."""
    registros = json.loads(texto)["value"]
    datas, valores = [], []
    for registro in registros:
        valor = registro.get("VALVALOR")
        if valor is None:
            continue
        # "1994-04-29T00:00:00-03:00": só a data importa, o fuso é descartado.
        datas.append(pd.Timestamp(registro["VALDATA"][:10]))
        valores.append(valor)
    return limpar(pd.Series(valores, index=datas, dtype="float64"), nome)


def serie(codigo: str, atualizar: bool) -> pd.Series:
    """Série inteira do Ipeadata, com cache em `ipeadata/{codigo}.json`."""
    caminho = baixar(URL.format(codigo=codigo), f"ipeadata/{codigo}.json", atualizar)
    return ler(caminho.read_text(encoding="utf-8"), codigo)
