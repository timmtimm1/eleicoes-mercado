"""Linha de comando do estudo."""

import pandas as pd
import typer

from eleicoes import conferir as conferencia
from eleicoes import series

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
