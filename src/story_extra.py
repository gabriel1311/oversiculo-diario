"""
Stories extras do dia — completam o trio "3 stories por dia" do plano.

Além do Story que sai junto com o Reel, a conta publica mais dois:

- teaser (12h33 Brasília): cartaz convidando para o post do dia. Se o post já
  saiu (dias de 8h), chama para o feed; se ainda vem (12h/19h), anuncia a hora.
- replay (20h33 Brasília): republica a arte do post de hoje como Story — quem
  não viu no feed vê no Story, e o perfil fecha o dia ativo.

Mesmo formato de duas fases do post principal: a Graph API baixa a imagem de
uma URL pública, então o cartaz do teaser precisa estar commitado antes da
fase de publicação (o replay usa o .jpg do dia, que o post já commitou).

Estado em dados/stories-extra.json garante a idempotência (re-rodar não
publica de novo). Defensivo como métricas: story é bônus — falhou, avisa e
sai com 0.

    python -m src.story_extra --fase preparar --modo teaser
    python -m src.story_extra --fase publicar --modo teaser
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from src import imagem, instagram, versiculos
from src.principal import url_publica

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "dados" / "stories-extra.json"


def _carregar_estado() -> dict:
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {}


def _salvar_estado(estado: dict) -> None:
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ja_publicado(dia: str, modo: str) -> bool:
    return modo in _carregar_estado().get(dia, {})


def _post_de_hoje(dia: str) -> dict | None:
    for h in versiculos.carregar_historico():
        if h.get("data") == dia and h.get("id_post"):
            return h
    return None


def _agenda_de_hoje(dia: str) -> dict | None:
    caminho = RAIZ / "dados" / "agenda.json"
    if not caminho.exists():
        return None
    for item in json.loads(caminho.read_text(encoding="utf-8")):
        if item.get("data") == dia:
            return item
    return None


def _caminho_teaser(dia: str) -> Path:
    return RAIZ / "posts" / "stories" / f"{dia}-teaser.jpg"


def preparar(dia: str, modo: str) -> int:
    if _ja_publicado(dia, modo):
        print(f"[story-extra] {modo} de {dia} já publicado — nada a gerar")
        return 0

    if modo == "replay":
        arte = RAIZ / "posts" / f"{dia}.jpg"
        if not arte.exists():
            print(f"::warning::Sem arte de {dia} em posts/ — o post do dia saiu?")
        return 0

    # teaser: o texto depende de o post do dia já ter saído ou não. Acentos
    # são bem-vindos; emoji não (as fontes serifadas do PIL não os desenham).
    publicado = _post_de_hoje(dia)
    if publicado:
        texto = f"A palavra de hoje já está no feed: {publicado['referencia']}. Corre lá e salve para o seu dia."
    else:
        agenda = _agenda_de_hoje(dia)
        if agenda:
            texto = f"Hoje tem palavra nova às {agenda['hora']}h: {agenda['referencia']}. Te espero aqui."
        else:
            texto = "Hoje tem palavra nova no feed. Te espero aqui."

    destino = _caminho_teaser(dia)
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.gerar(texto, "Versículo do dia", destino, seed=f"{dia}-teaser")
    print(f"[story-extra] teaser gerado: {destino.relative_to(RAIZ)} ({destino.stat().st_size // 1024} KB)")
    return 0


def publicar(dia: str, modo: str) -> int:
    if _ja_publicado(dia, modo):
        print(f"[story-extra] {modo} de {dia} já publicado — nada a fazer")
        return 0

    if modo == "replay":
        relativo = f"posts/{dia}.jpg"
        if not (RAIZ / relativo).exists():
            print(f"::warning::Sem arte de {dia}; pulando o replay")
            return 0
    else:
        relativo = f"posts/stories/{dia}-teaser.jpg"
        if not (RAIZ / relativo).exists():
            print(f"::warning::Teaser de {dia} não foi gerado; nada a publicar")
            return 0

    sid = instagram.publicar_story_imagem(url_publica(relativo))
    estado = _carregar_estado()
    estado.setdefault(dia, {})[modo] = {
        "id": sid,
        "quando": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
    _salvar_estado(estado)
    print(f"[story-extra] {modo} de {dia} publicado: {sid}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fase", choices=["preparar", "publicar"], required=True)
    parser.add_argument("--modo", choices=["teaser", "replay"], required=True)
    args = parser.parse_args()
    dia = datetime.date.today().isoformat()
    try:
        if args.fase == "preparar":
            return preparar(dia, args.modo)
        return publicar(dia, args.modo)
    except Exception as erro:  # story é bônus: nunca derruba o workflow
        print(f"::warning::Story extra ({args.modo}) falhou: {erro}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
