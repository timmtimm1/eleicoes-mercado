from datetime import date

from eleicoes import empresas
from eleicoes.empresas import Empresa, Sucessao


def test_familias_juntam_cadeias_e_ciclos():
    sucessoes = [
        Sucessao("AMBV", "ABEV", 5.0, ""),
        Sucessao("NATU", "NTCO", 1.0, ""),
        Sucessao("NTCO", "NATU", 1.0, ""),
        Sucessao("AAAA", "BBBB", 1.0, ""),
        Sucessao("BBBB", "CCCC", 1.0, ""),
    ]
    familias = empresas.familias(sucessoes)
    assert familias["AMBV"] == familias["ABEV"] == "ABEV"
    assert familias["NATU"] == familias["NTCO"] == "NATU"
    assert familias["AAAA"] == familias["BBBB"] == familias["CCCC"] == "AAAA"
    assert "PETR" not in familias


def test_estatal_na_data_do_primeiro_turno():
    petrobras = Empresa("PETR", "Petrobras", "petroleo", "", "estatal", "União", None)
    vale = Empresa("VALE", "Vale", "mineracao_siderurgia", "", "estatal", "União", date(1997, 5, 6))
    itau = Empresa("ITUB", "Itaú", "bancos", "", "privada", "", None)
    assert empresas.e_estatal(petrobras, date(2026, 10, 4))
    assert empresas.e_estatal(vale, date(1994, 10, 3))
    assert not empresas.e_estatal(vale, date(1998, 10, 4))
    assert not empresas.e_estatal(itau, date(1994, 10, 3))
    assert not empresas.e_estatal(None, date(1994, 10, 3))


def test_tabelas_do_repositorio_carregam_e_se_conversam():
    cadastro = empresas.carregar_empresas()
    assert cadastro["PETR"].controle == "estatal"
    assert cadastro["ELET"].privatizada_em == date(2022, 6, 14)
    for sucessao in empresas.carregar_sucessoes():
        assert sucessao.fator > 0
    assert (1998, "TELB") in empresas.carregar_exclusoes()
