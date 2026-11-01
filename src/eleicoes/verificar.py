"""Confere a planilha contra os CSVs de resultado.

A planilha sai do openpyxl só com fórmulas. Aqui várias cópias leves (sem as abas de séries e
de empresas) têm a eleição e a janela trocadas no Painel; o LibreOffice abre todas de uma vez,
calcula e grava; os números do Painel são lidos e comparados com o que está nos CSVs. Se uma
fórmula buscar a linha errada ou a lista trocar o ano errado, aparece aqui. O arquivo publicado
em `saida/` nunca é tocado: as cópias vivem numa pasta temporária.
"""

import tempfile
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from eleicoes import caminhos, planilha
from eleicoes.nomes import NOMES_DAS_JANELAS

ERROS = ("#DIV/0!", "#REF!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "Err:")
TOLERANCIA = 1e-6

# Eleição × janela: de dados completos a janelas que não existem ou ainda não aconteceram.
COMBINACOES = [
    (2026, "t2_d1"),  # o caso que motivou o estudo
    (2026, "t1_d1"),
    (2026, "posse_1ano"),  # ainda não aconteceu
    (2002, "entre_turnos"),
    (2002, "t2_d1"),
    (1994, "t1_d1"),  # sem "só Brasil"
    (1994, "entre_turnos"),  # sem 2º turno
    (1998, "posse_1ano"),
    (2014, "t2_d20"),
    (2022, "ate_posse"),
    (2010, "corrida"),
    (2006, "posse_100d"),
]


def _esperado(valor) -> float | str:
    return planilha.SEM_DADO if pd.isna(valor) else float(valor)


def _confere(onde: str, obtido, esperado: float | str, problemas: list[str]) -> None:
    if isinstance(esperado, str):
        if obtido != esperado:
            problemas.append(f"{onde}: planilha {obtido!r}, CSV sem valor ({esperado!r})")
        return
    if not isinstance(obtido, int | float) or abs(obtido - esperado) > TOLERANCIA:
        problemas.append(f"{onde}: planilha {obtido!r}, CSV {esperado:.6f}")


def _data_esperada(valor) -> object:
    return planilha.SEM_DADO if pd.isna(valor) else pd.Timestamp(valor).to_pydatetime()


def _erros_na_planilha(wb, nome: str) -> list[str]:
    achados = []
    for ws in wb.worksheets:
        for linha in ws.iter_rows():
            for celula in linha:
                if isinstance(celula.value, str) and celula.value.startswith(ERROS):
                    achados.append(f"{nome} {ws.title}!{celula.coordinate}: {celula.value}")
    return achados


def conferir(combinacoes: list[tuple[int, str]] | None = None) -> list[str]:
    """Lista de divergências (vazia quando o Painel e os CSVs concordam)."""
    combinacoes = combinacoes or COMBINACOES
    tabela = pd.read_csv(caminhos.RESULTADOS / "janelas.csv").set_index(["ano", "janela", "medida"])
    carteiras = pd.read_csv(caminhos.RESULTADOS / "carteiras.csv").set_index(
        ["ano", "janela", "carteira"]
    )
    problemas: list[str] = []
    with tempfile.TemporaryDirectory() as pasta:
        entrada = Path(pasta) / "entrada"
        entrada.mkdir()
        arquivos = []
        for numero, (ano, janela) in enumerate(combinacoes):
            wb = planilha.montar(completa=False)
            ws = wb["Painel"]
            ws[planilha.CELULA_ELEICAO].value = ano
            ws[planilha.CELULA_JANELA].value = NOMES_DAS_JANELAS[janela]
            arquivo = entrada / f"combinacao_{numero:02d}.xlsx"
            wb.save(arquivo)
            arquivos.append(arquivo)
        for (ano, janela), pronto in zip(
            combinacoes, planilha.recalcular(arquivos, Path(pasta)), strict=True
        ):
            wb = load_workbook(pronto, data_only=True)
            nome = f"{ano} · {NOMES_DAS_JANELAS[janela]}"
            problemas += _erros_na_planilha(wb, nome)
            ws = wb["Painel"]

            for i, (medida, *_) in enumerate(planilha.MEDIDAS_DO_PAINEL):
                linha = planilha.PRIMEIRA_LINHA_MEDIDAS + i
                existe = (ano, janela, medida) in tabela.index
                registro = tabela.loc[(ano, janela, medida)] if existe else None
                for coluna, campo in (
                    (planilha.COL_BRUTA, "variacao"),
                    (planilha.COL_SO_BRASIL, "so_brasil"),
                ):
                    esperado = _esperado(registro[campo]) if existe else planilha.SEM_DADO
                    _confere(
                        f"{nome} · {medida} {campo}",
                        ws.cell(linha, coluna).value,
                        esperado,
                        problemas,
                    )

            for i, (carteira, *_) in enumerate(planilha.CARTEIRAS_DO_PAINEL):
                linha = planilha.PRIMEIRA_LINHA_CARTEIRAS + i
                existe = (ano, janela, carteira) in carteiras.index
                registro = carteiras.loc[(ano, janela, carteira)] if existe else None
                for coluna, campo in (
                    (planilha.COL_MEDIA, "variacao"),
                    (planilha.COL_MEDIANA, "mediana"),
                ):
                    esperado = _esperado(registro[campo]) if existe else planilha.SEM_DADO
                    _confere(
                        f"{nome} · {carteira} {campo}",
                        ws.cell(linha, coluna).value,
                        esperado,
                        problemas,
                    )

            ibov = (
                tabela.loc[(ano, janela, "ibov")] if (ano, janela, "ibov") in tabela.index else None
            )
            for celula, campo in ((planilha.CELULA_INICIO, "inicio"), (planilha.CELULA_FIM, "fim")):
                esperada = planilha.SEM_DADO if ibov is None else _data_esperada(ibov[campo])
                if ws[celula].value != esperada:
                    problemas.append(
                        f"{nome} · {campo}: planilha {ws[celula].value!r}, CSV {esperada!r}"
                    )
    return problemas


def conferir_arquivo(arquivo: Path = planilha.ARQUIVO) -> list[str]:
    """O arquivo publicado: sem células de erro e com o Painel na seleção que ele traz."""
    wb = load_workbook(arquivo, data_only=True)
    problemas = _erros_na_planilha(wb, arquivo.name)
    faltando = [nome for nome in planilha.ORDEM if nome not in wb.sheetnames]
    if faltando:
        problemas.append(f"{arquivo.name}: faltam abas {faltando}")
    painel = wb["Painel"]
    ano, janela_nome = painel[planilha.CELULA_ELEICAO].value, painel[planilha.CELULA_JANELA].value
    codigo = {v: k for k, v in NOMES_DAS_JANELAS.items()}.get(janela_nome)
    if codigo is None:
        problemas.append(f"{arquivo.name}: janela do Painel desconhecida: {janela_nome!r}")
        return problemas
    esperado = pd.read_csv(caminhos.RESULTADOS / "janelas.csv").set_index(
        ["ano", "janela", "medida"]
    )
    valor = painel.cell(planilha.PRIMEIRA_LINHA_MEDIDAS, planilha.COL_BRUTA).value
    _confere(
        f"{arquivo.name} · Painel {ano} {codigo} ibov",
        valor,
        _esperado(esperado.loc[(ano, codigo, "ibov"), "variacao"]),
        problemas,
    )
    return problemas
