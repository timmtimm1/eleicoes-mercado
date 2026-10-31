from datetime import date

import pandas as pd
import pytest

from eleicoes import calendario

# Quarta 07/10 é feriado: sem pregão. 10 e 11 são fim de semana.
PREGOES = pd.DatetimeIndex(
    pd.to_datetime(
        [
            "2020-10-01",
            "2020-10-02",
            "2020-10-05",
            "2020-10-06",
            "2020-10-08",
            "2020-10-09",
            "2020-10-12",
            "2020-10-13",
        ]
    )
)

YAML = """\
# Cabeçalho de comentários
# que o carregador ignora.
- ano: 2020
  vencedor: Ana
  segundo: Beto
  posse: 2021-01-01
  situacao: oposicao
  candidato_mercado: Beto
  turnos:
    - numero: 2
      data: 2020-10-25
      resultado:
        - {candidato: Ana, pct: 52.0}
        - {candidato: Beto, pct: 48.0}
    - numero: 1
      data: 2020-10-04
      resultado:
        - {candidato: Ana, pct: 40.0}
        - {candidato: Beto, pct: 35.0}
"""


def test_ultimo_pregao_antes_e_estritamente_antes():
    assert calendario.ultimo_pregao_antes("2020-10-05", PREGOES) == pd.Timestamp("2020-10-02")
    # Domingo: o último pregão antes é a sexta.
    assert calendario.ultimo_pregao_antes(date(2020, 10, 4), PREGOES) == pd.Timestamp("2020-10-02")
    # Feriado no meio: o pregão antes de quinta 08/10 é terça 06/10.
    assert calendario.ultimo_pregao_antes("2020-10-08", PREGOES) == pd.Timestamp("2020-10-06")


def test_ultimo_pregao_ate_inclui_o_proprio_dia():
    assert calendario.ultimo_pregao_ate("2020-10-05", PREGOES) == pd.Timestamp("2020-10-05")
    assert calendario.ultimo_pregao_ate("2020-10-07", PREGOES) == pd.Timestamp("2020-10-06")
    assert calendario.ultimo_pregao_ate("2020-10-11", PREGOES) == pd.Timestamp("2020-10-09")


def test_pregao_depois_conta_pregoes_e_nao_dias():
    assert calendario.pregao_depois("2020-10-04", 1, PREGOES) == pd.Timestamp("2020-10-05")
    # Pulando o feriado de 07/10: 05, 06, 08, 09, 12.
    assert calendario.pregao_depois("2020-10-04", 5, PREGOES) == pd.Timestamp("2020-10-12")
    # Estritamente depois: a partir de um pregão, ele mesmo não conta.
    assert calendario.pregao_depois("2020-10-05", 1, PREGOES) == pd.Timestamp("2020-10-06")


def test_datas_fora_do_calendario_devolvem_none():
    assert calendario.pregao_depois("2020-10-04", 20, PREGOES) is None
    assert calendario.pregao_depois("2020-10-13", 1, PREGOES) is None
    assert calendario.ultimo_pregao_ate("2020-12-01", PREGOES) is None
    assert calendario.ultimo_pregao_antes("2020-12-01", PREGOES) is None
    assert calendario.ultimo_pregao_antes("2020-10-01", PREGOES) is None
    assert calendario.ultimo_pregao_ate("2020-09-30", PREGOES) is None


def test_carregar_eleicoes(tmp_path):
    caminho = tmp_path / "eleicoes.yaml"
    caminho.write_text(YAML, encoding="utf-8")
    (eleicao,) = calendario.carregar_eleicoes(caminho)
    assert eleicao.ano == 2020
    assert eleicao.posse == date(2021, 1, 1)
    assert eleicao.adversario_mercado == "Ana"
    assert eleicao.primeiro_turno.data == date(2020, 10, 4)
    assert eleicao.turno_decisivo.numero == 2
    assert eleicao.turno_decisivo.resultado == {"Ana": 52.0, "Beto": 48.0}


def test_adversario_quando_o_mercado_ganhou(tmp_path):
    caminho = tmp_path / "eleicoes.yaml"
    caminho.write_text(YAML.replace("candidato_mercado: Beto", "candidato_mercado: Ana"))
    (eleicao,) = calendario.carregar_eleicoes(caminho)
    assert eleicao.adversario_mercado == "Beto"


def test_pregoes_vem_da_serie_ibov(pasta_dados):
    from eleicoes import series

    series.gravar(pd.Series([1.0, 2.0], index=pd.to_datetime(["2020-10-01", "2020-10-02"])), "ibov")
    assert list(calendario.pregoes()) == [pd.Timestamp("2020-10-01"), pd.Timestamp("2020-10-02")]


@pytest.mark.parametrize("n", [1, 2])
def test_pregao_depois_devolve_timestamp(n):
    assert isinstance(calendario.pregao_depois("2020-10-01", n, PREGOES), pd.Timestamp)
