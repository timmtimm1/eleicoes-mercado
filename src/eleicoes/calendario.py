"""Eleições, turnos e o calendário de pregões do estudo.

O calendário oficial é o das datas da série `ibov` (Yahoo): toda janela conta pregões nele.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd
import yaml

from eleicoes import series
from eleicoes.caminhos import DADOS


@dataclass(frozen=True)
class Turno:
    """Um turno e o resultado do TSE: candidato → % dos votos válidos."""

    numero: int
    data: date
    resultado: dict[str, float]


@dataclass(frozen=True)
class Eleicao:
    ano: int
    vencedor: str
    segundo: str
    posse: date
    situacao: str
    candidato_mercado: str
    turnos: tuple[Turno, ...]

    @property
    def adversario_mercado(self) -> str:
        """O outro entre o vencedor e o segundo colocado."""
        return self.segundo if self.candidato_mercado == self.vencedor else self.vencedor

    @property
    def primeiro_turno(self) -> Turno:
        return self.turnos[0]

    @property
    def turno_decisivo(self) -> Turno:
        """O último turno: o 1º em 1994 e 1998, o 2º nas demais."""
        return self.turnos[-1]


def _data(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor))


def carregar_eleicoes(caminho=DADOS / "eleicoes.yaml") -> list[Eleicao]:
    """Lê o YAML de eleições (comentários no cabeçalho são ignorados)."""
    with open(caminho, encoding="utf-8") as arquivo:  # noqa: PTH123
        bruto = yaml.safe_load(arquivo)
    eleicoes = []
    for item in bruto:
        turnos = tuple(
            Turno(
                numero=int(turno["numero"]),
                data=_data(turno["data"]),
                resultado={r["candidato"]: float(r["pct"]) for r in turno["resultado"]},
            )
            for turno in sorted(item["turnos"], key=lambda t: t["numero"])
        )
        eleicoes.append(
            Eleicao(
                ano=int(item["ano"]),
                vencedor=item["vencedor"],
                segundo=item["segundo"],
                posse=_data(item["posse"]),
                situacao=item["situacao"],
                candidato_mercado=item["candidato_mercado"],
                turnos=turnos,
            )
        )
    return sorted(eleicoes, key=lambda e: e.ano)


def pregoes() -> pd.DatetimeIndex:
    """Datas dos pregões: as da série `ibov`."""
    return pd.DatetimeIndex(series.ler("ibov").index)


def _depois_do_fim(data, calendario: pd.DatetimeIndex) -> bool:
    return pd.Timestamp(data) > calendario[-1]


def ultimo_pregao_antes(data, calendario: pd.DatetimeIndex) -> pd.Timestamp | None:
    """Último pregão estritamente antes de `data`; None se não há, ou se `data` é futura."""
    alvo = pd.Timestamp(data)
    if _depois_do_fim(alvo, calendario):
        return None
    posicao = calendario.searchsorted(alvo, side="left") - 1
    return calendario[posicao] if posicao >= 0 else None


def ultimo_pregao_ate(data, calendario: pd.DatetimeIndex) -> pd.Timestamp | None:
    """Último pregão em ou antes de `data`; None se não há, ou se `data` é futura."""
    alvo = pd.Timestamp(data)
    if _depois_do_fim(alvo, calendario):
        return None
    posicao = calendario.searchsorted(alvo, side="right") - 1
    return calendario[posicao] if posicao >= 0 else None


def pregao_depois(data, n: int, calendario: pd.DatetimeIndex) -> pd.Timestamp | None:
    """O n-ésimo pregão estritamente depois de `data` (n=1 é o primeiro); None se não existe."""
    posicao = calendario.searchsorted(pd.Timestamp(data), side="right") + n - 1
    return calendario[posicao] if posicao < len(calendario) else None
