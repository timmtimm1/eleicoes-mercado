"""Pastas do projeto."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "dados"
CACHE = DADOS / "cache"
SERIES = DADOS / "series"
RESULTADOS = DADOS / "resultados"
SITE = RAIZ / "site"
SAIDA = RAIZ / "saida"
PREMISSAS = RAIZ / "premissas"
