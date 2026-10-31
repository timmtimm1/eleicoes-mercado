import numpy as np
import pandas as pd
import pytest

from eleicoes import calendario, surpresa

YAML = """\
- ano: 2020
  vencedor: Ana
  segundo: Beto
  posse: 2021-01-01
  situacao: oposicao
  candidato_mercado: Beto
  turnos:
    - numero: 1
      data: 2020-10-04
      resultado:
        - {candidato: Ana, pct: 45.0}
        - {candidato: Beto, pct: 40.0}
    - numero: 2
      data: 2020-10-25
      resultado:
        - {candidato: Ana, pct: 48.0}
        - {candidato: Beto, pct: 52.0}
"""

PESQUISAS = pd.DataFrame(
    [
        # 1º turno: Ana 42 e Beto 36 na média (margem do Beto: -6).
        (2020, 1, "X", "Ana", 40.0),
        (2020, 1, "X", "Beto", 35.0),
        (2020, 1, "Y", "Ana", 44.0),
        (2020, 1, "Y", "Beto", 37.0),
        (2020, 1, "Y", "Carla", 10.0),
        # 2º turno: um instituto só.
        (2020, 2, "Z", "Ana", 50.0),
        (2020, 2, "Z", "Beto", 50.0),
        (2019, 1, "W", "Ana", 99.0),
    ],
    columns=["ano", "turno", "instituto", "candidato", "pct_validos"],
)

JANELAS = pd.DataFrame(
    [
        (2020, "t1_d1", "ibov", 2.5, np.nan),
        (2020, "t1_d1", "ibov_usd", 3.0, 1.5),
        (2020, "t1_d1", "dolar", -1.0, -0.5),
        (2020, "t2_d1", "ibov", -4.0, np.nan),
    ],
    columns=["ano", "janela", "medida", "variacao", "so_brasil"],
)


@pytest.fixture
def tabela(tmp_path):
    caminho = tmp_path / "eleicoes.yaml"
    caminho.write_text(YAML, encoding="utf-8")
    return surpresa.calcular(calendario.carregar_eleicoes(caminho), PESQUISAS, JANELAS)


def test_margens_e_surpresa_a_favor_do_candidato_do_mercado(tabela):
    assert list(tabela.columns) == surpresa.COLUNAS
    primeiro = tabela.iloc[0]
    assert primeiro["candidato_mercado"] == "Beto"
    assert primeiro["adversario"] == "Ana"
    assert primeiro["margem_resultado"] == pytest.approx(-5.0)
    assert primeiro["margem_pesquisas"] == pytest.approx(-6.0)
    assert primeiro["surpresa"] == pytest.approx(1.0)
    assert primeiro["favorito_pesquisas"] == "Ana"
    assert not primeiro["mercado_ganhou_turno"]
    assert primeiro["institutos"] == "X;Y"
    assert primeiro["n_institutos"] == 2
    assert primeiro["data"] == "2020-10-04"


def test_segundo_turno_empatado_nas_pesquisas_e_vitoria_do_mercado(tabela):
    segundo = tabela.iloc[1]
    assert segundo["margem_resultado"] == pytest.approx(4.0)
    assert segundo["margem_pesquisas"] == pytest.approx(0.0)
    assert segundo["surpresa"] == pytest.approx(4.0)
    assert segundo["favorito_pesquisas"] == "empate"
    assert segundo["mercado_ganhou_turno"]


def test_reacao_no_d1_vem_das_janelas(tabela):
    primeiro, segundo = tabela.iloc[0], tabela.iloc[1]
    assert primeiro["ibov_d1"] == 2.5
    assert primeiro["ibov_usd_so_brasil_d1"] == 1.5
    assert primeiro["dolar_d1"] == -1.0
    assert primeiro["dolar_so_brasil_d1"] == -0.5
    assert np.isnan(primeiro["prefixado_10a_d1"])
    assert segundo["ibov_d1"] == -4.0
    assert np.isnan(segundo["dolar_d1"])


def test_sem_pesquisa_a_surpresa_fica_vazia(tmp_path):
    caminho = tmp_path / "eleicoes.yaml"
    caminho.write_text(YAML, encoding="utf-8")
    vazio = PESQUISAS.iloc[0:0]
    tabela = surpresa.calcular(calendario.carregar_eleicoes(caminho), vazio, JANELAS)
    assert tabela["margem_pesquisas"].isna().all()
    assert tabela["surpresa"].isna().all()
    assert (tabela["favorito_pesquisas"] == "").all()
    assert (tabela["n_institutos"] == 0).all()


def test_correlacao_de_uma_reta_perfeita():
    tabela = pd.DataFrame(
        {
            "turno": [1, 1, 1, 2, 2, 2, 2],
            "surpresa": [-2.0, 0.0, 3.0, -4.0, 1.0, 2.0, np.nan],
            "ibov_d1": [-4.0, 0.0, 6.0, 8.0, -2.0, -4.0, 1.0],
        }
    )
    resultado = surpresa.correlacao_surpresa(tabela).set_index("grupo")
    assert resultado.loc["1º turno", "n"] == 3
    assert resultado.loc["1º turno", "correlacao"] == pytest.approx(1.0)
    assert resultado.loc["1º turno", "inclinacao"] == pytest.approx(2.0)
    assert resultado.loc["2º turno", "n"] == 3  # a linha sem surpresa não entra
    assert resultado.loc["2º turno", "correlacao"] == pytest.approx(-1.0)
    assert resultado.loc["todos", "n"] == 6
