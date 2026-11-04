"""
Série "Números da Bíblia" (desde 07/11/2026): um Reel narrado por semana, aos
sábados. Diferente do post do dia, o episódio NÃO é gerado aqui: ele é feito no
Mac (serie/motor.html + serie/render.js, desenho em código + voz oficial) e o
vídeo pronto é commitado em posts/serie/. Este módulo só publica o episódio
agendado para hoje e registra o id.

dados/serie.json:
    {"episodios": [{"data": "AAAA-MM-DD", "slug": "...", "titulo": "...",
                    "publicado": null | "<id do post>"}]}
Arquivos de cada episódio: posts/serie/<slug>.mp4, <slug>.jpg (capa), <slug>.txt (legenda).

    python3 -m src.serie --fase verificar   # escreve 'tem=true|false' p/ o workflow
    python3 -m src.serie --fase publicar
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from src import instagram
from src.principal import url_publica

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / "dados" / "serie.json"
DIR = "posts/serie"


def _hoje() -> str:
    return datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()


def _do_dia(dados: dict) -> dict | None:
    hoje = _hoje()
    return next((e for e in dados["episodios"] if e["data"] == hoje and not e.get("publicado")), None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fase", choices=["verificar", "publicar"], required=True)
    fase = ap.parse_args().fase
    dados = json.loads(ARQ.read_text(encoding="utf-8"))
    ep = _do_dia(dados)

    if fase == "verificar":
        print(f"[serie] episódio de hoje: {ep['slug'] if ep else 'nenhum'}")
        saida = os.environ.get("GITHUB_OUTPUT")
        if saida:
            with open(saida, "a") as f:
                f.write(f"tem={'true' if ep else 'false'}\n")
        return 0

    if not ep:
        print("[serie] nada agendado para hoje (ou já publicado).")
        return 0
    slug = ep["slug"]
    for ext in ("mp4", "jpg", "txt"):
        if not (RAIZ / DIR / f"{slug}.{ext}").exists():
            print(f"::error::Falta {DIR}/{slug}.{ext}", file=sys.stderr)
            return 1
    legenda = (RAIZ / DIR / f"{slug}.txt").read_text(encoding="utf-8").strip()
    id_post = instagram.publicar_reel(url_publica(f"{DIR}/{slug}.mp4"), legenda,
                                      cover_url=url_publica(f"{DIR}/{slug}.jpg"))
    print(f"[serie] publicado: {ep['titulo']} → {id_post}")
    ep["publicado"] = id_post
    ARQ.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
