"""Painel: montagem do HTML completo, sem rede."""

import json

import pytest

from eleicoes import painel, site

ABAS = ["agora", "historico", "pesquisas", "setores", "cenarios", "propostas"]


@pytest.fixture(scope="module")
def html(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("painel")
    return painel.construir(pasta).read_text(encoding="utf-8")


def _dados(html: str) -> dict:
    inicio = html.index("const DADOS = ") + len("const DADOS = ")
    fim = html.index(";\n", inicio)
    return json.loads(html[inicio:fim].replace("<\\/", "</"))


def test_documento_completo_com_titulo_e_sem_rede(html):
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="pt-BR">' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "<title>Eleições e Mercado 2026</title>" in html
    assert "<script src=" not in html
    assert "fetch(" not in html
    assert "<!--__" not in html and "/*__" not in html and "__DADOS_ATE__" not in html


def test_json_escapado_e_com_dados_de_2026(html):
    inicio = html.index("const DADOS = ")
    fim = html.index(";\n", inicio)
    assert "</" not in html[inicio:fim]
    dados = _dados(html)
    assert dados["dados_ate"] == "30/10/2026"
    assert any(e["ano"] == 2026 for e in dados["eleicoes"])
    assert dados["agora"]["series"]["ibov"][-1][0].startswith("2026-10")
    assert "2026|t2_d1" in dados["setores"]["dados"]


def test_as_seis_abas_estao_no_documento(html):
    for aba in ABAS:
        assert f'id="aba-{aba}"' in html
        assert f'id="painel-{aba}"' in html


def test_rodape_tem_o_aviso_e_os_links(html):
    assert site.AVISO_FINAL in html
    assert site.PAGINA in html
    assert site.REPOSITORIO in html


def test_seis_numeros_chave_com_estado_e_contexto():
    chaves = painel.dados_do_painel()["chaves"]
    assert len(chaves) == 6
    for c in chaves:
        assert c["estado"] in {"recorde", "fora", "dentro"}
        assert c["contexto"] and c["valor"] and c["estado_texto"]


def test_estado_recorde_fora_e_dentro():
    import pandas as pd

    serie = pd.DataFrame(
        {
            "ano": [1994, 1998, 2002, 2006, 2010, 2026],
            "valor": [1.0, -1.0, 2.0, -2.0, 0.0, 0.0],
        }
    )
    assert painel._estado(serie, 0.0)[0] == "dentro"
    serie.loc[serie["ano"] == 2026, "valor"] = 5.0
    assert painel._estado(serie, 5.0)[0] == "recorde"
    # 4 não é o maior em módulo (há um -5), mas está a mais de 2 desvios das outras eleições.
    antigas = pd.DataFrame(
        {"ano": [1994, 1998, 2002, 2006, 2010, 2014], "valor": [0.1, -0.1, 0.2, -0.2, 0.0, -5.0]}
    )
    com_2026 = pd.concat([antigas, pd.DataFrame({"ano": [2026], "valor": [4.0]})])
    assert painel._estado(com_2026, 4.0)[0] == "fora"


def test_correlacao_de_todos_bate_com_a_da_pagina():
    dados = painel.dados_do_painel()
    todos = next(c for c in dados["pesquisas"]["correlacoes"] if c["grupo"] == "Todos os turnos")
    da_pagina = next(c for c in dados["surpresa"]["correlacoes"] if c["grupo"] == "todos")
    assert todos["n"] == da_pagina["n"]
    assert todos["correlacao"] == pytest.approx(da_pagina["correlacao"], abs=1e-3)
    sem_2026 = next(c for c in dados["pesquisas"]["correlacoes"] if c["grupo"] == "Sem 2026")
    assert sem_2026["n"] == todos["n"] - 2
