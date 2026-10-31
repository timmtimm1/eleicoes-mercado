"""Séries do SGS, o sistema de séries temporais do Banco Central."""

import json
import urllib.error
from datetime import date, timedelta

import pandas as pd

from eleicoes.baixar import baixar
from eleicoes.fontes import limpar

URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    "?formato=json&dataInicial={inicio}&dataFinal={fim}"
)
# A API recusa janelas de mais de 10 anos em séries diárias.
ANOS_POR_BLOCO = 5


def blocos(inicio: date, fim: date) -> list[tuple[date, date]]:
    """Quebra [inicio, fim] em pedaços de até 5 anos, sem buraco nem sobreposição."""
    resultado = []
    atual = inicio
    while atual <= fim:
        proximo_inicio = (pd.Timestamp(atual) + pd.DateOffset(years=ANOS_POR_BLOCO)).date()
        resultado.append((atual, min(proximo_inicio - timedelta(days=1), fim)))
        atual = proximo_inicio
    return resultado


def _ler_bloco(texto: str) -> pd.Series:
    """Converte o JSON do SGS (`data` dd/mm/aaaa, `valor` texto com ponto) em série."""
    registros = json.loads(texto)
    if not registros:
        return pd.Series(dtype="float64")
    tabela = pd.DataFrame(registros)
    datas = pd.to_datetime(tabela["data"], format="%d/%m/%Y")
    valores = pd.to_numeric(tabela["valor"], errors="coerce")
    return pd.Series(valores.to_numpy(), index=datas)


def sgs(codigo: int, inicio: date, fim: date, atualizar: bool) -> pd.Series:
    """Série diária do SGS entre `inicio` e `fim`, em blocos guardados no cache."""
    partes = []
    for bloco_inicio, bloco_fim in blocos(inicio, fim):
        nome = f"bcb/sgs_{codigo}_{bloco_inicio:%Y%m%d}_{bloco_fim:%Y%m%d}.json"
        # O último bloco leva a data de fim no nome: um dia novo não reaproveita o cache de ontem.
        url = URL.format(
            codigo=codigo, inicio=f"{bloco_inicio:%d/%m/%Y}", fim=f"{bloco_fim:%d/%m/%Y}"
        )
        try:
            caminho = baixar(url, nome, atualizar)
        except urllib.error.HTTPError as erro:
            if erro.code == 404 and "Value(s) not found" in erro.read().decode("utf-8", "replace"):
                continue
            raise
        partes.append(_ler_bloco(caminho.read_text(encoding="utf-8")))
    if not partes:
        return limpar(pd.Series(dtype="float64"), str(codigo))
    return limpar(pd.concat(partes), str(codigo))
