"""COTAHIST anual da B3: baixa o zip, lê o layout posicional e grava Parquet por ano.

Porte do leitor do projeto modelagem-b3 (`modelagem/b3/cotahist.py`), que por sua vez veio do
volume-scanner. Parser, esquema e validação são os mesmos; saiu o que dependia de httpx, DuckDB
e manifesto. Escreve em blocos porque o arquivo descompactado de um ano recente passa de 700 MB
e a máquina tem 8 GB de RAM.

Registro de largura fixa de 245 bytes. As posições abaixo são 1-indexadas e inclusivas, como no
layout da B3. `V99` tem 2 casas decimais implícitas: lê-se como inteiro e divide-se por 100.

FATCOT (fator de cotação) não está na tabela do plano da B3, mas é necessário: em parte das
linhas o preço é cotado por lote de 100, 1.000 ou 1.000.000 de ações. Os preços de saída
(abertura, máxima, mínima, médio, fechamento) já saem divididos por ele.

Moeda: os arquivos de 1993 e do 1º semestre de 1994 estão em cruzeiro real (ou cruzeiros, em
1993), e o Real só começa em 01/07/1994. Os preços e volumes saem como estão no arquivo, sem
conversão; quem compara volume entre datas tem de cuidar disso (ver `liquidez.py`).

Validação `VOLTOT ~= PREMED x QUATOT`: a linha passa por qualquer de três critérios: o
intervalo exato do truncamento ([PREMED, PREMED + quantum) x QUATOT, que vale nos arquivos
recentes), desvio relativo de até 1% (a regra do plano), ou até 2 quanta por ação (papel abaixo
de R$ 1, onde o truncamento sozinho já passa de 1%). Só o truncamento exato reprovava 5% das
linhas de 2011 por desvios de 0,01-0,1% em papéis líquidos (RENT3, NATU3): os arquivos antigos
não seguem a mesma aritmética. Com os três, 2011 reprova 0,016% (dias de evento corporativo,
como MNDL4), e um parser desalinhado continua reprovando quase tudo.

Só mantemos CODBDI de ação em qualquer situação (02 lote padrão, 05 sancionada, 06
concordatária, 07 recuperação extrajudicial, 08 recuperação judicial, 09 RAET) e 14 (ETF).
Guardar só o 02 faria a empresa sumir do dado justo quando ela quebra (viés de
sobrevivência). A seleção final de ações de verdade (sem BDR, recibo, direito) fica em
`acoes.py`.

Passar do `TETO_FALHA_PRECO` aborta a conversão DAQUELE ANO; quem orquestra vários anos
(`garantir_anos`) não deixa um ano ruim derrubar o resto.

A extração é vetorizada: cada bloco lido vira uma matriz de bytes numpy e cada campo é uma
fatia de colunas. O filtro de TIPREG/TPMERC/CODBDI acontece nessa matriz, antes de montar
qualquer DataFrame.
"""

from __future__ import annotations

import contextlib
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

import numpy as np
import numpy.typing as npt
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from eleicoes import caminhos
from eleicoes.baixar import baixar

URL_BASE = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist"

RECORD_LENGTH = 245
CHUNK_REGISTROS_PADRAO = 100_000

# TOTNEG e N(05): 99999 e teto do campo, nao contagem real de negocios.
NEGOCIOS_SENTINELA = 99999

# Falhar em mais que isso da validacao de preco aborta a conversao do ano:
# sinal de que o parser esta desalinhado, nao de ruido normal do dado.
TETO_FALHA_PRECO = 0.005

TOLERANCIA_RELATIVA_PADRAO = 0.01

CODBDI_ACOES = frozenset({"02", "05", "06", "07", "08", "09"})
CODBDI_ETF = frozenset({"14"})
CODBDI_MANTIDOS = CODBDI_ACOES | CODBDI_ETF
_CODBDI_MANTIDOS_BYTES = np.array(
    [codigo.encode("ascii") for codigo in sorted(CODBDI_MANTIDOS)], dtype="S2"
)

# nome -> (posicao inicial, posicao final), 1-indexado inclusivo.
CAMPOS: dict[str, tuple[int, int]] = {
    "TIPREG": (1, 2),
    "DATA": (3, 10),
    "CODBDI": (11, 12),
    "CODNEG": (13, 24),
    "TPMERC": (25, 27),
    "NOMRES": (28, 39),
    "ESPECI": (40, 49),
    "PREABE": (57, 69),
    "PREMAX": (70, 82),
    "PREMIN": (83, 95),
    "PREMED": (96, 108),
    "PREULT": (109, 121),
    "TOTNEG": (148, 152),
    "QUATOT": (153, 170),
    "VOLTOT": (171, 188),
    "FATCOT": (211, 217),
    "CODISI": (231, 242),
    "DISMES": (243, 245),
}

COLUNAS_COTAHIST = (
    "data",
    "codbdi",
    "ticker",
    "tpmerc",
    "nomres",
    "especi",
    "isin",
    "dismes",
    "abertura",
    "maxima",
    "minima",
    "medio",
    "fechamento",
    "negocios",
    "negocios_censurado",
    "quantidade",
    "volume",
    "fatcot",
)

SCHEMA_COTAHIST = pa.schema(
    [
        ("data", pa.date32()),
        ("codbdi", pa.string()),
        ("ticker", pa.string()),
        ("tpmerc", pa.string()),
        ("nomres", pa.string()),
        ("especi", pa.string()),
        ("isin", pa.string()),
        ("dismes", pa.int32()),
        ("abertura", pa.float64()),
        ("maxima", pa.float64()),
        ("minima", pa.float64()),
        ("medio", pa.float64()),
        ("fechamento", pa.float64()),
        ("negocios", pa.int64()),
        ("negocios_censurado", pa.bool_()),
        ("quantidade", pa.int64()),
        ("volume", pa.float64()),
        ("fatcot", pa.int32()),
    ]
)


class CotahistError(Exception):
    """Falha ao ler um arquivo COTAHIST."""


class LayoutCotahistError(CotahistError):
    """O arquivo nao tem a largura de registro esperada."""


@dataclass(frozen=True)
class RelatorioAno:
    """O que a conversao de um ano encontrou."""

    ano: int
    total_registros: int
    linhas: int
    precos_checados: int
    precos_falhos: int
    negocios_censurados: int
    contagem_codbdi: dict[str, int] = field(default_factory=dict)

    @property
    def taxa_falha(self) -> float:
        """Fracao das linhas checaveis que violou a identidade de preco."""
        return self.precos_falhos / self.precos_checados if self.precos_checados else 0.0

    def resumo(self) -> str:
        return (
            f"{self.ano}: {self.total_registros:,} registros, {self.linhas:,} apos filtros, "
            f"validacao de preco {1 - self.taxa_falha:.3%} ok ({self.precos_falhos:,} falhas), "
            f"{self.negocios_censurados:,} com TOTNEG censurado"
        )


class ValidacaoPrecoError(CotahistError):
    """VOLTOT ~= PREMED x QUATOT / FATCOT falhou acima do tolerado: parser desalinhado.

    Carrega o `relatorio` (mesmo sem o parquet ter sido escrito) para quem
    orquestra varios anos poder reportar a falha sem perder os numeros.
    """

    def __init__(self, relatorio: RelatorioAno) -> None:
        self.relatorio = relatorio
        super().__init__(
            f"COTAHIST {relatorio.ano}: VOLTOT ~= PREMED x QUATOT / FATCOT falhou em "
            f"{relatorio.taxa_falha:.3%} das linhas, acima do teto de {TETO_FALHA_PRECO:.3%}. "
            "O parser esta desalinhado (ou o dado da fonte tem ruido incomum); carga abortada."
        )


def url_cotahist(ano: int) -> str:
    """URL do arquivo anual do COTAHIST, como a B3 publica."""
    return f"{URL_BASE}/COTAHIST_A{ano}.ZIP"


def _campo(matriz: npt.NDArray[np.uint8], nome: str) -> npt.NDArray[np.bytes_]:
    """Uma coluna posicional da matriz de bytes, como array de bytes."""
    inicio, fim = CAMPOS[nome]
    largura = fim - inicio + 1
    fatia: npt.NDArray[np.bytes_] = matriz[:, inicio - 1 : fim].copy().view(f"S{largura}")
    return fatia.ravel()


def _como_inteiro(coluna: npt.NDArray[np.bytes_]) -> npt.NDArray[np.int64]:
    """Campo numerico zero-preenchido (ASCII) para inteiro, sem decodificar texto."""
    return coluna.astype(np.int64)


def _como_texto(coluna: npt.NDArray[np.bytes_]) -> pd.Series:
    """Campo de texto (pode ter acento, ex. NOMRES) para Series pandas, stripado."""
    return pd.Series(coluna).str.decode("latin-1").str.strip()


def _nome_txt(zf: zipfile.ZipFile) -> str:
    """O arquivo de dados do zip: um `.TXT` (anos recentes) ou o único arquivo (anos antigos)."""
    candidatos = [n for n in zf.namelist() if n.upper().endswith(".TXT")]
    if not candidatos:
        # Os zips até ~2000 trazem `COTAHIST.A1993`, sem extensão .TXT.
        candidatos = [n for n in zf.namelist() if not n.endswith("/")]
    if len(candidatos) != 1:
        raise LayoutCotahistError(
            f"esperava exatamente um arquivo de dados no zip, achei {candidatos or 'nenhum'}"
        )
    return candidatos[0]


def _detectar_stride(cabeca: bytes) -> int:
    """Bytes por linha, incluindo a quebra: 246 com LF, 247 com CRLF."""
    quebra = cabeca.find(b"\n")
    if quebra == -1:
        raise LayoutCotahistError("nenhuma quebra de linha nos primeiros bytes do arquivo")
    stride = quebra + 1
    if stride - RECORD_LENGTH not in (1, 2):
        raise LayoutCotahistError(
            f"linha de {stride} bytes: esperado {RECORD_LENGTH} mais quebra de 1 ou 2 bytes"
        )
    return stride


def _normalizar_linhas(buffer: bytes, stride: int) -> bytes:
    """Devolve o bloco com toda linha na largura certa, recodificando de UTF-8 para latin-1.

    O COTAHIST é latin-1, mas em 2026 a linha de FROTA OCEÂNI (NOMRES) veio em UTF-8: o "Â"
    ocupa 2 bytes, a linha fica com 246 e desloca todos os campos seguintes. Recodificar essa
    linha para latin-1 a devolve à largura de 245. Qualquer outra irregularidade continua erro.
    """
    linhas = []
    for original in buffer.splitlines(keepends=True):
        linha = original
        if len(linha) != stride:
            with contextlib.suppress(UnicodeDecodeError, UnicodeEncodeError):
                linha = original.decode("utf-8").encode("latin-1")
            if len(linha) != stride:
                raise LayoutCotahistError(
                    f"linha de {len(original)} bytes: esperado {stride} (largura irregular)"
                )
        linhas.append(linha)
    return b"".join(linhas)


def _ler_bloco(handle: IO[bytes], stride: int, registros: int) -> npt.NDArray[np.uint8] | None:
    """Le um bloco e devolve a matriz (linhas x stride), ou None no fim do arquivo."""
    buffer = handle.read(stride * registros)
    if not buffer:
        return None
    if len(buffer) % stride or not buffer.endswith(b"\n"):
        # Só chega aqui com linha fora do padrão; termina a linha cortada ao meio pelo bloco.
        if not buffer.endswith(b"\n"):
            buffer += handle.readline()
        buffer = _normalizar_linhas(buffer, stride)
    return np.frombuffer(buffer, dtype=np.uint8).reshape(-1, stride)


def _montar_bloco(
    selecionado: npt.NDArray[np.uint8],
) -> tuple[pd.DataFrame, npt.NDArray[np.float64]]:
    """Linhas do bloco ja filtradas, mais o quantum de preco (0,01 / FATCOT) de cada uma."""
    negocios_bruto = _como_inteiro(_campo(selecionado, "TOTNEG"))
    censurado = negocios_bruto >= NEGOCIOS_SENTINELA
    negocios = pd.array(negocios_bruto, dtype="Int64")
    negocios[censurado] = pd.NA

    fatcot = _como_inteiro(_campo(selecionado, "FATCOT"))
    fatcot_float = fatcot.astype(np.float64)

    quadro = pd.DataFrame(
        {
            "data": pd.to_datetime(
                _como_texto(_campo(selecionado, "DATA")), format="%Y%m%d"
            ).dt.date,
            "codbdi": _como_texto(_campo(selecionado, "CODBDI")),
            "ticker": _como_texto(_campo(selecionado, "CODNEG")),
            "tpmerc": _como_texto(_campo(selecionado, "TPMERC")),
            "nomres": _como_texto(_campo(selecionado, "NOMRES")),
            "especi": _como_texto(_campo(selecionado, "ESPECI")),
            "isin": _como_texto(_campo(selecionado, "CODISI")),
            "dismes": _como_inteiro(_campo(selecionado, "DISMES")).astype("int32"),
            "abertura": _como_inteiro(_campo(selecionado, "PREABE")) / 100.0 / fatcot_float,
            "maxima": _como_inteiro(_campo(selecionado, "PREMAX")) / 100.0 / fatcot_float,
            "minima": _como_inteiro(_campo(selecionado, "PREMIN")) / 100.0 / fatcot_float,
            "medio": _como_inteiro(_campo(selecionado, "PREMED")) / 100.0 / fatcot_float,
            "fechamento": _como_inteiro(_campo(selecionado, "PREULT")) / 100.0 / fatcot_float,
            "negocios": negocios,
            "negocios_censurado": censurado,
            "quantidade": _como_inteiro(_campo(selecionado, "QUATOT")),
            "volume": _como_inteiro(_campo(selecionado, "VOLTOT")) / 100.0,
            "fatcot": fatcot.astype("int32"),
        }
    )
    quantum = 0.01 / fatcot_float
    return quadro, quantum


def validar_preco(
    quadro: pd.DataFrame,
    quantum: npt.NDArray[np.float64],
    *,
    tolerancia: float = TOLERANCIA_RELATIVA_PADRAO,
) -> tuple[int, int]:
    """(linhas checaveis, falhas) de `VOLTOT ~= PREMED x QUATOT / FATCOT` (ver modulo)."""
    volume = quadro["volume"].to_numpy(dtype=float)
    checavel = volume > 0
    if not checavel.any():
        return 0, 0

    quantidade = quadro["quantidade"].to_numpy(dtype=float)
    medio = quadro["medio"].to_numpy(dtype=float)
    piso = medio * quantidade
    teto = piso + quantum * quantidade
    # Folga so para ruido de ponto flutuante, nao de tolerancia.
    truncamento = (volume >= piso * (1 - 1e-6)) & (volume <= teto * (1 + 1e-6))
    relativo = np.abs(piso - volume) / np.where(checavel, volume, 1.0) <= tolerancia
    com_quantidade = np.where(quantidade > 0, quantidade, 1.0)
    por_acao = np.abs(volume / com_quantidade - medio) <= 2 * quantum
    ok = truncamento | relativo | por_acao

    return int(checavel.sum()), int((checavel & ~ok).sum())


def converter_ano(
    zip_path: Path,
    ano: int,
    destino: Path,
    *,
    chunk_records: int = CHUNK_REGISTROS_PADRAO,
) -> RelatorioAno:
    """Converte o COTAHIST anual (zip da B3) em Parquet, em blocos.

    Escrita atomica em `.tmp`, promovida so se a validacao de preco passar.
    Levanta `ValidacaoPrecoError` se falhar em mais de `TETO_FALHA_PRECO` das
    linhas checaveis -- sinal de parser desalinhado, carga abortada.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".tmp")

    total = 0
    mantidos = 0
    checados = 0
    falhas = 0
    censurados = 0
    contagem_codbdi: Counter[str] = Counter()

    try:
        with zipfile.ZipFile(zip_path) as zf:
            nome = _nome_txt(zf)
            with zf.open(nome) as bruto, pq.ParquetWriter(tmp, SCHEMA_COTAHIST) as writer:
                stride = _detectar_stride(bruto.read(RECORD_LENGTH + 2))
                bruto.seek(0)

                while (matriz := _ler_bloco(bruto, stride, chunk_records)) is not None:
                    tipreg_ok = _campo(matriz, "TIPREG") == b"01"
                    total += int(tipreg_ok.sum())

                    tpmerc_ok = _campo(matriz, "TPMERC") == b"010"
                    relevante = tipreg_ok & tpmerc_ok
                    codbdi_bruto = _campo(matriz, "CODBDI")
                    if relevante.any():
                        codigos, contagens = np.unique(codbdi_bruto[relevante], return_counts=True)
                        for codigo, n in zip(codigos, contagens, strict=True):
                            contagem_codbdi[codigo.decode("latin-1")] += int(n)

                    manter = relevante & np.isin(codbdi_bruto, _CODBDI_MANTIDOS_BYTES)
                    selecionado = matriz[manter]
                    if not len(selecionado):
                        continue

                    bloco, quantum = _montar_bloco(selecionado)
                    checaveis_bloco, falhas_bloco = validar_preco(bloco, quantum)
                    checados += checaveis_bloco
                    falhas += falhas_bloco
                    censurados += int(bloco["negocios_censurado"].sum())

                    tabela = pa.Table.from_pandas(
                        bloco, schema=SCHEMA_COTAHIST, preserve_index=False
                    )
                    writer.write_table(tabela)
                    mantidos += tabela.num_rows
    except Exception:
        # Arquivo ilegível ou fora do layout: não deixa o `.tmp` pela metade.
        tmp.unlink(missing_ok=True)
        raise

    relatorio = RelatorioAno(
        ano=ano,
        total_registros=total,
        linhas=mantidos,
        precos_checados=checados,
        precos_falhos=falhas,
        negocios_censurados=censurados,
        contagem_codbdi=dict(contagem_codbdi),
    )

    if relatorio.taxa_falha > TETO_FALHA_PRECO:
        tmp.unlink(missing_ok=True)
        raise ValidacaoPrecoError(relatorio)

    tmp.replace(destino)
    return relatorio


def caminho_parquet(ano: int) -> Path:
    """Onde fica o Parquet do ano, no cache."""
    return caminhos.CACHE / "b3" / f"cotahist_{ano}.parquet"


def garantir_anos(
    anos: Iterable[int],
    atualizar: bool,
    *,
    ao_converter: Callable[[RelatorioAno], None] | None = None,
) -> dict[int, RelatorioAno | ValidacaoPrecoError]:
    """Deixa o Parquet de cada ano no cache; devolve o que foi convertido agora.

    Com o Parquet no cache e `atualizar` falso, o ano não é tocado. Senão baixa o zip (o do
    ano corrente precisa de `atualizar=True`: a B3 regrava o arquivo todo dia) e converte.
    Um ano que reprova na validação entra no resultado como a própria exceção (com o
    relatório) e não impede os outros; o Parquet dele não é gravado.
    """
    resultado: dict[int, RelatorioAno | ValidacaoPrecoError] = {}
    for ano in sorted(set(anos)):
        destino = caminho_parquet(ano)
        if destino.exists() and not atualizar:
            continue
        zip_path = baixar(url_cotahist(ano), f"b3/COTAHIST_A{ano}.ZIP", atualizar)
        try:
            relatorio = converter_ano(zip_path, ano, destino)
        except ValidacaoPrecoError as erro:
            resultado[ano] = erro
            continue
        resultado[ano] = relatorio
        if ao_converter is not None:
            ao_converter(relatorio)
    return resultado
