import json

import pandas as pd

from eleicoes.fontes import ipeadata, msci


def test_ipeadata_corta_o_fuso_e_descarta_nulo():
    texto = json.dumps(
        {
            "value": [
                {"VALDATA": "1994-04-29T00:00:00-03:00", "VALVALOR": 1120.0},
                {"VALDATA": "1994-04-28T00:00:00-03:00", "VALVALOR": None},
                {"VALDATA": "1994-05-02T00:00:00-03:00", "VALVALOR": 1150.5},
            ]
        }
    )
    serie = ipeadata.ler(texto, "teste")
    assert list(serie.index) == [pd.Timestamp("1994-04-29"), pd.Timestamp("1994-05-02")]
    assert list(serie) == [1120.0, 1150.5]
    assert serie.name == "teste"


def test_msci_converte_data_aaaammdd():
    texto = json.dumps(
        {
            "indexes": {
                "INDEX_LEVELS": [
                    {"level_eod": 241.69, "calc_date": 19980902},
                    {"level_eod": 240.0, "calc_date": 19980901},
                ]
            }
        }
    )
    serie = msci.ler(texto)
    assert list(serie.index) == [pd.Timestamp("1998-09-01"), pd.Timestamp("1998-09-02")]
    assert serie.iloc[1] == 241.69
    assert serie.name == "msci_em"
