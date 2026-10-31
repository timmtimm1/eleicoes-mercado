import pandas as pd
import pytest

from eleicoes import conferir, series


def _gravar(nome, datas, valores):
    series.gravar(pd.Series(valores, index=pd.to_datetime(datas)), nome)


def test_variacao_usa_o_pregao_anterior_existente():
    # 02/10 é domingo e 03/10 não tem dado: o pregão anterior a 04/10 é 29/09.
    serie = pd.Series([100.0, 110.0], index=pd.to_datetime(["2026-09-29", "2026-10-04"]))
    assert conferir.variacao_percentual(serie, pd.Timestamp("2026-10-04")) == pytest.approx(10.0)
    assert conferir.variacao_percentual(
        serie, pd.Timestamp("2026-09-29")
    ) != conferir.variacao_percentual(serie, pd.Timestamp("2026-09-29"))  # primeira data: NaN
    assert pd.isna(conferir.variacao_percentual(serie, pd.Timestamp("2026-10-03")))


def test_conferir_marca_ok_dentro_e_fora_da_tolerancia(pasta_dados):
    _gravar("ibov", ["2026-10-02", "2026-10-05"], [100.0, 107.7])
    checagens = [
        conferir.Checagem("dentro", "ibov", "2026-10-05", 7.70, 0.05, "teste", variacao=True),
        conferir.Checagem("fora", "ibov", "2026-10-05", 7.90, 0.05, "teste", variacao=True),
        conferir.Checagem("nível", "ibov", "2026-10-05", 107.0, 0.5, "teste"),
        conferir.Checagem("sem dado", "ibov", "2026-10-06", 107.0, 0.5, "teste"),
    ]
    tabela = conferir.conferir(checagens)
    assert list(tabela.columns) == conferir.COLUNAS
    assert list(tabela["ok"]) == [True, False, False, False]
    assert tabela.loc[1, "diferenca"] == pytest.approx(-0.2)


def test_comparar_ibov_conta_datas_e_diferencas(pasta_dados, monkeypatch):
    _gravar("ibov", ["2022-10-03", "2022-10-04", "2022-10-05"], [100.0, 102.0, 104.0])
    _gravar("ibov_ipea", ["2022-10-03", "2022-10-04", "2022-10-06"], [100.0, 100.0, 90.0])
    monkeypatch.setattr(conferir, "ANOS_DE_ELEICAO", [2022])
    tabela = conferir.comparar_ibov()
    linha = tabela.iloc[0]
    assert linha["datas_comuns"] == 2
    assert linha["maior_diferenca_pct"] == pytest.approx(2.0)
    assert linha["mediana_diferenca_pct"] == pytest.approx(1.0)
    assert linha["so_yahoo"].startswith("1 (2022-10-05")
    assert linha["so_ipeadata"].startswith("1 (2022-10-06")
