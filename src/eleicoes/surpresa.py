"""Surpresa: resultado do TSE contra a média das últimas pesquisas, a favor do candidato do mercado.

Positivo = o candidato do mercado foi melhor nas urnas do que as pesquisas diziam. O sinal
bate com o da reação da bolsa.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from eleicoes import calendario, caminhos
from eleicoes.calendario import Eleicao
from eleicoes.janelas import gravar_tabela

COLUNAS = [
    "ano",
    "turno",
    "data",
    "candidato_mercado",
    "adversario",
    "margem_pesquisas",
    "margem_resultado",
    "surpresa",
    "favorito_pesquisas",
    "mercado_ganhou_turno",
    "n_institutos",
    "institutos",
    "ibov_d1",
    "ibov_usd_so_brasil_d1",
    "dolar_d1",
    "dolar_so_brasil_d1",
    "prefixado_10a_d1",
]
# coluna de surpresa.csv → (medida, coluna de janelas.csv) na janela t{turno}_d1
REACAO_D1 = {
    "ibov_d1": ("ibov", "variacao"),
    "ibov_usd_so_brasil_d1": ("ibov_usd", "so_brasil"),
    "dolar_d1": ("dolar", "variacao"),
    "dolar_so_brasil_d1": ("dolar", "so_brasil"),
    "prefixado_10a_d1": ("prefixado_10a", "variacao"),
}


def _reacao(janelas: pd.DataFrame, ano: int, turno: int) -> dict[str, float]:
    do_turno = janelas[(janelas["ano"] == ano) & (janelas["janela"] == f"t{turno}_d1")]
    reacao = {}
    for coluna, (medida, origem) in REACAO_D1.items():
        linha = do_turno[do_turno["medida"] == medida]
        reacao[coluna] = float(linha[origem].iloc[0]) if not linha.empty else np.nan
    return reacao


def calcular(
    eleicoes: list[Eleicao], pesquisas: pd.DataFrame, janelas: pd.DataFrame
) -> pd.DataFrame:
    """Uma linha por turno."""
    linhas = []
    for eleicao in eleicoes:
        mercado, adversario = eleicao.candidato_mercado, eleicao.adversario_mercado
        for turno in eleicao.turnos:
            margem_resultado = turno.resultado[mercado] - turno.resultado[adversario]
            do_turno = pesquisas[
                (pesquisas["ano"] == eleicao.ano)
                & (pesquisas["turno"] == turno.numero)
                & pesquisas["candidato"].isin([mercado, adversario])
            ]
            medias = do_turno.groupby("candidato")["pct_validos"].mean()
            institutos = sorted(do_turno["instituto"].unique())
            margem_pesquisas = np.nan
            favorito = ""
            if mercado in medias and adversario in medias:
                margem_pesquisas = float(medias[mercado] - medias[adversario])
                favorito = mercado if margem_pesquisas > 0 else adversario
                if margem_pesquisas == 0:
                    favorito = "empate"
            linhas.append(
                {
                    "ano": eleicao.ano,
                    "turno": turno.numero,
                    "data": turno.data.isoformat(),
                    "candidato_mercado": mercado,
                    "adversario": adversario,
                    "margem_pesquisas": margem_pesquisas,
                    "margem_resultado": margem_resultado,
                    "surpresa": margem_resultado - margem_pesquisas,
                    "favorito_pesquisas": favorito,
                    "mercado_ganhou_turno": margem_resultado > 0,
                    "n_institutos": len(institutos),
                    "institutos": ";".join(institutos),
                    **_reacao(janelas, eleicao.ano, turno.numero),
                }
            )
    return pd.DataFrame(linhas, columns=COLUNAS)


def calcular_surpresa(janelas: pd.DataFrame) -> pd.DataFrame:
    """Surpresa com `dados/eleicoes.yaml` e `dados/pesquisas.csv`."""
    pesquisas = pd.read_csv(caminhos.DADOS / "pesquisas.csv")
    return calcular(calendario.carregar_eleicoes(), pesquisas, janelas)


def gravar_surpresa(tabela: pd.DataFrame) -> Path:
    caminho = caminhos.RESULTADOS / "surpresa.csv"
    gravar_tabela(tabela, caminho)
    return caminho


def correlacao_surpresa(tabela: pd.DataFrame) -> pd.DataFrame:
    """Surpresa e Ibovespa no D+1: n, correlação de Pearson e inclinação (% de bolsa por ponto).

    Só entram turnos que têm surpresa e `ibov_d1`. Com menos de 3 turnos, correlação e
    inclinação ficam vazias.
    """
    completos = tabela.dropna(subset=["surpresa", "ibov_d1"])
    grupos = {
        "1º turno": completos[completos["turno"] == 1],
        "2º turno": completos[completos["turno"] == 2],
        "todos": completos,
    }
    linhas = []
    for nome, grupo in grupos.items():
        n = len(grupo)
        correlacao = inclinacao = np.nan
        if n >= 3 and grupo["surpresa"].nunique() > 1:
            x, y = grupo["surpresa"].to_numpy(), grupo["ibov_d1"].to_numpy()
            correlacao = float(np.corrcoef(x, y)[0, 1])
            inclinacao = float(np.polyfit(x, y, 1)[0])
        linhas.append({"grupo": nome, "n": n, "correlacao": correlacao, "inclinacao": inclinacao})
    return pd.DataFrame(linhas)
