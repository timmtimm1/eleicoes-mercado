"""Planilha: estrutura e fórmulas do Painel; a conferência com o LibreOffice pula se faltar."""

import shutil

import pandas as pd
import pytest
from openpyxl import load_workbook

from eleicoes import caminhos, planilha, verificar
from eleicoes.nomes import NOMES_DAS_JANELAS


@pytest.fixture(scope="module")
def leve():
    return planilha.montar(completa=False)


def test_abas_na_ordem(leve):
    esperado = [n for n in planilha.ORDEM if n not in ("Empresas", "Séries")]
    assert leve.sheetnames == esperado
    assert planilha.montar(completa=True).sheetnames == planilha.ORDEM


def test_listas_do_painel_tem_as_nove_eleicoes_e_as_onze_janelas(leve):
    painel = leve["Painel"]
    listas = {str(v.sqref): v for v in painel.data_validations.dataValidation}
    assert set(listas) == {planilha.CELULA_ELEICAO, planilha.CELULA_JANELA}
    assert all(v.type == "list" for v in listas.values())
    anos = [painel.cell(r, 11).value for r in range(4, 13)]
    assert anos == list(range(1994, 2027, 4))[:0] or (anos[0] == 1994 and anos[-1] == 2026)
    assert len(anos) == 9
    nomes = [painel.cell(r, 12).value for r in range(4, 15)]
    assert nomes == list(NOMES_DAS_JANELAS.values())
    assert listas[planilha.CELULA_JANELA].formula1 == "=$L$4:$L$14"
    assert listas[planilha.CELULA_ELEICAO].formula1 == "=$K$4:$K$12"


def test_celulas_de_entrada_em_azul(leve):
    painel = leve["Painel"]
    for celula in (planilha.CELULA_ELEICAO, planilha.CELULA_JANELA):
        assert painel[celula].font.color.rgb.endswith("0000FF")
    assert painel[planilha.CELULA_JANELA].value == "Dia seguinte ao 2º turno"


def test_formula_do_painel_aponta_para_a_chave_certa(leve):
    painel, janelas = leve["Painel"], leve["Janelas"]
    primeira = planilha.PRIMEIRA_LINHA_MEDIDAS
    for i, (codigo, *_) in enumerate(planilha.MEDIDAS_DO_PAINEL):
        linha = primeira + i
        assert painel.cell(linha, planilha.COL_CHAVE).value == f'=$C$4&"|"&$C$5&"|{codigo}"'
        busca = painel.cell(linha, planilha.COL_LINHA).value
        assert busca == f'=IFERROR(MATCH($H{linha},Janelas!$A$2:$A${janelas.max_row},0),"")'
        bruta = painel.cell(linha, planilha.COL_BRUTA).value
        assert f"INDEX(Janelas!$L$2:$L${janelas.max_row},$I{linha})" in bruta
        assert f"INDEX(Janelas!$N$2:$N${janelas.max_row}" in painel.cell(linha, 4).value
    for i, (codigo, *_) in enumerate(planilha.CARTEIRAS_DO_PAINEL):
        linha = planilha.PRIMEIRA_LINHA_CARTEIRAS + i
        assert painel.cell(linha, planilha.COL_CHAVE).value.endswith(f'"|{codigo}"')
        assert "Carteiras!$A$2" in painel.cell(linha, planilha.COL_LINHA).value
        assert "Carteiras!$K$2" in painel.cell(linha, planilha.COL_MEDIA).value
        assert "Carteiras!$L$2" in painel.cell(linha, planilha.COL_MEDIANA).value


def test_coluna_chave_das_abas_de_dados(leve):
    janelas = leve["Janelas"]
    assert janelas["A2"].value == '=B2&"|"&C2&"|"&E2'
    assert janelas["A1"].value == "Chave (ano|janela|medida)"
    carteiras = leve["Carteiras"]
    assert carteiras["A2"].value == '=B2&"|"&C2&"|"&E2'
    tabela = pd.read_csv(caminhos.RESULTADOS / "janelas.csv")
    assert janelas.max_row == len(tabela) + 1
    # a primeira linha de dados é 1994 · Corrida · Ibovespa, com o nome da janela da tela
    assert (janelas["B2"].value, janelas["C2"].value, janelas["E2"].value) == (
        1994,
        "Corrida (60 dias antes)",
        "ibov",
    )


def test_abas_de_dados_e_aviso(leve):
    assert leve["Fontes"].max_row == len(pd.read_csv(caminhos.SERIES / "catalogo.csv")) + 1
    gatilhos = [c.value for c in leve["Cenários"]["D"] if c.value]
    assert any("Copom" in str(g) for g in gatilhos)
    assert planilha.AVISO_FINAL in [c.value for c in leve["Painel"]["B"]]
    completa = planilha.montar(completa=True)
    assert completa["Empresas"].max_row == 9 * 60 + 1
    assert [c.value for c in completa["Séries"][1]][:3] == [
        "Data",
        "Ibovespa (pontos)",
        "Dólar (R$ por US$)",
    ]


def test_confere_comparacao_de_numeros():
    problemas: list[str] = []
    verificar._confere("x", 1.0, 1.0, problemas)
    verificar._confere("y", "—", "—", problemas)
    assert problemas == []
    verificar._confere("z", 1.5, 1.0, problemas)
    verificar._confere("w", 0, "—", problemas)
    assert len(problemas) == 2


@pytest.mark.skipif(shutil.which("soffice") is None, reason="sem LibreOffice")
def test_recalcular_e_verificar_no_libreoffice(tmp_path):
    combinacoes = [(2026, "t2_d1"), (1994, "entre_turnos"), (2002, "t1_d1")]
    assert verificar.conferir(combinacoes) == []
    # o arquivo recalculado traz números, não só fórmulas
    wb = planilha.montar(completa=False)
    arquivo = tmp_path / "entrada" / "painel.xlsx"
    arquivo.parent.mkdir()
    wb.save(arquivo)
    pronto = planilha.recalcular([arquivo], tmp_path)[0]
    painel = load_workbook(pronto, data_only=True)["Painel"]
    assert painel.cell(planilha.PRIMEIRA_LINHA_MEDIDAS, planilha.COL_BRUTA).value == pytest.approx(
        -13.884622
    )
