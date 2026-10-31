"""Monta todas as séries do estudo e grava em `dados/series/`.

Cada série vira um CSV `data,valor` (data ISO, ordenada) e o `catalogo.csv` descreve
todas. Os CSVs vão para o git, então o formato é fixo para o diff mostrar só o que mudou.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import pandas as pd

from eleicoes import caminhos
from eleicoes.fontes import bcb, ipeadata, msci, tesouro, yahoo

PRIMEIRO_DIA = date(1993, 1, 1)
# O BCB dá o dólar na moeda de cada época: cruzeiros até 31/07/1993 (Cr$ 1.000 viraram
# CR$ 1) e cruzeiros reais até 30/06/1994 (CR$ 2.750 viraram R$ 1, a paridade da URV).
INICIO_DO_CRUZEIRO_REAL = pd.Timestamp("1993-08-01")
INICIO_DO_REAL = pd.Timestamp("1994-07-01")
CRUZEIROS_POR_CRUZEIRO_REAL = 1000
CRUZEIROS_REAIS_POR_REAL = 2750
CASAS_DECIMAIS = 6
COLUNAS_CATALOGO = [
    "nome",
    "descricao",
    "unidade",
    "fonte",
    "codigo",
    "url",
    "inicio",
    "fim",
    "linhas",
]

URL_YAHOO = "https://finance.yahoo.com/quote/{codigo}"
URL_IPEADATA = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo}')"
URL_BCB = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"


@dataclass(frozen=True)
class Definicao:
    """O que a série é e como obtê-la."""

    nome: str
    descricao: str
    unidade: str
    fonte: str
    codigo: str
    url: str
    obter: Callable[[bool], pd.Series]


def _yahoo(nome, ticker, descricao, unidade):
    return Definicao(
        nome,
        descricao,
        unidade,
        "Yahoo",
        ticker,
        URL_YAHOO.format(codigo=ticker),
        lambda atualizar: yahoo.fechamento(ticker, atualizar),
    )


def _ipeadata(nome, codigo, descricao, unidade):
    return Definicao(
        nome,
        descricao,
        unidade,
        "Ipeadata",
        codigo,
        URL_IPEADATA.format(codigo=codigo),
        lambda atualizar: ipeadata.serie(codigo, atualizar),
    )


def _bcb(nome, codigo, descricao, unidade):
    return Definicao(
        nome,
        descricao,
        unidade,
        "BCB SGS",
        str(codigo),
        URL_BCB.format(codigo=codigo),
        lambda atualizar: bcb.sgs(codigo, PRIMEIRO_DIA, date.today(), atualizar),
    )


def _tesouro(nome, codigo, descricao, unidade, coluna, funcao):
    """Série do Tesouro Direto; `coluna` escolhe `taxa` ou `prazo_anos` da mesma tabela."""
    return Definicao(
        nome,
        descricao,
        unidade,
        "Tesouro Direto",
        codigo,
        tesouro.URL,
        lambda atualizar: funcao(atualizar)[coluna],
    )


def em_reais(serie: pd.Series) -> pd.Series:
    """Passa o dólar de antes do Real para a escala do Real, sem degrau na troca de moeda."""
    convertida = serie.copy()
    antes_do_real = convertida.index < INICIO_DO_REAL
    convertida[antes_do_real] = convertida[antes_do_real] / CRUZEIROS_REAIS_POR_REAL
    antes_do_cruzeiro_real = convertida.index < INICIO_DO_CRUZEIRO_REAL
    convertida[antes_do_cruzeiro_real] = (
        convertida[antes_do_cruzeiro_real] / CRUZEIROS_POR_CRUZEIRO_REAL
    )
    return convertida


def no_fim_do_mes(serie: pd.Series) -> pd.Series:
    """Série mensal do Ipeadata (data no dia 1º) com a data no último dia do mês.

    O Ipeadata data o valor de fim de outubro como 01/10. Deixado assim, uma janela que
    começa em 4 de outubro já enxergaria o fechamento do mês inteiro.
    """
    movida = serie.copy()
    movida.index = movida.index + pd.offsets.MonthEnd(0)
    return movida


def definicoes() -> list[Definicao]:
    """As séries do estudo, na ordem em que aparecem no catálogo."""
    dez_anos = "Tesouro Prefixado com Juros Semestrais, vencimento mais perto de 10 anos"
    um_ano = "Tesouro Prefixado, vencimento mais perto de 1 ano"
    return [
        _yahoo("ibov", "^BVSP", "Ibovespa, fechamento", "pontos"),
        _ipeadata("ibov_ipea", "GM366_IBVSP366", "Ibovespa, fechamento (Ipeadata)", "pontos"),
        Definicao(
            "dolar",
            "Dólar comercial, venda (antes do Real convertido: Cr$ ÷ 2.750.000, CR$ ÷ 2.750)",
            "R$ por US$",
            "BCB SGS",
            "1",
            URL_BCB.format(codigo=1),
            lambda atualizar: em_reais(bcb.sgs(1, PRIMEIRO_DIA, date.today(), atualizar)),
        ),
        _bcb("selic", 1178, "Selic diária anualizada (base 252)", "% a.a."),
        _ipeadata(
            "embi",
            "JPM366_EMBI366",
            "EMBI+ Risco-Brasil (encerrado em jul/2024)",
            "pontos-base",
        ),
        Definicao(
            "swap360_mensal",
            "Swap DI × pré 360 dias, fim de mês (mensal; data no último dia do mês)",
            "% a.a.",
            "Ipeadata",
            "BMF12_SWAPDI360F12",
            URL_IPEADATA.format(codigo="BMF12_SWAPDI360F12"),
            lambda atualizar: no_fim_do_mes(ipeadata.serie("BMF12_SWAPDI360F12", atualizar)),
        ),
        _tesouro(
            "prefixado_10a", "NTN-F ~10 anos", dez_anos, "% a.a.", "taxa", tesouro.prefixado_10a
        ),
        _tesouro(
            "prefixado_10a_prazo",
            "",
            "Prazo do título usado em prefixado_10a",
            "anos",
            "prazo_anos",
            tesouro.prefixado_10a,
        ),
        _tesouro("prefixado_1a", "LTN ~1 ano", um_ano, "% a.a.", "taxa", tesouro.prefixado_1a),
        _tesouro(
            "prefixado_1a_prazo",
            "",
            "Prazo do título usado em prefixado_1a",
            "anos",
            "prazo_anos",
            tesouro.prefixado_1a,
        ),
        Definicao(
            "msci_em",
            "MSCI Emergentes em dólar",
            "pontos (US$)",
            "MSCI",
            msci.CODIGO,
            msci.URL.format(inicio=msci.PRIMEIRO_DIA, fim="<hoje>"),
            msci.emergentes_usd,
        ),
        _yahoo("sp500", "^GSPC", "S&P 500", "pontos"),
        _yahoo("dxy", "DX-Y.NYB", "Índice do dólar no mundo", "pontos"),
        _yahoo("ust10", "^TNX", "Treasury 10 anos", "% a.a."),
    ]


def formatar_numero(valor: float) -> str:
    """Até 6 casas, sem zeros à direita: 5.5007, 206911.89, 12.9."""
    texto = f"{valor:.{CASAS_DECIMAIS}f}".rstrip("0").rstrip(".")
    return "0" if texto in ("", "-0") else texto


def gravar(serie: pd.Series, nome: str) -> None:
    """Grava `dados/series/{nome}.csv` com colunas `data,valor`."""
    tabela = pd.DataFrame(
        {
            "data": serie.index.strftime("%Y-%m-%d"),
            "valor": [formatar_numero(v) for v in serie.to_numpy()],
        }
    )
    caminhos.SERIES.mkdir(parents=True, exist_ok=True)
    tabela.to_csv(caminhos.SERIES / f"{nome}.csv", index=False)


def ler(nome: str) -> pd.Series:
    """Lê uma série gravada em `dados/series/`."""
    tabela = pd.read_csv(caminhos.SERIES / f"{nome}.csv", parse_dates=["data"])
    return pd.Series(tabela["valor"].to_numpy(dtype="float64"), index=tabela["data"], name=nome)


def extrair(atualizar: bool) -> pd.DataFrame:
    """Baixa (ou lê do cache) todas as séries, grava os CSVs e devolve o catálogo."""
    linhas = []
    for definicao in definicoes():
        serie = definicao.obter(atualizar)
        serie = serie[serie.index >= pd.Timestamp(PRIMEIRO_DIA)].dropna()
        gravar(serie, definicao.nome)
        linhas.append(
            {
                "nome": definicao.nome,
                "descricao": definicao.descricao,
                "unidade": definicao.unidade,
                "fonte": definicao.fonte,
                "codigo": definicao.codigo,
                "url": definicao.url,
                "inicio": serie.index.min().strftime("%Y-%m-%d"),
                "fim": serie.index.max().strftime("%Y-%m-%d"),
                "linhas": len(serie),
            }
        )
    catalogo = pd.DataFrame(linhas, columns=COLUNAS_CATALOGO)
    catalogo.to_csv(caminhos.SERIES / "catalogo.csv", index=False)
    return catalogo
