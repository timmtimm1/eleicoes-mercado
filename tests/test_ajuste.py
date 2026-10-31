import numpy as np
import pandas as pd
import pytest

from eleicoes import ajuste

DATAS = pd.bdate_range("2010-03-01", periods=8)
IBOV_PLANO = pd.Series(100_000.0, index=pd.bdate_range("2010-01-01", "2010-12-31"))


def _quadro(precos, especi=None, ticker="XXXX4", fatcot=1):
    return pd.DataFrame(
        {
            "data": DATAS[: len(precos)],
            "ticker": ticker,
            "especi": especi or ["PN  N1"] * len(precos),
            "fechamento": precos,
            "fatcot": fatcot,
        }
    )


def test_desdobramento_2_para_1_e_neutralizado():
    especi = ["PN  N1"] * 4 + ["PN  EB N1"] * 4
    adj, ajustes, _ = ajuste.ajustar_papel(
        _quadro([40, 41, 42, 41, 20.5, 20.8, 21, 20.6], especi), IBOV_PLANO
    )
    assert [(a.motivo, a.fator) for a in ajustes] == [(ajuste.MOTIVO_MARCADO, 0.5)]
    assert ajustes[0].data == DATAS[4]
    assert ajustes[0].variacao_bruta == pytest.approx(-50.0)
    # O último preço fica igual ao bruto e os anteriores caem para a mesma escala.
    assert adj.iloc[-1] == pytest.approx(20.6)
    assert adj.iloc[3] == pytest.approx(20.5)
    assert adj.pct_change().abs().max() < 0.03


def test_bonificacao_de_10_por_cento_e_neutralizada():
    especi = ["PN  N1"] * 3 + ["PN  EB N1"] * 3
    adj, ajustes, _ = ajuste.ajustar_papel(
        _quadro([22, 22.2, 22.0, 20.1, 20.3, 20.2], especi), IBOV_PLANO
    )
    assert len(ajustes) == 1
    assert ajustes[0].fator == pytest.approx(1 / 1.1)
    assert adj.pct_change().abs().max() < 0.015


def test_dividendo_sem_bonificacao_nao_e_evento_em_acoes():
    especi = ["PN  N1"] * 3 + ["PN  ED N1"] * 3
    adj, ajustes, _ = ajuste.ajustar_papel(
        _quadro([22, 22.2, 22.0, 21.4, 21.5, 21.6], especi), IBOV_PLANO
    )
    assert ajustes == []
    assert adj.iloc[0] == 22


def test_tira_o_mercado_antes_de_achar_o_fator():
    ibov = IBOV_PLANO.copy()
    ibov[DATAS[4] :] = 97_000.0  # o índice cai 3% no dia do desdobramento
    especi = ["PN  N1"] * 4 + ["PN  EB N1"] * 4
    _, ajustes, _ = ajuste.ajustar_papel(_quadro([40, 41, 42, 41, 19.9, 20, 20, 20], especi), ibov)
    assert [a.fator for a in ajustes] == [0.5]


def test_variacao_grande_sem_fator_redondo_nao_e_neutralizada():
    adj, ajustes, _ = ajuste.ajustar_papel(
        _quadro([40, 41, 42, 41, 24.6, 25, 25.5, 25]), IBOV_PLANO
    )
    assert ajustes == []
    assert adj.iloc[3] == 41  # queda de 40% de verdade fica na série


def test_evento_marcado_sem_fator_e_registrado_e_nao_neutralizado():
    especi = ["PN  N1"] * 4 + ["PN  EB N1"] * 4
    adj, ajustes, _ = ajuste.ajustar_papel(
        _quadro([40, 41, 42, 41, 24, 24.2, 24, 24], especi), IBOV_PLANO
    )
    assert [(a.motivo, np.isnan(a.fator)) for a in ajustes] == [(ajuste.MOTIVO_SEM_FATOR, True)]
    assert adj.iloc[3] == 41


def test_variacao_grande_sem_sufixo_com_fator_cheio_e_neutralizada():
    _, ajustes, _ = ajuste.ajustar_papel(
        _quadro([40, 41, 42, 41, 20.5, 20.8, 21, 20.6]), IBOV_PLANO
    )
    assert [(a.motivo, a.fator) for a in ajustes] == [(ajuste.MOTIVO_GRANDE, 0.5)]


def test_grupamento_com_mudanca_de_cotacao_usa_fator_combinado():
    # Grupamento de 1.000 para 1 junto com desdobramento de 2 para 1: o preço sobe 500 vezes.
    especi = ["PN  N1"] * 3 + ["PN  EG N1"] * 3
    _, ajustes, _ = ajuste.ajustar_papel(
        _quadro([0.07, 0.075, 0.08, 39.4, 40, 40.5], especi, fatcot=1000), IBOV_PLANO
    )
    assert [a.fator for a in ajustes] == pytest.approx([500])


def test_papel_de_centavos_nao_identifica_fator():
    # Degrau de R$ 0,01 num papel de R$ 0,02: dobrar ou cair pela metade é ruído.
    _, ajustes, _ = ajuste.ajustar_papel(_quadro([0.02, 0.01, 0.02, 0.01]), IBOV_PLANO)
    assert ajustes == []


def test_sufixo_do_evento():
    especi = pd.Series(["PN  EB N1", "ON *EJ", "UNT  N2", "PNA  EDB", "ON", "PN *INT"])
    assert list(ajuste.sufixo_do_evento(especi)) == ["EB", "EJ", "", "EDB", "", ""]
    assert ajuste.e_evento_em_acoes("EB")
    assert ajuste.e_evento_em_acoes("EG")
    assert ajuste.e_evento_em_acoes("EDB")
    assert not ajuste.e_evento_em_acoes("ED")
    assert not ajuste.e_evento_em_acoes("EJ")
    assert not ajuste.e_evento_em_acoes("ES")
