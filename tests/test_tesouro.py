import pandas as pd

from eleicoes.fontes import tesouro

CABECALHO = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha\n"
)


def _csv(tmp_path, linhas):
    caminho = tmp_path / "tesouro.csv"
    caminho.write_text(CABECALHO + "\n".join(linhas) + "\n", encoding="utf-8")
    return caminho


def test_escolhe_vencimento_mais_perto_de_10_anos_e_de_1_ano(tmp_path):
    ntnf = "Tesouro Prefixado com Juros Semestrais"
    ltn = "Tesouro Prefixado"
    caminho = _csv(
        tmp_path,
        [
            # NTN-F: vencimentos de 3, 9 e 12 anos em 02/01/2006. O de 9 anos é o mais perto de 10.
            f"{ntnf};01/01/2009;02/01/2006;16,00;16,10;1000",
            f"{ntnf};01/01/2015;02/01/2006;14,50;14,60;1000",
            f"{ntnf};01/01/2018;02/01/2006;14,00;14,10;1000",
            # No dia seguinte só sobra o de 3 anos e o de 12.
            f"{ntnf};01/01/2009;03/01/2006;16,05;16,15;1000",
            f"{ntnf};01/01/2018;03/01/2006;13,90;14,00;1000",
            # LTN: 0,5 ano e 1,3 ano. O de 1,3 está mais perto de 1 (0,3 contra 0,5).
            f"{ltn};01/07/2006;02/01/2006;17,00;17,10;900",
            f"{ltn};01/05/2007;02/01/2006;15,00;15,10;900",
            f"{ltn};01/05/2007;03/01/2006;15,20;15,30;900",
        ],
    )
    tabela = tesouro.ler(caminho)

    dez = tesouro.mais_proximo_de(tabela, tesouro.NTN_F, 10)
    assert list(dez.columns) == ["taxa", "prazo_anos"]
    assert dez.loc["2006-01-02", "taxa"] == 14.50
    assert dez.loc["2006-01-03", "taxa"] == 13.90
    # De 02/01/2006 a 01/01/2015 são 3286 dias.
    assert dez.loc["2006-01-02", "prazo_anos"] == 3286 / 365.25

    um = tesouro.mais_proximo_de(tabela, tesouro.LTN, 1)
    assert um.loc["2006-01-02", "taxa"] == 15.00
    assert um.loc["2006-01-03", "taxa"] == 15.20
    assert um.index.equals(pd.DatetimeIndex(["2006-01-02", "2006-01-03"], name="data"))


def test_ignora_titulo_vencido_e_taxa_vazia(tmp_path):
    ltn = "Tesouro Prefixado"
    caminho = _csv(
        tmp_path,
        [
            f"{ltn};01/01/2006;02/01/2006;18,00;18,10;900",
            f"{ltn};01/01/2007;02/01/2006;;;900",
            f"{ltn};01/07/2007;02/01/2006;15,00;15,10;900",
        ],
    )
    tabela = tesouro.ler(caminho)
    um = tesouro.mais_proximo_de(tabela, tesouro.LTN, 1)
    assert um.loc["2006-01-02", "taxa"] == 15.00
