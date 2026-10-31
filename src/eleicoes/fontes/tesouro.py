"""Taxas do Tesouro Direto (Tesouro Transparente), desde 31/12/2004."""

import pandas as pd

from eleicoes.baixar import baixar

URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3"
    "/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv"
)
NTN_F = "Tesouro Prefixado com Juros Semestrais"
LTN = "Tesouro Prefixado"
DIAS_POR_ANO = 365.25


def _tabela(atualizar: bool) -> pd.DataFrame:
    caminho = baixar(URL, "tesouro/PrecoTaxaTesouroDireto.csv", atualizar)
    return ler(caminho)


def ler(caminho) -> pd.DataFrame:
    """Lê o CSV do Tesouro: data, título, vencimento e a taxa de compra da manhã."""
    bruto = pd.read_csv(caminho, sep=";", decimal=",", encoding="utf-8-sig")
    tabela = pd.DataFrame(
        {
            "titulo": bruto["Tipo Titulo"],
            "data": pd.to_datetime(bruto["Data Base"], format="%d/%m/%Y"),
            "vencimento": pd.to_datetime(bruto["Data Vencimento"], format="%d/%m/%Y"),
            "taxa": pd.to_numeric(bruto["Taxa Compra Manha"], errors="coerce"),
        }
    )
    return tabela.dropna(subset=["taxa"])


def mais_proximo_de(tabela: pd.DataFrame, titulo: str, anos: float) -> pd.DataFrame:
    """Em cada dia, o vencimento do título com prazo mais perto de `anos`.

    Devolve `taxa` (% ao ano) e `prazo_anos`, indexados pela data. Em empate, fica o
    vencimento mais curto.
    """
    do_titulo = tabela[tabela["titulo"] == titulo].copy()
    do_titulo["prazo_anos"] = (do_titulo["vencimento"] - do_titulo["data"]).dt.days / DIAS_POR_ANO
    do_titulo = do_titulo[do_titulo["prazo_anos"] > 0]
    do_titulo["distancia"] = (do_titulo["prazo_anos"] - anos).abs()
    do_titulo = do_titulo.sort_values(["data", "distancia", "vencimento"])
    escolhido = do_titulo.drop_duplicates("data", keep="first").set_index("data").sort_index()
    return escolhido[["taxa", "prazo_anos"]].astype("float64")


def prefixado_10a(atualizar: bool) -> pd.DataFrame:
    """NTN-F (Prefixado com Juros Semestrais) com vencimento mais perto de 10 anos."""
    return mais_proximo_de(_tabela(atualizar), NTN_F, 10)


def prefixado_1a(atualizar: bool) -> pd.DataFrame:
    """LTN (Prefixado) com vencimento mais perto de 1 ano."""
    return mais_proximo_de(_tabela(atualizar), LTN, 1)
