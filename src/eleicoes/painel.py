"""Painel interativo: um HTML só, com abas, filtros e os dados embutidos.

`site/painel.html` é o molde (estrutura, estilo e a lógica das abas), `site/graficos.js` desenha
os gráficos. Os dados são os mesmos da página longa (`site.dados_da_pagina()`), mais o que o painel
calcula para si: os seis números-chave, as correlações das pesquisas e as carteiras de cada
eleição e janela. Sai em `site/painel_completo.html`, um documento inteiro que serve de artefato.
"""

import html
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eleicoes import caminhos, janelas, site
from eleicoes.nomes import NOMES_DOS_SETORES

TITULO = "Eleições e Mercado 2026"
ARQUIVO = "painel_completo.html"
CORPO = '<div class="wrap">'
ANO = 2026
COPOM = (
    "2026-11-04",
    "Reunião do Copom, que decide a Selic. Os cenários olham se os cortes continuam.",
)
# Setores de verdade: "outros" não forma carteira.
SETORES = [chave for chave in NOMES_DOS_SETORES if chave != "outros"]
MINIMO_DE_EMPRESAS = 3
LIMITE_DO_PADRAO = 2.0  # desvios-padrão

STATUS_NO_SELO = {"aprovada": "aprovadas", "proposta": "em proposta"}

REGRA_DOS_CHIPS = (
    "Recorde da série: o maior valor em módulo entre todos os turnos. Fora do padrão: mais de "
    "2 desvios-padrão da média das outras eleições (sem 2026). Dentro do padrão: o resto. "
    "A cor diz se o número é incomum, não se é bom ou ruim."
)


# ---------------------------------------------------------------- números-chave


def _serie_por_turno(tabela: pd.DataFrame, janelas_do_turno: tuple[str, str]) -> pd.DataFrame:
    """Uma linha por (ano, turno) com a coluna `valor`, a partir de uma tabela já filtrada."""
    do_turno = tabela[tabela["janela"].isin(janelas_do_turno)].dropna(subset=["valor"])
    return do_turno.assign(turno=lambda t: t["janela"].str[1].astype(int))[
        ["ano", "turno", "valor"]
    ]


def _estado(serie: pd.DataFrame, valor: float) -> tuple[str, float, float, float]:
    """Estado (recorde, fora ou dentro do padrão), média, desvio e distância em desvios."""
    antigos = serie[serie["ano"] != ANO]["valor"]
    media, desvio = float(antigos.mean()), float(antigos.std(ddof=1))
    distancia = abs(valor - media) / desvio if desvio > 0 else float("inf")
    if abs(valor) >= serie["valor"].abs().max():
        return "recorde", media, desvio, distancia
    if distancia > LIMITE_DO_PADRAO:
        return "fora", media, desvio, distancia
    return "dentro", media, desvio, distancia


def _contexto(serie: pd.DataFrame, valor: float, termos: dict, formatar) -> str:
    """Posição de 2026 na série: “Pior de 16 turnos; o 2º pior foi −4,5% em 1998.”"""
    termo, palavra, feminino = termos["pos" if valor >= 0 else "neg"]
    de = termos.get("conector", "de")
    ordinal = "ª" if feminino else "º"
    artigo = "a" if feminino else "o"
    # 1 = o mais extremo do mesmo lado de zero.
    ordenada = serie.sort_values("valor", ascending=valor < 0)
    posicao = (
        int((ordenada["valor"] < valor).sum() if valor < 0 else (ordenada["valor"] > valor).sum())
        + 1
    )
    total = len(serie)
    if posicao > 1:
        return f"{posicao}{ordinal} {termo} {de} {total} turnos."
    segundo = ordenada.iloc[1]
    quando = f"{int(segundo['ano'])}" + (
        f" ({int(segundo['turno'])}º turno)" if segundo["ano"] == ANO else ""
    )
    return (
        f"{termo.capitalize()} {de} {total} turnos; {artigo} 2{ordinal} {palavra} foi "
        f"{formatar(segundo['valor'])} em {quando}."
    )


def _cartao(
    rotulo: str, serie: pd.DataFrame, termos: dict, formatar, unidade_do_desvio: str
) -> dict:
    """Um cartão: valor de 2026 no 2º turno, contexto calculado e chip de estado."""
    valor = float(serie[(serie["ano"] == ANO) & (serie["turno"] == 2)]["valor"].iloc[0])
    estado, media, desvio, distancia = _estado(serie, valor)
    return {
        "rotulo": rotulo,
        "valor": formatar(valor),
        "contexto": _contexto(serie, valor, termos, formatar),
        "estado": estado,
        "estado_texto": {
            "recorde": "recorde da série",
            "fora": "fora do padrão",
            "dentro": "dentro do padrão",
        }[estado],
        "n": len(serie),
        "media_sem_2026": formatar(media),
        "desvio_sem_2026": f"{site._pt(desvio, 1 if desvio >= 1 else 2)} {unidade_do_desvio}",
        "distancia": site._pt(distancia, 1),
    }


def chaves(
    tabela_janelas: pd.DataFrame, tabela_surpresa: pd.DataFrame, carteiras: pd.DataFrame
) -> list[dict]:
    """Os seis números-chave de 2026, todos lidos das tabelas de resultado."""

    def da_medida(medida: str, coluna: str = "variacao") -> pd.DataFrame:
        linhas = tabela_janelas[tabela_janelas["medida"] == medida]
        return linhas.assign(valor=linhas[coluna])

    def pct(v: float) -> str:
        return f"{site._pt(v, 1, True)}%"

    def pp(casas: int):
        return lambda v: f"{site._pt(v, casas, True)} p.p."

    pior_melhor = {"neg": ("pior", "pior", False), "pos": ("melhor", "melhor", False)}
    alta_queda = {"neg": ("maior queda", "maior", True), "pos": ("maior alta", "maior", True)}
    d1, d5 = ("t1_d1", "t2_d1"), ("t1_d5", "t2_d5")
    dolar_d1 = _serie_por_turno(da_medida("dolar"), d1)
    juro_d1 = _serie_por_turno(da_medida("prefixado_10a"), d1)
    estatais = carteiras[carteiras["carteira"] == "estatais_menos_privadas"]
    estatais = _serie_por_turno(estatais.assign(valor=estatais["variacao"]), d1)
    surpresa_ = tabela_surpresa.assign(valor=tabela_surpresa["surpresa"]).dropna(subset=["valor"])
    surpresa_ = surpresa_.assign(janela="t" + surpresa_["turno"].astype(str) + "_d1")
    return [
        _cartao(
            "Ibovespa no dia seguinte ao 2º turno",
            _serie_por_turno(da_medida("ibov"), d1),
            pior_melhor,
            pct,
            "p.p.",
        ),
        _cartao(
            "Ibovespa nos 5 pregões depois do 2º turno",
            _serie_por_turno(da_medida("ibov"), d5),
            pior_melhor,
            pct,
            "p.p.",
        ),
        _cartao("Dólar no dia seguinte", dolar_d1, alta_queda, pct, "p.p."),
        _cartao("Tesouro 10 anos no dia seguinte", juro_d1, alta_queda, pp(2), "p.p."),
        _cartao(
            "Surpresa das pesquisas no 2º turno",
            _serie_por_turno(surpresa_, d1),
            {"neg": ("pior", "pior", True), "pos": ("melhor", "melhor", True)},
            lambda v: f"{site._pt(v, 1, True)} pontos",
            "pontos",
        ),
        _cartao(
            "Estatais menos privadas no dia seguinte",
            estatais,
            {
                "neg": ("maior vantagem das privadas", "maior", True),
                "pos": ("maior vantagem das estatais", "maior", True),
                "conector": "em",
            },
            pp(1),
            "p.p.",
        ),
    ]


# ---------------------------------------------------------------- pesquisas


def pesquisas(tabela: pd.DataFrame) -> dict:
    """Correlação entre surpresa e Ibovespa no dia seguinte, em quatro recortes, e a inclinação."""
    completos = tabela.dropna(subset=["surpresa", "ibov_d1"])
    recortes = [
        ("Todos os turnos", completos),
        ("Sem 2026", completos[completos["ano"] != ANO]),
        ("Só 1º turno", completos[completos["turno"] == 1]),
        ("Só 2º turno", completos[completos["turno"] == 2]),
    ]
    saida = []
    for nome, grupo in recortes:
        correlacao = inclinacao = intercepto = None
        if len(grupo) >= MINIMO_DE_EMPRESAS and grupo["surpresa"].nunique() > 1:
            x, y = grupo["surpresa"].to_numpy(), grupo["ibov_d1"].to_numpy()
            correlacao = float(np.corrcoef(x, y)[0, 1])
            inclinacao, intercepto = (float(v) for v in np.polyfit(x, y, 1))
        saida.append(
            {
                "grupo": nome,
                "n": len(grupo),
                "correlacao": site._limpo(correlacao),
                "inclinacao": site._limpo(inclinacao),
                "intercepto": site._limpo(intercepto),
            }
        )
    return {"correlacoes": saida}


# ---------------------------------------------------------------- setores


def _grupo(linha: pd.Series) -> dict:
    return {
        "media": site._limpo(float(linha["variacao"])),
        "mediana": site._limpo(float(linha["mediana"])),
        "n": int(linha["n_empresas"]),
    }


def _empresa(linha) -> dict:
    return {
        "nome": linha.empresa,
        "setor": NOMES_DOS_SETORES[linha.setor],
        "estatal": bool(linha.estatal),
        "variacao": round(float(linha.variacao), 2),
    }


def setores(carteiras: pd.DataFrame, empresas: pd.DataFrame, eleicoes: list[dict]) -> dict:
    """Carteiras e empresas de cada eleição × janela, com a janela padrão de cada eleição."""
    por_carteira = {
        chave: g.set_index("carteira") for chave, g in carteiras.groupby(["ano", "janela"])
    }
    por_empresa = {
        chave: g[g["status"] == "ok"].sort_values("variacao")
        for chave, g in empresas.groupby(["ano", "janela"])
    }
    dados: dict[str, Any] = {}
    for eleicao in eleicoes:
        for janela in janelas.JANELAS:
            chave = (eleicao["ano"], janela)
            if chave not in por_carteira:
                dados[f"{chave[0]}|{janela}"] = {
                    "aconteceu": False,
                    "motivo": "Esta eleição não teve 2º turno.",
                }
                continue
            do_dia = por_carteira[chave]
            if do_dia.loc["todas", "status"] != "ok":
                dados[f"{chave[0]}|{janela}"] = {
                    "aconteceu": False,
                    "motivo": "Ainda não aconteceu.",
                }
                continue
            setores_ok, sem_carteira = [], []
            for setor in SETORES:
                linha = do_dia.loc[setor] if setor in do_dia.index else None
                if (
                    linha is None
                    or linha["status"] != "ok"
                    or linha["n_empresas"] < MINIMO_DE_EMPRESAS
                ):
                    sem_carteira.append(NOMES_DOS_SETORES[setor])
                    continue
                setores_ok.append(
                    {
                        "setor": NOMES_DOS_SETORES[setor],
                        **_grupo(linha),
                        "contra_todas": site._limpo(float(linha["contra_todas"])),
                    }
                )
            da_janela = por_empresa[chave]
            dados[f"{chave[0]}|{janela}"] = {
                "aconteceu": True,
                "todas": _grupo(do_dia.loc["todas"]),
                "estatais": _grupo(do_dia.loc["estatais"]),
                "privadas": _grupo(do_dia.loc["privadas"]),
                "estatais_menos_privadas": site._limpo(
                    float(do_dia.loc["estatais_menos_privadas", "variacao"])
                ),
                "setores": setores_ok,
                "sem_carteira": sem_carteira,
                "mais_cairam": [_empresa(r) for r in da_janela.head(8).itertuples()],
                "mais_subiram": [_empresa(r) for r in da_janela.tail(8).iloc[::-1].itertuples()],
                "n_empresas": len(da_janela),
            }
    return {
        "dados": dados,
        "padrao": {e["ano"]: f"t{e['decisivo']}_d1" for e in eleicoes},
    }


# ---------------------------------------------------------------- tudo junto


def _acompanhar(cenarios: dict) -> list[dict]:
    """Datas conhecidas dos próximos meses, na ordem."""
    itens = [{"data": COPOM[0], "texto": COPOM[1]}]
    horizontes = {h["id"]: h for h in cenarios["horizontes"]}
    itens.append(
        {
            "data": cenarios["posse"],
            "texto": "Posse do novo mandato. O horizonte “Posse” dos cenários mede até o último "
            f"pregão antes, em {site._data_br(horizontes['ate_posse']['data'])}.",
        }
    )
    itens.append(
        {
            "data": horizontes["posse_100d"]["data"],
            "texto": "100 dias de governo: segundo horizonte dos cenários.",
        }
    )
    itens.append(
        {
            "data": horizontes["posse_1ano"]["data"],
            "texto": "1 ano de governo: terceiro horizonte dos cenários.",
        }
    )
    return sorted(itens, key=lambda i: i["data"])


def dados_do_painel() -> dict[str, Any]:
    """Os dados da página longa que o painel usa, mais o que ele calcula."""
    base = site.dados_da_pagina()
    tabela_janelas = site._ler("janelas.csv")
    tabela_surpresa = site._ler("surpresa.csv")
    carteiras = site._ler("carteiras.csv")
    empresas = site._ler("carteiras_empresas.csv")
    for chave in ("destaques", "decisivo", "estatais", "setores", "metodo", "catalogo"):
        base.pop(chave)
    return {
        **base,
        "chaves": chaves(tabela_janelas, tabela_surpresa, carteiras),
        "regra_dos_chips": REGRA_DOS_CHIPS,
        "selo": "Cenários: premissas "
        + STATUS_NO_SELO.get(base["cenarios"]["status"], base["cenarios"]["status"]),
        "pesquisas": pesquisas(tabela_surpresa),
        "setores": setores(carteiras, empresas, base["eleicoes"]),
        "acompanhar": _acompanhar(base["cenarios"]),
        "links": {"pagina": site.PAGINA, "codigo": site.REPOSITORIO},
    }


def construir(saida: Path | None = None) -> Path:
    """Grava o painel completo (`painel_completo.html`) a partir do molde `site/painel.html`."""
    saida = saida or caminhos.SITE
    molde = (caminhos.SITE / "painel.html").read_text(encoding="utf-8")
    graficos = (caminhos.SITE / "graficos.js").read_text(encoding="utf-8")
    conteudo = dados_do_painel()
    dados = json.dumps(conteudo, ensure_ascii=False, separators=(",", ":"))
    # "</" dentro de um <script> fecharia o bloco antes da hora.
    dados = dados.replace("</", "<\\/")
    fragmento = molde.replace("__DADOS_ATE__", conteudo["dados_ate"])
    fragmento = fragmento.replace("__SELO__", html.escape(conteudo["selo"]))
    fragmento = fragmento.replace("__AVISO__", html.escape(conteudo["aviso"]))
    fragmento = fragmento.replace("__PAGINA__", site.PAGINA).replace(
        "__REPOSITORIO__", site.REPOSITORIO
    )
    fragmento = fragmento.replace("/*__GRAFICOS__*/", graficos).replace("/*__DADOS__*/", dados)
    # O molde começa por <title>, <link> e <style>: isso vai no <head>.
    cabeca, corpo = fragmento.split(CORPO, 1)
    destino = saida / ARQUIVO
    destino.write_text(
        '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{cabeca}</head>\n<body>\n{CORPO}{corpo}</body>\n</html>\n",
        encoding="utf-8",
    )
    return destino
