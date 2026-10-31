import io
import itertools
import json
import urllib.error
from datetime import date

import pandas as pd

from eleicoes.fontes import bcb


def test_janela_de_30_anos_vira_blocos_de_ate_10_anos():
    pedacos = bcb.blocos(date(1993, 1, 1), date(2026, 10, 31))
    assert pedacos[0][0] == date(1993, 1, 1)
    assert pedacos[-1][1] == date(2026, 10, 31)
    for (inicio, fim), (proximo, _) in itertools.pairwise(pedacos):
        assert proximo == fim + pd.Timedelta(days=1)
        assert (fim - inicio).days < 3653
    assert all((fim - inicio).days < 3653 for inicio, fim in pedacos)
    assert len(pedacos) == 7


def test_bloco_unico_quando_cabe():
    assert bcb.blocos(date(2024, 1, 1), date(2024, 6, 30)) == [
        (date(2024, 1, 1), date(2024, 6, 30))
    ]


def test_converte_valor_e_data():
    texto = json.dumps(
        [{"data": "26/10/2026", "valor": "5.5007"}, {"data": "23/10/2026", "valor": "5.0377"}]
    )
    serie = bcb._ler_bloco(texto)
    assert serie.loc[pd.Timestamp("2026-10-26")] == 5.5007
    assert serie.loc[pd.Timestamp("2026-10-23")] == 5.0377


def test_404_sem_valores_vira_vazio(pasta_dados, monkeypatch):
    def falso(url, nome, atualizar, **kwargs):
        corpo = io.BytesIO(b'{"error":"Value(s) not found"}')
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, corpo)

    monkeypatch.setattr(bcb, "baixar", falso)
    serie = bcb.sgs(1, date(2026, 1, 1), date(2026, 2, 1), atualizar=False)
    assert serie.empty


def test_junta_blocos_e_remove_repetidos(pasta_dados, monkeypatch):
    por_inicio = {
        "01/01/2020": [{"data": "31/12/2024", "valor": "1.5"}],
        "01/01/2025": [
            {"data": "31/12/2024", "valor": "1.6"},
            {"data": "02/01/2025", "valor": "2.0"},
        ],
    }

    def falso(url, nome, atualizar, **kwargs):
        inicio = url.split("dataInicial=")[1].split("&")[0]
        caminho = pasta_dados / nome.replace("/", "_")
        caminho.write_text(json.dumps(por_inicio[inicio]), encoding="utf-8")
        return caminho

    monkeypatch.setattr(bcb, "baixar", falso)
    serie = bcb.sgs(1, date(2020, 1, 1), date(2025, 6, 30), atualizar=False)
    assert list(serie.index) == [pd.Timestamp("2024-12-31"), pd.Timestamp("2025-01-02")]
    # No dia repetido vale o valor do bloco mais novo.
    assert serie.loc[pd.Timestamp("2024-12-31")] == 1.6
