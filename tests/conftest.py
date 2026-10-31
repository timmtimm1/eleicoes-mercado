import pytest

from eleicoes import baixar, caminhos


@pytest.fixture
def pasta_dados(tmp_path, monkeypatch):
    """Cache e séries numa pasta temporária, sem espera entre tentativas de rede."""
    monkeypatch.setattr(caminhos, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(caminhos, "SERIES", tmp_path / "series")
    monkeypatch.setattr(baixar, "ESPERA_ENTRE_TENTATIVAS", 0)
    return tmp_path
