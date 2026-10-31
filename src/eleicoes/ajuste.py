"""Preço de cada papel ajustado por desdobramento, grupamento e bonificação (sem dividendos).

O COTAHIST traz o preço bruto: um desdobramento 2:1 aparece como queda de 50% e uma bonificação
de 10% como queda de 9%. O ajuste acha esses dias e divide a variação do papel pelo fator do
evento, deixando o resto (o mercado e o que for do papel).

O que a investigação nos dados mostrou (1994 a 2026, as empresas das listas de liquidez):

- A `especi` ganha um sufixo no **primeiro pregão ex** do evento e o mantém por cerca de 8
  pregões: `ED` dividendo, `EJ` juros sobre capital próprio, `ES` subscrição, `EC` cisão, `EB`
  bonificação **e desdobramento** (a PETR4 de 28/04/2008 aparece como `EB` e cai 49,5%), `EG`
  grupamento, e combinações (`EDB`, `EJB`, `EBD`, `EBG`, `EBS`). Só os sufixos com `B` ou `G`
  são evento em ações. Os outros mexem em dinheiro, e dinheiro fica no preço (só preço, sem
  dividendos). O dia do evento é o primeiro da sequência com o sufixo.
- Dos pregões com variação acima de 25% que casam com um fator redondo, só os que começam
  um sufixo `B`/`G` são evento de fato. Os sem sufixo são quase todos movimento de verdade
  (queda de 25%, 33% ou 50% em um dia de papel em crise), ou ruído de degrau de preço em
  papel de centavos. Por isso o sem-sufixo só é neutralizado quando o fator é de
  desdobramento ou grupamento "cheio" (2, 3, 4, 5, 10, 100, 1000 ou os inversos).
- Num evento marcado, o fator pode ser a combinação de dois (grupamento de 1.000 para 1 junto
  com desdobramento de 2 para 1 dá 500): quando a variação passa de 2,7 vezes e nenhum fator
  simples serve, aceita-se o produto de dois fatores redondos. Abaixo disso o produto "serve"
  para quase tudo (CMIG4 em 27/04/2007 casaria com 1/1,65, e o fator era 1/1,5).
- A tolerância é de 2% sem sufixo e de 7% com sufixo (a bonificação sai junto com dividendo
  e o papel tem a variação própria do dia). O degrau de preço (0,01 / FATCOT) soma na
  tolerância: sem sufixo, passando de 6% o fator não se identifica; com sufixo, até 25%
  (PDGR3 a R$ 0,06). Fora disso o evento marcado vai para `evento_sem_fator`.
- `EC`, `EDC` e `ES` (cisão e subscrição) são transferência de valor, não evento em
  ações, e ficam no preço. O Yahoo ajusta alguns como se fossem desdobramento (CSAN3 em
  06/10/2014, CYRE3 em 09/08/2007, MRVE3 em 21/12/2018); aqui seguem como queda de preço.
"""

import re
from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd

TOLERANCIA = 0.02
# Num evento marcado a variação própria do papel no dia (dividendo junto, ruído) entra na
# razão: 2% rejeitava eventos de verdade (BBDC4 em 07/04/2008: razão 0,683 contra 1/1,5; CMIG4
# em 27/04/2007: 0,627 contra 1/1,5, pago junto com dividendo).
TOLERANCIA_MARCADO = 0.07
# O degrau de preço pode deixar a tolerância grande (PDGR3 a R$ 0,06); acima disso desiste.
TOLERANCIA_MAXIMA_MARCADO = 0.25
# Produto de dois fatores só para variações maiores que 2,7 vezes.
LIMITE_EVENTO_COMBINADO = 1.0
# Sem sufixo, o dia anterior do papel tem de estar a, no máximo, esse número de dias: depois de
# um buraco a variação mistura semanas de mercado.
DIAS_MAXIMOS_SEM_SUFIXO = 5
# Sem sufixo, só variações acima de 25% entram.
LIMITE_VARIACAO_GRANDE = 0.25
# Sem sufixo, se o degrau de preço deixa a tolerância acima disso, o fator não se identifica.
TOLERANCIA_MAXIMA = 0.06
# Evento marcado com variação menor que isso (em módulo) não vale registro.
MINIMO_PARA_REGISTRO = 0.04
# Evento marcado em que a razão (sem o mercado) fica a menos disso de 1 não mexeu no preço: o
# sufixo muda de `EB` para `EJB` uns dias depois do ex, e com 7% de tolerância a razão ~1 casaria
# com 1/1,05.
RAZAO_SEM_EVENTO = 0.03

_BASE = [1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.5, 2, 3, 4, 5, 6, 8, 10, 20, 50, 100, 1000]
_CHEIOS = [2, 3, 4, 5, 10, 100, 1000]
FATORES_REDONDOS = np.array(
    sorted({*_BASE, *(1 / x for x in _BASE), 4 / 3, 3 / 4, 3 / 2, 2 / 3, 5 / 4, 4 / 5})
)
FATORES_CHEIOS = np.array(sorted({*_CHEIOS, *(1 / x for x in _CHEIOS)}))
# Produtos de dois fatores redondos, só para eventos marcados e grandes.
FATORES_COMBINADOS = np.array(
    sorted({a * b for a, b in product(FATORES_REDONDOS, repeat=2) if abs(np.log(a * b)) > 0.5})
)

MOTIVO_MARCADO = "evento_em_acoes"
MOTIVO_GRANDE = "variacao_grande"
MOTIVO_SEM_FATOR = "evento_sem_fator"

# Sufixo de evento na `especi`: logo depois do tipo, com ou sem `*` (ex.: `PN  EB N1`, `ON *EJ`).
_SUFIXO = re.compile(r"(?:^|[\s*])(E[A-Z]{1,3})(?=\s|$)")
_EM_ACOES = re.compile(r"^E[A-Z]*[BG]")


@dataclass(frozen=True)
class Ajuste:
    data: pd.Timestamp
    ticker: str
    variacao_bruta: float  # em %
    fator: float  # NaN em `evento_sem_fator`
    motivo: str


def sufixo_do_evento(especi: pd.Series) -> pd.Series:
    """Sufixo `E..` da `especi` (`EB`, `EDJ`...), vazio se não há."""
    tipo = especi.str.replace(r"^(ON|PN[A-Z]?|UNT)", "", regex=True)
    return tipo.str.extract(_SUFIXO)[0].fillna("")


def e_evento_em_acoes(sufixo: str) -> bool:
    return bool(_EM_ACOES.match(sufixo))


def _fator_mais_proximo(razao: float, candidatos: np.ndarray, tolerancia: float) -> float:
    """O candidato a até `tolerancia` (relativa) de `razao`, o mais próximo; NaN se nenhum."""
    relativo = np.abs(razao / candidatos - 1)
    melhor = int(relativo.argmin())
    return float(candidatos[melhor]) if relativo[melhor] <= tolerancia else np.nan


def escolher_fator(razao: float, marcado: bool, tolerancia: float) -> float:
    """O fator redondo do evento, ou NaN. Ver o texto do módulo para as listas."""
    if not marcado:
        return _fator_mais_proximo(razao, FATORES_CHEIOS, tolerancia)
    tolerancia = max(tolerancia, TOLERANCIA_MARCADO)
    if tolerancia > TOLERANCIA_MAXIMA_MARCADO:
        return np.nan
    fator = _fator_mais_proximo(razao, FATORES_REDONDOS, tolerancia)
    if np.isnan(fator) and abs(np.log(razao)) > LIMITE_EVENTO_COMBINADO:
        fator = _fator_mais_proximo(razao, FATORES_COMBINADOS, tolerancia)
    return fator


def ajustar_papel(
    quadro: pd.DataFrame, ibov: pd.Series
) -> tuple[pd.Series, list[Ajuste], pd.Series]:
    """Preço ajustado de um ticker, os ajustes feitos e o fator de cada pregão.

    `quadro`: colunas data, ticker, especi, fechamento, fatcot, de um só ticker. `ibov`: nível
    diário do Ibovespa, para tirar o mercado da variação antes de procurar o fator.

    O preço ajustado termina igual ao bruto e os anteriores são multiplicados pelos fatores
    posteriores (só a razão entre datas importa). O terceiro valor é o multiplicador do pregão
    (1 onde não houve ajuste), no índice de datas do ticker.
    """
    quadro = quadro.sort_values("data")
    datas = pd.DatetimeIndex(quadro["data"])
    preco = quadro["fechamento"].to_numpy(dtype=float)
    ticker = quadro["ticker"].iloc[0]
    sufixo = sufixo_do_evento(quadro["especi"]).to_numpy()
    degrau = 0.01 / quadro["fatcot"].to_numpy(dtype=float)
    nivel_ibov = ibov.reindex(datas, method="ffill").to_numpy(dtype=float)

    multiplicador = np.ones(len(preco))
    ajustes: list[Ajuste] = []
    for i in range(1, len(preco)):
        anterior, atual = preco[i - 1], preco[i]
        if not (anterior > 0 and atual > 0):
            continue
        bruto = atual / anterior
        inicio_do_sufixo = sufixo[i] != "" and sufixo[i] != sufixo[i - 1]
        marcado = inicio_do_sufixo and e_evento_em_acoes(sufixo[i])
        if not marcado and (
            abs(bruto - 1) <= LIMITE_VARIACAO_GRANDE
            or (datas[i] - datas[i - 1]).days > DIAS_MAXIMOS_SEM_SUFIXO
        ):
            continue
        mercado = nivel_ibov[i] / nivel_ibov[i - 1] if nivel_ibov[i - 1] > 0 else 1.0
        razao = bruto / (mercado if np.isfinite(mercado) else 1.0)
        # O degrau de preço de cada ponta soma erro à razão.
        tolerancia = TOLERANCIA + (degrau[i - 1] / anterior) + (degrau[i] / atual)
        if not marcado and tolerancia > TOLERANCIA_MAXIMA:
            continue
        if marcado and abs(razao - 1) < RAZAO_SEM_EVENTO:
            continue
        fator = escolher_fator(razao, marcado, tolerancia)
        variacao = (bruto - 1) * 100
        if np.isnan(fator):
            if marcado and abs(bruto - 1) > MINIMO_PARA_REGISTRO:
                ajustes.append(Ajuste(datas[i], ticker, variacao, np.nan, MOTIVO_SEM_FATOR))
            continue
        multiplicador[i] = fator
        motivo = MOTIVO_MARCADO if marcado else MOTIVO_GRANDE
        ajustes.append(Ajuste(datas[i], ticker, variacao, fator, motivo))

    # O preço antes do evento passa a valer o preço vezes o fator (a queda some).
    posteriores = np.append(np.cumprod(multiplicador[::-1])[::-1][1:], 1.0)
    ajustado = pd.Series(preco * posteriores, index=datas, name=ticker)
    return ajustado, ajustes, pd.Series(multiplicador, index=datas)
