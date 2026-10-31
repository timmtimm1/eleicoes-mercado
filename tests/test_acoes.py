from datetime import date

import pandas as pd

from eleicoes import acoes
from eleicoes.fontes import cotahist


def _linha(ticker, especi, codbdi="02", data="2010-05-03", isin="", volume=1000.0):
    return {
        "data": date.fromisoformat(data),
        "codbdi": codbdi,
        "ticker": ticker,
        "nomres": "EMPRESA",
        "especi": especi,
        "isin": isin,
        "fechamento": 10.0,
        "volume": volume,
        "negocios": 5,
    }


def test_so_acoes_tira_bdr_recibo_direito_etf_e_fundo():
    quadro = pd.DataFrame(
        [
            _linha("PETR3", "ON  ED N2"),
            _linha("PETR4", "PN  N2"),
            _linha("CSAN5", "PNA  N1"),
            _linha("CESP6", "PNB"),
            _linha("TAEE11", "UNT  N2"),
            _linha("AAPL34", "DRN"),
            _linha("BPAT33", "DR3"),
            _linha("RCTB41", "RPN*"),
            _linha("RCSA11", "R11"),
            _linha("PETR1", "DIR  PN"),
            _linha("VALE9", "BNS  PN"),
            _linha("BOVA11", "CI", codbdi="14"),
            _linha("IBOV11", "IBOV", codbdi="02"),
            _linha("HGLG11", "CI", codbdi="12"),
        ]
    )
    assert list(acoes.so_acoes(quadro)["ticker"]) == [
        "PETR3",
        "PETR4",
        "CSAN5",
        "CESP6",
        "TAEE11",
    ]


def test_so_acoes_mantem_situacao_especial_e_unit_no_codbdi_14():
    quadro = pd.DataFrame(
        [
            _linha("OGXP3", "ON", codbdi="08"),
            _linha("CBMA4", "PN", codbdi="05"),
            _linha("UBBR11", "UNT", codbdi="14", data="2006-05-03"),
            _linha("YPF 5", "ON", codbdi="14"),
            _linha("SMAL11", "SML)", codbdi="02"),
        ]
    )
    assert list(acoes.so_acoes(quadro)["ticker"]) == ["OGXP3", "CBMA4", "UBBR11"]


def test_raiz_e_ticker_dos_dois_formatos():
    ticker = pd.Series(["TEL 4", "PET 4", "TELB4", "PETR4", "TAEE11"])
    isin = pd.Series(["TELBACPN", "BRPETRACNPR6", "BRTELBACNPR9", "BRPETRACNPR6", "BRTAEEACNPR0"])
    raiz = acoes.raiz_do_ticker(ticker, isin)
    assert list(raiz) == ["TELB", "PETR", "TELB", "PETR", "TAEE"]
    assert list(acoes.ticker_no_formato_novo(ticker, raiz, isin)) == [
        "TELB4",
        "PETR4",
        "TELB4",
        "PETR4",
        "TAEE11",
    ]


def test_ler_precos_corta_o_periodo_e_le_so_os_anos_necessarios(pasta_dados):
    destino = cotahist.caminho_parquet(2009)
    destino.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _linha("PETR4", "PN", data="2009-12-30", isin="BRPETRACNPR6"),
            _linha("AAPL34", "DRN", data="2009-12-30"),
        ]
    ).to_parquet(destino)
    pd.DataFrame(
        [
            _linha("PETR4", "PN", data="2010-01-04", isin="BRPETRACNPR6"),
            _linha("PETR4", "PN", data="2010-02-01", isin="BRPETRACNPR6"),
        ]
    ).to_parquet(cotahist.caminho_parquet(2010))
    # 2011 não existe e não é pedido: ler_precos não deve tocar nele.
    precos = acoes.ler_precos(date(2009, 12, 31), date(2010, 1, 31))

    assert list(precos.columns) == acoes.COLUNAS
    assert list(precos["ticker"]) == ["PETR4"]
    assert precos["data"].iloc[0] == pd.Timestamp("2010-01-04")
    assert precos["raiz"].iloc[0] == "PETR"
