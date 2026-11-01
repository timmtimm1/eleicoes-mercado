"""Gera a planilha do estudo: dados prontos e um Painel com fórmulas.

No Painel escolhe-se a eleição e a janela em duas listas; as células de baixo buscam o
resultado nas abas Janelas e Carteiras com INDEX e MATCH. A busca usa uma coluna-chave
`ano|janela|medida` (ou `ano|janela|carteira`) que cada uma dessas abas tem na coluna A.

As demais abas são o dado: Surpresa, Cenários, Empresas, Séries diárias e Fontes. Abre e calcula
no LibreOffice e no Excel; o arquivo publicado é recalculado pelo LibreOffice, para já chegar com
os números em qualquer visualizador.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from eleicoes import calendario, caminhos, cenarios, series
from eleicoes.nomes import NOMES_DAS_JANELAS, NOMES_DOS_SETORES

ARQUIVO = caminhos.SAIDA / "eleicoes_mercado.xlsx"
AVISO_FINAL = (
    "Não é recomendação de investimento. É uma análise com dados públicos (B3, Banco Central, "
    "Tesouro, Ipeadata, MSCI, Yahoo, TSE e institutos de pesquisa) e simulações com dados "
    "reais e projetados."
)

AZUL = Font(color="0000FF", bold=True)
NEGRITO = Font(bold=True)
TITULO = Font(bold=True, size=15)
CINZA = Font(italic=True, color="595959")
BRANCO = Font(bold=True, color="FFFFFF")
FUNDO_CABECALHO = PatternFill("solid", fgColor="3B4148")
FUNDO_SECAO = PatternFill("solid", fgColor="E7E9EC")
FUNDO_ENTRADA = PatternFill("solid", fgColor="FBF4DC")
QUEBRA = Alignment(wrap_text=True, vertical="top")
DATA = "DD/MM/YYYY"
SEM_DADO = "—"

ORDEM = [
    "Leia-me",
    "Painel",
    "Janelas",
    "Carteiras",
    "Surpresa",
    "Cenários",
    "Empresas",
    "Séries",
    "Fontes",
]

# --- Painel: endereços fixos (o `verificar` troca as listas e lê as respostas).
CELULA_ELEICAO, CELULA_JANELA = "C4", "C5"
CELULA_INICIO, CELULA_FIM, CELULA_SITUACAO = "C6", "C7", "C8"
COL_BRUTA, COL_SO_BRASIL = 3, 4  # C e D
COL_MEDIA, COL_MEDIANA = 3, 4
PRIMEIRA_LINHA_MEDIDAS = 12
# A unidade vai no próprio número, com sinal: +9,19%, +2,52 p.p., −34 p.b.
FORMATO_DA_UNIDADE = {
    "%": '+0.00"%";-0.00"%";0.00"%"',
    "p.p.": '+0.00" p.p.";-0.00" p.p.";0.00" p.p."',
    "p.b.": '+0" p.b.";-0" p.b.";0" p.b."',
}
MEDIDAS_DO_PAINEL = [
    # código em janelas.csv, nome, unidade, explicação
    (
        "ibov",
        "Ibovespa (em reais)",
        "%",
        "Quanto o índice da bolsa subiu (+) ou caiu (−) na janela. Não tem “só Brasil”: ele "
        "já é em reais; veja a bolsa em dólar logo abaixo.",
    ),
    (
        "ibov_usd",
        "Ibovespa em dólar",
        "%",
        "O mesmo índice convertido em dólar. “Só Brasil” tira o que as bolsas de países "
        "emergentes fizeram no mesmo período.",
    ),
    (
        "dolar",
        "Dólar (R$ por US$)",
        "%",
        "Positivo: o dólar ficou mais caro (o real perdeu valor). “Só Brasil” tira o que o "
        "dólar fez frente às outras moedas do mundo.",
    ),
    (
        "selic",
        "Selic",
        "p.p.",
        "Mudança da taxa básica de juros, em pontos percentuais (a diferença entre duas "
        "taxas). Só há a variação bruta: a Selic anda em degraus.",
    ),
    (
        "prefixado_1a",
        "Tesouro prefixado 1 ano",
        "p.p.",
        "Mudança do juro que o governo paga em títulos de 1 ano, em pontos percentuais. Só "
        "existe desde dezembro de 2004.",
    ),
    (
        "prefixado_10a",
        "Tesouro prefixado 10 anos",
        "p.p.",
        "Mudança do juro de longo prazo, em pontos percentuais. “Só Brasil” tira o que os "
        "juros dos EUA fizeram. Só existe desde dezembro de 2004.",
    ),
    (
        "embi",
        "Risco-país (EMBI+)",
        "p.b.",
        "Mudança do risco-país em pontos-base (100 pontos-base = 1 ponto percentual). O índice "
        "acabou em julho de 2024; 2026 fica sem dado.",
    ),
]
PRIMEIRA_LINHA_CARTEIRAS = 23
CARTEIRAS_DO_PAINEL = [
    (
        "estatais",
        "Estatais",
        "As estatais entre as 60 empresas mais negociadas antes do 1º turno, com peso igual "
        "e só preço (sem dividendos).",
    ),
    ("privadas", "Privadas", "As outras empresas das 60, também com peso igual e só preço."),
    (
        "estatais_menos_privadas",
        "Estatais menos privadas",
        "Positivo: as estatais foram melhor que as privadas. Em pontos percentuais.",
    ),
    (
        "todas",
        "Todas as 60 (média)",
        "A média de todas as 60 empresas: o ponto de comparação das outras carteiras.",
    ),
]
COL_CHAVE, COL_LINHA = 8, 9  # H e I: a chave de busca e a linha achada


def _janelas_por_nome() -> dict[str, str]:
    return {v: k for k, v in NOMES_DAS_JANELAS.items()}


def _cabecalho(ws: Worksheet, linha: int, titulos: list[str]) -> None:
    for coluna, titulo in enumerate(titulos, 1):
        celula = ws.cell(linha, coluna, titulo)
        celula.font, celula.fill = BRANCO, FUNDO_CABECALHO
        celula.alignment = Alignment(wrap_text=True, vertical="center")


def _larguras(ws: Worksheet, larguras: list[float]) -> None:
    for coluna, largura in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(coluna)].width = largura


def _numero(valor) -> float | None:
    return None if pd.isna(valor) else float(valor)


def _data(valor):
    return None if pd.isna(valor) or valor == "" else pd.Timestamp(valor).to_pydatetime()


# ---------------------------------------------------------------- abas de dados


def _aba_janelas(wb: Workbook) -> int:
    ws = wb.create_sheet("Janelas")
    tabela = pd.read_csv(caminhos.RESULTADOS / "janelas.csv")
    _cabecalho(
        ws,
        1,
        [
            "Chave (ano|janela|medida)",
            "Eleição",
            "Janela",
            "Código da janela",
            "Medida (código)",
            "Medida",
            "Início",
            "Fim",
            "Pregões",
            "Valor no início",
            "Valor no fim",
            "Variação",
            "Unidade",
            "Só Brasil",
            "Controle do “só Brasil”",
            "Beta",
            "Pregões da estimação",
            "Situação",
            "Observação",
        ],
    )
    nomes = {
        "ibov": "Ibovespa",
        "ibov_usd": "Ibovespa em dólar",
        "dolar": "Dólar",
        "selic": "Selic",
        "prefixado_1a": "Tesouro prefixado 1 ano",
        "prefixado_10a": "Tesouro prefixado 10 anos",
        "embi": "Risco-país (EMBI+)",
        "swap360": "Swap DI × pré 360 dias",
    }
    for i, r in enumerate(tabela.itertuples(index=False), 2):
        ws.cell(i, 1, f'=B{i}&"|"&C{i}&"|"&E{i}')
        valores = [
            int(r.ano),
            NOMES_DAS_JANELAS[r.janela],
            r.janela,
            r.medida,
            nomes[r.medida],
            _data(r.inicio),
            _data(r.fim),
            None if pd.isna(r.pregoes) else int(r.pregoes),
            _numero(r.valor_inicio),
            _numero(r.valor_fim),
            _numero(r.variacao),
            r.unidade,
            _numero(r.so_brasil),
            None if pd.isna(r.controle) else r.controle,
            _numero(r.beta),
            None if pd.isna(r.pregoes_estimacao) else int(r.pregoes_estimacao),
            r.status,
            None if pd.isna(r.observacao) else r.observacao,
        ]
        for coluna, valor in enumerate(valores, 2):
            ws.cell(i, coluna, valor)
        ws.cell(i, 7).number_format = ws.cell(i, 8).number_format = DATA
        for coluna in (10, 11, 12, 14):
            ws.cell(i, coluna).number_format = "0.00"
    _larguras(ws, [26, 9, 26, 14, 14, 26, 12, 12, 9, 14, 14, 11, 9, 11, 14, 8, 12, 18, 40])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:S{len(tabela) + 1}"
    return len(tabela) + 1


def _aba_carteiras(wb: Workbook) -> int:
    ws = wb.create_sheet("Carteiras")
    tabela = pd.read_csv(caminhos.RESULTADOS / "carteiras.csv")
    _cabecalho(
        ws,
        1,
        [
            "Chave (ano|janela|carteira)",
            "Eleição",
            "Janela",
            "Código da janela",
            "Carteira (código)",
            "Carteira",
            "Início",
            "Fim",
            "Empresas",
            "Empresas fora",
            "Variação (média, peso igual)",
            "Mediana",
            "Contra as 60 (p.p.)",
            "Situação",
        ],
    )
    nomes = {
        "todas": "Todas as 60",
        "estatais": "Estatais",
        "privadas": "Privadas",
        "estatais_menos_privadas": "Estatais menos privadas",
        **NOMES_DOS_SETORES,
    }
    for i, r in enumerate(tabela.itertuples(index=False), 2):
        ws.cell(i, 1, f'=B{i}&"|"&C{i}&"|"&E{i}')
        valores = [
            int(r.ano),
            NOMES_DAS_JANELAS[r.janela],
            r.janela,
            r.carteira,
            nomes.get(r.carteira, r.carteira),
            _data(r.inicio),
            _data(r.fim),
            None if pd.isna(r.n_empresas) else int(r.n_empresas),
            None if pd.isna(r.n_fora) else int(r.n_fora),
            _numero(r.variacao),
            _numero(r.mediana),
            _numero(r.contra_todas),
            r.status,
        ]
        for coluna, valor in enumerate(valores, 2):
            ws.cell(i, coluna, valor)
        ws.cell(i, 7).number_format = ws.cell(i, 8).number_format = DATA
        for coluna in (11, 12, 13):
            ws.cell(i, coluna).number_format = "0.00"
    _larguras(ws, [28, 9, 26, 14, 22, 24, 12, 12, 10, 10, 16, 10, 14, 18])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:N{len(tabela) + 1}"
    return len(tabela) + 1


def _aba_surpresa(wb: Workbook) -> None:
    ws = wb.create_sheet("Surpresa")
    tabela = pd.read_csv(caminhos.RESULTADOS / "surpresa.csv")
    ws["A1"] = (
        "Surpresa = margem do candidato do mercado nas urnas menos a margem dele nas pesquisas "
        "(pontos, votos válidos). Positivo: ele foi melhor que as pesquisas diziam."
    )
    ws["A1"].font = CINZA
    titulos = {
        "ano": "Eleição",
        "turno": "Turno",
        "data": "Data do turno",
        "candidato_mercado": "Candidato do mercado",
        "adversario": "Adversário",
        "margem_pesquisas": "Margem nas pesquisas",
        "margem_resultado": "Margem no TSE",
        "surpresa": "Surpresa",
        "favorito_pesquisas": "Favorito nas pesquisas",
        "mercado_ganhou_turno": "Candidato do mercado ganhou o turno",
        "n_institutos": "Institutos",
        "institutos": "Quais",
        "ibov_d1": "Ibovespa D+1 (%)",
        "ibov_usd_so_brasil_d1": "Ibovespa em dólar só Brasil D+1 (%)",
        "dolar_d1": "Dólar D+1 (%)",
        "dolar_so_brasil_d1": "Dólar só Brasil D+1 (%)",
        "prefixado_10a_d1": "Tesouro 10 anos D+1 (p.p.)",
    }
    _cabecalho(ws, 3, [titulos[c] for c in tabela.columns])
    for i, linha in enumerate(tabela.itertuples(index=False), 4):
        for coluna, valor in enumerate(linha, 1):
            if pd.isna(valor):
                continue
            if tabela.columns[coluna - 1] == "data":
                valor = _data(valor)
            elif isinstance(valor, bool | np.bool_):
                valor = "sim" if valor else "não"
            elif hasattr(valor, "item"):
                valor = valor.item()
            celula = ws.cell(i, coluna, valor)
            if tabela.columns[coluna - 1] == "data":
                celula.number_format = DATA
            elif isinstance(valor, float):
                celula.number_format = "0.00"
    _larguras(ws, [9, 7, 13, 20, 20, 12, 12, 10, 20, 16, 10, 36, 12, 16, 12, 14, 14])
    ws.row_dimensions[3].height = 48
    ws.freeze_panes = "A4"


def _aba_cenarios(wb: Workbook) -> None:
    ws = wb.create_sheet("Cenários")
    tabela = pd.read_csv(caminhos.RESULTADOS / "cenarios.csv")
    premissas = cenarios.carregar_premissas()
    ws["A1"] = (
        f"Cenários para 2026 a 2028 (premissas: {premissas['status']}). Sem chance em %: com 9 "
        "eleições, um número seria chute. Mundo parado: se o exterior subir ou cair, isso "
        "soma por cima."
    )
    ws["A1"].font = CINZA
    titulos = [
        "Cenário",
        "Horizonte",
        "Data",
        "Medida",
        "Unidade da variação",
        "Eleições com dado",
        "Variação mínima",
        "Variação média",
        "Variação máxima",
        "Nível de hoje (30/10/2026)",
        "Nível mínimo",
        "Nível no meio",
        "Nível máximo",
        "Premissas",
    ]
    _cabecalho(ws, 3, titulos)
    for i, r in enumerate(tabela.itertuples(index=False), 4):
        valores = [
            r.cenario,
            r.horizonte,
            _data(r.data),
            r.medida,
            r.unidade,
            r.analogos_com_dado if isinstance(r.analogos_com_dado, str) else None,
            *(_numero(v) for v in (r.minimo, r.central, r.maximo)),
            *(_numero(v) for v in (r.nivel_base, r.nivel_minimo, r.nivel_central, r.nivel_maximo)),
            r.status_premissas,
        ]
        for coluna, valor in enumerate(valores, 1):
            celula = ws.cell(i, coluna, valor)
            if coluna == 3:
                celula.number_format = DATA
            elif isinstance(valor, float):
                celula.number_format = "#,##0.00"
    linha = len(tabela) + 6
    ws.cell(linha, 1, "Gatilhos: o que precisaria acontecer em cada cenário").font = TITULO
    linha += 1
    _cabecalho(ws, linha, ["Cenário", "Título", "Eleições parecidas", "Gatilho"])
    for cenario in premissas["cenarios"]:
        for gatilho in cenario["gatilhos"]:
            linha += 1
            ws.cell(linha, 1, cenario["nome"])
            ws.cell(linha, 2, cenario["titulo"])
            ws.cell(linha, 3, " e ".join(str(a) for a in cenario["analogos"]))
            ws.cell(linha, 4, " ".join(gatilho.split())).alignment = QUEBRA
        linha += 1
        ws.cell(linha, 1, cenario["nome"])
        ws.cell(linha, 2, "Por que estas eleições")
        ws.cell(linha, 4, " ".join(cenario["por_que_estes"].split())).alignment = QUEBRA
    _larguras(ws, [14, 22, 22, 90, 12, 14, 12, 12, 12, 16, 12, 12, 12, 12])
    ws.freeze_panes = "A4"


def _aba_empresas(wb: Workbook) -> None:
    ws = wb.create_sheet("Empresas")
    tabela = pd.read_csv(caminhos.RESULTADOS / "liquidez.csv")
    _cabecalho(
        ws,
        1,
        [
            "Eleição",
            "Posição",
            "Raiz",
            "Ticker",
            "Nome na B3",
            "Espécie",
            "Volume (R$ milhões)",
            "Pregões com negócio",
            "Pregões no período",
            "Raízes somadas",
            "Empresa",
            "Setor",
            "Estatal",
            "Fora das carteiras",
        ],
    )
    for i, r in enumerate(tabela.itertuples(index=False), 2):
        valores = [
            int(r.ano),
            int(r.posicao),
            r.raiz,
            r.ticker,
            r.nomres,
            r.especi,
            float(r.volume_milhoes),
            int(r.pregoes_com_negocio),
            int(r.pregoes_no_periodo),
            r.raizes_somadas,
            r.empresa,
            NOMES_DOS_SETORES.get(r.setor, r.setor),
            "sim" if r.estatal else "não",
            "sim" if r.excluida else "não",
        ]
        for coluna, valor in enumerate(valores, 1):
            ws.cell(i, coluna, valor)
        ws.cell(i, 7).number_format = "#,##0.0"
    _larguras(ws, [9, 9, 8, 9, 22, 14, 14, 12, 12, 14, 28, 24, 8, 12])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:N{len(tabela) + 1}"


def _aba_series(wb: Workbook) -> None:
    ws = wb.create_sheet("Séries")
    colunas = [
        ("ibov", "Ibovespa (pontos)"),
        ("dolar", "Dólar (R$ por US$)"),
        ("selic", "Selic (% ao ano)"),
        ("prefixado_10a", "Tesouro 10 anos (% ao ano)"),
        ("embi", "EMBI+ (pontos-base)"),
        ("msci_em", "MSCI Emergentes (US$)"),
    ]
    datas = calendario.pregoes()
    tabela = pd.DataFrame({titulo: series.ler(nome).reindex(datas) for nome, titulo in colunas})
    _cabecalho(ws, 1, ["Data", *tabela.columns])
    for i, (data, linha) in enumerate(tabela.iterrows(), 2):
        ws.cell(i, 1, data.to_pydatetime()).number_format = DATA
        for coluna, valor in enumerate(linha, 2):
            if not pd.isna(valor):
                ws.cell(i, coluna, float(valor))
    _larguras(ws, [12, 16, 18, 16, 24, 18, 20])
    ws.freeze_panes = "B2"


def _aba_fontes(wb: Workbook) -> None:
    ws = wb.create_sheet("Fontes")
    tabela = pd.read_csv(caminhos.SERIES / "catalogo.csv", keep_default_na=False)
    _cabecalho(
        ws,
        1,
        ["Série", "Descrição", "Unidade", "Fonte", "Código", "Início", "Fim", "Pregões", "Link"],
    )
    for i, r in enumerate(tabela.itertuples(index=False), 2):
        valores = [r.nome, r.descricao, r.unidade, r.fonte, r.codigo, r.inicio, r.fim, r.linhas]
        for coluna, valor in enumerate(valores, 1):
            ws.cell(i, coluna, valor)
        ws.cell(i, 6, _data(r.inicio)).number_format = DATA
        ws.cell(i, 7, _data(r.fim)).number_format = DATA
        link = ws.cell(i, 9, r.url)
        link.hyperlink = r.url
        link.font = Font(color="0563C1", underline="single")
    _larguras(ws, [16, 60, 14, 16, 22, 12, 12, 10, 70])
    ws.freeze_panes = "A2"


# ---------------------------------------------------------------- Leia-me e Painel


def _aba_leiame(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "Leia-me"
    ws["B2"] = "Eleições e mercado: bolsa, dólar e juros de 1994 a 2026"
    ws["B2"].font = TITULO
    linhas = [
        (
            "O que é",
            "Os dados do estudo sobre como a bolsa, o dólar e os juros reagiram a cada "
            "eleição para presidente, de 1994 a 2026, mais um Painel em que você escolhe a "
            "eleição e o período e as fórmulas mostram o resultado.",
        ),
        ("Painel", "Escolha a eleição e a janela nas duas células azuis. O resto se calcula."),
        (
            "Janelas",
            "Uma linha por eleição, período e medida: Ibovespa, dólar, Selic, Tesouro e "
            "risco-país, com a variação bruta e o “só Brasil”. O Painel busca aqui.",
        ),
        (
            "Carteiras",
            "Estatais, privadas e setores (empresas de peso igual, só preço) em cada período. "
            "O Painel busca aqui as estatais e as privadas.",
        ),
        (
            "Surpresa",
            "As pesquisas da véspera contra o resultado do TSE, e a reação do mercado no dia "
            "seguinte.",
        ),
        (
            "Cenários",
            "As faixas de Ibovespa, dólar e juros na posse, aos 100 dias e em 1 ano, e os "
            "gatilhos de cada cenário. Sem chance em %.",
        ),
        (
            "Empresas",
            "As 60 empresas mais negociadas antes de cada eleição, com setor e se eram estatais.",
        ),
        (
            "Séries",
            "Os valores diários de Ibovespa, dólar, Selic, Tesouro 10 anos, EMBI+ e MSCI "
            "Emergentes, alinhados pelos dias em que a bolsa abriu.",
        ),
        ("Fontes", "De onde veio cada série, com o link."),
        (
            "Três palavras",
            "“Só Brasil”: a variação depois de tirar o que o exterior fez no mesmo período. "
            "“p.p.”: pontos percentuais, a diferença entre duas taxas. “Pregão”: dia em que a "
            "bolsa abre.",
        ),
        (
            "Cores",
            "Células com letra azul e fundo amarelo são as que você muda. As pretas são fórmulas.",
        ),
        ("Aviso", AVISO_FINAL),
    ]
    for i, (rotulo, texto) in enumerate(linhas, 4):
        ws.cell(i, 2, rotulo).font = NEGRITO
        ws.cell(i, 2).alignment = Alignment(vertical="top")
        ws.cell(i, 3, texto).alignment = QUEBRA
        ws.row_dimensions[i].height = 18 * (1 + len(texto) // 95)
    _larguras(ws, [3, 16, 100])


def _formula_valor(coluna_dados: str, aba: str, ultima: int, linha_busca: str) -> str:
    """Valor da coluna na linha achada, ou — se a linha não existe ou a célula está vazia."""
    faixa = f"{aba}!${coluna_dados}$2:${coluna_dados}${ultima}"
    return (
        f'=IF(NOT(ISNUMBER({linha_busca})),"{SEM_DADO}",'
        f'IF(INDEX({faixa},{linha_busca})="","{SEM_DADO}",INDEX({faixa},{linha_busca})))'
    )


def _aba_painel(wb: Workbook, ultima_janelas: int, ultima_carteiras: int) -> None:
    ws = wb.create_sheet("Painel")
    ws["B1"] = "Painel: escolha uma eleição e uma janela"
    ws["B1"].font = TITULO
    ws["B2"] = (
        "Mude só as duas células azuis. Tudo abaixo vem das abas Janelas e Carteiras. “—” quer "
        "dizer que não há dado (a eleição não teve esse período, ele ainda não aconteceu ou a "
        "série não existia)."
    )
    ws["B2"].font = CINZA

    anos = [e.ano for e in calendario.carregar_eleicoes()]
    nomes_janelas = list(NOMES_DAS_JANELAS.values())
    # As listas ficam à direita, na própria aba, porque uma lista direta aceita só 255 letras.
    ws["K3"], ws["L3"] = "Lista de eleições", "Lista de janelas"
    ws["K3"].font = ws["L3"].font = CINZA
    for i, ano in enumerate(anos, 4):
        ws.cell(i, 11, ano).font = CINZA
    for i, nome in enumerate(nomes_janelas, 4):
        ws.cell(i, 12, nome).font = CINZA

    ws["B4"], ws["B5"] = "Eleição", "Janela"
    ws[CELULA_ELEICAO], ws[CELULA_JANELA] = anos[-1], NOMES_DAS_JANELAS["t2_d1"]
    for celula in (CELULA_ELEICAO, CELULA_JANELA):
        ws[celula].font, ws[celula].fill = AZUL, FUNDO_ENTRADA
    ws["D4"] = "Escolha o ano na lista."
    ws["D5"] = "Escolha o período na lista. O que cada um mede está em “Janelas” e no Leia-me."
    for celula in ("D4", "D5"):
        ws[celula].font = CINZA
    lista_eleicao = DataValidation(
        type="list", formula1=f"=$K$4:$K${3 + len(anos)}", allow_blank=False
    )
    lista_janela = DataValidation(
        type="list", formula1=f"=$L$4:$L${3 + len(nomes_janelas)}", allow_blank=False
    )
    for lista, celula in ((lista_eleicao, CELULA_ELEICAO), (lista_janela, CELULA_JANELA)):
        lista.error, lista.errorTitle = "Escolha um item da lista.", "Valor fora da lista"
        ws.add_data_validation(lista)
        lista.add(celula)

    # Início, fim e situação, a partir da linha do Ibovespa.
    linha_ibov = f"$I${PRIMEIRA_LINHA_MEDIDAS}"
    ws["B6"], ws["B7"], ws["B8"] = "Início da janela", "Fim da janela", "Situação"
    ws[CELULA_INICIO] = _formula_valor("G", "Janelas", ultima_janelas, linha_ibov)
    ws[CELULA_FIM] = _formula_valor("H", "Janelas", ultima_janelas, linha_ibov)
    ws[CELULA_INICIO].number_format = ws[CELULA_FIM].number_format = DATA
    situacao = f"Janelas!$R$2:$R${ultima_janelas}"
    ws[CELULA_SITUACAO] = (
        f'=IF(NOT(ISNUMBER({linha_ibov})),"Esta eleição não teve essa janela (sem 2º turno).",'
        f'IF(INDEX({situacao},{linha_ibov})="ainda_nao_aconteceu","Ainda não aconteceu.",'
        f'"Com dados."))'
    )
    ws["D6"] = "O último pregão antes do turno é a base de quase todas as janelas."
    ws["D7"] = "O dia em que a janela termina."
    ws["D6"].font = ws["D7"].font = CINZA
    for celula in (CELULA_INICIO, CELULA_FIM, CELULA_SITUACAO):
        ws[celula].alignment = Alignment(horizontal="right")

    def secao(linha: int, titulo: str, colunas: list[str]) -> None:
        ws.cell(linha, 2, titulo).font = NEGRITO
        for coluna in range(2, 8):
            ws.cell(linha, coluna).fill = FUNDO_SECAO
        _cabecalho_painel(ws, linha + 1, colunas)

    secao(
        PRIMEIRA_LINHA_MEDIDAS - 2,
        "Mercado: o que mudou na janela",
        ["Medida", "Variação bruta", "Só Brasil", "Unidade", "O que é"],
    )
    for i, (codigo, nome, unidade, explicacao) in enumerate(MEDIDAS_DO_PAINEL):
        linha = PRIMEIRA_LINHA_MEDIDAS + i
        ws.cell(linha, 2, nome).font = NEGRITO
        ws.cell(linha, COL_CHAVE, f'=$C$4&"|"&$C$5&"|{codigo}"')
        ws.cell(
            linha, COL_LINHA, f'=IFERROR(MATCH($H{linha},Janelas!$A$2:$A${ultima_janelas},0),"")'
        )
        ws.cell(linha, COL_BRUTA, _formula_valor("L", "Janelas", ultima_janelas, f"$I{linha}"))
        ws.cell(linha, COL_SO_BRASIL, _formula_valor("N", "Janelas", ultima_janelas, f"$I{linha}"))
        ws.cell(linha, 5, unidade)
        ws.cell(linha, 6, explicacao).alignment = QUEBRA
        for coluna in (COL_BRUTA, COL_SO_BRASIL):
            ws.cell(linha, coluna).number_format = FORMATO_DA_UNIDADE.get(unidade, "0.00")
            ws.cell(linha, coluna).alignment = Alignment(horizontal="right")
        ws.row_dimensions[linha].height = 32

    secao(
        PRIMEIRA_LINHA_CARTEIRAS - 2,
        "Estatais e privadas: variação das carteiras (peso igual, só preço)",
        ["Carteira", "Média", "Mediana", "Unidade", "O que é"],
    )
    for i, (codigo, nome, explicacao) in enumerate(CARTEIRAS_DO_PAINEL):
        linha = PRIMEIRA_LINHA_CARTEIRAS + i
        ws.cell(linha, 2, nome).font = NEGRITO
        ws.cell(linha, COL_CHAVE, f'=$C$4&"|"&$C$5&"|{codigo}"')
        ws.cell(
            linha,
            COL_LINHA,
            f'=IFERROR(MATCH($H{linha},Carteiras!$A$2:$A${ultima_carteiras},0),"")',
        )
        ws.cell(linha, COL_MEDIA, _formula_valor("K", "Carteiras", ultima_carteiras, f"$I{linha}"))
        ws.cell(
            linha, COL_MEDIANA, _formula_valor("L", "Carteiras", ultima_carteiras, f"$I{linha}")
        )
        ws.cell(linha, 5, "% (p.p. na diferença)" if "menos" in codigo else "%")
        ws.cell(linha, 6, explicacao).alignment = QUEBRA
        formato = FORMATO_DA_UNIDADE["p.p." if "menos" in codigo else "%"]
        for coluna in (COL_MEDIA, COL_MEDIANA):
            ws.cell(linha, coluna).number_format = formato
            ws.cell(linha, coluna).alignment = Alignment(horizontal="right")
        ws.row_dimensions[linha].height = 32

    ws.cell(PRIMEIRA_LINHA_CARTEIRAS + len(CARTEIRAS_DO_PAINEL) + 1, 2, AVISO_FINAL).font = CINZA
    ws.cell(PRIMEIRA_LINHA_MEDIDAS - 1, COL_CHAVE, "Chave de busca").font = CINZA
    ws.cell(PRIMEIRA_LINHA_MEDIDAS - 1, COL_LINHA, "Linha achada").font = CINZA
    ws.cell(PRIMEIRA_LINHA_CARTEIRAS - 1, COL_CHAVE, "Chave de busca").font = CINZA
    ws.cell(PRIMEIRA_LINHA_CARTEIRAS - 1, COL_LINHA, "Linha achada").font = CINZA
    for linha in ws.iter_rows(min_row=PRIMEIRA_LINHA_MEDIDAS, max_row=PRIMEIRA_LINHA_CARTEIRAS + 3):
        for celula in linha[1:6]:
            alinhamento = celula.alignment
            celula.alignment = Alignment(
                horizontal=alinhamento.horizontal,
                wrap_text=alinhamento.wrap_text,
                vertical="center",
            )
    _larguras(ws, [3, 28, 28, 16, 22, 70, 3, 26, 12, 3, 18, 28])
    ws.freeze_panes = "A4"


def _cabecalho_painel(ws: Worksheet, linha: int, titulos: list[str]) -> None:
    for coluna, titulo in enumerate(titulos, 2):
        celula = ws.cell(linha, coluna, titulo)
        celula.font, celula.fill = BRANCO, FUNDO_CABECALHO
        celula.alignment = Alignment(horizontal="left" if coluna in (2, 6) else "right")


# ---------------------------------------------------------------- montagem


def montar(completa: bool = True) -> Workbook:
    """A pasta de trabalho, só com fórmulas e dados.

    Sem `completa`, ficam de fora as abas Empresas e Séries (que o Painel não usa): serve às
    conferências, que recalculam várias cópias.
    """
    wb = Workbook()
    _aba_leiame(wb)
    ultima_janelas = _aba_janelas(wb)
    ultima_carteiras = _aba_carteiras(wb)
    _aba_painel(wb, ultima_janelas, ultima_carteiras)
    _aba_surpresa(wb)
    _aba_cenarios(wb)
    if completa:
        _aba_empresas(wb)
        _aba_series(wb)
    _aba_fontes(wb)
    wb._sheets = [wb[nome] for nome in ORDEM if nome in wb.sheetnames]
    wb.active = 1  # abre no Painel
    return wb


def recalcular(planilhas: list[Path], destino: Path) -> list[Path]:
    """Abre no LibreOffice sem tela e salva com os valores calculados.

    O LibreOffice usa um perfil à parte, numa pasta temporária: com o programa aberto no perfil
    de sempre, o modo sem tela trava esperando a janela. Vários arquivos vão numa chamada só.
    """
    soffice = shutil.which("soffice")
    if soffice is None:
        raise RuntimeError("LibreOffice (soffice) não encontrado")
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run(
            [
                soffice,
                f"-env:UserInstallation={Path(perfil).as_uri()}",
                "--headless",
                "--calc",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(destino),
                *map(str, planilhas),
            ],
            check=True,
            capture_output=True,
            timeout=600,
        )
    return [destino / p.name for p in planilhas]


def gerar(pronta: bool = True) -> Path:
    """Grava a planilha em saida/.

    Com `pronta`, o LibreOffice abre o arquivo, calcula tudo e grava de novo: assim a planilha já
    chega com os números em qualquer programa. Sem LibreOffice instalado, fica só com as
    fórmulas.
    """
    caminhos.SAIDA.mkdir(exist_ok=True)
    wb = montar()
    if pronta and shutil.which("soffice"):
        with tempfile.TemporaryDirectory() as pasta:
            bruta = Path(pasta) / "entrada" / ARQUIVO.name
            bruta.parent.mkdir()
            wb.save(bruta)
            shutil.copy(recalcular([bruta], Path(pasta))[0], ARQUIVO)
    else:
        wb.save(ARQUIVO)
    return ARQUIVO
