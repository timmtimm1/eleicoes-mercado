"""Com os dados reais do repositório (dados/series e dados/eleicoes.yaml); sem rede."""

import pandas as pd
import pytest

from eleicoes import calendario, janelas, surpresa


@pytest.fixture(scope="module")
def tabela():
    return janelas.calcular_janelas()


def _linha(tabela, ano, janela, medida="ibov"):
    linhas = tabela[(tabela["ano"] == ano) & (tabela["janela"] == janela)]
    return linhas[linhas["medida"] == medida].iloc[0]


def test_2026_depois_do_segundo_turno(tabela):
    linha = _linha(tabela, 2026, "t2_d1")
    assert linha["inicio"] == "2026-10-23"
    assert linha["fim"] == "2026-10-26"
    assert linha["variacao"] == pytest.approx(-13.88, abs=0.05)
    assert _linha(tabela, 2026, "t2_d5")["fim"] == "2026-10-30"
    assert _linha(tabela, 2026, "t2_d5")["pregoes"] == 5


def test_2026_depois_do_primeiro_turno(tabela):
    assert _linha(tabela, 2026, "t1_d1")["variacao"] == pytest.approx(7.70, abs=0.05)


def test_1994_sem_pregao_em_03_de_outubro(tabela):
    linha = _linha(tabela, 1994, "t1_d1")
    assert linha["inicio"] == "1994-09-30"
    assert linha["fim"] == "1994-10-04"


def test_1994_so_com_variacao_bruta(tabela):
    de_1994 = tabela[tabela["ano"] == 1994]
    assert de_1994["so_brasil"].isna().all()
    assert _linha(tabela, 1994, "t1_d1")["variacao"] == pytest.approx(-2.72, abs=0.05)


def test_beta_da_bolsa_em_dolar_fica_numa_faixa_plausivel(tabela):
    betas = tabela[(tabela["medida"] == "ibov_usd") & (tabela["janela"] == "corrida")]
    betas = betas.set_index("ano")["beta"].dropna()
    assert betas.between(0.5, 1.6).all(), betas.to_dict()


def test_2026_t2_d20_ainda_nao_aconteceu(tabela):
    assert _linha(tabela, 2026, "t2_d20")["status"] == "ainda_nao_aconteceu"


def test_anos_sem_segundo_turno_nao_tem_janelas_do_segundo(tabela):
    antigos = tabela[tabela["ano"].isin([1994, 1998])]
    assert not antigos["janela"].isin(janelas.JANELAS[4:8]).any()


def test_surpresa_de_2026_com_dados_reais(tabela):
    resultado = surpresa.calcular_surpresa(tabela).set_index(["ano", "turno"])
    segundo = resultado.loc[(2026, 2)]
    assert segundo["margem_resultado"] == pytest.approx(-3.58)
    assert segundo["ibov_d1"] == pytest.approx(-13.88, abs=0.05)
    assert segundo["surpresa"] < 0
    assert pd.notna(surpresa.correlacao_surpresa(resultado.reset_index()).loc[2, "correlacao"])
    assert len(calendario.carregar_eleicoes()) == 9
