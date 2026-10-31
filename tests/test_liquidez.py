from datetime import date

import pandas as pd

from eleicoes import liquidez
from eleicoes.calendario import Eleicao, Turno

PREGOES = pd.bdate_range("1994-01-03", "2010-12-31")


def _eleicao(ano, dia_do_turno):
    return Eleicao(
        ano=ano,
        vencedor="Ana",
        segundo="Beto",
        posse=date(ano + 1, 1, 1),
        situacao="oposicao",
        candidato_mercado="Beto",
        turnos=(Turno(1, dia_do_turno, {"Ana": 50.0, "Beto": 40.0}),),
    )


def _precos(linhas):
    """linhas: (data, raiz, ticker, volume)."""
    return pd.DataFrame(
        [
            {
                "data": pd.Timestamp(data),
                "ticker": ticker,
                "raiz": raiz,
                "nomres": raiz + " SA",
                "especi": "PN" if ticker.endswith("4") else "ON",
                "codbdi": "02",
                "fechamento": 10.0,
                "volume": volume,
                "negocios": 1,
            }
            for data, raiz, ticker, volume in linhas
        ]
    )


def test_periodo_termina_no_ultimo_pregao_antes_do_turno_e_tem_365_dias():
    # 3 de outubro de 2010 é domingo: o último pregão antes é a sexta, 1º de outubro.
    inicio, fim = liquidez.periodo(_eleicao(2010, date(2010, 10, 3)), PREGOES)
    assert fim == date(2010, 10, 1)
    assert inicio == date(2009, 10, 2)
    assert (fim - inicio).days + 1 == 365


def test_periodo_de_1994_comeca_no_real():
    inicio, fim = liquidez.periodo(_eleicao(1994, date(1994, 10, 3)), PREGOES)
    assert fim == date(1994, 9, 30)
    assert inicio == date(1994, 7, 1)


def test_ranking_soma_a_raiz_e_o_representante_e_o_ticker_mais_negociado():
    precos = _precos(
        [
            ("2010-01-04", "AAAA", "AAAA3", 100.0),
            ("2010-01-04", "AAAA", "AAAA4", 300.0),
            ("2010-01-05", "AAAA", "AAAA3", 150.0),
            ("2010-01-04", "BBBB", "BBBB4", 500.0),
            ("2010-01-05", "BBBB", "BBBB4", 0.0),
            ("2010-01-05", "CCCC", "CCCC3", 10_000_000.0),
        ]
    )
    tabela = liquidez.ranking(precos, 2010)

    assert list(tabela["raiz"]) == ["CCCC", "AAAA", "BBBB"]
    assert list(tabela["posicao"]) == [1, 2, 3]
    assert list(tabela["ticker"]) == ["CCCC3", "AAAA4", "BBBB4"]
    assert list(tabela["especi"]) == ["ON", "PN", "PN"]
    aaaa = tabela[tabela["raiz"] == "AAAA"].iloc[0]
    assert aaaa["volume_milhoes"] == 550.0 / 1e6
    assert aaaa["pregoes_com_negocio"] == 2
    # Dois pregões no período; BBBB só teve negócio num deles (volume 0 não conta).
    assert set(tabela["pregoes_no_periodo"]) == {2}
    assert tabela[tabela["raiz"] == "BBBB"].iloc[0]["pregoes_com_negocio"] == 1


def test_ranking_fica_com_as_maiores_raizes():
    precos = _precos([("2010-01-04", f"R{i:03d}", f"R{i:03d}3", float(i)) for i in range(1, 11)])
    tabela = liquidez.ranking(precos, 2010, top=3)
    assert list(tabela["raiz"]) == ["R010", "R009", "R008"]


def test_calcular_liquidez_usa_o_periodo_de_cada_eleicao_e_ordena():
    pedidos = []

    def ler(inicio, fim):
        pedidos.append((inicio, fim))
        return _precos([(fim, "AAAA", "AAAA3", 1.0), (fim, "BBBB", "BBBB3", 2.0)])

    eleicoes = [_eleicao(2010, date(2010, 10, 3)), _eleicao(1994, date(1994, 10, 3))]
    tabela = liquidez.calcular_liquidez(eleicoes, PREGOES, ler=ler)

    assert pedidos == [
        (date(2009, 10, 2), date(2010, 10, 1)),
        (date(1994, 7, 1), date(1994, 9, 30)),
    ]
    assert list(tabela.columns) == liquidez.COLUNAS
    assert list(zip(tabela["ano"], tabela["posicao"], tabela["raiz"], strict=True)) == [
        (1994, 1, "BBBB"),
        (1994, 2, "AAAA"),
        (2010, 1, "BBBB"),
        (2010, 2, "AAAA"),
    ]
