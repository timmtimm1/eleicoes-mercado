"""Linha de comando do estudo."""

from datetime import date

import pandas as pd
import typer

from eleicoes import acoes, calendario, caminhos, series, surpresa
from eleicoes import carteiras as carteiras_estudo
from eleicoes import conferir as conferencia
from eleicoes import conferir_acoes as conferir_acoes_estudo
from eleicoes import empresas as empresas_csv
from eleicoes import janelas as estudo
from eleicoes import liquidez as liquidez_estudo
from eleicoes.fontes import cotahist

PRIMEIRO_ANO_COTAHIST = 1993

app = typer.Typer(
    help="Bolsa, dólar e juros diante das eleições presidenciais de 1994 a 2026.",
    no_args_is_help=True,
)


@app.command()
def extrair(
    atualizar: bool = typer.Option(False, help="Baixa tudo de novo, ignorando o cache."),
) -> None:
    """Baixa as séries de mercado e grava em dados/series/."""
    catalogo = series.extrair(atualizar)
    typer.echo(catalogo[["nome", "inicio", "fim", "linhas"]].to_string(index=False))


@app.command()
def conferir() -> None:
    """Compara os dados com números da imprensa; sai com código 1 se algum não bater."""
    tabela = conferencia.conferir()
    exibicao = tabela.assign(ok=tabela["ok"].map({True: "✓", False: "✗"}))
    with pd.option_context("display.width", 250, "display.max_colwidth", 70):
        typer.echo(exibicao.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
        typer.echo("")
        typer.echo("Ibovespa: Yahoo × Ipeadata (1º de julho do ano a 31/12 do ano seguinte)")
        comparacao = conferencia.comparar_ibov()
        typer.echo(comparacao.to_string(index=False, float_format=lambda v: f"{v:.6f}"))
    if not tabela["ok"].all():
        raise typer.Exit(code=1)


def _quadro(tabela: pd.DataFrame, medida: str, coluna: str, titulo: str) -> None:
    """Linhas = ano, colunas = janelas, valores com 1 casa; `-` onde não há valor."""
    do_medida = tabela[tabela["medida"] == medida]
    larga = do_medida.pivot(index="ano", columns="janela", values=coluna)
    larga = larga.reindex(columns=[j for j in estudo.JANELAS if j in larga.columns])
    typer.echo(titulo)
    typer.echo(larga.to_string(float_format=lambda v: f"{v:.1f}", na_rep="-"))
    typer.echo("")


@app.command()
def janelas() -> None:
    """Calcula as janelas e a surpresa, grava em dados/resultados/ e mostra os quadros."""
    tabela = estudo.calcular_janelas()
    estudo.gravar_janelas(tabela)
    tabela_surpresa = surpresa.calcular_surpresa(tabela)
    surpresa.gravar_surpresa(tabela_surpresa)
    _quadro(tabela, "ibov", "variacao", "Ibovespa: variação bruta (%)")
    _quadro(tabela, "ibov_usd", "variacao", "Ibovespa em dólar: variação bruta (%)")
    _quadro(tabela, "ibov_usd", "so_brasil", "Ibovespa em dólar: só Brasil (%)")
    _quadro(tabela, "dolar", "variacao", "Dólar: variação bruta (%)")
    _quadro(tabela, "dolar", "so_brasil", "Dólar: só Brasil (%, positivo = real mais fraco)")
    _quadro(tabela, "prefixado_10a", "variacao", "Tesouro prefixado ~10 anos: variação (p.p.)")
    _quadro(tabela, "embi", "variacao", "Risco-país EMBI+: variação (pontos-base)")
    typer.echo("Surpresa (pontos, a favor do candidato do mercado) e reação no D+1 (%)")
    colunas = [
        "ano",
        "turno",
        "candidato_mercado",
        "margem_pesquisas",
        "margem_resultado",
        "surpresa",
        "favorito_pesquisas",
        "mercado_ganhou_turno",
        "ibov_d1",
        "ibov_usd_so_brasil_d1",
        "dolar_d1",
        "prefixado_10a_d1",
    ]
    with pd.option_context("display.width", 250):
        typer.echo(
            tabela_surpresa[colunas].to_string(
                index=False, float_format=lambda v: f"{v:.2f}", na_rep="-"
            )
        )
        typer.echo("")
        typer.echo("Correlação entre a surpresa e o Ibovespa no D+1")
        correlacoes = surpresa.correlacao_surpresa(tabela_surpresa)
        typer.echo(
            correlacoes.to_string(index=False, float_format=lambda v: f"{v:.2f}", na_rep="-")
        )


@app.command()
def liquidez(
    atualizar: bool = typer.Option(False, help="Baixa o COTAHIST de todos os anos de novo."),
) -> None:
    """Lista as 60 ações mais negociadas antes de cada eleição e grava em dados/resultados/."""
    hoje = date.today()
    anos = range(PRIMEIRO_ANO_COTAHIST, hoje.year + 1)
    # A B3 regrava o arquivo do ano corrente todo dia: ele é sempre baixado de novo.
    convertidos = cotahist.garantir_anos(
        [ano for ano in anos if ano != hoje.year],
        atualizar,
        ao_converter=lambda r: typer.echo(r.resumo()),
    )
    convertidos |= cotahist.garantir_anos(
        [hoje.year], True, ao_converter=lambda r: typer.echo(r.resumo())
    )
    reprovados = {a: e for a, e in convertidos.items() if isinstance(e, cotahist.CotahistError)}
    for ano, erro in reprovados.items():
        typer.echo(f"ERRO {ano}: {erro}", err=True)
    if reprovados:
        raise typer.Exit(code=1)

    eleicoes = calendario.carregar_eleicoes()
    tabela = liquidez_estudo.calcular_liquidez(
        eleicoes,
        calendario.pregoes(),
        empresas=empresas_csv.carregar_empresas(),
        sucessoes=empresas_csv.carregar_sucessoes(),
        exclusoes=empresas_csv.carregar_exclusoes(),
    )
    caminho = liquidez_estudo.gravar_liquidez(tabela)
    for eleicao in eleicoes:
        do_ano = tabela[tabela["ano"] == eleicao.ano]
        inicio, fim = liquidez_estudo.periodo(eleicao, calendario.pregoes())
        typer.echo("")
        typer.echo(
            f"{eleicao.ano}: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}, "
            f"{do_ano['pregoes_no_periodo'].iloc[0]} pregões"
        )
        for linha in do_ano.itertuples(index=False):
            marcas = []
            if ";" in linha.raizes_somadas:
                marcas.append(f"soma {linha.raizes_somadas}")
            if linha.setor == empresas_csv.SETOR_SEM_CLASSIFICACAO:
                marcas.append("SEM CLASSIFICAÇÃO")
            if linha.excluida:
                marcas.append("excluída")
            sufixo = f"  [{'; '.join(marcas)}]" if marcas else ""
            typer.echo(
                f"{linha.posicao:>3}  {linha.raiz:<5} {linha.ticker:<8} {linha.nomres}{sufixo}"
            )
    typer.echo("")
    typer.echo(f"Gravado em {caminho}")


def _mercado_das_carteiras(tabela_liquidez: pd.DataFrame, sucessoes):
    """Preços ajustados de todos os papéis das raízes das listas (e das sucessoras)."""
    raizes = set(";".join(tabela_liquidez["raizes_somadas"]).split(";"))
    for s in sucessoes:
        if s.raiz_antiga in raizes or s.raiz_nova in raizes:
            raizes |= {s.raiz_antiga, s.raiz_nova}
    precos = acoes.ler_precos(carteiras_estudo.PRIMEIRO_DIA_DO_REAL, date.today())
    return carteiras_estudo.montar_mercado(precos[precos["raiz"].isin(raizes)], series.ler("ibov"))


@app.command()
def carteiras() -> None:
    """Calcula as carteiras de estatais, privadas e setores por janela e grava os CSVs."""
    caminho = caminhos.RESULTADOS / "liquidez.csv"
    if not caminho.exists():
        typer.echo("Falta dados/resultados/liquidez.csv: rode `eleicoes liquidez` antes.", err=True)
        raise typer.Exit(code=1)
    tabela_liquidez = pd.read_csv(caminho)
    sucessoes = empresas_csv.carregar_sucessoes()
    eleicoes = calendario.carregar_eleicoes()
    pregoes = calendario.pregoes()
    mercado = _mercado_das_carteiras(tabela_liquidez, sucessoes)
    resultado = carteiras_estudo.calcular_carteiras(
        eleicoes, tabela_liquidez, mercado, sucessoes, pregoes
    )
    gravados = carteiras_estudo.gravar(*resultado)
    tabela, _, ajustes, emendas = resultado

    diferenca = tabela[tabela["carteira"] == "estatais_menos_privadas"]
    larga = diferenca.pivot(index="ano", columns="janela", values="variacao")
    larga = larga.reindex(columns=[j for j in estudo.JANELAS if j in larga.columns])
    typer.echo("Estatais menos privadas (pontos percentuais de variação, peso igual)")
    typer.echo(larga.to_string(float_format=lambda v: f"{v:.1f}", na_rep="-"))
    for titulo, escolher in (
        ("D+1 do turno decisivo", lambda e: f"t{e.turno_decisivo.numero}_d1"),
        ("1 ano depois da posse", lambda e: "posse_1ano"),
    ):
        typer.echo("")
        typer.echo(f"Variação de cada carteira (%): {titulo}")
        linhas = []
        for eleicao in eleicoes:
            do_ano = tabela[
                (tabela["ano"] == eleicao.ano) & (tabela["janela"] == escolher(eleicao))
            ]
            do_ano = do_ano[do_ano["carteira"] != "estatais_menos_privadas"]
            linhas.append(do_ano.set_index("carteira")["variacao"].rename(eleicao.ano))
        quadro = pd.DataFrame(linhas)
        with pd.option_context("display.width", 250):
            typer.echo(quadro.to_string(float_format=lambda v: f"{v:.1f}", na_rep="-"))
    typer.echo("")
    por_motivo = ajustes["motivo"].value_counts().to_dict()
    typer.echo(f"Ajustes de eventos em ações: {por_motivo}; emendas de ticker: {len(emendas)}")
    typer.echo("Gravado: " + ", ".join(str(c) for c in gravados))


@app.command("conferir-acoes")
def conferir_acoes(
    atualizar: bool = typer.Option(False, help="Baixa os preços do Yahoo de novo."),
) -> None:
    """Compara a variação de cada empresa e janela com a do Yahoo (só para conferir)."""
    caminho = caminhos.RESULTADOS / "carteiras_empresas.csv"
    if not caminho.exists():
        typer.echo("Falta carteiras_empresas.csv: rode `eleicoes carteiras` antes.", err=True)
        raise typer.Exit(code=1)
    empresas = pd.read_csv(caminho)
    tabela, ausentes = conferir_acoes_estudo.conferir(
        calendario.carregar_eleicoes(), empresas, calendario.pregoes(), atualizar
    )
    conferir_acoes_estudo.gravar(tabela)
    diferentes = tabela[tabela["diferenca"].abs() > conferir_acoes_estudo.LIMITE_DIFERENCA]
    typer.echo(f"{len(tabela)} pares (empresa, janela) comparados")
    typer.echo(f"{len(diferentes)} diferem mais de 2 pontos")
    typer.echo(f"Sem dado no Yahoo ({len(ausentes)}): {' '.join(ausentes)}")
    piores = tabela.loc[tabela["diferenca"].abs().sort_values(ascending=False).index].head(15)
    colunas = ["ano", "janela", "ticker", "variacao", "variacao_yahoo", "diferenca", "ajustes"]
    with pd.option_context("display.width", 250, "display.max_colwidth", 60):
        typer.echo(piores[colunas].to_string(index=False, float_format=lambda v: f"{v:.1f}"))
