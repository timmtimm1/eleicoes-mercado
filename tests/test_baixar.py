import urllib.error

import pytest

from eleicoes import baixar as modulo


class RespostaFalsa:
    def __init__(self, conteudo: bytes):
        self.conteudo = conteudo

    def read(self):
        return self.conteudo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_usa_cache_sem_atualizar(pasta_dados, monkeypatch):
    chamadas = []

    def falso(pedido, timeout):
        chamadas.append(pedido.full_url)
        return RespostaFalsa(b"abc")

    monkeypatch.setattr(modulo.urllib.request, "urlopen", falso)
    caminho = modulo.baixar("http://x/a", "pasta/a.txt", atualizar=False)
    modulo.baixar("http://x/a", "pasta/a.txt", atualizar=False)
    assert caminho.read_bytes() == b"abc"
    assert len(chamadas) == 1
    modulo.baixar("http://x/a", "pasta/a.txt", atualizar=True)
    assert len(chamadas) == 2
    assert not list(caminho.parent.glob("*.parcial"))


def test_tenta_de_novo_e_falha_com_erro_claro(pasta_dados, monkeypatch):
    chamadas = []

    def falso(pedido, timeout):
        chamadas.append(timeout)
        raise TimeoutError("sem resposta")

    monkeypatch.setattr(modulo.urllib.request, "urlopen", falso)
    with pytest.raises(modulo.FonteIndisponivelError):
        modulo.baixar("http://x/a", "a.txt", atualizar=True)
    assert len(chamadas) == modulo.TENTATIVAS
    assert not (pasta_dados / "cache" / "a.txt").exists()


def test_erro_4xx_nao_repete(pasta_dados, monkeypatch):
    chamadas = []

    def falso(pedido, timeout):
        chamadas.append(1)
        raise urllib.error.HTTPError(pedido.full_url, 404, "não achou", {}, None)

    monkeypatch.setattr(modulo.urllib.request, "urlopen", falso)
    with pytest.raises(urllib.error.HTTPError):
        modulo.baixar("http://x/a", "a.txt", atualizar=True)
    assert len(chamadas) == 1
