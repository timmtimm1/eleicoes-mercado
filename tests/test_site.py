"""Página: montagem do HTML com um README falso, sem rede."""

import json

import pytest

from eleicoes import site

LEIAME_FALSO = """# Título

<!-- resumo:inicio -->
Resumo de teste com **destaque**.
<!-- resumo:fim -->

<!-- analise:inicio -->
### Análise de teste

| a | b |
|---|---|
| 1 | 2 |

Fim da análise.
<!-- analise:fim -->
"""

SECOES = ["resumo", "agora", "historico", "pesquisas", "setores", "propostas", "cenarios"]
SECOES += ["analise", "limites"]


@pytest.fixture
def sem_propostas(tmp_path, monkeypatch):
    monkeypatch.setattr(site, "PROPOSTAS", tmp_path / "nao_existe.yaml")
    monkeypatch.setattr(site, "MARCOS", tmp_path / "nao_existe.csv")


@pytest.fixture
def leiame(tmp_path):
    caminho = tmp_path / "LEIAME.md"
    caminho.write_text(LEIAME_FALSO, encoding="utf-8")
    return caminho


def _dados_do_html(html: str) -> dict:
    inicio = html.index("const DADOS = ") + len("const DADOS = ")
    fim = html.index(";\n", inicio)
    return json.loads(html[inicio:fim].replace("<\\/", "</"))


def test_pagina_tem_as_nove_secoes_e_os_trechos_do_leiame(tmp_path, leiame, sem_propostas):
    saida = tmp_path / "site"
    saida.mkdir()
    html = site.construir(leiame, saida).read_text(encoding="utf-8")
    for secao in SECOES:
        assert f'<section class="bloco" id="{secao}">' in html
    for numero in range(1, 10):
        assert f'<span class="n">{numero}</span>' in html
    assert "Resumo de teste com <strong>destaque</strong>." in html
    assert "Fim da análise." in html
    assert '<div class="rolagem"><table>' in html  # tabela do markdown com rolagem
    assert "<!--__" not in html  # nenhum marcador do molde ficou sem troca
    assert "__DADOS_ATE__" not in html
    assert "dados até 30/10/2026" in html.lower()


def test_titulo_aviso_e_frases_obrigatorias(tmp_path, leiame, sem_propostas):
    html = site.construir(leiame, tmp_path).read_text(encoding="utf-8")
    assert "<title>Eleições e mercado: bolsa, dólar e juros de 1994 a 2026</title>" in html
    assert "Sem chance em %: com 9 eleições, um número seria chute." in html
    assert "Mundo parado: se o exterior subir ou cair, isso soma por cima." in html
    dados = _dados_do_html(html)
    assert dados["aviso"] == site.AVISO_FINAL
    assert (
        "No pessimista o Ibovespa quase não cai em pontos porque o real perde valor; "
        "em dólar ele cai 25% a 31%." in dados["cenarios"]["frase_pessimista"]
    )
    assert dados["cenarios"]["status"] == "aprovada"


def test_sem_propostas_a_secao_fica_em_revisao(tmp_path, leiame, sem_propostas):
    html = site.construir(leiame, tmp_path).read_text(encoding="utf-8")
    assert _dados_do_html(html)["propostas"] is None
    assert "Em revisão." in html


def test_com_propostas_e_marcos(tmp_path, leiame, monkeypatch):
    (tmp_path / "propostas.yaml").write_text(
        """
- ano: 2002
  candidatos:
    - nome: Lula
      fiscal: {texto: Superávit primário, fonte: "https://exemplo.org/a"}
    - nome: Serra
      fiscal: {texto: Responsabilidade fiscal, fonte: "https://exemplo.org/b"}
  realizado:
    fiscal: {texto: Cumpriu a meta, fonte: "https://exemplo.org/c"}
  sinais_pos_eleicao:
    - {data: 2002-11-01, texto: Palocci na Fazenda, fonte: "https://exemplo.org/d"}
""",
        encoding="utf-8",
    )
    (tmp_path / "marcos.csv").write_text(
        "ano,data,tipo,descricao,fonte\n"
        "2002,2002-06-22,carta,Carta ao Povo Brasileiro,https://exemplo.org/e\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(site, "PROPOSTAS", tmp_path / "propostas.yaml")
    monkeypatch.setattr(site, "MARCOS", tmp_path / "marcos.csv")
    propostas = _dados_do_html(site.construir(leiame, tmp_path).read_text(encoding="utf-8"))[
        "propostas"
    ]
    eleicao = propostas["eleicoes"][0]
    assert [c["nome"] for c in eleicao["candidatos"]] == ["Lula", "Serra"]
    assert eleicao["candidatos"][0]["temas"]["fiscal"]["texto"] == "Superávit primário"
    assert eleicao["candidatos"][0]["temas"]["privatizacoes"] is None  # tema sem texto
    assert eleicao["sinais_pos_eleicao"][0]["data"] == "2002-11-01"
    assert propostas["marcos"][0]["descricao"] == "Carta ao Povo Brasileiro"
    assert list(propostas["temas"]) == list(site.TEMAS)


def test_fecha_script_dentro_do_json_e_escapado(tmp_path, leiame, monkeypatch):
    monkeypatch.setattr(
        site, "dados_da_pagina", lambda: {"dados_ate": "01/01/2000", "x": "</script><b>"}
    )
    html = site.construir(leiame, tmp_path).read_text(encoding="utf-8")
    assert '"x":"<\\/script><b>"' in html
    assert '"x":"</script>' not in html


def test_artefato_nao_tem_link_de_download(tmp_path, leiame, sem_propostas):
    site.construir(leiame, tmp_path)
    completa = (tmp_path / "index.html").read_text(encoding="utf-8")
    artefato = (tmp_path / "artefato.html").read_text(encoding="utf-8")
    assert f"{site.REPOSITORIO}/raw/main/saida/eleicoes_mercado.xlsx" in completa
    assert site.REPOSITORIO not in artefato
    assert "Baixar a planilha" not in artefato
    assert "<html" not in artefato
    assert "<title>" in artefato


def test_sem_readme_ou_sem_marcadores_a_pagina_falha_com_mensagem_clara(tmp_path):
    with pytest.raises(ValueError, match="não achei"):
        site.trecho_do_leiame("resumo", tmp_path / "nao_existe.md")
    sem_marcadores = tmp_path / "vazio.md"
    sem_marcadores.write_text("# nada aqui", encoding="utf-8")
    with pytest.raises(ValueError, match="marcador de 'resumo'"):
        site.construir(sem_marcadores, tmp_path)
    assert not (tmp_path / "index.html").exists()


def test_destaques_so_dizem_o_que_os_dados_mostram():
    dados = site.dados_da_pagina()
    ibov, dolar, juro, surpresa = dados["destaques"]
    assert ibov["valor"] == "−13,9%"
    assert ibov["contexto"].startswith("A maior queda")
    assert "−4,5%, em 1998" in ibov["contexto"]
    assert dolar["valor"] == "+9,2%"
    assert juro["valor"] == "+2,5 p.p."
    assert surpresa["valor"] == "−5,4 pontos"
    assert "A pior surpresa de 14 turnos" in surpresa["contexto"]


def test_destaque_nao_afirma_extremo_que_nao_e():
    import pandas as pd

    tabela = pd.DataFrame(
        {
            "ano": [1998, 2026],
            "janela": ["t1_d1", "t2_d1"],
            "medida": ["ibov", "ibov"],
            "variacao": [-20.0, -13.9],
        }
    )
    posicao, total, segundo = site._comparacao(
        site._d1_de_todos_os_turnos(tabela, "ibov"), 2026, 2, maior_primeiro=False
    )
    assert (posicao, total) == (2, 2)
    frase = site._frase_extremo(posicao, total, segundo, "A maior queda", "desde 1994", str)
    assert "A maior queda no dia" not in frase
    assert frase.startswith("2º lugar")


def test_numeros_em_portugues():
    assert site._pt(-13.884, 1) == "−13,9"
    assert site._pt(9.19, 1, True) == "+9,2"
    assert site._pt(167922, 0) == "167.922"
    assert site._pt(0.0, 1, True) == "0,0"


def test_mapa_de_calor_explica_celulas_vazias():
    mapa = {o["nome"]: o for o in site.dados_da_pagina()["mapa"]}
    ibov = mapa["Ibovespa"]["linhas"]
    por_ano = {linha["ano"]: linha["celulas"] for linha in ibov}
    assert len(por_ano[2026]) == 11
    entre_turnos = 4
    assert por_ano[1994][entre_turnos]["motivo"] == "Esta eleição não teve 2º turno."
    assert por_ano[2026][8]["motivo"] == "Ainda não aconteceu."  # até a posse
    so_brasil = mapa["Ibovespa em dólar, só Brasil"]["linhas"][0]["celulas"][0]
    assert "1994 só há variação bruta" in so_brasil["motivo"]
    embi = {linha["ano"]: linha["celulas"] for linha in mapa["Risco-país (EMBI+)"]["linhas"]}
    assert "acabou em julho de 2024" in embi[2026][1]["motivo"]
    assert por_ano[2026][5]["v"] == pytest.approx(-13.88, abs=0.01)


def test_correlacao_e_tendencia_vem_do_python():
    surpresa = site.dados_da_pagina()["surpresa"]
    todos = next(c for c in surpresa["correlacoes"] if c["grupo"] == "todos")
    assert todos["n"] == 14
    assert todos["correlacao"] == pytest.approx(0.69, abs=0.005)
    assert surpresa["tendencia"]["inclinacao"] == pytest.approx(todos["inclinacao"], abs=1e-3)


def test_comando_pagina_falha_com_mensagem_clara(tmp_path):
    from typer.testing import CliRunner

    from eleicoes.cli import app

    resultado = CliRunner().invoke(app, ["pagina", "--leiame", str(tmp_path / "nao_existe.md")])
    assert resultado.exit_code == 1
    assert "não achei" in resultado.output
