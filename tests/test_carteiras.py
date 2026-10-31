from datetime import date

import numpy as np
import pandas as pd
import pytest

from eleicoes import carteiras
from eleicoes.calendario import Eleicao, Turno
from eleicoes.empresas import Sucessao

PREGOES = pd.bdate_range("2009-01-01", "2012-12-31")
IBOV = pd.Series(100_000.0, index=PREGOES)
ELEICAO = Eleicao(
    ano=2010,
    vencedor="Ana",
    segundo="Beto",
    posse=date(2011, 1, 1),
    situacao="oposicao",
    candidato_mercado="Beto",
    turnos=(Turno(1, date(2010, 10, 3), {"Ana": 50.0, "Beto": 40.0}),),
)


def _papel(ticker, raiz, datas, precos, volume=1_000_000.0):
    return pd.DataFrame(
        {
            "data": datas,
            "ticker": ticker,
            "raiz": raiz,
            "especi": "PN  N1",
            "fechamento": precos,
            "volume": volume,
            "fatcot": 1,
        }
    )


def _mercado(*papeis):
    return carteiras.montar_mercado(pd.concat(papeis, ignore_index=True), IBOV)


def _linha_de_liquidez(raiz, ticker, setor="bancos", estatal=False, excluida=False):
    return {
        "ano": 2010,
        "raiz": raiz,
        "ticker": ticker,
        "empresa": raiz.title(),
        "setor": setor,
        "estatal": estatal,
        "excluida": excluida,
    }


def _variacoes(liquidez, mercado, sucessoes=()):
    empresas, emendas = carteiras.variacoes_das_empresas(
        ELEICAO, pd.DataFrame(liquidez), mercado, list(sucessoes), PREGOES
    )
    return empresas, emendas


def _reta(inicio, fim, ponta_inicial, ponta_final):
    datas = pd.bdate_range(inicio, fim)
    return datas, np.linspace(ponta_inicial, ponta_final, len(datas))


def test_emenda_na_mesma_raiz_usa_a_razao_dos_dias_em_comum():
    # Um caminho de preço só; o papel B vale o dobro do A e os dois negociam em novembro.
    caminho = pd.Series(
        np.linspace(10, 15, len(PREGOES[PREGOES >= "2010-01-04"])),
        index=PREGOES[PREGOES >= "2010-01-04"],
    )
    a = caminho["2010-01-04":"2010-11-30"]
    b = 2 * caminho["2010-11-01":"2011-06-30"]
    mercado = _mercado(
        _papel("AAAA11", "AAAA", a.index, a.to_numpy()),
        _papel("AAAA3", "AAAA", b.index, b.to_numpy()),
    )
    serie = carteiras.serie_da_empresa(mercado, "AAAA11", pd.Timestamp("2011-06-30"), [])
    assert [e.ticker_para for e in serie.emendas] == ["AAAA3"]
    assert serie.emendas[0].base == "sobreposicao"
    assert serie.emendas[0].escala == pytest.approx(0.5)
    # Sem salto na emenda: a série segue a de B na escala de A.
    assert serie.precos.pct_change().abs().max() < 0.01
    assert serie.precos.iloc[-1] == pytest.approx(caminho["2011-06-30"])
    assert [s[0] for s in serie.segmentos] == ["AAAA11", "AAAA3"]


def test_emenda_na_sucessora_usa_o_fator_da_tabela():
    datas_a, precos_a = _reta("2010-01-04", "2010-11-30", 50, 52)
    datas_b, precos_b = _reta("2010-12-06", "2011-06-30", 10.6, 12)
    mercado = _mercado(
        _papel("AMBV4", "AMBV", datas_a, precos_a), _papel("ABEV3", "ABEV", datas_b, precos_b)
    )
    sucessoes = [Sucessao("AMBV", "ABEV", 5.0, "")]
    serie = carteiras.serie_da_empresa(mercado, "AMBV4", pd.Timestamp("2011-06-30"), sucessoes)
    emenda = serie.emendas[0]
    assert (emenda.tipo, emenda.base, emenda.fator_tabela) == ("sucessora", "continuidade", 5.0)
    assert serie.precos.iloc[-1] == pytest.approx(60, rel=0.01)  # 12 x 5
    assert serie.precos.pct_change().abs().max() < 0.06


def test_sem_continuacao_a_serie_para():
    datas, precos = _reta("2010-01-04", "2010-12-30", 10, 12)
    mercado = _mercado(_papel("AAAA3", "AAAA", datas, precos))
    serie = carteiras.serie_da_empresa(mercado, "AAAA3", pd.Timestamp("2011-06-30"), [])
    assert serie.emendas == []
    assert serie.precos.index.max() == pd.Timestamp("2010-12-30")


def test_carteira_de_peso_igual_e_empresa_que_some_sai_da_janela():
    # Janela da corrida de 2010: de 04/08 a 01/10.
    cobre_tudo = pd.bdate_range("2010-01-04", "2011-12-30")
    sobe = _papel("SOBE3", "SOBE", cobre_tudo, np.linspace(10, 10, len(cobre_tudo)))
    sobe["fechamento"] = np.where(sobe["data"] >= "2010-09-01", 11.0, 10.0)  # +10%
    cai = _papel("CAIX3", "CAIX", cobre_tudo, np.linspace(10, 10, len(cobre_tudo)))
    cai["fechamento"] = np.where(cai["data"] >= "2010-09-01", 9.0, 10.0)  # -10%
    some = _papel("SOME3", "SOME", *_reta("2010-01-04", "2010-09-15", 10, 10))  # para antes do fim
    liquidez = [
        _linha_de_liquidez("SOBE", "SOBE3"),
        _linha_de_liquidez("CAIX", "CAIX3"),
        _linha_de_liquidez("SOME", "SOME3"),
    ]
    empresas, _ = _variacoes(liquidez, _mercado(sobe, cai, some))
    corrida = empresas[empresas["janela"] == "corrida"].set_index("raiz")
    assert corrida.loc["SOBE", "variacao"] == pytest.approx(10)
    assert corrida.loc["CAIX", "variacao"] == pytest.approx(-10)
    assert corrida.loc["SOME", "status"] == carteiras.SEM_DADO_FIM

    tabela = carteiras.montar_carteiras(ELEICAO, empresas, PREGOES)
    todas = tabela[(tabela["janela"] == "corrida") & (tabela["carteira"] == "todas")].iloc[0]
    assert (todas["n_empresas"], todas["n_fora"]) == (2, 1)
    assert todas["variacao"] == pytest.approx(0)


def test_empresa_sem_classificacao_fica_so_na_carteira_todas():
    datas = pd.bdate_range("2010-01-04", "2011-12-30")
    papeis = [
        _papel(f"{r}3", r, datas, np.full(len(datas), 10.0))
        for r in ("BAN1", "BAN2", "BAN3", "ESTA", "SEMC")
    ]
    liquidez = [
        _linha_de_liquidez("BAN1", "BAN13"),
        _linha_de_liquidez("BAN2", "BAN23"),
        _linha_de_liquidez("BAN3", "BAN33"),
        _linha_de_liquidez("ESTA", "ESTA3", setor="petroleo", estatal=True),
        _linha_de_liquidez("SEMC", "SEMC3", setor="sem_classificacao"),
    ]
    empresas, _ = _variacoes(liquidez, _mercado(*papeis))
    tabela = carteiras.montar_carteiras(ELEICAO, empresas, PREGOES)
    do_t1 = tabela[tabela["janela"] == "t1_d1"].set_index("carteira")
    assert do_t1.loc["todas", "n_empresas"] == 5
    assert do_t1.loc["estatais", "n_empresas"] == 1
    assert do_t1.loc["privadas", "n_empresas"] == 3  # sem classificação fica de fora
    assert do_t1.loc["bancos", "n_empresas"] == 3
    # Petróleo tem 1 empresa só: não vira carteira de setor.
    assert "petroleo" not in do_t1.index
    assert "sem_classificacao" not in do_t1.index
    assert "estatais_menos_privadas" in do_t1.index


def test_empresa_excluida_fica_fora_de_todas():
    datas = pd.bdate_range("2010-01-04", "2011-12-30")
    papeis = [_papel(f"{r}3", r, datas, np.full(len(datas), 10.0)) for r in ("AAAA", "BBBB")]
    liquidez = [
        _linha_de_liquidez("AAAA", "AAAA3"),
        _linha_de_liquidez("BBBB", "BBBB3", excluida=True),
    ]
    empresas, _ = _variacoes(liquidez, _mercado(*papeis))
    tabela = carteiras.montar_carteiras(ELEICAO, empresas, PREGOES)
    todas = tabela[(tabela["janela"] == "t1_d1") & (tabela["carteira"] == "todas")].iloc[0]
    assert todas["n_empresas"] == 1
    assert set(empresas.loc[empresas["raiz"] == "BBBB", "status"]) == {carteiras.EXCLUIDA}


def test_preco_asof_respeita_o_limite_de_5_dias():
    serie = pd.Series([10.0, 11.0], index=pd.to_datetime(["2010-01-04", "2010-01-11"]))
    assert carteiras.preco_asof(serie, pd.Timestamp("2010-01-09")) == 10.0
    assert np.isnan(carteiras.preco_asof(serie, pd.Timestamp("2010-01-10")))
    assert np.isnan(carteiras.preco_asof(serie, pd.Timestamp("2010-01-01")))
