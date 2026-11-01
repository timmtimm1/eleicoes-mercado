"""Gera analises/propostas.md a partir de dados/propostas.yaml e dados/marcos.csv.

Uso (na raiz do repositório):
    uv run --no-project --with pyyaml python scripts/propostas_md.py

O markdown sai só dos dois arquivos de dados. Se eles mudarem, rode de novo.
"""
import csv
from datetime import date
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
PROPOSTAS = RAIZ / "dados" / "propostas.yaml"
MARCOS = RAIZ / "dados" / "marcos.csv"
SAIDA = RAIZ / "analises" / "propostas.md"

TEMAS = [
    ("fiscal", "Gastos e regra fiscal"),
    ("privatizacoes", "Privatizações"),
    ("estatais", "Petrobras e estatais"),
    ("banco_central", "Banco Central e juros"),
    ("reformas", "Reformas"),
    ("cambio_comercio", "Câmbio e comércio"),
]

INTRO = (
    "Propostas e marcos revisados e aprovados em 31/10/2026. Este arquivo é gerado por "
    "`scripts/propostas_md.py` a partir de `dados/propostas.yaml` (propostas dos "
    "dois principais candidatos de cada eleição de 1994 a 2026, o que o vencedor "
    "fez no 1º ano e meio e, em 2026, os sinais e a contestação depois da "
    "eleição) e de `dados/marcos.csv` (fatos com data que mexeram no mercado). "
    "Cada célula traz o texto e um link de fonte (programa de governo, "
    "imprensa da época ou documento oficial). \"—\" quer dizer que nenhuma fonte "
    "foi encontrada. Os dados foram pesquisados e conferidos em 31/10/2026. "
    "Não edite aqui: corrija os dois arquivos de dados e rode o script de novo."
)


def celula(item):
    """Texto + [fonte](url) de um item {texto, fonte}; '—' se não houver."""
    texto = (item.get("texto") or "").strip()
    fonte = (item.get("fonte") or "").strip()
    if not fonte and (not texto or texto.lower().startswith("sem fonte")):
        return "—"
    texto = texto.replace("|", "\\|").replace("\n", " ")
    return f"{texto} [fonte]({fonte})" if fonte else texto


def tabela(cabecalho, linhas):
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(linha) + " |" for linha in linhas]
    return "\n".join(saida)


def data_br(iso):
    d = date.fromisoformat(str(iso))
    return d.strftime("%d/%m/%Y")


def item_lista(d, texto, fonte):
    return f"- {data_br(d)} — {texto} ([fonte]({fonte}))"


def main():
    eleicoes = yaml.safe_load(PROPOSTAS.read_text(encoding="utf-8"))
    with MARCOS.open(encoding="utf-8", newline="") as f:
        marcos = list(csv.DictReader(f))

    out = ["# Propostas e marcos das eleições presidenciais (1994–2026)", "", INTRO, ""]

    for e in sorted(eleicoes, key=lambda x: x["ano"], reverse=True):
        ano = e["ano"]
        cands = e["candidatos"]
        nomes = [c["nome"] for c in cands]
        out += [f"## {ano} — {' × '.join(nomes)}", ""]

        out += ["### Propostas", ""]
        linhas = [
            [rotulo] + [celula(c.get(chave, {})) for c in cands]
            for chave, rotulo in TEMAS
        ]
        out += [tabela(["Tema"] + nomes, linhas), ""]

        if "realizado" in e:
            vencedor = nomes[0]  # o primeiro de cada eleição é o vencedor
            out += [f"### O que foi feito no 1º ano e meio ({vencedor})", ""]
            linhas = [
                [rotulo, celula(e["realizado"].get(chave, {}))] for chave, rotulo in TEMAS
            ]
            out += [tabela(["Tema", "O que foi feito"], linhas), ""]

        if e.get("sinais_pos_eleicao"):
            out += ["### Sinais depois da eleição", ""]
            out += [item_lista(s["data"], s["texto"], s["fonte"]) for s in e["sinais_pos_eleicao"]]
            out += [""]
        if e.get("contestacao"):
            out += ["### Contestação do resultado", ""]
            out += [item_lista(s["data"], s["texto"], s["fonte"]) for s in e["contestacao"]]
            out += [""]

        out += ["### Marcos", ""]
        do_ano = sorted((m for m in marcos if int(m["ano"]) == ano), key=lambda m: m["data"])
        out += [item_lista(m["data"], m["descricao"], m["fonte"]) for m in do_ano]
        out += [""]

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    print(f"Escrito {SAIDA.relative_to(RAIZ)} ({len(out)} linhas)")


if __name__ == "__main__":
    main()
