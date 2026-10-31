"""Com os dados reais: precisa dos Parquets do COTAHIST em dados/cache/b3 e de liquidez.csv."""

from datetime import date

import pandas as pd
import pytest

from eleicoes import acoes, calendario, caminhos, carteiras, series
from eleicoes import empresas as empresas_csv
from eleicoes.fontes import cotahist

pytestmark = pytest.mark.skipif(
    not (
        cotahist.caminho_parquet(2008).exists() and (caminhos.RESULTADOS / "liquidez.csv").exists()
    ),
    reason="precisa do cache do COTAHIST e de dados/resultados/liquidez.csv",
)


@pytest.fixture(scope="module")
def resultado():
    liquidez = pd.read_csv(caminhos.RESULTADOS / "liquidez.csv")
    sucessoes = empresas_csv.carregar_sucessoes()
    eleicao = next(e for e in calendario.carregar_eleicoes() if e.ano == 2026)
    pregoes = calendario.pregoes()
    precos = acoes.ler_precos(date(2025, 6, 1), date(2026, 10, 30))
    mercado = carteiras.montar_mercado(precos, series.ler("ibov"))
    empresas, _ = carteiras.variacoes_das_empresas(eleicao, liquidez, mercado, sucessoes, pregoes)
    return carteiras.montar_carteiras(eleicao, empresas, pregoes)


def test_2026_t2_d1_tem_5_estatais(resultado):
    linhas = resultado[resultado["janela"] == "t2_d1"].set_index("carteira")
    assert linhas.loc["estatais", "n_empresas"] == 5
    assert linhas.loc["privadas", "n_empresas"] == 55
    assert linhas.loc["todas", "n_empresas"] == 60
    assert linhas.loc["estatais_menos_privadas", "variacao"] == pytest.approx(
        linhas.loc["estatais", "variacao"] - linhas.loc["privadas", "variacao"]
    )


def test_petr4_em_abril_de_2008_sem_queda_de_50_por_cento():
    precos = acoes.ler_precos(date(2008, 4, 1), date(2008, 5, 30))
    petr4 = precos[precos["ticker"] == "PETR4"]
    bruto = petr4.set_index("data")["fechamento"]
    assert bruto.pct_change().min() < -0.4  # o desdobramento está no preço bruto
    ajustada, ajustes, _ = carteiras.ajuste.ajustar_papel(petr4, series.ler("ibov"))
    assert ajustada.pct_change().min() > -0.1
    assert [(a.data, a.fator) for a in ajustes] == [(pd.Timestamp("2008-04-28"), 0.5)]
