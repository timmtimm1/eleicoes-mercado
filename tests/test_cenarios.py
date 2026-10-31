import numpy as np
import pandas as pd
import pytest

from eleicoes import cenarios


def _janelas(ano, d5, posse, medida="ibov_usd", partida="t2_d5"):
    """Duas linhas de janelas.csv: só Brasil no D+5 e até a posse, para uma medida."""
    return pd.DataFrame(
        {
            "ano": [ano, ano],
            "janela": [partida, "ate_posse"],
            "medida": [medida, medida],
            "so_brasil": [d5, posse],
        }
    )


def test_trecho_depois_da_partida_em_percentual():
    # Até o D+5 caiu 20%; até a posse, 10% desde o começo: do D+5 à posse subiu 12,5%.
    janelas = _janelas(2022, -20.0, -10.0)
    assert cenarios._desde_a_partida(janelas, 2022, "ibov_usd", "ate_posse") == pytest.approx(12.5)


def test_trecho_depois_da_partida_em_pontos_e_eleicao_de_um_turno():
    janelas = _janelas(1998, 0.4, 1.0, medida="prefixado_10a", partida="t1_d5")
    valor = cenarios._desde_a_partida(janelas, 1998, "prefixado_10a", "ate_posse")
    assert valor == pytest.approx(0.6)


def test_ibov_em_reais_e_o_em_dolar_vezes_o_dolar():
    janelas = pd.concat(
        [_janelas(2014, 0.0, -10.0, "ibov_usd"), _janelas(2014, 0.0, 20.0, "dolar")]
    )
    caminhos_ = cenarios.caminhos_pos_choque(janelas)
    linha = caminhos_[(caminhos_["horizonte"] == "ate_posse") & (caminhos_["medida"] == "ibov")]
    assert linha["so_brasil"].iloc[0] == pytest.approx((0.9 * 1.2 - 1) * 100)


def test_faixa_vai_do_menor_ao_maior_analogo_e_aplica_no_nivel():
    caminhos_ = pd.DataFrame(
        {
            "ano": [2002, 2006, 2010],
            "horizonte": ["ate_posse"] * 3,
            "medida": ["dolar"] * 3,
            "so_brasil": [-10.0, 10.0, 50.0],
            "unidade": ["%"] * 3,
        }
    )
    premissas = {
        "status": "proposta",
        "horizontes": {"ate_posse": "2027-01-04", "posse_100d": "x", "posse_1ano": "y"},
        "cenarios": [{"nome": "otimista", "analogos": [2002, 2006]}],
    }
    base = {"ibov": 100.0, "ibov_usd": 20.0, "dolar": 5.0, "prefixado_10a": 15.0}
    tabela = cenarios.projetar(caminhos_, premissas, base)
    linha = tabela[(tabela["horizonte"] == "ate_posse") & (tabela["medida"] == "dolar")].iloc[0]
    assert (linha["minimo"], linha["central"], linha["maximo"]) == (-10.0, 0.0, 10.0)
    assert linha["nivel_minimo"] == pytest.approx(4.5)
    assert linha["nivel_maximo"] == pytest.approx(5.5)
    assert linha["analogos_com_dado"] == "2002;2006"
    sem_dado = tabela[(tabela["horizonte"] == "posse_1ano") & (tabela["medida"] == "dolar")]
    assert np.isnan(sem_dado["central"].iloc[0])


def test_premissas_do_repositorio_tem_os_tres_cenarios_e_seguem_como_proposta():
    premissas = cenarios.carregar_premissas()
    assert [c["nome"] for c in premissas["cenarios"]] == ["otimista", "base", "pessimista"]
    assert all(len(c["analogos"]) == 2 for c in premissas["cenarios"])
    assert all(c["gatilhos"] for c in premissas["cenarios"])
    assert str(premissas["posse"]) == "2027-01-05"
