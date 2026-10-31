"""Carteiras de peso igual por janela: todas, estatais, privadas e setores.

Cada empresa do top 60 da eleição vira uma série diária de preço: o ticker representante,
ajustado por desdobramento, grupamento e bonificação (`ajuste.py`), e, se ele para de negociar
antes do fim da janela mais longa, emendado em outro ticker da mesma raiz ou da raiz sucessora
(`sucessoes.csv`). Cada emenda fica registrada. Só preço, sem dividendos.

Carteira = comprar e segurar, peso igual: a variação é a média das variações das empresas
entre o início e o fim da janela, com preço *as-of* de no máximo 5 dias de atraso. Empresa
sem preço no início não entra naquela janela; empresa sem preço no fim sai dela e conta em
`n_fora`. Os setores entram com pelo menos 3 empresas na eleição; `outros` e as empresas sem
classificação ficam só em `todas`.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from eleicoes import ajuste, caminhos, janelas
from eleicoes.calendario import Eleicao
from eleicoes.empresas import SETOR_SEM_CLASSIFICACAO, Sucessao
from eleicoes.janelas import gravar_tabela

LIMITE_DIAS_SEM_PRECO = 5
# A continuação precisa começar até tantos dias depois de o ticker anterior parar.
DIAS_ATE_A_CONTINUACAO = 20
DIAS_PARA_ESCOLHER_CONTINUACAO = 120
# A emenda compara os dois papéis nos dias em comum dos últimos 30 dias do antigo.
DIAS_DE_SOBREPOSICAO = 30
MINIMO_DE_EMPRESAS_NO_SETOR = 3
SETOR_FORA_DOS_SETORES = {"outros", SETOR_SEM_CLASSIFICACAO}
PRIMEIRO_DIA_DO_REAL = date(1994, 7, 4)

COLUNAS_CARTEIRAS = [
    "ano",
    "janela",
    "carteira",
    "inicio",
    "fim",
    "n_empresas",
    "n_fora",
    "variacao",
    "mediana",
    "contra_todas",
    "status",
]
COLUNAS_EMPRESAS = [
    "ano",
    "janela",
    "raiz",
    "empresa",
    "setor",
    "estatal",
    "tickers_usados",
    "variacao",
    "ajustes",
    "status",
]
COLUNAS_AJUSTES = ["ticker", "data", "variacao_bruta", "fator", "motivo"]
COLUNAS_EMENDAS = [
    "ano",
    "raiz",
    "ticker_de",
    "ticker_para",
    "data",
    "tipo",
    "escala",
    "fator_tabela",
    "base",
]
# Estados de uma empresa numa janela.
OK = "ok"
SEM_DADO_INICIO = "sem_dado_inicio"
SEM_DADO_FIM = "sem_dado_fim"
AINDA_NAO = "ainda_nao_aconteceu"
EXCLUIDA = "excluida"


@dataclass
class Mercado:
    """Preços ajustados de todos os tickers relevantes."""

    ajustadas: dict[str, pd.Series]
    volumes: dict[str, pd.Series]
    raiz: dict[str, str]
    ajustes: dict[str, list[ajuste.Ajuste]]

    def tickers_da_raiz(self, raiz: str) -> list[str]:
        return [t for t, r in self.raiz.items() if r == raiz]


@dataclass(frozen=True)
class Emenda:
    ticker_de: str
    ticker_para: str
    data: pd.Timestamp
    tipo: str  # "mesma_raiz" ou "sucessora"
    escala: float  # preço novo vezes escala = preço antigo, no ponto da emenda
    fator_tabela: float  # `fator` do sucessoes.csv acumulado (1 na mesma raiz)
    base: str  # "sobreposicao" (razão dos dois no último dia em comum) ou "continuidade"


@dataclass
class SerieEmpresa:
    precos: pd.Series
    segmentos: list[tuple[str, pd.Timestamp, pd.Timestamp]]  # ticker, primeiro e último dia usados
    emendas: list[Emenda]


def montar_mercado(precos: pd.DataFrame, ibov: pd.Series) -> Mercado:
    """Ajusta cada ticker de `precos` (saída de `acoes.ler_precos`, só volume positivo)."""
    precos = precos[precos["volume"] > 0]
    ajustadas, volumes, raiz, ajustes = {}, {}, {}, {}
    for ticker, quadro in precos.groupby("ticker"):
        serie, lista, _ = ajuste.ajustar_papel(quadro, ibov)
        ajustadas[ticker] = serie
        volumes[ticker] = pd.Series(
            quadro.sort_values("data")["volume"].to_numpy(), index=serie.index
        )
        raiz[ticker] = quadro["raiz"].iloc[-1]
        ajustes[ticker] = lista
    return Mercado(ajustadas, volumes, raiz, ajustes)


def _sucessoras(raiz: str, sucessoes: list[Sucessao]) -> list[tuple[str, float]]:
    """Raízes sucessoras em ordem de proximidade, com o fator acumulado até elas."""
    achadas: list[tuple[str, float]] = []
    visitadas = {raiz}
    fila = [(raiz, 1.0)]
    while fila:
        atual, fator = fila.pop(0)
        for s in sucessoes:
            if s.raiz_antiga == atual and s.raiz_nova not in visitadas:
                visitadas.add(s.raiz_nova)
                achadas.append((s.raiz_nova, fator * s.fator))
                fila.append((s.raiz_nova, fator * s.fator))
    return achadas


def _melhor_continuacao(
    mercado: Mercado, ticker: str, ultimo: pd.Timestamp, visitados: set[str], sucessoes
) -> tuple[str, str, float] | None:
    """(ticker, tipo, fator) que continua `ticker` depois de `ultimo`, ou None.

    Primeiro os outros tickers da mesma raiz, depois os da raiz sucessora mais próxima. Vale
    quem negocia depois de `ultimo`, começa até 20 dias depois dele e tem mais volume nos
    120 dias seguintes.
    """
    raiz = mercado.raiz[ticker]
    grupos = [
        (raiz, 1.0, "mesma_raiz"),
        *((r, f, "sucessora") for r, f in _sucessoras(raiz, sucessoes)),
    ]
    for raiz_do_grupo, fator, tipo in grupos:
        melhor, volume_melhor = None, 0.0
        for candidato in mercado.tickers_da_raiz(raiz_do_grupo):
            if candidato in visitados:
                continue
            datas = mercado.ajustadas[candidato].index
            if datas.max() <= ultimo or datas.min() > ultimo + pd.Timedelta(
                days=DIAS_ATE_A_CONTINUACAO
            ):
                continue
            depois = mercado.volumes[candidato]
            janela = depois[
                (depois.index > ultimo)
                & (depois.index <= ultimo + pd.Timedelta(days=DIAS_PARA_ESCOLHER_CONTINUACAO))
            ]
            if janela.sum() > volume_melhor:
                melhor, volume_melhor = candidato, float(janela.sum())
        if melhor is not None:
            return melhor, tipo, fator
    return None


def serie_da_empresa(
    mercado: Mercado, representante: str, ate: pd.Timestamp, sucessoes: list[Sucessao]
) -> SerieEmpresa:
    """Série do representante, emendada onde ele para de negociar antes de `ate`."""
    atual = representante
    escala = 1.0  # preço do `atual` vezes escala = preço na unidade do representante
    composta = mercado.ajustadas[atual].copy()
    segmentos = [(atual, composta.index.min())]
    fins: list[pd.Timestamp] = []
    emendas: list[Emenda] = []
    visitados = {atual}
    while True:
        ultimo = mercado.ajustadas[atual].index.max()
        if ultimo + pd.Timedelta(days=LIMITE_DIAS_SEM_PRECO) >= ate:
            break
        escolha = _melhor_continuacao(mercado, atual, ultimo, visitados, sucessoes)
        if escolha is None:
            break
        proximo, tipo, fator = escolha
        antigo = mercado.ajustadas[atual] * escala
        novo = mercado.ajustadas[proximo]
        em_comum = antigo.index.intersection(novo.index)
        em_comum = em_comum[
            (em_comum <= ultimo) & (em_comum > ultimo - pd.Timedelta(days=DIAS_DE_SOBREPOSICAO))
        ]
        if len(em_comum):
            corte = em_comum.max()
            # Mediana da razão nos dias em comum: um dia ruim de papel pouco líquido não manda.
            escala_nova = float((antigo[em_comum] / novo[em_comum]).median())
            base = "sobreposicao"
        else:
            corte = ultimo
            escala_nova = escala * fator
            base = "continuidade"
        emendas.append(Emenda(atual, proximo, corte, tipo, escala_nova / escala, fator, base))
        composta = pd.concat(
            [composta[composta.index <= corte], (novo * escala_nova)[novo.index > corte]]
        )
        fins.append(corte)
        segmentos.append((proximo, novo.index[novo.index > corte].min()))
        visitados.add(proximo)
        atual, escala = proximo, escala_nova
    fins.append(composta.index.max())
    return SerieEmpresa(
        composta[composta.index <= ate],
        [(t, i, f) for (t, i), f in zip(segmentos, fins, strict=True)],
        emendas,
    )


def preco_asof(serie: pd.Series, data: pd.Timestamp) -> float:
    """Último preço em ou antes de `data`, NaN se tem mais de 5 dias."""
    posicao = serie.index.searchsorted(data, side="right") - 1
    if posicao < 0 or (data - serie.index[posicao]).days > LIMITE_DIAS_SEM_PRECO:
        return np.nan
    return float(serie.iloc[posicao])


def _tickers_no_periodo(serie: SerieEmpresa, inicio, fim) -> list[str]:
    return [t for t, primeiro, ultimo in serie.segmentos if primeiro <= fim and ultimo >= inicio]


def _texto_ajustes(mercado, serie, tickers, inicio, fim) -> str:
    feitos = sem_fator = 0
    for ticker in tickers:
        for a in mercado.ajustes[ticker]:
            if inicio < a.data <= fim:
                if a.motivo == ajuste.MOTIVO_SEM_FATOR:
                    sem_fator += 1
                else:
                    feitos += 1
    emendas = sum(1 for e in serie.emendas if inicio < e.data <= fim)
    partes = [
        (feitos, "eventos neutralizados"),
        (sem_fator, "eventos sem fator"),
        (emendas, "emendas"),
    ]
    return "; ".join(f"{n} {texto}" for n, texto in partes if n)


def variacoes_das_empresas(
    eleicao: Eleicao,
    liquidez: pd.DataFrame,
    mercado: Mercado,
    sucessoes: list[Sucessao],
    pregoes: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, list[tuple[str, Emenda]]]:
    """Uma linha por (empresa, janela) da eleição, e as emendas feitas (raiz, emenda)."""
    datas = janelas.datas_das_janelas(eleicao, pregoes)
    fins = [fim for _, _, fim in datas if fim is not None]
    ate = max(fins)
    linhas, emendas = [], []
    for empresa in liquidez[liquidez["ano"] == eleicao.ano].itertuples(index=False):
        base = {
            "ano": eleicao.ano,
            "raiz": empresa.raiz,
            "empresa": empresa.empresa,
            "setor": empresa.setor,
            "estatal": bool(empresa.estatal),
        }
        serie = None
        if not empresa.excluida:
            serie = serie_da_empresa(mercado, empresa.ticker, ate, sucessoes)
            emendas += [(empresa.raiz, e) for e in serie.emendas]
        for janela, inicio, fim in datas:
            linha = {
                **base,
                "janela": janela,
                "tickers_usados": "",
                "variacao": np.nan,
                "ajustes": "",
                "status": OK,
            }
            if empresa.excluida:
                linha["status"] = EXCLUIDA
            elif fim is None:
                linha["status"] = AINDA_NAO
            elif inicio is None:
                linha["status"] = SEM_DADO_INICIO
            else:
                p0, p1 = preco_asof(serie.precos, inicio), preco_asof(serie.precos, fim)
                if np.isnan(p0):
                    linha["status"] = SEM_DADO_INICIO
                elif np.isnan(p1):
                    linha["status"] = SEM_DADO_FIM
                else:
                    tickers = _tickers_no_periodo(serie, inicio, fim)
                    linha["tickers_usados"] = ";".join(tickers)
                    linha["variacao"] = (p1 / p0 - 1) * 100
                    linha["ajustes"] = _texto_ajustes(mercado, serie, tickers, inicio, fim)
            linhas.append(linha)
    return pd.DataFrame(linhas, columns=COLUNAS_EMPRESAS), emendas


def _carteiras_da_eleicao(empresas: pd.DataFrame) -> dict[str, pd.Series]:
    """Nome da carteira -> máscara das empresas dela (linhas de `empresas`, uma eleição)."""
    do_universo = empresas["status"] != EXCLUIDA
    classificada = empresas["setor"] != SETOR_SEM_CLASSIFICACAO
    carteiras = {
        "todas": do_universo,
        "estatais": do_universo & classificada & empresas["estatal"],
        "privadas": do_universo & classificada & ~empresas["estatal"],
    }
    # Contagem por empresa (uma janela só), para não contar a mesma empresa de novo.
    por_empresa = empresas.drop_duplicates("raiz")
    contagem = por_empresa[
        (por_empresa["status"] != EXCLUIDA) & ~por_empresa["setor"].isin(SETOR_FORA_DOS_SETORES)
    ]["setor"].value_counts()
    for setor in sorted(contagem[contagem >= MINIMO_DE_EMPRESAS_NO_SETOR].index):
        carteiras[setor] = do_universo & (empresas["setor"] == setor)
    return carteiras


def montar_carteiras(
    eleicao: Eleicao, empresas: pd.DataFrame, pregoes: pd.DatetimeIndex
) -> pd.DataFrame:
    """Carteiras de peso igual de cada janela da eleição."""
    datas = {
        janela: (inicio, fim) for janela, inicio, fim in janelas.datas_das_janelas(eleicao, pregoes)
    }
    carteiras = _carteiras_da_eleicao(empresas)
    linhas = []
    for janela, (inicio, fim) in datas.items():
        da_janela = empresas[empresas["janela"] == janela]
        resultados = {}
        for nome, mascara in carteiras.items():
            membros = da_janela[mascara.loc[da_janela.index]]
            com_dado = membros[membros["status"] == OK]
            resultados[nome] = {
                "n_empresas": len(com_dado),
                "n_fora": int((membros["status"] == SEM_DADO_FIM).sum()),
                "variacao": com_dado["variacao"].mean() if len(com_dado) else np.nan,
                # A média de peso igual sofre com um caso extremo (Embraer +1.077% em 1998-99);
                # a mediana vai ao lado para mostrar a empresa típica.
                "mediana": com_dado["variacao"].median() if len(com_dado) else np.nan,
            }
        todas = resultados["todas"]["variacao"]
        for nome, r in resultados.items():
            linhas.append(_linha_da_carteira(eleicao, janela, nome, inicio, fim, r, todas))
        if "estatais" in resultados and "privadas" in resultados:
            diferenca = resultados["estatais"]["variacao"] - resultados["privadas"]["variacao"]
            linhas.append(
                {
                    **_linha_da_carteira(
                        eleicao,
                        janela,
                        "estatais_menos_privadas",
                        inicio,
                        fim,
                        {"variacao": diferenca},
                        todas,
                    ),
                    "n_empresas": pd.NA,
                    "n_fora": pd.NA,
                    "contra_todas": np.nan,
                }
            )
    return pd.DataFrame(linhas, columns=COLUNAS_CARTEIRAS)


def _linha_da_carteira(eleicao, janela, nome, inicio, fim, resultado, todas) -> dict:
    variacao = resultado["variacao"]
    if fim is None:
        status = AINDA_NAO
    elif inicio is None or np.isnan(variacao):
        status = "sem_dado"
    else:
        status = OK
    return {
        "ano": eleicao.ano,
        "janela": janela,
        "carteira": nome,
        "inicio": "" if inicio is None else inicio.strftime("%Y-%m-%d"),
        "fim": "" if fim is None else fim.strftime("%Y-%m-%d"),
        "n_empresas": resultado.get("n_empresas", 0),
        "n_fora": resultado.get("n_fora", 0),
        "variacao": variacao,
        "mediana": resultado.get("mediana", np.nan),
        "contra_todas": variacao - todas if status == OK else np.nan,
        "status": status,
    }


def calcular_carteiras(
    eleicoes: list[Eleicao],
    liquidez: pd.DataFrame,
    mercado: Mercado,
    sucessoes: list[Sucessao],
    pregoes: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(carteiras, empresas, ajustes, emendas) de todas as eleições."""
    por_carteira, por_empresa, todas_emendas = [], [], []
    for eleicao in eleicoes:
        empresas, emendas = variacoes_das_empresas(eleicao, liquidez, mercado, sucessoes, pregoes)
        por_empresa.append(empresas)
        por_carteira.append(montar_carteiras(eleicao, empresas, pregoes))
        todas_emendas += [
            {
                "ano": eleicao.ano,
                "raiz": raiz,
                "ticker_de": e.ticker_de,
                "ticker_para": e.ticker_para,
                "data": e.data.strftime("%Y-%m-%d"),
                "tipo": e.tipo,
                "escala": e.escala,
                "fator_tabela": e.fator_tabela,
                "base": e.base,
            }
            for raiz, e in emendas
        ]
    ajustes = pd.DataFrame(
        [
            {
                "ticker": a.ticker,
                "data": a.data.strftime("%Y-%m-%d"),
                "variacao_bruta": a.variacao_bruta,
                "fator": a.fator,
                "motivo": a.motivo,
            }
            for lista in mercado.ajustes.values()
            for a in lista
        ],
        columns=COLUNAS_AJUSTES,
    ).sort_values(["ticker", "data"], ignore_index=True)
    return (
        pd.concat(por_carteira, ignore_index=True),
        pd.concat(por_empresa, ignore_index=True),
        ajustes,
        pd.DataFrame(todas_emendas, columns=COLUNAS_EMENDAS),
    )


def gravar(carteiras, empresas, ajustes, emendas) -> list:
    saidas = {
        "carteiras.csv": carteiras,
        "carteiras_empresas.csv": empresas,
        "ajustes_eventos.csv": ajustes,
        "emendas.csv": emendas,
    }
    caminhos_gravados = []
    for nome, tabela in saidas.items():
        caminho = caminhos.RESULTADOS / nome
        gravar_tabela(tabela, caminho)
        caminhos_gravados.append(caminho)
    return caminhos_gravados
