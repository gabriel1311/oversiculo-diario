"""
Stories de destaque (Sobre · Versículos · Oração).

Gera 3 artes verticais no estilo da marca e publica cada uma como Story.
Depois, no app, é só tocar em "Novo destaque" e fixar cada uma — criar o
destaque em si é a única parte que a API não faz.

    python3 -m src.destaques --fase preparar   # gera as 3 imagens
    python3 -m src.destaques --fase publicar   # publica como stories
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import ImageDraw

from src import imagem, instagram
from src.principal import url_publica

RAIZ = Path(__file__).resolve().parent.parent
DIR = RAIZ / "posts" / "destaques"

W, H = 1080, 1920

# Sem emoji nos textos: as fontes do projeto (serifadas) não têm esses glifos.
CARTOES = [
    {
        "slug": "sobre",
        "titulo": "SOBRE",
        "linhas": [
            "Um versículo por dia, às 8h.",
            "Palavra, fé e esperança",
            "para começar o dia com Deus.",
        ],
    },
    {
        "slug": "versiculos",
        "titulo": "VERSÍCULOS",
        "linhas": [
            "Os versículos que já",
            "passaram por aqui,",
            "guardados para você reler.",
        ],
    },
    {
        "slug": "oracao",
        "titulo": "ORAÇÃO",
        "linhas": [
            "Como podemos orar por você?",
            "Manda a sua oração",
            "no direct.",
        ],
    },
]


def _gerar_cartao(cartao: dict, destino: Path) -> None:
    pal = imagem.PALETAS[0]  # marinho + dourado: a cara da marca
    img = imagem._fundo(pal, W, H)
    d = ImageDraw.Draw(img)
    imagem._moldura(d, pal, "dupla", W, H)

    # Ornamento no alto, título Cinzel, texto e assinatura.
    imagem._ornamento(d, 640, pal, "estrela", W // 2)

    fonte_titulo = imagem._fonte("Cinzel.ttf", 92, "Bold")
    d.text((W // 2, 730), cartao["titulo"], font=fonte_titulo, fill=pal["ouro"], anchor="ma")

    fonte_txt = imagem._fonte("EBGaramond.ttf", 52, "Regular")
    y = 940
    for linha in cartao["linhas"]:
        d.text((W // 2, y), linha, font=fonte_txt, fill=pal["texto"], anchor="ma")
        y += 76

    imagem._ornamento(d, y + 40, pal, "losango", W // 2)

    fonte_handle = imagem._fonte("Cinzel.ttf", 26, "Regular")
    d.text((W // 2, H - 200), " ".join(imagem.HANDLE.upper()), font=fonte_handle,
           fill=pal["ouro_fraco"], anchor="ma")

    imagem._salvar(img, destino)


def preparar() -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    for c in CARTOES:
        destino = DIR / f"{c['slug']}.jpg"
        _gerar_cartao(c, destino)
        print(f"[destaques] {destino.relative_to(RAIZ)}")
    return 0


def publicar() -> int:
    falhas = 0
    for c in CARTOES:
        rel = f"posts/destaques/{c['slug']}.jpg"
        if not (RAIZ / rel).exists():
            print(f"::error::{rel} não existe — rode a fase preparar", file=sys.stderr)
            return 1
        url = url_publica(rel)
        try:
            id_story = instagram.publicar_story_imagem(url)
            print(f"[destaques] story '{c['slug']}' publicado: {id_story}")
        except instagram.ErroInstagram as erro:
            falhas += 1
            print(f"::warning::story '{c['slug']}' falhou: {erro}")
    return 1 if falhas == len(CARTOES) else 0


def main() -> int:
    opcoes = argparse.ArgumentParser()
    opcoes.add_argument("--fase", choices=("preparar", "publicar"), required=True)
    argumentos = opcoes.parse_args()
    return preparar() if argumentos.fase == "preparar" else publicar()


if __name__ == "__main__":
    raise SystemExit(main())
