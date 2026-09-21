"""Monta a legenda do post.

A legenda traz o texto do versículo por escrito — importante para acessibilidade:
quem usa leitor de tela não "lê" a imagem, então o versículo precisa estar no
texto. Antes dele vai um gancho de 1 linha; depois vem a reflexão (uma por
versículo, em dados/reflexoes.json), um convite a salvar/enviar e as hashtags. Sem API, sem chave, sem custo.
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

# Fecho de engajamento. Desde 21/09 o foco é SALVAR e ENVIAR: são os sinais
# que fazem o Instagram distribuir um Reel para quem não segue (em 43 posts
# tínhamos 0,6 salvo/post e o alcance parado em ~150). "Marque alguém" saiu —
# quase ninguém marca mais; enviar por DM é o gesto atual. Alterna por versículo.
PERGUNTAS = [
    "Salve para reler quando o dia apertar. 🔖",
    "Envie para alguém que precisa ler isso hoje. 💛",
    "Salve este versículo e volte nele durante a semana. ✨",
    "Conhece alguém passando por um momento difícil? Envie esta palavra. 🙏",
    "Comente “amém” se essa palavra é para você hoje. 🙏",
    "Envie para quem você ama — pode ser a resposta que a pessoa esperava. 💛",
]

# Gancho: a 1ª linha é o que aparece embaixo do Reel antes do "mais". Fala com a
# dor/situação de quem está rolando o feed, pelo tema do versículo (as mesmas
# hashtags temáticas de versiculos.TEMAS_DIA). Versículo sem tema cai no geral.
GANCHOS = [
    ({"ansiedade", "paz", "descanso", "consolo", "saudemental", "presenca"},
     ["Para você que está cansado:", "Se a ansiedade apertou hoje, leia isto:", "Respira. Esta palavra é para você:"]),
    ({"forca", "coragem", "animo", "perseveranca", "semmedo", "recomeco", "novavida"},
     ["Para quem pensou em desistir:", "Se hoje faltou força, leia isto:", "Você não está sozinho nessa luta:"]),
    ({"esperanca", "confianca", "refugio", "proposito", "direcao", "bencao"},
     ["Para quem está esperando uma resposta:", "Quando nada parece fazer sentido, lembre:", "Deus não esqueceu de você:"]),
    ({"protecao", "seguranca", "provisao", "cura", "coracao"},
     ["Para o seu coração hoje:", "Se você está com medo, leia isto:", "Deus está cuidando de você:"]),
    ({"amor", "amordedeus", "perdao", "relacionamentos", "amizade"},
     ["Você é mais amado do que imagina:", "Leia devagar — é sobre você:", "Para lembrar quando se sentir sozinho:"]),
    ({"sabedoria", "mente", "proverbios"},
     ["Um conselho que muda o dia:", "Guarde isto antes de decidir qualquer coisa:", "Sabedoria para hoje:"]),
    ({"gratidao", "louvor", "adoracao", "alegria", "graca", "misericordia", "salvacao", "evangelho"},
     ["Motivo para agradecer hoje:", "Antes de reclamar do dia, leia isto:", "A melhor notícia que você vai ler hoje:"]),
]
GANCHOS_GERAIS = ["A palavra de hoje é para você:", "Leia isto antes de continuar o seu dia:", "Deus tem uma palavra para você hoje:"]

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


def _gancho(hashtags: list[str], consulta: str) -> str:
    tags = set(hashtags)
    # O tema com mais hashtags em comum vence (empate: o primeiro da lista).
    temas, opcoes = max(GANCHOS, key=lambda g: len(g[0] & tags))
    if not temas & tags:
        opcoes = GANCHOS_GERAIS
    return opcoes[_semente(consulta + "gancho") % len(opcoes)]


def gerar(texto: str, referencia: str, consulta: str) -> str:
    ref = _reflexoes().get(consulta, {})
    reflexao = ref.get("reflexao") or REFLEXAO_PADRAO
    hashtags = ref.get("hashtags") or HASHTAGS_PADRAO
    pergunta = PERGUNTAS[_semente(consulta) % len(PERGUNTAS)]

    # Gancho na 1ª linha; o versículo entra por escrito (acessibilidade); depois
    # reflexão, convite e tags.
    return (
        f"{_gancho(hashtags, consulta)}\n\n"
        f"“{texto}”\n"
        f"— {referencia}\n\n"
        f"{reflexao}\n\n"
        f"{pergunta}\n\n"
        + _hashtags(hashtags, consulta)
    )
