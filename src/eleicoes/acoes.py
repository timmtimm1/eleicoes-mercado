"""Preços diários das ações da B3, a partir dos Parquets do COTAHIST.

Só ação de empresa: ON, PN (qualquer classe: PNA, PNB...) e unit. Ficam de fora BDR (`DR1`,
`DR2`, `DR3`, `DRN`...), recibo (`R11`, `RON`, `RPN`, `REC`), direito (`DIR`), bônus (`BNS`),
cotas de fundo e ETF (`CI`, `IBO`, `FID`...) e qualquer outra `especi`. A coluna `especi` do
COTAHIST traz o tipo na primeira palavra e, depois, o segmento de governança (`NM`, `N1`) ou
um evento (`*ED` com dividendo, `*EJ` com juros): só o tipo decide.

CODBDI: 02 (lote padrão) e os de situação especial (05 a 09: sancionada, concordatária,
recuperação). O 14 não entra, com uma exceção: até 2007 a B3 listava as units (Unibanco,
ALL, Equatorial) no 14, junto com os fundos, e sem elas o Unibanco sumiria do estudo. No 14 só
passam linhas cuja `especi` é unit.

Tickers: até 13/03/1998 o ticker tinha 3 letras e um espaço (`TEL 4`, `PET 4`); depois passou
a 4 letras (`TELB4`, `PETR4`). O espaço é tirado do ticker e a raiz das linhas antigas vem do
código da empresa no ISIN (`BRTELBACNPR9` e `TELBACPN` dão `TELB`), que é o mesmo nos dois
formatos. O ticker antigo vira o novo: raiz do ISIN mais o número da classe (`TEL 4` vira
`TELB4`, `PET 4` vira `PETR4`). Sem isso a janela de 1998 trataria `TEL` e `TELB` como duas
empresas, e os preços de um papel teriam dois nomes.

Moeda: os preços e volumes de 1993 e do 1º semestre de 1994 estão em cruzeiros (até julho de
1993) e cruzeiros reais (agosto de 1993 a 30/06/1994); o Real começa em 01/07/1994. Nada aqui
converte: quem compara volumes tem de ficar de 01/07/1994 em diante (`INICIO_REAL`).
"""

import re
from datetime import date

import pandas as pd

from eleicoes.fontes import cotahist

INICIO_REAL = date(1994, 7, 1)

COLUNAS = [
    "data",
    "ticker",
    "raiz",
    "nomres",
    "especi",
    "codbdi",
    "fechamento",
    "volume",
    "negocios",
    "fatcot",
]

CODBDI_ACAO = frozenset({"02", "05", "06", "07", "08", "09"})
# Units que a B3 lançava no CODBDI 14 até 2007 (ver docstring do módulo).
CODBDI_UNIT_EM_14 = "14"

# Tipo de ação na `especi`: ON, PN, PNA..PNG, PNV e UNT, seguidos de espaço, `*` ou fim.
# O lookahead barra `PRA`, `PRB`, `PNX...` desconhecidos e `DRN`, `DIR`, `REC`.
_TIPO_ACAO = re.compile(r"^(ON|PN[A-Z]?|UNT)(?![A-Z])")
_TICKER_ANTIGO = re.compile(r"^.{3} ")


def tipo_da_especi(especi: pd.Series) -> pd.Series:
    """Primeira palavra da `especi`; vazio se não é ação (ON, PN, PNA... ou UNT)."""
    return especi.str.extract(_TIPO_ACAO)[0].fillna("")


def so_acoes(quadro: pd.DataFrame) -> pd.DataFrame:
    """Linhas de ação de empresa: tipo ON/PN/UNT no CODBDI certo (ver docstring do módulo)."""
    tipo = tipo_da_especi(quadro["especi"])
    e_acao = tipo != ""
    no_codbdi = quadro["codbdi"].isin(CODBDI_ACAO) | (
        (quadro["codbdi"] == CODBDI_UNIT_EM_14) & (tipo == "UNT")
    )
    return quadro[e_acao & no_codbdi]


def raiz_do_ticker(ticker: pd.Series, isin: pd.Series) -> pd.Series:
    """Quatro primeiras letras do ticker; nos tickers antigos (`TEL 4`), o código do ISIN."""
    # ISIN de 12 posições (`BRTELBACNPR9`): empresa em 3-6. Os mais velhos (`TELBACPN`): 1-4.
    completo = (isin.str.len() == 12) & isin.str.startswith("BR")
    codigo = isin.str[2:6].where(completo, isin.str[:4])
    antigo = _e_ticker_antigo(ticker, isin)
    return codigo.where(antigo, ticker.str[:4]).str.strip()


def _e_ticker_antigo(ticker: pd.Series, isin: pd.Series) -> pd.Series:
    """Ticker de 3 letras e espaço (`TEL 4`) com ISIN que dá o código da empresa."""
    return ticker.str.match(_TICKER_ANTIGO) & (isin.str.len() >= 8)


def ticker_no_formato_novo(ticker: pd.Series, raiz: pd.Series, isin: pd.Series) -> pd.Series:
    """`TEL 4` com raiz `TELB` vira `TELB4`; os tickers de 4 letras só perdem espaços."""
    antigo = _e_ticker_antigo(ticker, isin) & (raiz.str.len() == 4)
    novo = raiz + ticker.str[4:].str.strip()
    return novo.where(antigo, ticker.str.replace(" ", "", regex=False))


def ler_precos(inicio: date, fim: date) -> pd.DataFrame:
    """Ações negociadas de `inicio` a `fim` (inclusive), uma linha por papel e dia.

    Colunas: data, ticker, raiz, nomres, especi, codbdi, fechamento, volume, negocios, fatcot
    (o fator de cotação dá o menor degrau de preço: 0,01 / fatcot).
    O volume é financeiro, na moeda da época (ver docstring do módulo). Lê só os Parquets dos
    anos que a janela toca, e só as colunas de que precisa.
    """
    partes = []
    for ano in range(inicio.year, fim.year + 1):
        caminho = cotahist.caminho_parquet(ano)
        if not caminho.exists():
            raise FileNotFoundError(f"{caminho} não existe; rode `eleicoes liquidez` antes.")
        quadro = pd.read_parquet(
            caminho,
            columns=[
                "data",
                "codbdi",
                "ticker",
                "nomres",
                "especi",
                "isin",
                "fechamento",
                "volume",
                "negocios",
                "fatcot",
            ],
        )
        quadro["data"] = pd.to_datetime(quadro["data"])
        no_periodo = (quadro["data"] >= pd.Timestamp(inicio)) & (
            quadro["data"] <= pd.Timestamp(fim)
        )
        quadro = quadro[no_periodo]
        partes.append(so_acoes(quadro))
    if not partes:
        return pd.DataFrame(columns=COLUNAS)
    todos = pd.concat(partes, ignore_index=True)
    todos["raiz"] = raiz_do_ticker(todos["ticker"], todos["isin"])
    todos["ticker"] = ticker_no_formato_novo(todos["ticker"], todos["raiz"], todos["isin"])
    return todos[COLUNAS].sort_values(["data", "ticker"], ignore_index=True)
