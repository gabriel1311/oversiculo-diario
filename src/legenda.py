"""Monta a legenda do post.

A legenda traz o texto do versículo por escrito — importante para acessibilidade:
quem usa leitor de tela não "lê" a imagem, então o versículo precisa estar no
texto. Depois vem a reflexão (uma por versículo, em dados/reflexoes.json), uma
pergunta de engajamento e as hashtags. Sem API, sem chave, sem custo.
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

# Fecho de engajamento: um convite a comentar/salvar/compartilhar. Alterna por
# versículo (determinístico) para não sair sempre igual. O algoritmo do Instagram
# valoriza comentário e salvamento, então vale o convite.
PERGUNTAS = [
    "E você, o que essa palavra fala ao seu coração hoje? 🙏",
    "Comente um 🙏 se isso tocou você hoje.",
    "Marque alguém que precisa ler isso hoje. 💛",
    "Salve este post para reler ao longo do dia. ✨",
    "Compartilhe com quem você ama. 🙏",
    "Qual palavra dessa passagem mais falou com você?",
]

# Hashtags gerais somadas às específicas do versículo (sem repetir). Três
# conjuntos que alternam por versículo: tags gigantes (#deus, #biblia) afogam
# conta pequena, então cada conjunto mistura poucas grandes com cauda média,
# onde um post novo ainda aparece no topo — e o bloco não sai sempre idêntico
# (bloco repetido todo dia perde alcance).
POOLS_HASHTAGS = [
    [
        "versiculododia", "palavradedeus", "devocional", "bomdiacomdeus",
        "deusnocontrole", "mensagemdefe", "versiculosbiblicos", "fecrista",
        "jesuscristo", "biblia",
    ],
    [
        "versiculododia", "palavradodia", "devocionaldiario", "deusefiel",
        "palavraprohoje", "mensagemdodia", "versiculos", "cristaos",
        "gratidao", "deus",
    ],
    [
        "versiculododia", "palavradedeus", "reflexaododia", "amanhecercomdeus",
        "confianodeus", "fortalecendoafe", "salmos", "gospel",
        "oracaododia", "jesus",
    ],
]
MAX_HASHTAGS = 12


def _reflexoes() -> dict:
    if not ARQUIVO_REFLEXOES.exists():
        return {}
    return json.loads(ARQUIVO_REFLEXOES.read_text(encoding="utf-8"))


def _semente(consulta: str) -> int:
    """Número estável a partir da consulta — mesma consulta, mesma escolha."""
    return sum(ord(c) for c in consulta)


def _hashtags(especificas: list[str], consulta: str) -> str:
    pool = POOLS_HASHTAGS[_semente(consulta + "tags") % len(POOLS_HASHTAGS)]
    vistas: list[str] = []
    for tag in especificas + pool:
        if tag not in vistas:
            vistas.append(tag)
        if len(vistas) >= MAX_HASHTAGS:
            break
    return " ".join("#" + t for t in vistas)


def gerar(texto: str, referencia: str, consulta: str) -> str:
    ref = _reflexoes().get(consulta, {})
    reflexao = ref.get("reflexao") or REFLEXAO_PADRAO
    hashtags = ref.get("hashtags") or HASHTAGS_PADRAO
    pergunta = PERGUNTAS[_semente(consulta) % len(PERGUNTAS)]

    # O versículo entra por escrito (acessibilidade); depois reflexão, convite e tags.
    return (
        f"“{texto}”\n"
        f"— {referencia}\n\n"
        f"{reflexao}\n\n"
        f"{pergunta}\n\n"
        + _hashtags(hashtags, consulta)
    )
