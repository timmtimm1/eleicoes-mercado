from datetime import date

import numpy as np
import pandas as pd
import pytest

from eleicoes import janelas
from eleicoes.calendario import Eleicao, Turno

# 2008 a 2011 em dias úteis, menos a quarta 07/10/2009 (feriado inventado).
PREGOES = pd.bdate_range("2008-01-01", "2010-10-30").drop(pd.Timestamp("2009-10-07"))


def _eleicao(dois_turnos=True, ano=2009):
    turnos = [Turno(1, date(ano, 10, 4), {"Ana": 40.0, "Beto": 35.0})]
    if dois_turnos:
        turnos.append(Turno(2, date(ano, 10, 25), {"Ana": 52.0, "Beto": 48.0}))
    return Eleicao(
        ano=ano,
        vencedor="Ana",
        segundo="Beto",
        posse=date(ano + 1, 1, 1),
        situacao="oposicao",
        candidato_mercado="Beto",
        turnos=tuple(turnos),
    )


def _niveis(pregoes, choque_brasil=None, beta=1.5, semente=1):
    """Séries inventadas: retornos do exterior aleatórios, Brasil = beta × exterior + ruído."""
    sorteio = np.random.default_rng(semente)
    exterior = sorteio.normal(0, 0.01, len(pregoes))
    ruido = sorteio.normal(0, 0.0005, len(pregoes))
    brasil = beta * exterior + ruido
    if choque_brasil is not None:
        brasil[pregoes.get_loc(choque_brasil[0])] += choque_brasil[1]
    nivel_exterior = 100 * np.exp(np.cumsum(exterior))
    nivel_brasil = 100 * np.exp(np.cumsum(brasil))
    niveis = {}
    for nome in [*janelas.SERIES_LIDAS, "swap360_mensal", "ibov_usd"]:
        niveis[nome] = pd.Series(nivel_exterior, index=pregoes)
    niveis["ibov"] = pd.Series(nivel_brasil, index=pregoes)
    niveis["ibov_usd"] = pd.Series(nivel_brasil, index=pregoes)
    niveis["dolar"] = pd.Series(nivel_brasil, index=pregoes)
    return niveis


def _linha(tabela, janela, medida, ano=2009):
    linhas = tabela[(tabela["ano"] == ano) & (tabela["janela"] == janela)]
    return linhas[linhas["medida"] == medida].iloc[0]


def test_d5_conta_pregoes_e_nao_dias():
    tabela = janelas.calcular([_eleicao()], _niveis(PREGOES), PREGOES)
    linha = _linha(tabela, "t1_d5", "ibov")
    # 1º turno em domingo 04/10: base na sexta 02/10. Pregões 05, 06, 08 (07 é feriado), 09, 12.
    assert linha["inicio"] == "2009-10-02"
    assert linha["fim"] == "2009-10-12"
    assert linha["pregoes"] == 5
    assert linha["status"] == "ok"


def test_janela_no_futuro_vira_ainda_nao_aconteceu():
    tabela = janelas.calcular([_eleicao(ano=2010)], _niveis(PREGOES), PREGOES)
    # Calendário acaba em 30/10/2010: o 2º turno (25/10) ainda não tem D+20 nem posse.
    for nome in ("t2_d20", "ate_posse", "posse_100d", "posse_1ano"):
        linhas = tabela[tabela["janela"] == nome]
        assert set(linhas["status"]) == {"ainda_nao_aconteceu"}
        assert linhas["variacao"].isna().all()
        assert linhas["fim"].eq("").all()
    assert _linha(tabela, "t2_d1", "ibov", ano=2010)["status"] == "ok"


def test_eleicao_sem_segundo_turno_nao_gera_janelas_do_segundo():
    tabela = janelas.calcular([_eleicao(dois_turnos=False)], _niveis(PREGOES), PREGOES)
    nomes = set(tabela["janela"])
    assert not any(n.startswith("t2_") or n == "entre_turnos" for n in nomes)
    assert {"corrida", "t1_d1", "ate_posse", "posse_1ano"} <= nomes
    # A base das janelas da posse é o 1º turno, que é o decisivo.
    assert _linha(tabela, "ate_posse", "ibov")["inicio"] == "2009-10-02"


def test_ordem_das_linhas_e_colunas():
    tabela = janelas.calcular([_eleicao()], _niveis(PREGOES), PREGOES)
    assert list(tabela.columns) == janelas.COLUNAS
    primeiras = tabela.head(len(janelas.MEDIDAS))
    assert list(primeiras["medida"]) == [m.nome for m in janelas.MEDIDAS]
    assert list(dict.fromkeys(tabela["janela"])) == janelas.JANELAS


def test_variacao_bruta_em_percentual_e_em_pontos():
    niveis = _niveis(PREGOES)
    niveis["ibov"] = pd.Series(100.0, index=PREGOES)
    niveis["ibov"].loc["2009-10-05":] = 110.0
    niveis["selic"] = pd.Series(10.0, index=PREGOES)
    niveis["selic"].loc["2009-10-05":] = 10.75
    tabela = janelas.calcular([_eleicao()], niveis, PREGOES)
    assert _linha(tabela, "t1_d1", "ibov")["variacao"] == pytest.approx(10.0)
    selic = _linha(tabela, "t1_d1", "selic")
    assert selic["variacao"] == pytest.approx(0.75)
    assert selic["unidade"] == "p.p."
    assert pd.isna(selic["so_brasil"])


def test_swap_mensal_so_vale_nas_janelas_longas():
    tabela = janelas.calcular([_eleicao()], _niveis(PREGOES), PREGOES)
    assert _linha(tabela, "t1_d1", "swap360")["status"] == "sem_dado"
    assert _linha(tabela, "entre_turnos", "swap360")["status"] == "sem_dado"
    assert _linha(tabela, "corrida", "swap360")["status"] == "ok"
    assert _linha(tabela, "posse_100d", "swap360")["status"] == "ok"


def test_modelo_de_mercado_recupera_o_beta_e_zera_o_que_o_mundo_explica():
    tabela = janelas.calcular([_eleicao()], _niveis(PREGOES), PREGOES)
    linha = _linha(tabela, "t1_d5", "ibov_usd")
    assert linha["controle"] == "msci_em"
    assert linha["beta"] == pytest.approx(1.5, abs=0.05)
    assert linha["pregoes_estimacao"] == 250
    assert abs(linha["variacao"]) > 0.5  # a variação bruta é grande...
    assert abs(linha["so_brasil"]) < 0.5  # ...e o que sobra do Brasil é quase nada
    longa = _linha(tabela, "posse_100d", "ibov_usd")
    assert abs(longa["so_brasil"]) < 1.0


def test_choque_so_no_brasil_aparece_no_so_brasil():
    choque = (pd.Timestamp("2009-10-05"), np.log(0.9))
    niveis = _niveis(PREGOES, choque_brasil=choque)
    tabela = janelas.calcular([_eleicao()], niveis, PREGOES)
    assert _linha(tabela, "t1_d1", "ibov_usd")["so_brasil"] == pytest.approx(-10.0, abs=0.5)
    assert _linha(tabela, "t1_d1", "dolar")["so_brasil"] == pytest.approx(-10.0, abs=0.5)


def test_so_brasil_aguenta_um_buraco_no_meio_da_janela():
    niveis = _niveis(PREGOES)
    cheio = janelas.calcular([_eleicao()], niveis, PREGOES)
    niveis["ust10"].loc["2009-10-13"] = np.nan
    furado = janelas.calcular([_eleicao()], niveis, PREGOES)
    antes = _linha(cheio, "t1_d20", "prefixado_10a")["so_brasil"]
    depois = _linha(furado, "t1_d20", "prefixado_10a")["so_brasil"]
    assert depois == pytest.approx(antes, abs=1e-9)


def test_sem_dado_na_ponta_da_janela():
    niveis = _niveis(PREGOES)
    niveis["embi"].loc["2009-10-05"] = np.nan
    tabela = janelas.calcular([_eleicao()], niveis, PREGOES)
    assert _linha(tabela, "t1_d1", "embi")["status"] == "sem_dado"
    assert _linha(tabela, "t1_d5", "embi")["status"] == "ok"


def test_so_brasil_vazio_quando_falta_o_controle():
    niveis = _niveis(PREGOES)
    niveis["ust10"].loc["2009-10-05"] = np.nan
    tabela = janelas.calcular([_eleicao()], niveis, PREGOES)
    linha = _linha(tabela, "t1_d1", "prefixado_1a")
    assert linha["status"] == "ok"
    assert pd.isna(linha["variacao"]) is False
    assert pd.isna(linha["so_brasil"])


def test_beta_de_dimson_pega_o_atraso_do_exterior():
    # O exterior só reage no dia seguinte ao que o Brasil faz: o beta do mesmo dia seria ~0.
    gerador = np.random.default_rng(7)
    datas = pd.bdate_range("2008-01-01", periods=400)
    choques = pd.Series(gerador.normal(0, 0.01, len(datas)), index=datas)
    brasil = 0.8 * choques
    exterior = choques.shift(1)
    modelo = janelas.estimar_beta(brasil, exterior, datas[300])
    assert modelo.beta == pytest.approx(0.8, abs=0.05)
    assert modelo.pares == 250


def test_alinhar_ffill_so_ate_o_limite_de_dias():
    serie = pd.Series(
        [1.0, 2.0], index=pd.to_datetime(["2020-01-02", "2020-01-20"]), dtype="float64"
    )
    calendario_ = pd.to_datetime(["2020-01-01", "2020-01-03", "2020-01-07", "2020-01-08"])
    alinhada = janelas.alinhar(serie, pd.DatetimeIndex(calendario_), 5)
    assert np.isnan(alinhada["2020-01-01"])  # antes do primeiro valor
    assert alinhada["2020-01-03"] == 1.0
    assert alinhada["2020-01-07"] == 1.0  # 5 dias depois: ainda vale
    assert np.isnan(alinhada["2020-01-08"])  # 6 dias: sem dado
    sem_limite = janelas.alinhar(serie, pd.DatetimeIndex(calendario_), None)
    assert sem_limite["2020-01-08"] == 1.0


def test_gravar_tabela_formata_numeros_e_deixa_vazio_o_que_falta(tmp_path):
    tabela = pd.DataFrame(
        {"a": [1.23456789, np.nan], "b": pd.array([3, pd.NA], dtype="Int64"), "c": ["x", ""]}
    )
    caminho = tmp_path / "saida" / "t.csv"
    janelas.gravar_tabela(tabela, caminho)
    assert caminho.read_text() == "a,b,c\n1.234568,3,x\n,,\n"
