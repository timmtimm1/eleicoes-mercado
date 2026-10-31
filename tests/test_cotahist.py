"""Leitor do COTAHIST: registros sintéticos de 245 bytes, sem rede."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from eleicoes.fontes import cotahist

_CAMPOS_NUMERICOS = frozenset(
    {
        "PREABE",
        "PREMAX",
        "PREMIN",
        "PREMED",
        "PREULT",
        "TOTNEG",
        "QUATOT",
        "VOLTOT",
        "FATCOT",
        "DISMES",
    }
)

# PREMED=10,20 x QUATOT=1.000.000 / FATCOT=1 = 10.200.000,00 reais = VOLTOT.
_PADRAO: dict[str, int | str] = {
    "TIPREG": "01",
    "DATA": "20250115",
    "CODBDI": "02",
    "CODNEG": "TEST3",
    "TPMERC": "010",
    "NOMRES": "TESTE SA",
    "ESPECI": "ON NM",
    "PREABE": 1000,
    "PREMAX": 1050,
    "PREMIN": 980,
    "PREMED": 1020,
    "PREULT": 1030,
    "TOTNEG": 100,
    "QUATOT": 1_000_000,
    "VOLTOT": 1_020_000_000,
    "FATCOT": 1,
    "CODISI": "BRTESTACNOR0",
    "DISMES": 100,
}


def _registro(**valores: int | str) -> bytes:
    """Um registro de 245 bytes do COTAHIST; campos default ja fecham a identidade de preco."""
    campos: dict[str, int | str] = {**_PADRAO, **valores}
    linha = bytearray(b" " * cotahist.RECORD_LENGTH)
    for nome, (inicio, fim) in cotahist.CAMPOS.items():
        largura = fim - inicio + 1
        valor = campos.get(nome, "")
        texto = (
            str(int(valor)).rjust(largura, "0")
            if nome in _CAMPOS_NUMERICOS
            else str(valor).ljust(largura)
        )
        linha[inicio - 1 : fim] = texto[:largura].encode("latin-1")
    return bytes(linha) + b"\n"


def _zip_cotahist(caminho: Path, ano: int, registros: list[bytes]) -> Path:
    with zipfile.ZipFile(caminho, "w") as zf:
        zf.writestr(f"COTAHIST_A{ano}.TXT", b"".join(registros))
    return caminho


def test_converter_ano_campos_basicos(tmp_path: Path) -> None:
    zip_path = _zip_cotahist(tmp_path / "cot.zip", 2025, [_registro()])
    destino = tmp_path / "cotahist_2025.parquet"
    relatorio = cotahist.converter_ano(zip_path, 2025, destino)

    assert relatorio.linhas == 1
    assert relatorio.precos_falhos == 0
    df = pd.read_parquet(destino)
    assert len(df) == 1
    linha = df.iloc[0]
    assert linha["ticker"] == "TEST3"
    assert linha["codbdi"] == "02"
    assert linha["nomres"] == "TESTE SA"
    assert linha["especi"] == "ON NM"
    assert linha["isin"] == "BRTESTACNOR0"
    assert linha["dismes"] == 100
    assert linha["abertura"] == pytest.approx(10.00)
    assert linha["maxima"] == pytest.approx(10.50)
    assert linha["minima"] == pytest.approx(9.80)
    assert linha["medio"] == pytest.approx(10.20)
    assert linha["fechamento"] == pytest.approx(10.30)
    assert linha["negocios"] == 100
    assert not linha["negocios_censurado"]
    assert linha["quantidade"] == 1_000_000
    assert linha["volume"] == pytest.approx(10_200_000.00)
    assert linha["fatcot"] == 1


def test_converter_ano_fatcot_divide_precos(tmp_path: Path) -> None:
    """FATCOT 1000: preco cotado por lote de 1000 acoes, saida ja em preco por acao."""
    registro = _registro(FATCOT=1000, QUATOT=100_000_000, VOLTOT=102_000_000)
    zip_path = _zip_cotahist(tmp_path / "cot.zip", 2025, [registro])
    destino = tmp_path / "cotahist_2025.parquet"
    relatorio = cotahist.converter_ano(zip_path, 2025, destino)
    assert relatorio.precos_falhos == 0

    df = pd.read_parquet(destino)
    linha = df.iloc[0]
    assert linha["fatcot"] == 1000
    assert linha["medio"] == pytest.approx(1020 / 100 / 1000)
    assert linha["fechamento"] == pytest.approx(1030 / 100 / 1000)
    assert linha["abertura"] == pytest.approx(1000 / 100 / 1000)


def test_converter_ano_totneg_censurado(tmp_path: Path) -> None:
    registro = _registro(TOTNEG=99999)
    zip_path = _zip_cotahist(tmp_path / "cot.zip", 2025, [registro])
    destino = tmp_path / "cotahist_2025.parquet"
    cotahist.converter_ano(zip_path, 2025, destino)

    df = pd.read_parquet(destino)
    linha = df.iloc[0]
    assert bool(linha["negocios_censurado"]) is True
    assert pd.isna(linha["negocios"])


def test_converter_ano_filtra_tipreg_tpmerc_codbdi(tmp_path: Path) -> None:
    registros = [
        _registro(CODNEG="MANT02", CODBDI="02"),  # mantido: acao, lote padrao
        _registro(CODNEG="MANT14", CODBDI="14"),  # mantido: ETF
        _registro(CODNEG="FORA10", CODBDI="10"),  # fora: direitos
        _registro(CODNEG="FORATM", TPMERC="020"),  # fora: nao e mercado a vista
        _registro(CODNEG="FORATR", TIPREG="02"),  # fora: nao e registro de negociacao
    ]
    zip_path = _zip_cotahist(tmp_path / "cot.zip", 2025, registros)
    destino = tmp_path / "cotahist_2025.parquet"
    relatorio = cotahist.converter_ano(zip_path, 2025, destino)

    df = pd.read_parquet(destino)
    assert sorted(df["ticker"]) == ["MANT02", "MANT14"]
    # total_registros conta so TIPREG=='01' -- 4 das 5 linhas (FORATR fica de fora).
    assert relatorio.total_registros == 4
    # contagem_codbdi so olha TIPREG=01 & TPMERC=010 -- FORATM (TPMERC 020) fica de fora dela.
    assert relatorio.contagem_codbdi == {"02": 1, "14": 1, "10": 1}


def test_converter_ano_isin_e_dismes_distintos_por_papel(tmp_path: Path) -> None:
    registros = [
        _registro(CODNEG="AAAA3", CODISI="BRAAAACNOR9", DISMES=8),
        _registro(CODNEG="BBBB4", CODISI="BRBBBBCNPR3", DISMES=234),
    ]
    zip_path = _zip_cotahist(tmp_path / "cot.zip", 2025, registros)
    destino = tmp_path / "cotahist_2025.parquet"
    cotahist.converter_ano(zip_path, 2025, destino)

    df = pd.read_parquet(destino).set_index("ticker")
    assert df.loc["AAAA3", "isin"] == "BRAAAACNOR9"
    assert df.loc["AAAA3", "dismes"] == 8
    assert df.loc["BBBB4", "isin"] == "BRBBBBCNPR3"
    assert df.loc["BBBB4", "dismes"] == 234


def test_converter_ano_valida_preco_e_aborta(tmp_path: Path) -> None:
    """VOLTOT bem diferente de PREMED x QUATOT em mais de 0,5% das linhas checaveis: aborta."""
    registros = [_registro(CODNEG=f"BAD{i:03d}", VOLTOT=1) for i in range(3)]
    registros.append(_registro(CODNEG="OK001"))
    zip_path = _zip_cotahist(tmp_path / "cot.zip", 2025, registros)
    destino = tmp_path / "cotahist_2025.parquet"

    with pytest.raises(cotahist.ValidacaoPrecoError) as excinfo:
        cotahist.converter_ano(zip_path, 2025, destino)
    assert not destino.exists()
    assert not destino.with_suffix(".parquet.tmp").exists()
    # O relatorio vem junto na excecao -- quem orquestra varios anos usa isso
    # para reportar a falha sem perder os numeros daquele ano.
    assert excinfo.value.relatorio.taxa_falha == pytest.approx(3 / 4)


def test_validar_preco_aceita_desvio_pequeno_dos_arquivos_antigos() -> None:
    # RENT3 em 03/01/2011: VOLTOT 0,04% acima de PREMED x QUATOT -- fora do
    # intervalo exato do truncamento, mas nao e desalinhamento.
    quadro = pd.DataFrame(
        {"volume": [32_812_080.00], "quantidade": [1_221_100.0], "medio": [26.86]}
    )
    checaveis, falhas = cotahist.validar_preco(quadro, np.array([0.01]))
    assert (checaveis, falhas) == (1, 0)


def test_validar_preco_aceita_papel_de_centavos() -> None:
    quadro = pd.DataFrame({"volume": [1_050.00], "quantidade": [100_000.0], "medio": [0.01]})
    checaveis, falhas = cotahist.validar_preco(quadro, np.array([0.01]))
    assert (checaveis, falhas) == (1, 0)


def test_validar_preco_modo_truncamento_aceita_no_intervalo() -> None:
    quadro = pd.DataFrame(
        {"volume": [10_200_000.00], "quantidade": [1_000_000.0], "medio": [10.20]}
    )
    quantum = np.array([0.01])
    checaveis, falhas = cotahist.validar_preco(quadro, quantum)
    assert (checaveis, falhas) == (1, 0)


def test_validar_preco_modo_truncamento_recusa_fora_do_intervalo() -> None:
    quadro = pd.DataFrame({"volume": [1.0], "quantidade": [1_000_000.0], "medio": [10.20]})
    quantum = np.array([0.01])
    checaveis, falhas = cotahist.validar_preco(quadro, quantum)
    assert (checaveis, falhas) == (1, 1)


def test_zip_antigo_sem_extensao_txt(tmp_path: Path) -> None:
    """Os zips até ~2000 trazem `COTAHIST.A1993`, sem .TXT."""
    zip_path = tmp_path / "cot.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("COTAHIST.A1993", _registro(DATA="19930104", CODNEG="PET 4"))
    destino = tmp_path / "cotahist_1993.parquet"
    relatorio = cotahist.converter_ano(zip_path, 1993, destino)
    assert relatorio.linhas == 1
    assert pd.read_parquet(destino).iloc[0]["ticker"] == "PET 4"


def test_linha_em_utf_8_volta_a_largura_certa(tmp_path: Path) -> None:
    """Em 2026 a linha de FROTA OCEÂNI veio em UTF-8 (246 bytes) e deslocava os campos."""
    normal = _registro(CODNEG="AAAA3")
    em_utf8 = _registro(CODNEG="FROT3", NOMRES="FROTA OCEÂNI")
    em_utf8 = em_utf8.decode("latin-1").encode("utf-8")  # o Â passa a ocupar 2 bytes
    assert len(em_utf8) == len(normal) + 1
    depois = _registro(CODNEG="BBBB4", PREMED=2000, VOLTOT=2_000_000_000)
    zip_path = _zip_cotahist(tmp_path / "cot.zip", 2026, [normal, em_utf8, depois])
    destino = tmp_path / "cotahist_2026.parquet"

    # Bloco de 2 registros: a linha irregular fica no meio e o bloco seguinte começa certo.
    relatorio = cotahist.converter_ano(zip_path, 2026, destino, chunk_records=2)

    df = pd.read_parquet(destino).set_index("ticker")
    assert relatorio.precos_falhos == 0
    assert list(df.index) == ["AAAA3", "FROT3", "BBBB4"]
    assert df.loc["FROT3", "nomres"] == "FROTA OCEÂNI"
    assert df.loc["FROT3", "medio"] == pytest.approx(10.20)
    assert df.loc["BBBB4", "medio"] == pytest.approx(20.00)


def test_linha_de_largura_errada_que_nao_e_utf_8_continua_erro(tmp_path: Path) -> None:
    quebrada = _registro()[:-5] + b"\n"
    zip_path = _zip_cotahist(tmp_path / "cot.zip", 2025, [_registro(), quebrada, _registro()])
    destino = tmp_path / "cotahist_2025.parquet"
    with pytest.raises(cotahist.LayoutCotahistError):
        cotahist.converter_ano(zip_path, 2025, destino)
    assert not destino.with_suffix(".parquet.tmp").exists()


def test_garantir_anos_pula_o_que_esta_no_cache(pasta_dados: Path, monkeypatch) -> None:
    pedidos: list[str] = []

    def falso_baixar(url: str, nome: str, atualizar: bool) -> Path:
        pedidos.append(nome)
        return _zip_cotahist(pasta_dados / "falso.zip", int(nome[-8:-4]), [_registro()])

    monkeypatch.setattr(cotahist, "baixar", falso_baixar)
    primeira = cotahist.garantir_anos([2024, 2025], atualizar=False)
    assert sorted(primeira) == [2024, 2025]
    assert pedidos == ["b3/COTAHIST_A2024.ZIP", "b3/COTAHIST_A2025.ZIP"]
    assert cotahist.caminho_parquet(2025).exists()

    pedidos.clear()
    assert cotahist.garantir_anos([2024, 2025], atualizar=False) == {}
    assert pedidos == []
    # Com atualizar, baixa e converte de novo.
    assert sorted(cotahist.garantir_anos([2025], atualizar=True)) == [2025]
    assert pedidos == ["b3/COTAHIST_A2025.ZIP"]


def test_garantir_anos_ano_reprovado_nao_derruba_os_outros(pasta_dados: Path, monkeypatch) -> None:
    def falso_baixar(url: str, nome: str, atualizar: bool) -> Path:
        ano = int(nome[-8:-4])
        registros = [_registro(VOLTOT=1)] if ano == 2024 else [_registro()]
        return _zip_cotahist(pasta_dados / "falso.zip", ano, registros)

    monkeypatch.setattr(cotahist, "baixar", falso_baixar)
    resultado = cotahist.garantir_anos([2024, 2025], atualizar=False)
    assert isinstance(resultado[2024], cotahist.ValidacaoPrecoError)
    assert isinstance(resultado[2025], cotahist.RelatorioAno)
    assert not cotahist.caminho_parquet(2024).exists()
    assert cotahist.caminho_parquet(2025).exists()
