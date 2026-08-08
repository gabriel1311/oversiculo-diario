"""Monta a legenda do post.

A legenda traz o texto do versículo por escrito — importante para acessibilidade:
quem usa leitor de tela não "lê" a imagem, então o versículo precisa estar no
texto. Depois vem a reflexão (uma por versículo, em dados/reflexoes.json) e as
hashtags. Sem API, sem chave, sem custo.
"""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_REFLEXOES = RAIZ / "dados" / "reflexoes.json"

REFLEXAO_PADRAO = "Que esta palavra acompanhe o seu dia."
HASHTAGS_PADRAO = [
    "versiculododia", "biblia", "fe", "deus", "palavradedeus",
    "jesus", "oracao", "esperanca", "devocional", "cristao",
]


def _reflexoes() -> dict:
    if not ARQUIVO_REFLEXOES.exists():
        return {}
    return json.loads(ARQUIVO_REFLEXOES.read_text(encoding="utf-8"))


def gerar(texto: str, referencia: str, consulta: str) -> str:
    ref = _reflexoes().get(consulta, {})
    reflexao = ref.get("reflexao") or REFLEXAO_PADRAO
    hashtags = ref.get("hashtags") or HASHTAGS_PADRAO

    # O versículo entra por escrito (acessibilidade); a reflexão vem depois.
    return (
        f"“{texto}”\n"
        f"— {referencia}\n\n"
        f"{reflexao}\n\n"
        + " ".join("#" + h for h in hashtags)
    )
