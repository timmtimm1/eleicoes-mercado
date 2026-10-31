"""Estudo de evento: variação de cada série em cada janela, bruta e "só Brasil".

"Só Brasil" é o modelo de mercado: beta do Brasil contra o exterior em 250 pregões antes da
corrida; na janela, soma dos retornos diários anormais (Brasil menos beta vezes exterior,
sem intercepto).

O beta é o de Dimson: soma dos coeficientes do exterior no dia anterior, no mesmo dia e no
dia seguinte. A bolsa da Ásia fecha antes da brasileira abrir, então parte do que acontece
aqui num dia só aparece no índice de emergentes no dia seguinte; com o beta do mesmo dia
só, o Brasil parece menos ligado ao mundo do que é (2026: 0,27 no mesmo dia, 0,6 com os
três dias).
"""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from eleicoes import calendario, caminhos, series
from eleicoes.calendario import Eleicao

JANELAS = [
    "corrida",
    "t1_d1",
    "t1_d5",
    "t1_d20",
    "entre_turnos",
    "t2_d1",
    "t2_d5",
    "t2_d20",
    "ate_posse",
    "posse_100d",
    "posse_1ano",
]
JANELAS_DO_SEGUNDO_TURNO = {"entre_turnos", "t2_d1", "t2_d5", "t2_d20"}
# O swap é mensal: só enxerga janelas longas.
JANELAS_LONGAS = {"corrida", "ate_posse", "posse_100d", "posse_1ano"}

COLUNAS = [
    "ano",
    "janela",
    "medida",
    "inicio",
    "fim",
    "pregoes",
    "valor_inicio",
    "valor_fim",
    "variacao",
    "unidade",
    "so_brasil",
    "controle",
    "beta",
    "pregoes_estimacao",
    "status",
    "observacao",
]
COLUNAS_INTEIRAS = ["pregoes", "pregoes_estimacao"]

DIAS_DA_CORRIDA = 60
PREGOES_DE_ESTIMACAO = 250
MINIMO_DE_PARES = 150
LIMITE_DIAS_SEM_DADO = 5
# Mensal, com data no dia 1º: vale até o mês seguinte.
LIMITE_DIAS_MENSAL = 35
# 1994 fica sem "só Brasil": os 250 pregões de estimação caem quase todos na hiperinflação
# (antes de 01/07/1994) e não há índice de emergentes diário antes de 1997. Contra o S&P 500
# o beta da bolsa dava 2,8, número sem sentido econômico.
ANO_SEM_SO_BRASIL = 1994


@dataclass(frozen=True)
class Medida:
    nome: str
    unidade: str  # "%", "p.p." ou "p.b."
    em_percentual: bool  # True: variação relativa (log nos retornos); False: diferença de nível
    serie: str  # chave em `niveis`
    controle: str | None = None  # série do exterior; None: sem "só Brasil"


MEDIDAS = [
    Medida("ibov", "%", True, "ibov"),
    Medida("ibov_usd", "%", True, "ibov_usd", "msci_em"),
    Medida("dolar", "%", True, "dolar", "dxy"),
    Medida("selic", "p.p.", False, "selic"),
    Medida("prefixado_1a", "p.p.", False, "prefixado_1a", "ust10"),
    Medida("prefixado_10a", "p.p.", False, "prefixado_10a", "ust10"),
    Medida("embi", "p.b.", False, "embi"),
    Medida("swap360", "p.p.", False, "swap360_mensal"),
]
SERIES_LIDAS = [
    "ibov",
    "dolar",
    "selic",
    "prefixado_1a",
    "prefixado_10a",
    "embi",
    "msci_em",
    "dxy",
    "ust10",
]


def controle_da_medida(medida: Medida, ano: int) -> str | None:
    """Série do exterior que desconta a medida; None quando não há "só Brasil"."""
    if ano == ANO_SEM_SO_BRASIL:
        return None
    return medida.controle


def alinhar(serie: pd.Series, calendario_: pd.DatetimeIndex, limite_dias: int | None):
    """Valor *as-of* da série em cada pregão; NaN se o último valor tem mais de `limite_dias`."""
    posicao = serie.index.searchsorted(calendario_, side="right") - 1
    existe = posicao >= 0
    ultimas_datas = serie.index[np.where(existe, posicao, 0)]
    valores = np.where(existe, serie.to_numpy()[np.where(existe, posicao, 0)], np.nan)
    if limite_dias is not None:
        atraso = (calendario_ - ultimas_datas).days
        valores = np.where(atraso <= limite_dias, valores, np.nan)
    return pd.Series(valores, index=calendario_, dtype="float64")


def ler_niveis(calendario_: pd.DatetimeIndex, ler=series.ler) -> dict[str, pd.Series]:
    """Todas as séries do estudo nos pregões do calendário, mais `ibov_usd`."""
    niveis = {nome: alinhar(ler(nome), calendario_, LIMITE_DIAS_SEM_DADO) for nome in SERIES_LIDAS}
    niveis["swap360_mensal"] = alinhar(ler("swap360_mensal"), calendario_, LIMITE_DIAS_MENSAL)
    niveis["ibov_usd"] = niveis["ibov"] / niveis["dolar"]
    return niveis


def datas_das_janelas(eleicao: Eleicao, pregoes: pd.DatetimeIndex):
    """(janela, início, fim) de cada janela da eleição; None onde a data não existe ainda."""
    primeiro = eleicao.primeiro_turno.data
    decisivo = eleicao.turno_decisivo.data
    base_t1 = calendario.ultimo_pregao_antes(primeiro, pregoes)
    base_decisivo = calendario.ultimo_pregao_antes(decisivo, pregoes)
    posse = pd.Timestamp(eleicao.posse)
    janelas = [
        (
            "corrida",
            calendario.ultimo_pregao_ate(primeiro - timedelta(days=DIAS_DA_CORRIDA), pregoes),
            base_t1,
        )
    ]
    for dias in (1, 5, 20):
        janelas.append((f"t1_d{dias}", base_t1, calendario.pregao_depois(primeiro, dias, pregoes)))
    if len(eleicao.turnos) > 1:
        segundo = eleicao.turnos[1].data
        base_t2 = calendario.ultimo_pregao_antes(segundo, pregoes)
        janelas.append(("entre_turnos", base_t1, base_t2))
        for dias in (1, 5, 20):
            janelas.append(
                (f"t2_d{dias}", base_t2, calendario.pregao_depois(segundo, dias, pregoes))
            )
    janelas += [
        ("ate_posse", base_decisivo, calendario.ultimo_pregao_antes(posse, pregoes)),
        (
            "posse_100d",
            base_decisivo,
            calendario.ultimo_pregao_ate(posse + timedelta(days=100), pregoes),
        ),
        (
            "posse_1ano",
            base_decisivo,
            calendario.ultimo_pregao_ate(posse + pd.DateOffset(years=1), pregoes),
        ),
    ]
    return janelas


def retornos_diarios(nivel: pd.Series, em_percentual: bool) -> pd.Series:
    """Retorno em log (para %) ou diferença de nível (para p.p.) entre pregões seguidos."""
    if em_percentual:
        return np.log(nivel).diff()
    return nivel.diff()


@dataclass(frozen=True)
class Modelo:
    """Beta do Brasil contra o exterior numa eleição; `beta` é NaN se faltou dado."""

    beta: float
    pares: int
    observacao: str = ""


def estimar_beta(
    brasil: pd.Series, exterior: pd.Series, fim_estimacao: pd.Timestamp | None
) -> Modelo:
    """Beta de Dimson nos 250 pregões que terminam em `fim_estimacao` (inclusive).

    MQO do retorno do Brasil contra o do exterior no dia anterior, no mesmo dia e no dia
    seguinte, com intercepto; o beta é a soma dos três coeficientes.
    """
    if fim_estimacao is None:
        return Modelo(np.nan, 0)
    regressores = pd.DataFrame(
        {"anterior": exterior.shift(1), "mesmo_dia": exterior, "seguinte": exterior.shift(-1)}
    )
    posicao = brasil.index.get_loc(fim_estimacao)
    janela = slice(max(posicao - PREGOES_DE_ESTIMACAO + 1, 0), posicao + 1)
    y = brasil.iloc[janela]
    x = regressores.iloc[janela]
    validos = y.notna() & x.notna().all(axis=1)
    pares = int(validos.sum())
    if pares < MINIMO_DE_PARES:
        return Modelo(np.nan, pares)
    matriz = np.column_stack([np.ones(pares), x[validos].to_numpy()])
    coeficientes = np.linalg.lstsq(matriz, y[validos].to_numpy(), rcond=None)[0]
    return Modelo(float(coeficientes[1:].sum()), pares)


def so_brasil(
    brasil: pd.Series, exterior: pd.Series, beta: float, inicio, fim, em_percentual: bool
) -> float:
    """Soma dos retornos anormais entre `inicio` e `fim`; NaN se falta dado numa das pontas.

    Sem intercepto, a soma dos retornos diários anormais (Brasil menos beta vezes exterior)
    é a variação do Brasil menos beta vezes a do exterior entre as pontas. Calcular pelas
    pontas dá o mesmo número e aguenta um dia sem dado no meio da janela.
    """
    if np.isnan(beta):
        return np.nan
    if em_percentual:
        soma = np.log(brasil[fim] / brasil[inicio]) - beta * np.log(
            exterior[fim] / exterior[inicio]
        )
        return float((np.exp(soma) - 1) * 100)
    return float((brasil[fim] - brasil[inicio]) - beta * (exterior[fim] - exterior[inicio]))


def _linha(eleicao, janela, medida, inicio, fim) -> dict:
    return {
        "ano": eleicao.ano,
        "janela": janela,
        "medida": medida.nome,
        "inicio": "" if inicio is None else inicio.strftime("%Y-%m-%d"),
        "fim": "" if fim is None else fim.strftime("%Y-%m-%d"),
        "pregoes": pd.NA,
        "valor_inicio": np.nan,
        "valor_fim": np.nan,
        "variacao": np.nan,
        "unidade": medida.unidade,
        "so_brasil": np.nan,
        "controle": "",
        "beta": np.nan,
        "pregoes_estimacao": pd.NA,
        "status": "ok",
        "observacao": "",
    }


def calcular(
    eleicoes: list[Eleicao], niveis: dict[str, pd.Series], pregoes: pd.DatetimeIndex
) -> pd.DataFrame:
    """Uma linha por (eleição, janela, medida), na ordem de JANELAS e MEDIDAS."""
    linhas = []
    for eleicao in eleicoes:
        datas = datas_das_janelas(eleicao, pregoes)
        inicio_corrida = datas[0][1]
        fim_estimacao = None
        if inicio_corrida is not None and pregoes.get_loc(inicio_corrida) > 0:
            fim_estimacao = pregoes[pregoes.get_loc(inicio_corrida) - 1]
        modelos = {}
        for medida in MEDIDAS:
            controle = controle_da_medida(medida, eleicao.ano)
            if controle is None:
                continue
            brasil = retornos_diarios(niveis[medida.serie], medida.em_percentual)
            exterior = retornos_diarios(niveis[controle], medida.em_percentual)
            modelos[medida.nome] = estimar_beta(brasil, exterior, fim_estimacao)
        for janela, inicio, fim in datas:
            for medida in MEDIDAS:
                linha = _linha(eleicao, janela, medida, inicio, fim)
                controle = controle_da_medida(medida, eleicao.ano)
                modelo = modelos.get(medida.nome)
                if modelo is not None:
                    linha["controle"] = controle
                    linha["beta"] = modelo.beta
                    linha["pregoes_estimacao"] = modelo.pares
                    linha["observacao"] = modelo.observacao
                if fim is None:
                    linha["status"] = "ainda_nao_aconteceu"
                elif inicio is None or (medida.nome == "swap360" and janela not in JANELAS_LONGAS):
                    linha["status"] = "sem_dado"
                    if medida.nome == "swap360":
                        linha["observacao"] = "dado mensal não enxerga janelas curtas"
                else:
                    _preencher(linha, medida, niveis[medida.serie], inicio, fim, pregoes)
                    if linha["status"] == "ok" and modelo is not None:
                        linha["so_brasil"] = so_brasil(
                            niveis[medida.serie],
                            niveis[controle],
                            modelo.beta,
                            inicio,
                            fim,
                            medida.em_percentual,
                        )
                linhas.append(linha)
    tabela = pd.DataFrame(linhas, columns=COLUNAS)
    for coluna in COLUNAS_INTEIRAS:
        tabela[coluna] = tabela[coluna].astype("Int64")
    return tabela


def _preencher(linha, medida, nivel, inicio, fim, pregoes) -> None:
    """Valores, número de pregões e variação bruta; `sem_dado` se faltar ponta da janela."""
    valor_inicio, valor_fim = nivel.loc[inicio], nivel.loc[fim]
    if np.isnan(valor_inicio) or np.isnan(valor_fim):
        linha["status"] = "sem_dado"
        return
    linha["pregoes"] = pregoes.get_loc(fim) - pregoes.get_loc(inicio)
    linha["valor_inicio"] = valor_inicio
    linha["valor_fim"] = valor_fim
    if medida.em_percentual:
        linha["variacao"] = (valor_fim / valor_inicio - 1) * 100
    else:
        linha["variacao"] = valor_fim - valor_inicio


def calcular_janelas(eleicoes: list[Eleicao] | None = None) -> pd.DataFrame:
    """Janelas com os dados gravados em `dados/series/` e o `dados/eleicoes.yaml`."""
    eleicoes = eleicoes or calendario.carregar_eleicoes()
    pregoes = calendario.pregoes()
    return calcular(eleicoes, ler_niveis(pregoes), pregoes)


def gravar_tabela(tabela: pd.DataFrame, caminho: Path) -> None:
    """CSV com até 6 casas decimais e células vazias no lugar de NaN."""
    saida = tabela.copy()
    for coluna in saida.columns:
        if pd.api.types.is_float_dtype(saida[coluna]):
            saida[coluna] = ["" if pd.isna(v) else series.formatar_numero(v) for v in saida[coluna]]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    saida.to_csv(caminho, index=False)


def gravar_janelas(tabela: pd.DataFrame) -> Path:
    caminho = caminhos.RESULTADOS / "janelas.csv"
    gravar_tabela(tabela, caminho)
    return caminho
