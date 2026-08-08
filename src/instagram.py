"""Publicação via Instagram Graph API (container + publish)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

VERSAO = os.environ.get("IG_API_VERSION", "v23.0")
# graph.INSTAGRAM.com, não graph.facebook.com: o token vem do caminho
# "Instagram Login", e esse token só é reconhecido no host do Instagram.
# Mandá-lo ao host do Facebook devolve "OAuthException 190: Cannot parse
# access token" — o Facebook não consegue nem decodificar um token de Instagram.
BASE = f"https://graph.instagram.com/{VERSAO}"


class ErroInstagram(RuntimeError):
    pass


def _post(caminho: str, campos: dict[str, str]) -> dict:
    dados = urllib.parse.urlencode(campos).encode()
    requisicao = urllib.request.Request(f"{BASE}/{caminho}", data=dados, method="POST")
    try:
        with urllib.request.urlopen(requisicao, timeout=90) as resposta:
            return json.load(resposta)
    except urllib.error.HTTPError as erro:
        corpo = erro.read().decode("utf-8", "replace")
        try:
            detalhe = json.loads(corpo)["error"]
            mensagem = f"{detalhe.get('type')} {detalhe.get('code')}: {detalhe.get('message')}"
        except Exception:
            mensagem = corpo[:400]
        raise ErroInstagram(f"HTTP {erro.code} em {caminho} — {mensagem}") from None


def _get(caminho: str, campos: dict[str, str]) -> dict:
    url = f"{BASE}/{caminho}?" + urllib.parse.urlencode(campos)
    try:
        with urllib.request.urlopen(url, timeout=60) as resposta:
            return json.load(resposta)
    except urllib.error.HTTPError as erro:
        corpo = erro.read().decode("utf-8", "replace")
        raise ErroInstagram(f"HTTP {erro.code} em {caminho} — {corpo[:400]}") from None


def _esperar_container(container: str, token: str, tentativas: int = 20) -> None:
    """
    O container leva alguns segundos até ficar pronto: o Instagram precisa baixar
    a mídia da URL pública. Publicar antes disso devolve erro, então esperamos
    o status virar FINISHED.

    Vídeo (Reel/Story) demora bem mais que imagem — o Instagram transcodifica —,
    então o chamador passa mais tentativas nesse caso.
    """
    for _ in range(tentativas):
        estado = _get(container, {"fields": "status_code,status", "access_token": token})
        codigo = estado.get("status_code")
        if codigo == "FINISHED":
            return
        if codigo == "ERROR":
            raise ErroInstagram(f"container falhou: {estado.get('status')}")
        time.sleep(5)
    raise ErroInstagram("container não ficou pronto a tempo")


def _credenciais() -> tuple[str, str]:
    token = os.environ.get("IG_ACCESS_TOKEN")
    conta = os.environ.get("IG_ACCOUNT_ID")
    if not token or not conta:
        raise ErroInstagram("faltam IG_ACCESS_TOKEN e/ou IG_ACCOUNT_ID no ambiente")
    return token, conta


def _publicar_container(conta: str, token: str, campos: dict[str, str], tentativas: int) -> str:
    """Cria o container com os campos dados, espera ficar pronto e publica."""
    criado = _post(f"{conta}/media", {**campos, "access_token": token})
    container = criado.get("id")
    if not container:
        raise ErroInstagram(f"resposta sem id de container: {criado}")
    print(f"[instagram] container {container}")

    _esperar_container(container, token, tentativas)

    publicado = _post(
        f"{conta}/media_publish",
        {"creation_id": container, "access_token": token},
    )
    id_post = publicado.get("id")
    if not id_post:
        raise ErroInstagram(f"resposta sem id do post: {publicado}")
    return id_post


def publicar_reel(url_video: str, legenda: str) -> str:
    """Publica o vídeo como Reel no feed (com legenda). Devolve o id do post."""
    token, conta = _credenciais()
    # share_to_feed=true faz o Reel aparecer também na grade do perfil.
    return _publicar_container(
        conta, token,
        {"media_type": "REELS", "video_url": url_video, "caption": legenda, "share_to_feed": "true"},
        tentativas=60,  # vídeo transcodifica devagar: até ~5 min de espera
    )


def publicar_story(url_video: str) -> str:
    """Publica o mesmo vídeo como Story. Story não aceita legenda. Devolve o id."""
    token, conta = _credenciais()
    return _publicar_container(
        conta, token,
        {"media_type": "STORIES", "video_url": url_video},
        tentativas=60,
    )


def publicar_carrossel(urls_imagens: list[str], legenda: str) -> str:
    """
    Publica um carrossel (2 a 10 imagens) no feed. Cada imagem vira um container
    filho (is_carousel_item), e um container-pai do tipo CAROUSEL os agrupa.
    Devolve o id do post.
    """
    token, conta = _credenciais()
    if not 2 <= len(urls_imagens) <= 10:
        raise ErroInstagram(f"carrossel aceita de 2 a 10 imagens, recebi {len(urls_imagens)}")

    filhos = []
    for url in urls_imagens:
        criado = _post(
            f"{conta}/media",
            {"image_url": url, "is_carousel_item": "true", "access_token": token},
        )
        filho = criado.get("id")
        if not filho:
            raise ErroInstagram(f"resposta sem id de item do carrossel: {criado}")
        _esperar_container(filho, token)  # imagem é rápida, mas garante o FINISHED
        filhos.append(filho)
        print(f"[instagram] item {filho}")

    return _publicar_container(
        conta, token,
        {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda},
        tentativas=30,
    )


def publicar(url_imagem: str, legenda: str) -> str:
    """Cria o container, espera o processamento e publica. Devolve o id do post."""
    token = os.environ.get("IG_ACCESS_TOKEN")
    conta = os.environ.get("IG_ACCOUNT_ID")
    if not token or not conta:
        raise ErroInstagram("faltam IG_ACCESS_TOKEN e/ou IG_ACCOUNT_ID no ambiente")

    criado = _post(
        f"{conta}/media",
        {"image_url": url_imagem, "caption": legenda, "access_token": token},
    )
    container = criado.get("id")
    if not container:
        raise ErroInstagram(f"resposta sem id de container: {criado}")
    print(f"[instagram] container {container}")

    _esperar_container(container, token)

    publicado = _post(
        f"{conta}/media_publish",
        {"creation_id": container, "access_token": token},
    )
    id_post = publicado.get("id")
    if not id_post:
        raise ErroInstagram(f"resposta sem id do post: {publicado}")
    return id_post


def dias_ate_expirar() -> int | None:
    """
    Antes checava a validade do token aqui, a cada post. Não faz mais nada.

    A saúde do token virou responsabilidade do workflow `renovar-token.yml`, que
    renova semanalmente e regrava o secret. Chamar a renovação aqui também, a
    cada publicação, só geraria um token novo por dia à toa. Mantido como no-op
    para não mexer em quem chama; retorna None, e o fluxo de publicação já trata
    None pulando o aviso.
    """
    return None
