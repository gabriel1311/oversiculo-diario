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
    a imagem da URL pública. Publicar antes disso devolve erro, então esperamos
    o status virar FINISHED.
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
    Quantos dias faltam para o token expirar, ou None se não der para saber.

    O token de longa duração do Instagram Login vale ~60 dias. Diferente do
    caminho do Facebook, ele não expõe a validade por um `debug_token`; o
    endpoint de refresh devolve `expires_in`, e como refrescar também estende o
    token, aproveitamos a mesma chamada para as duas coisas.

    Retorna None em qualquer falha — sem derrubar a publicação por causa disso.
    """
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        return None
    try:
        # host graph.instagram.com; refresh é um GET simples
        url = f"https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode(
            {"grant_type": "ig_refresh_token", "access_token": token}
        )
        with urllib.request.urlopen(url, timeout=30) as resposta:
            dados = json.load(resposta)
    except Exception:
        return None
    segundos = dados.get("expires_in")
    if not segundos:
        return None
    return max(0, int(segundos) // 86400)
