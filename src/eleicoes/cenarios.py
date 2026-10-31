"""Cenários de bolsa, dólar e juros para depois da eleição de 2026.

O ponto de partida é o 5º pregão depois do turno decisivo: em 2026 é 30/10, o último dado.
Para cada eleição passada, mede-se o que aconteceu desse ponto até a posse, os 100 dias e o
primeiro ano, só no "só Brasil" (descontado o mundo, como na fase 2). Cada cenário de
`premissas/cenarios.yaml` junta duas eleições parecidas; a faixa vai do menor ao maior
caminho delas, aplicado aos preços de 2026.

Supõe o mundo parado: se as bolsas emergentes ou o dólar no mundo andarem, isso soma por
cima. O Ibovespa em reais sai do Ibovespa em dólar vezes o dólar, eleição por eleição.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from eleicoes import caminhos, series
from eleicoes.janelas import gravar_tabela

PREMISSAS = caminhos.RAIZ / "premissas" / "cenarios.yaml"
HORIZONTES = ["ate_posse", "posse_100d", "posse_1ano"]
# Ponto de partida de cada eleição: 5 pregões depois do turno decisivo.
PARTIDA_UM_TURNO = "t1_d5"
PARTIDA_DOIS_TURNOS = "t2_d5"
MEDIDAS_EM_PERCENTUAL = ["ibov_usd", "dolar"]
MEDIDAS = ["ibov", "ibov_usd", "dolar", "prefixado_10a"]
UNIDADES = {"ibov": "%", "ibov_usd": "%", "dolar": "%", "prefixado_10a": "p.p."}
SERIE_DO_NIVEL = {"ibov": "ibov", "dolar": "dolar", "prefixado_10a": "prefixado_10a"}

COLUNAS_CAMINHOS = ["ano", "horizonte", "medida", "so_brasil", "unidade"]
COLUNAS_CENARIOS = [
    "cenario",
    "horizonte",
    "data",
    "medida",
    "unidade",
    "analogos_com_dado",
    "minimo",
    "central",
    "maximo",
    "nivel_base",
    "nivel_minimo",
    "nivel_central",
    "nivel_maximo",
    "status_premissas",
]


def carregar_premissas(caminho: Path = PREMISSAS) -> dict:
    with caminho.open(encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def _desde_a_partida(janelas: pd.DataFrame, ano: int, medida: str, horizonte: str) -> float:
    """Só Brasil da partida (D+5) até o horizonte, pela razão entre as duas janelas.

    As duas janelas começam no mesmo pregão (o último antes do turno) e usam o mesmo beta,
    então a diferença entre elas é o só Brasil do trecho que falta.
    """
    da_eleicao = janelas[(janelas["ano"] == ano) & (janelas["medida"] == medida)]
    valores = da_eleicao.set_index("janela")["so_brasil"]
    partida = PARTIDA_UM_TURNO if ano in (1994, 1998) else PARTIDA_DOIS_TURNOS
    if partida not in valores.index or horizonte not in valores.index:
        return np.nan
    inicio, fim = valores[partida], valores[horizonte]
    if medida in MEDIDAS_EM_PERCENTUAL:
        return ((1 + fim / 100) / (1 + inicio / 100) - 1) * 100
    return fim - inicio


def caminhos_pos_choque(janelas: pd.DataFrame) -> pd.DataFrame:
    """Só Brasil de cada eleição, da partida até cada horizonte, nas quatro medidas.

    O Ibovespa em reais é (1 + Ibovespa em dólar) x (1 + dólar) - 1, com o mundo parado.
    """
    linhas = []
    for ano in sorted(janelas["ano"].unique()):
        for horizonte in HORIZONTES:
            valores = {
                medida: _desde_a_partida(janelas, ano, medida, horizonte)
                for medida in ("ibov_usd", "dolar", "prefixado_10a")
            }
            em_dolar, cambio = valores["ibov_usd"] / 100, valores["dolar"] / 100
            valores["ibov"] = ((1 + em_dolar) * (1 + cambio) - 1) * 100
            for medida in MEDIDAS:
                linhas.append(
                    {
                        "ano": int(ano),
                        "horizonte": horizonte,
                        "medida": medida,
                        "so_brasil": valores[medida],
                        "unidade": UNIDADES[medida],
                    }
                )
    return pd.DataFrame(linhas, columns=COLUNAS_CAMINHOS)


def niveis_base(data_base: str) -> dict[str, float]:
    """Ibovespa, dólar e Tesouro de 10 anos no dia-base, e o Ibovespa em dólar."""
    dia = pd.Timestamp(data_base)
    niveis = {medida: float(series.ler(nome).loc[dia]) for medida, nome in SERIE_DO_NIVEL.items()}
    niveis["ibov_usd"] = niveis["ibov"] / niveis["dolar"]
    return niveis


def _nivel(base: float, variacao: float, medida: str) -> float:
    if np.isnan(variacao):
        return np.nan
    if UNIDADES[medida] == "p.p.":
        return base + variacao
    return base * (1 + variacao / 100)


def projetar(caminhos_: pd.DataFrame, premissas: dict, base: dict[str, float]) -> pd.DataFrame:
    """Faixa de cada cenário, horizonte e medida: menor, média e maior dos análogos."""
    linhas = []
    for cenario in premissas["cenarios"]:
        do_cenario = caminhos_[caminhos_["ano"].isin(cenario["analogos"])]
        for horizonte in HORIZONTES:
            for medida in MEDIDAS:
                valores = do_cenario[
                    (do_cenario["horizonte"] == horizonte) & (do_cenario["medida"] == medida)
                ]["so_brasil"].dropna()
                minimo, central, maximo = (
                    (valores.min(), valores.mean(), valores.max())
                    if len(valores)
                    else (np.nan,) * 3
                )
                linhas.append(
                    {
                        "cenario": cenario["nome"],
                        "horizonte": horizonte,
                        "data": str(premissas["horizontes"][horizonte]),
                        "medida": medida,
                        "unidade": UNIDADES[medida],
                        "analogos_com_dado": ";".join(
                            str(a) for a in do_cenario.loc[valores.index, "ano"]
                        ),
                        "minimo": minimo,
                        "central": central,
                        "maximo": maximo,
                        "nivel_base": base[medida],
                        "nivel_minimo": _nivel(base[medida], minimo, medida),
                        "nivel_central": _nivel(base[medida], central, medida),
                        "nivel_maximo": _nivel(base[medida], maximo, medida),
                        "status_premissas": premissas["status"],
                    }
                )
    return pd.DataFrame(linhas, columns=COLUNAS_CENARIOS)


def calcular() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê janelas.csv e as premissas, grava os dois CSVs de resultado e devolve os dois."""
    janelas = pd.read_csv(caminhos.RESULTADOS / "janelas.csv")
    premissas = carregar_premissas()
    caminhos_ = caminhos_pos_choque(janelas)
    cenarios = projetar(caminhos_, premissas, niveis_base(str(premissas["data_base"])))
    gravar_tabela(caminhos_, caminhos.RESULTADOS / "caminhos_pos_choque.csv")
    gravar_tabela(cenarios, caminhos.RESULTADOS / "cenarios.csv")
    return caminhos_, cenarios
