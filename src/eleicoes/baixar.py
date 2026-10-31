"""Download com cache em disco."""

import time
import urllib.error
import urllib.request
from pathlib import Path

from eleicoes import caminhos

TENTATIVAS = 3
ESPERA_ENTRE_TENTATIVAS = 5  # segundos
# Um único limite para conectar e ler: a rede daqui às vezes tem IPv6 quebrado e
# o pedido não pode ficar parado por minutos.
TIMEOUT = 60  # segundos


class FonteIndisponivelError(RuntimeError):
    """A fonte não respondeu depois de todas as tentativas."""


def baixar(
    url: str,
    nome: str,
    atualizar: bool,
    *,
    corpo: bytes | None = None,
    cabecalhos: dict | None = None,
) -> Path:
    """Baixa `url` para `CACHE / nome` e devolve o caminho.

    Com o arquivo já no cache e `atualizar` falso, não baixa nada. O download vai para
    um arquivo `.parcial` que só troca de nome no fim, para não deixar arquivo pela metade.
    """
    destino = caminhos.CACHE / nome
    if destino.exists() and not atualizar:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    pedido = urllib.request.Request(
        url, data=corpo, headers={"User-Agent": "curl/8", **(cabecalhos or {})}
    )
    ultimo_erro: Exception | None = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta:
                parcial.write_bytes(resposta.read())
            parcial.replace(destino)
            return destino
        except urllib.error.HTTPError as erro:
            parcial.unlink(missing_ok=True)
            if erro.code < 500:
                # Recusa do servidor (404 etc.): repetir não adianta, quem chamou decide.
                raise
            ultimo_erro = erro
            if tentativa < TENTATIVAS:
                time.sleep(ESPERA_ENTRE_TENTATIVAS)
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            ultimo_erro = erro
            parcial.unlink(missing_ok=True)
            if tentativa < TENTATIVAS:
                time.sleep(ESPERA_ENTRE_TENTATIVAS)
    raise FonteIndisponivelError(f"{url} não respondeu em {TENTATIVAS} tentativas: {ultimo_erro}")
