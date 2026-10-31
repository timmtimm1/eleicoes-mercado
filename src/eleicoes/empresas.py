"""Tabelas feitas à mão: classificação das empresas, sucessões de código e exclusões.

- `dados/empresas.csv`: por raiz, setor e se a empresa é estatal ou privada. Estatal numa
  eleição = `controle == "estatal"` e (`privatizada_em` vazio ou depois do 1º turno).
- `dados/sucessoes.csv`: a mesma empresa com código novo (`fator` = ações novas por ação
  antiga). Pode haver cadeia ou ciclo (NATU, NTCO, NATU): as raízes ligadas formam uma família.
- `dados/exclusoes.csv`: empresa que fica fora das carteiras de um ano.
"""

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from eleicoes.caminhos import DADOS

SETOR_SEM_CLASSIFICACAO = "sem_classificacao"


@dataclass(frozen=True)
class Empresa:
    raiz: str
    empresa: str
    setor: str
    segmento: str
    controle: str
    controlador: str
    privatizada_em: date | None


@dataclass(frozen=True)
class Sucessao:
    raiz_antiga: str
    raiz_nova: str
    fator: float
    observacao: str


def _ler_csv(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def carregar_empresas(caminho: Path = DADOS / "empresas.csv") -> dict[str, Empresa]:
    empresas = {}
    for linha in _ler_csv(caminho):
        privatizada = linha["privatizada_em"].strip()
        empresas[linha["raiz"]] = Empresa(
            raiz=linha["raiz"],
            empresa=linha["empresa"],
            setor=linha["setor"],
            segmento=linha["segmento"],
            controle=linha["controle"],
            controlador=linha["controlador"],
            privatizada_em=date.fromisoformat(privatizada) if privatizada else None,
        )
    return empresas


def carregar_sucessoes(caminho: Path = DADOS / "sucessoes.csv") -> list[Sucessao]:
    return [
        Sucessao(l["raiz_antiga"], l["raiz_nova"], float(l["fator"]), l["observacao"])
        for l in _ler_csv(caminho)  # noqa: E741
    ]


def carregar_exclusoes(caminho: Path = DADOS / "exclusoes.csv") -> set[tuple[int, str]]:
    return {(int(l["ano"]), l["raiz"]) for l in _ler_csv(caminho)}  # noqa: E741


def e_estatal(empresa: Empresa | None, primeiro_turno: date) -> bool:
    """Estatal na data do 1º turno: controle estatal e ainda não privatizada."""
    if empresa is None or empresa.controle != "estatal":
        return False
    return empresa.privatizada_em is None or empresa.privatizada_em > primeiro_turno


def familias(sucessoes: list[Sucessao]) -> dict[str, str]:
    """Raiz -> chave da família (a menor raiz, em ordem alfabética) das raízes ligadas.

    Só aparecem as raízes que estão em alguma sucessão; as outras são a própria família.
    """
    pai: dict[str, str] = {}

    def achar(raiz: str) -> str:
        pai.setdefault(raiz, raiz)
        while pai[raiz] != raiz:
            pai[raiz] = pai[pai[raiz]]
            raiz = pai[raiz]
        return raiz

    for sucessao in sucessoes:
        a, b = achar(sucessao.raiz_antiga), achar(sucessao.raiz_nova)
        if a != b:
            pai[max(a, b)] = min(a, b)
    return {raiz: achar(raiz) for raiz in list(pai)}
