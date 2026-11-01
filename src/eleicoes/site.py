"""Monta a página: um HTML só, com os dados embutidos.

`site/pagina.html` é o molde (estrutura, estilo e as seções), `site/graficos.js` desenha os
gráficos em SVG. Aqui os dois se juntam aos dados do estudo em `site/index.html`, que abre
direto no navegador, e em `site/artefato.html`, o mesmo conteúdo sem os links de download.

O texto da análise não fica no molde: mora no README, entre marcadores, e a página mostra o
mesmo texto, para não haver duas versões.
"""

import json
import math
from pathlib import Path
from typing import Any

import markdown
import pandas as pd
import yaml

from eleicoes import calendario, caminhos, cenarios, janelas, surpresa
from eleicoes.nomes import NOMES_DAS_JANELAS, NOMES_DOS_SETORES
from eleicoes.planilha import ARQUIVO

REPOSITORIO = "https://github.com/timmtimm1/eleicoes-mercado"
PAGINA = "https://timmtimm1.github.io/eleicoes-mercado/"
TITULO = "Eleições e mercado: bolsa, dólar e juros de 1994 a 2026"
DESCRICAO = (
    "Como a bolsa, o dólar e os juros reagiram a cada eleição para presidente de 1994 a 2026, "
    "e três cenários para os próximos 14 meses. Dados públicos; não é recomendação."
)
AVISO_FINAL = (
    "Não é recomendação de investimento. É uma análise com dados públicos (B3, Banco Central, "
    "Tesouro, Ipeadata, MSCI, Yahoo, TSE e institutos de pesquisa) e simulações com dados "
    "reais e projetados."
)

CORPO = '<div class="wrap">'
LIGACOES = "<!--__LIGACOES__-->"
LEIAME = caminhos.RAIZ / "README.md"
TRECHOS = {"<!--__RESUMO__-->": "resumo", "<!--__ANALISE__-->": "analise"}

PROPOSTAS = caminhos.DADOS / "propostas.yaml"
MARCOS = caminhos.DADOS / "marcos.csv"

INICIO_DA_LINHA = "2026-08-01"

# Mapa de calor: cada opção é (medida, coluna, nome, unidade).
OPCOES_DO_MAPA = [
    ("ibov", "variacao", "Ibovespa", "%"),
    ("ibov_usd", "variacao", "Ibovespa em dólar", "%"),
    ("ibov_usd", "so_brasil", "Ibovespa em dólar, só Brasil", "%"),
    ("dolar", "variacao", "Dólar", "%"),
    ("dolar", "so_brasil", "Dólar, só Brasil", "%"),
    ("prefixado_10a", "variacao", "Tesouro 10 anos", "p.p."),
    ("embi", "variacao", "Risco-país (EMBI+)", "p.b."),
]
TEMAS = {
    "fiscal": "Gastos e regra fiscal",
    "privatizacoes": "Privatizações",
    "estatais": "Petrobras e estatais",
    "banco_central": "Banco Central e juros",
    "reformas": "Reformas",
    "cambio_comercio": "Câmbio e comércio exterior",
}
NOMES_DAS_MEDIDAS = {
    "ibov": ("Ibovespa (pontos)", 0),
    "ibov_usd": ("Ibovespa em dólar (pontos)", 0),
    "dolar": ("Dólar (R$)", 2),
    "prefixado_10a": ("Tesouro 10 anos (% ao ano)", 2),
}
NOMES_DOS_HORIZONTES = {
    "ate_posse": "Posse",
    "posse_100d": "100 dias",
    "posse_1ano": "1 ano",
}

# Os limites do SPEC.md, em linguagem de gente.
LIMITES = [
    "Nove eleições são poucas. As faixas mostram o que já aconteceu, não preveem o que vai "
    "acontecer.",
    "1994: o Real tinha três meses e não existe índice de bolsas emergentes por dia antes de "
    "1997. Por isso 1994 só tem a variação bruta, sem o “só Brasil”.",
    "Juros: o Tesouro Direto começa em 31/12/2004. Em 1994 e 1998 só há a Selic. Em 2002 há "
    "a Selic por dia e o juro de 360 dias só uma vez por mês, então não dá para medir "
    "janelas curtas.",
    "Risco-país: o EMBI+ acabou em julho de 2024. Em 2026 o medo aparece nos juros, no dólar "
    "e na bolsa, não no risco-país.",
    "Estatais, privadas e setores: carteiras de peso igual e só preço, sem dividendos, nos "
    "dois lados. A lista de estatais muda a cada eleição (Vale até 1997, Telebras até 1998, "
    "Eletrobras até 2022, Sabesp até 2024).",
    "O índice de bolsas emergentes inclui o Brasil (cerca de 5%), o que puxa o “só Brasil” "
    "um pouco para zero em dias de queda forte.",
    "Pesquisas: média das últimas pesquisas de Datafolha, Ibope/Ipec, Quaest e AtlasIntel "
    "antes de cada turno. Em 1998 e no 2º turno de 2002 não há pesquisa na base.",
]
METODO = [
    "Cada janela parte do fechamento do último pregão antes do turno. Pregão é o dia em que "
    "a bolsa abre.",
    "“Só Brasil”: mede-se quanto o Brasil costuma andar junto com o exterior nos 250 pregões "
    "antes da campanha (inclui o dia anterior e o seguinte, porque a Ásia fecha antes da B3 "
    "abrir) e tira-se da variação a parte que o exterior explica.",
    "A Selic anda em degraus e vem do Banco Central: só variação bruta.",
    "Surpresa: margem do candidato que o mercado preferia no resultado do TSE menos a margem "
    "dele nas pesquisas. Positivo quer dizer melhor para ele do que as pesquisas diziam.",
    "Cenários: ponto de partida no 5º pregão depois do turno decisivo (em 2026, 30/10). A "
    "faixa vai do menor ao maior “só Brasil” de duas eleições parecidas, aplicado aos "
    "preços de 30/10/2026. Sem chance em %, e com o mundo parado.",
]


# ---------------------------------------------------------------- formatação em português


def _pt(valor: float, casas: int = 1, sinal: bool = False) -> str:
    """Número no formato brasileiro, com o sinal de menos tipográfico."""
    arredondado = round(valor, casas)
    texto = f"{abs(arredondado):,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if arredondado < 0:
        return "−" + texto
    return "+" + texto if sinal and arredondado > 0 else texto


def _data_br(iso: str) -> str:
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


def _limpo(valor: Any) -> Any:
    """NaN não é JSON: vira null."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    if isinstance(valor, float):
        return round(valor, 4)
    return valor


# ---------------------------------------------------------------- entradas


def _ler(nome: str) -> pd.DataFrame:
    return pd.read_csv(caminhos.RESULTADOS / nome)


def carregar_propostas() -> dict[str, Any] | None:
    """Propostas e marcos, ou None enquanto os dois arquivos não existirem (em revisão)."""
    if not (PROPOSTAS.exists() and MARCOS.exists()):
        return None
    with PROPOSTAS.open(encoding="utf-8") as arquivo:
        bruto = yaml.safe_load(arquivo)
    if not isinstance(bruto, list):
        raise ValueError(f"{PROPOSTAS.name} deve ser uma lista de eleições, uma por `ano`")
    por_ano = []
    for item in bruto:
        candidatos = [
            {
                "nome": c["nome"],
                "temas": {t: c.get(t) for t in TEMAS},
            }
            for c in item.get("candidatos", [])
        ]
        por_ano.append(
            {
                "ano": int(item["ano"]),
                "candidatos": candidatos,
                "realizado": {t: (item.get("realizado") or {}).get(t) for t in TEMAS},
                "sinais_pos_eleicao": _com_data_em_texto(item.get("sinais_pos_eleicao")),
                "contestacao": _com_data_em_texto(item.get("contestacao")),
            }
        )
    marcos = pd.read_csv(MARCOS, dtype=str, keep_default_na=False)
    return {
        "temas": TEMAS,
        "eleicoes": por_ano,
        "marcos": json.loads(marcos.to_json(orient="records")),
    }


def _com_data_em_texto(lista: list[dict] | None) -> list[dict]:
    """Datas do YAML viram texto ISO, que o JSON entende."""
    return [{**item, "data": str(item.get("data", ""))} for item in lista or []]


# ---------------------------------------------------------------- destaques do resumo


def _posicao(serie: pd.Series, valor: float, maior_primeiro: bool) -> tuple[int, pd.Series]:
    """Posição de `valor` (1 = o mais extremo) e a serie ordenada do mais extremo ao menos."""
    ordenada = serie.sort_values(ascending=not maior_primeiro)
    return int((ordenada > valor).sum() if maior_primeiro else (ordenada < valor).sum()) + 1, (
        ordenada
    )


def _d1_de_todos_os_turnos(tabela: pd.DataFrame, medida: str) -> pd.DataFrame:
    """Variação no dia seguinte de cada turno (1º e 2º) para uma medida."""
    d1 = tabela[(tabela["medida"] == medida) & tabela["janela"].isin(["t1_d1", "t2_d1"])]
    return d1.dropna(subset=["variacao"]).assign(turno=lambda t: t["janela"].str[1].astype(int))


def _comparacao(
    d1: pd.DataFrame, ano: int, turno: int, maior_primeiro: bool
) -> tuple[int, int, pd.Series]:
    """Posição de uma eleição entre todos os turnos, total de turnos e a segunda melhor."""
    do_caso = d1[(d1["ano"] == ano) & (d1["turno"] == turno)]["variacao"].iloc[0]
    posicao, ordenada = _posicao(d1["variacao"], do_caso, maior_primeiro)
    segundo = d1.loc[ordenada.index[1]] if len(ordenada) > 1 else None
    return posicao, len(d1), segundo


def _frase_extremo(posicao: int, total: int, segundo, o_que: str, desde: str, formatar) -> str:
    """“A maior queda…” só se for verdade nos dados; senão, a posição que ela tem."""
    if posicao == 1:
        resto = ""
        if segundo is not None:
            resto = (
                f" A segunda maior foi {formatar(segundo['variacao'])}, em "
                f"{int(segundo['ano'])} (depois do {int(segundo['turno'])}º turno)."
            )
        return f"{o_que} no dia seguinte a um turno {desde}.{resto}"
    return f"{posicao}º lugar entre {total} turnos {desde} ({o_que.replace('A maior', 'maior')})."


def destaques(tabela_janelas: pd.DataFrame, tabela_surpresa: pd.DataFrame) -> list[dict]:
    """Os quatro números do topo, com uma linha de contexto conferida nos dados."""
    ano, turno = 2026, 2
    pegar = {
        medida: _d1_de_todos_os_turnos(tabela_janelas, medida)
        for medida in ("ibov", "dolar", "prefixado_10a")
    }

    ibov = pegar["ibov"].query("ano == @ano and turno == @turno")["variacao"].iloc[0]
    posicao, total, segundo = _comparacao(pegar["ibov"], ano, turno, maior_primeiro=False)
    contexto_ibov = _frase_extremo(
        posicao,
        total,
        segundo,
        "A maior queda",
        "desde 1994",
        lambda v: f"{_pt(v, 1)}%",
    )

    dolar = pegar["dolar"].query("ano == @ano and turno == @turno")["variacao"].iloc[0]
    posicao, total, segundo = _comparacao(pegar["dolar"], ano, turno, maior_primeiro=True)
    contexto_dolar = _frase_extremo(
        posicao,
        total,
        segundo,
        "A maior alta",
        "desde 1994",
        lambda v: f"{_pt(v, 1, True)}%",
    )

    juro = pegar["prefixado_10a"].query("ano == @ano and turno == @turno")["variacao"].iloc[0]
    posicao, total, segundo = _comparacao(pegar["prefixado_10a"], ano, turno, maior_primeiro=True)
    contexto_juro = _frase_extremo(
        posicao,
        total,
        segundo,
        "A maior alta",
        f"entre os {total} que têm o dado (a série começa em 2005)",
        lambda v: f"{_pt(v, 2, True)} p.p.",
    )

    do_caso = tabela_surpresa[(tabela_surpresa["ano"] == ano) & (tabela_surpresa["turno"] == turno)]
    linha = do_caso.iloc[0]
    completos = tabela_surpresa.dropna(subset=["surpresa"])
    ordem = completos.sort_values("surpresa")
    primeiro_da_fila = ordem.iloc[0]
    if (primeiro_da_fila["ano"], primeiro_da_fila["turno"]) == (ano, turno):
        pior = (
            f"A pior surpresa de {len(completos)} turnos com pesquisa; a segunda pior foi "
            f"{_pt(ordem.iloc[1]['surpresa'], 1)} pontos, em {int(ordem.iloc[1]['ano'])}."
        )
    else:
        posicao_surpresa = int((completos["surpresa"] < linha["surpresa"]).sum()) + 1
        pior = f"{posicao_surpresa}ª pior surpresa de {len(completos)} turnos com pesquisa."
    margem = linha["margem_pesquisas"]
    quem, rival = linha["candidato_mercado"], linha["adversario"]
    nas_pesquisas = f"{quem if margem > 0 else rival} {_pt(abs(margem), 1)} pontos"
    no_resultado = linha["margem_resultado"]
    nas_urnas = f"{quem if no_resultado > 0 else rival} {_pt(abs(no_resultado), 1)} pontos"
    contexto_surpresa = f"Pesquisas: {nas_pesquisas} à frente. Urnas: {nas_urnas} à frente. {pior}"

    return [
        {
            "rotulo": "Ibovespa, dia seguinte ao 2º turno de 2026",
            "valor": f"{_pt(ibov, 1)}%",
            "contexto": contexto_ibov,
        },
        {
            "rotulo": "Dólar, no mesmo dia",
            "valor": f"{_pt(dolar, 1, True)}%",
            "contexto": contexto_dolar,
        },
        {
            "rotulo": "Tesouro de 10 anos, no mesmo dia",
            "valor": f"{_pt(juro, 1, True)} p.p.",
            "contexto": contexto_juro,
        },
        {
            "rotulo": "Surpresa das pesquisas, 2º turno de 2026",
            "valor": f"{_pt(linha['surpresa'], 1)} pontos",
            "contexto": contexto_surpresa,
        },
    ]


# ---------------------------------------------------------------- dados de cada seção


def _eleicoes() -> list[dict]:
    return [
        {
            "ano": e.ano,
            "vencedor": e.vencedor,
            "segundo": e.segundo,
            "posse": e.posse.isoformat(),
            "situacao": e.situacao,
            "turnos": [{"numero": t.numero, "data": t.data.isoformat()} for t in e.turnos],
            "decisivo": e.turno_decisivo.numero,
        }
        for e in calendario.carregar_eleicoes()
    ]


def _linhas_do_ano(eleicoes: list[dict], ano: int) -> dict:
    return next(e for e in eleicoes if e["ano"] == ano)


def _motivo(medida: str, coluna: str, ano: int, status: str, observacao: str | None) -> str:
    """Por que a célula do mapa de calor está vazia."""
    if status == "ainda_nao_aconteceu":
        return "Ainda não aconteceu."
    if medida == "embi" and ano == 2026:
        return "O risco-país (EMBI+) acabou em julho de 2024; em 2026 fica de fora."
    if medida == "prefixado_10a" and status == "sem_dado":
        return "O Tesouro Direto só tem dados desde dezembro de 2004."
    if coluna == "so_brasil" and ano == 1994:
        return (
            "Em 1994 só há variação bruta: não existe índice de bolsas emergentes por dia "
            "antes de 1997."
        )
    if status == "sem_dado":
        return observacao or "Sem dado."
    return "Sem dado."


def _mapa(tabela: pd.DataFrame, eleicoes: list[dict]) -> list[dict]:
    """Uma grade ano × janela para cada opção do seletor."""
    indice = tabela.set_index(["ano", "janela", "medida"])
    opcoes = []
    for medida, coluna, nome, unidade in OPCOES_DO_MAPA:
        linhas = []
        for eleicao in eleicoes:
            celulas = []
            for janela in janelas.JANELAS:
                chave = (eleicao["ano"], janela, medida)
                if janela in janelas.JANELAS_DO_SEGUNDO_TURNO and len(eleicao["turnos"]) == 1:
                    celulas.append({"v": None, "motivo": "Esta eleição não teve 2º turno."})
                    continue
                linha = indice.loc[chave]
                valor = linha[coluna]
                if pd.isna(valor):
                    celulas.append(
                        {
                            "v": None,
                            "motivo": _motivo(
                                medida,
                                coluna,
                                eleicao["ano"],
                                linha["status"],
                                None if pd.isna(linha["observacao"]) else linha["observacao"],
                            ),
                        }
                    )
                else:
                    celulas.append(
                        {
                            "v": _limpo(float(valor)),
                            "de": linha["inicio"],
                            "ate": linha["fim"],
                        }
                    )
            linhas.append({"ano": eleicao["ano"], "celulas": celulas})
        opcoes.append({"nome": nome, "unidade": unidade, "linhas": linhas})
    return opcoes


def _decisivo(tabela: pd.DataFrame, eleicoes: list[dict]) -> list[dict]:
    """Dia seguinte ao turno decisivo: Ibovespa bruto e Ibovespa em dólar só Brasil."""
    linhas = []
    indice = tabela.set_index(["ano", "janela", "medida"])
    for e in eleicoes:
        janela = f"t{e['decisivo']}_d1"
        bruto = indice.loc[(e["ano"], janela, "ibov")]
        em_dolar = indice.loc[(e["ano"], janela, "ibov_usd")]
        linhas.append(
            {
                "ano": e["ano"],
                "turno": e["decisivo"],
                "ibov": _limpo(float(bruto["variacao"])),
                "so_brasil": _limpo(float(em_dolar["so_brasil"])),
                "ibov_usd": _limpo(float(em_dolar["variacao"])),
            }
        )
    return linhas


def _agora(tabela: pd.DataFrame) -> dict:
    """Linhas diárias de 2026 e as janelas de 2026 já ocorridas."""
    from eleicoes import series

    recorte = {}
    for nome in ("ibov", "dolar"):
        serie = series.ler(nome).loc[INICIO_DA_LINHA:].dropna()
        recorte[nome] = [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in serie.items()]
    de_2026 = tabela[(tabela["ano"] == 2026) & (tabela["status"] == "ok")]
    indice = de_2026.set_index(["janela", "medida"])
    ocorridas = [j for j in janelas.JANELAS if (j, "ibov") in indice.index]  # só as que já têm dado
    linhas = []
    for janela in ocorridas:
        ibov = indice.loc[(janela, "ibov")]
        linhas.append(
            {
                "janela": NOMES_DAS_JANELAS[janela],
                "de": ibov["inicio"],
                "ate": ibov["fim"],
                "ibov": _limpo(float(ibov["variacao"])),
                "ibov_usd_so_brasil": _limpo(float(indice.loc[(janela, "ibov_usd")]["so_brasil"])),
                "dolar": _limpo(float(indice.loc[(janela, "dolar")]["variacao"])),
                "tesouro_10a": _limpo(float(indice.loc[(janela, "prefixado_10a")]["variacao"])),
            }
        )
    return {"series": recorte, "janelas": linhas}


def _surpresa(tabela: pd.DataFrame) -> dict:
    import numpy as np

    correlacoes = surpresa.correlacao_surpresa(tabela)
    completos = tabela.dropna(subset=["surpresa", "ibov_d1"])
    inclinacao, intercepto = np.polyfit(completos["surpresa"], completos["ibov_d1"], 1)
    registros = [
        {
            "ano": int(r.ano),
            "turno": int(r.turno),
            "data": r.data,
            "margem_pesquisas": _limpo(r.margem_pesquisas),
            "margem_resultado": _limpo(r.margem_resultado),
            "surpresa": _limpo(r.surpresa),
            "favorito": None if pd.isna(r.favorito_pesquisas) else r.favorito_pesquisas,
            "candidato_mercado": r.candidato_mercado,
            "ibov_d1": _limpo(r.ibov_d1),
            "dolar_d1": _limpo(r.dolar_d1),
        }
        for r in tabela.itertuples()
    ]
    return {
        "turnos": registros,
        "tendencia": {"inclinacao": float(inclinacao), "intercepto": float(intercepto)},
        "correlacoes": [
            {
                "grupo": c.grupo,
                "n": int(c.n),
                "correlacao": _limpo(c.correlacao),
                "inclinacao": _limpo(c.inclinacao),
            }
            for c in correlacoes.itertuples()
        ],
    }


def _estatais(carteiras: pd.DataFrame, eleicoes: list[dict]) -> dict:
    """Estatais × privadas por eleição, no dia seguinte ao turno decisivo e em 1 ano."""
    indice = carteiras.set_index(["ano", "janela", "carteira"])
    opcoes = {}
    for chave, nome in (
        ("decisivo", "Dia seguinte ao turno decisivo"),
        ("posse_1ano", "1 ano de governo"),
    ):
        linhas = []
        for e in eleicoes:
            janela = f"t{e['decisivo']}_d1" if chave == "decisivo" else chave
            linha = {"ano": e["ano"], "janela": janela}
            for carteira in ("estatais", "privadas", "todas", "estatais_menos_privadas"):
                registro = indice.loc[(e["ano"], janela, carteira)]
                aconteceu = registro["status"] == "ok"
                linha[carteira] = _limpo(float(registro["variacao"])) if aconteceu else None
                linha[f"{carteira}_mediana"] = (
                    _limpo(float(registro["mediana"])) if aconteceu else None
                )
            linha["n_estatais"] = int(indice.loc[(e["ano"], janela, "estatais")]["n_empresas"])
            linha["ainda_nao"] = bool(
                indice.loc[(e["ano"], janela, "todas")]["status"] == "ainda_nao_aconteceu"
            )
            linhas.append(linha)
        opcoes[chave] = {"nome": nome, "linhas": linhas}
    return opcoes


def _setores_e_empresas(carteiras: pd.DataFrame, empresas: pd.DataFrame) -> dict:
    """Setores e empresas de 2026 no dia seguinte ao 2º turno."""
    do_dia = carteiras[(carteiras["ano"] == 2026) & (carteiras["janela"] == "t2_d1")]
    do_dia = do_dia[do_dia["status"] == "ok"]
    setores = do_dia[do_dia["carteira"].isin(NOMES_DOS_SETORES)]
    todas = do_dia[do_dia["carteira"] == "todas"].iloc[0]
    empresas_do_dia = empresas[
        (empresas["ano"] == 2026) & (empresas["janela"] == "t2_d1") & (empresas["status"] == "ok")
    ].sort_values("variacao")

    def _empresa(r) -> dict:
        return {
            "nome": r.empresa,
            "setor": NOMES_DOS_SETORES[r.setor],
            "estatal": bool(r.estatal),
            "variacao": _limpo(float(r.variacao)),
        }

    return {
        "janela": NOMES_DAS_JANELAS["t2_d1"],
        "todas": _limpo(float(todas["variacao"])),
        "setores": [
            {
                "setor": NOMES_DOS_SETORES[r.carteira],
                "variacao": _limpo(float(r.variacao)),
                "mediana": _limpo(float(r.mediana)),
                "contra_todas": _limpo(float(r.contra_todas)),
                "n": int(r.n_empresas),
            }
            for r in setores.sort_values("variacao").itertuples()
        ],
        "mais_cairam": [_empresa(r) for r in empresas_do_dia.head(8).itertuples()],
        "menos_cairam": [_empresa(r) for r in empresas_do_dia.tail(8).iloc[::-1].itertuples()],
        "n_empresas": len(empresas_do_dia),
    }


def _cenarios() -> dict:
    premissas = cenarios.carregar_premissas()
    tabela = _ler("cenarios.csv")
    medidas = []
    for medida, (nome, casas) in NOMES_DAS_MEDIDAS.items():
        da_medida = tabela[tabela["medida"] == medida]
        faixas = {}
        for linha in da_medida.itertuples():
            faixas.setdefault(linha.cenario, {})[linha.horizonte] = {
                "minimo": _limpo(linha.nivel_minimo),
                "central": _limpo(linha.nivel_central),
                "maximo": _limpo(linha.nivel_maximo),
                "var_minimo": _limpo(linha.minimo),
                "var_maximo": _limpo(linha.maximo),
                "analogos": linha.analogos_com_dado
                if isinstance(linha.analogos_com_dado, str)
                else "",
            }
        medidas.append(
            {
                "id": medida,
                "nome": nome,
                "casas": casas,
                "unidade": da_medida["unidade"].iloc[0],
                "base": _limpo(float(da_medida["nivel_base"].iloc[0])),
                "faixas": faixas,
            }
        )
    return {
        "status": premissas["status"],
        "data_base": str(premissas["data_base"]),
        "posse": str(premissas["posse"]),
        "horizontes": [
            {"id": h, "nome": NOMES_DOS_HORIZONTES[h], "data": str(premissas["horizontes"][h])}
            for h in cenarios.HORIZONTES
        ],
        "cenarios": [
            {
                "id": c["nome"],
                "titulo": c["titulo"],
                "analogos": c["analogos"],
                "por_que": " ".join(c["por_que_estes"].split()),
                "gatilhos": [" ".join(g.split()) for g in c["gatilhos"]],
            }
            for c in premissas["cenarios"]
        ],
        "medidas": medidas,
        "frase_pessimista": _frase_do_pessimista(tabela),
    }


def _frase_do_pessimista(tabela: pd.DataFrame) -> str:
    """A frase sobre o pessimista, com os números do cenarios.csv."""

    def faixa(medida: str, horizonte: str) -> tuple[float, float]:
        linha = tabela[
            (tabela["cenario"] == "pessimista")
            & (tabela["medida"] == medida)
            & (tabela["horizonte"] == horizonte)
        ].iloc[0]
        return float(linha["minimo"]), float(linha["maximo"])

    queda_min, queda_max = faixa("ibov_usd", "posse_1ano")
    pontos_min, pontos_max = faixa("ibov", "posse_1ano")
    posse_min, posse_max = faixa("ibov", "ate_posse")
    frase = (
        "No pessimista o Ibovespa quase não cai em pontos porque o real perde valor; "
        f"em dólar ele cai {_pt(abs(queda_max), 0)}% a {_pt(abs(queda_min), 0)}%."
    )
    detalhe = (
        f" Isso vale para 1 ano de governo, quando a faixa em pontos vai de "
        f"{_pt(pontos_min, 0, True)}% a {_pt(pontos_max, 0, True)}%. Até a posse, o pessimista "
        f"tem queda de {_pt(abs(posse_max), 0)}% a {_pt(abs(posse_min), 0)}% em pontos."
    )
    return frase + detalhe


def _catalogo() -> list[dict]:
    tabela = pd.read_csv(caminhos.SERIES / "catalogo.csv", keep_default_na=False)
    return [
        {
            "nome": r.descricao,
            "fonte": r.fonte,
            "codigo": r.codigo,
            "inicio": r.inicio,
            "fim": r.fim,
            "url": r.url,
        }
        for r in tabela.itertuples()
    ]


def dados_da_pagina() -> dict[str, Any]:
    tabela_janelas = _ler("janelas.csv")
    tabela_surpresa = _ler("surpresa.csv")
    carteiras = _ler("carteiras.csv")
    empresas = _ler("carteiras_empresas.csv")
    eleicoes = _eleicoes()
    dados_ate = pd.read_csv(caminhos.SERIES / "catalogo.csv").query("nome == 'ibov'")["fim"].iloc[0]
    return {
        "dados_ate": _data_br(dados_ate),
        "janelas": [{"id": j, "nome": NOMES_DAS_JANELAS[j]} for j in janelas.JANELAS],
        "destaques": destaques(tabela_janelas, tabela_surpresa),
        "eleicoes": eleicoes,
        "agora": _agora(tabela_janelas),
        "decisivo": _decisivo(tabela_janelas, eleicoes),
        "mapa": _mapa(tabela_janelas, eleicoes),
        "surpresa": _surpresa(tabela_surpresa),
        "estatais": _estatais(carteiras, eleicoes),
        "setores": _setores_e_empresas(carteiras, empresas),
        "propostas": carregar_propostas(),
        "cenarios": _cenarios(),
        "limites": LIMITES,
        "metodo": METODO,
        "catalogo": _catalogo(),
        "aviso": AVISO_FINAL,
    }


# ---------------------------------------------------------------- montagem


def trecho_do_leiame(nome: str, leiame: Path = LEIAME) -> str:
    """O texto do README entre `<!-- nome:inicio -->` e `<!-- nome:fim -->`, em HTML."""
    if not leiame.exists():
        raise ValueError(f"não achei {leiame}: a página lê o texto da análise do README")
    texto = leiame.read_text(encoding="utf-8")
    inicio, fim = f"<!-- {nome}:inicio -->", f"<!-- {nome}:fim -->"
    if texto.count(inicio) != 1 or texto.count(fim) != 1:
        raise ValueError(
            f"o README precisa ter uma vez cada marcador de '{nome}': {inicio} e {fim}"
        )
    html = markdown.markdown(texto.split(inicio)[1].split(fim)[0], extensions=["tables"])
    # A tabela ganha rolagem própria, para não alargar a página no celular.
    return html.replace("<table>", '<div class="rolagem"><table>').replace(
        "</table>", "</table></div>"
    )


def _ligacoes() -> str:
    """Links da página publicada: a planilha e o código."""
    return (
        f'<p><a href="{REPOSITORIO}/raw/main/saida/{ARQUIVO.name}">Baixar a planilha (.xlsx)</a>'
        f' · <a href="{REPOSITORIO}">código e dados no GitHub</a></p>'
    )


def construir(leiame: Path = LEIAME, saida: Path | None = None) -> Path:
    """Grava a página completa (index.html) e o fragmento para publicar como artefato.

    `saida` é a pasta de destino (por padrão, `site/`); o molde sempre sai de `site/`.
    """
    saida = saida or caminhos.SITE
    molde = (caminhos.SITE / "pagina.html").read_text(encoding="utf-8")
    graficos = (caminhos.SITE / "graficos.js").read_text(encoding="utf-8")
    # Lê os trechos primeiro: sem README o erro vem antes de qualquer arquivo gravado.
    trechos = {marca: trecho_do_leiame(nome, leiame) for marca, nome in TRECHOS.items()}
    conteudo = dados_da_pagina()
    dados = json.dumps(conteudo, ensure_ascii=False, separators=(",", ":"))
    # "</" dentro de um <script> fecharia o bloco antes da hora.
    dados = dados.replace("</", "<\\/")
    fragmento = molde.replace("__DADOS_ATE__", conteudo["dados_ate"])
    fragmento = fragmento.replace("/*__GRAFICOS__*/", graficos).replace("/*__DADOS__*/", dados)
    for marca, html in trechos.items():
        fragmento = fragmento.replace(marca, html)
    # O artefato não deixa baixar arquivo: os links ficam só na página completa.
    (saida / "artefato.html").write_text(fragmento.replace(LIGACOES, ""), encoding="utf-8")

    # O molde começa por <title>, <link> e <style>: isso vai no <head> da página completa.
    cabeca, corpo = fragmento.replace(LIGACOES, _ligacoes()).split(CORPO, 1)
    destino = saida / "index.html"
    destino.write_text(
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta name="description" content="{DESCRICAO}">\n'
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:title" content="{TITULO}">\n'
        f'<meta property="og:description" content="{DESCRICAO}">\n'
        f'<meta property="og:url" content="{PAGINA}">\n'
        f'{cabeca}</head>\n<body style="margin:0">\n{CORPO}{corpo}</body>\n</html>\n',
        encoding="utf-8",
    )
    return destino
