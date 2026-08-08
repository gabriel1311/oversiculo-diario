"""
Carrossel semanal: um post com os versículos dos próximos 7 dias.

Mesma lógica de duas fases do post diário (a Graph API baixa as imagens de URLs
públicas, então elas precisam estar commitadas antes de publicar):

    python3 -m src.semanal --fase preparar    # gera as 7 imagens + legenda
    python3 -m src.semanal --fase publicar    # publica o carrossel
    python3 -m src.semanal --fase ensaio      # gera e para; não publica

As imagens usam o MESMO visual sorteado de cada dia (seed = data), então o
carrossel casa com o que sai no feed. É disparado à mão (workflow_dispatch).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src import imagem, instagram, versiculos
from src.principal import url_publica

RAIZ = Path(__file__).resolve().parent.parent
DIR_CARROSSEL = RAIZ / "posts" / "carrossel"
ARQUIVO_LEGENDA = DIR_CARROSSEL / "legenda.txt"
ARQUIVO_LISTA = DIR_CARROSSEL / "itens.json"

HASHTAGS = [
    "versiculododia", "biblia", "fe", "deus", "palavradedeus",
    "jesus", "esperanca", "devocional", "versiculos", "semana",
]


def _itens(n: int = 7) -> list[dict]:
    """Os próximos n dias da agenda, com o texto do versículo anexado."""
    agenda = json.loads((RAIZ / "dados" / "agenda.json").read_text(encoding="utf-8"))
    textos = {v.consulta: v.texto for v in versiculos.carregar_pool()}
    itens = []
    for item in agenda[:n]:
        itens.append({
            "data": item["data"],
            "referencia": item["referencia"],
            "consulta": item["consulta"],
            "texto": textos.get(item["consulta"], ""),
        })
    return itens


def _legenda(itens: list[dict]) -> str:
    linhas = [f"{i+1}. {it['referencia']}" for i, it in enumerate(itens)]
    return (
        "Sua semana com a Palavra 🙏\n\n"
        "Arraste para ver os versículos dos próximos dias:\n"
        + "\n".join(linhas)
        + "\n\nQual deles você mais precisa ouvir hoje? Salve este post. 💛\n\n"
        + " ".join("#" + h for h in HASHTAGS)
    )


def preparar(ensaio: bool) -> int:
    itens = _itens()
    if len(itens) < 2:
        print("::error::Agenda insuficiente para montar o carrossel (mín. 2 dias).", file=sys.stderr)
        return 1

    DIR_CARROSSEL.mkdir(parents=True, exist_ok=True)
    for it in itens:
        destino = DIR_CARROSSEL / f"{it['data']}.jpg"
        imagem.gerar_quadrado(it["texto"], it["referencia"], destino, seed=it["data"])
        print(f"[carrossel] {destino.relative_to(RAIZ)}")

    ARQUIVO_LISTA.write_text(json.dumps(itens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    legenda = _legenda(itens)
    ARQUIVO_LEGENDA.write_text(legenda + "\n", encoding="utf-8")
    print(f"[legenda]\n{legenda}\n")

    if ensaio:
        print("[ensaio] carrossel gerado; nada foi publicado")
    return 0


def publicar() -> int:
    if not ARQUIVO_LISTA.exists() or not ARQUIVO_LEGENDA.exists():
        print("::error::Arquivos do carrossel não encontrados — rode a fase preparar.", file=sys.stderr)
        return 1

    itens = json.loads(ARQUIVO_LISTA.read_text(encoding="utf-8"))
    legenda = ARQUIVO_LEGENDA.read_text(encoding="utf-8").strip()
    urls = [url_publica(f"posts/carrossel/{it['data']}.jpg") for it in itens]
    print(f"[carrossel] {len(urls)} imagens")

    try:
        id_post = instagram.publicar_carrossel(urls, legenda)
    except instagram.ErroInstagram as erro:
        print(f"::error::Falha ao publicar o carrossel: {erro}", file=sys.stderr)
        return 1

    print(f"[instagram] carrossel publicado: {id_post}")
    return 0


def main() -> int:
    opcoes = argparse.ArgumentParser()
    opcoes.add_argument("--fase", choices=("preparar", "publicar", "ensaio"), required=True)
    argumentos = opcoes.parse_args()
    if argumentos.fase == "publicar":
        return publicar()
    return preparar(ensaio=argumentos.fase == "ensaio")


if __name__ == "__main__":
    raise SystemExit(main())
