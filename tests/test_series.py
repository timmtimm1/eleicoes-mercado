import pandas as pd

from eleicoes import series


def test_formatar_numero_sem_zeros_a_direita():
    assert series.formatar_numero(5.5007) == "5.5007"
    assert series.formatar_numero(206911.89) == "206911.89"
    assert series.formatar_numero(12.0) == "12"
    assert series.formatar_numero(24.29999923706055) == "24.299999"
    assert series.formatar_numero(-0.0000001) == "0"


def test_gravar_formato_do_csv(pasta_dados):
    serie = pd.Series(
        [1.25, 2.0, 3.1234567],
        index=pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"]),
    )
    series.gravar(serie, "teste")
    texto = (pasta_dados / "series" / "teste.csv").read_text()
    assert texto == "data,valor\n2020-01-02,1.25\n2020-01-03,2\n2020-01-06,3.123457\n"
    assert series.ler("teste").iloc[2] == 3.123457


def test_extrair_grava_series_e_catalogo(pasta_dados, monkeypatch):
    indice = pd.to_datetime(["1992-12-31", "1993-01-04", "1993-01-05"])

    def definicao(nome):
        return series.Definicao(
            nome,
            f"série {nome}",
            "pontos",
            "Falsa",
            "X",
            "http://x",
            lambda atualizar: pd.Series([1.0, 2.0, 3.0], index=indice),
        )

    monkeypatch.setattr(series, "definicoes", lambda: [definicao("b"), definicao("a")])
    catalogo = series.extrair(atualizar=False)

    assert list(catalogo.columns) == series.COLUNAS_CATALOGO
    # Mantém a ordem das definições e corta antes de 1993.
    assert list(catalogo["nome"]) == ["b", "a"]
    assert list(catalogo["inicio"]) == ["1993-01-04", "1993-01-04"]
    assert list(catalogo["fim"]) == ["1993-01-05", "1993-01-05"]
    assert list(catalogo["linhas"]) == [2, 2]
    assert (
        pasta_dados / "series" / "a.csv"
    ).read_text() == "data,valor\n1993-01-04,2\n1993-01-05,3\n"
    cabecalho = (pasta_dados / "series" / "catalogo.csv").read_text().splitlines()[0]
    assert cabecalho == "nome,descricao,unidade,fonte,codigo,url,inicio,fim,linhas"


def test_definicoes_tem_as_14_series():
    nomes = [d.nome for d in series.definicoes()]
    assert len(nomes) == 14 and len(set(nomes)) == 14
    assert {"ibov", "ibov_ipea", "dolar", "prefixado_10a_prazo", "ust10"} <= set(nomes)


def test_dolar_antes_do_real_vira_reais():
    datas = pd.to_datetime(["1994-06-29", "1994-06-30", "1994-07-01", "1994-07-04"])
    cruzeiros = pd.Series([2698.46, 2750.0, 1.0, 0.94], index=datas)
    convertida = series.em_reais(cruzeiros)
    assert convertida.round(4).tolist() == [0.9813, 1.0, 1.0, 0.94]
