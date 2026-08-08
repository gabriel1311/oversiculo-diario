"""Gera a legenda do post com a API do Claude, com queda para modelo fixo."""

from __future__ import annotations

import json
import os
import textwrap

MODELO = "claude-opus-5"

ESQUEMA = {
    "type": "object",
    "properties": {
        "reflexao": {
            "type": "string",
            "description": "Reflexão curta sobre o versículo, 2 a 4 frases, tom acolhedor e direto.",
        },
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "De 8 a 12 hashtags em português, sem o caractere #.",
        },
    },
    "required": ["reflexao", "hashtags"],
    "additionalProperties": False,
}

INSTRUCAO = textwrap.dedent(
    """\
    Você escreve as legendas de um perfil de Instagram que publica um versículo
    bíblico por dia, em português do Brasil.

    A reflexão acompanha a imagem do versículo. Escreva para quem passa o dedo
    pelo feed de manhã: comece pelo que importa, sem introdução do tipo "hoje
    vamos refletir". Fale com a pessoa, não sobre o versículo. Duas a quatro
    frases, linguagem simples, sem jargão de púlpito e sem prometer resultados
    materiais. Não repita o versículo — ele já está na imagem logo acima.

    As hashtags devem misturar termos amplos (fé, versículo do dia) com outros
    mais específicos ao tema do versículo. Sem o caractere #, uma por item.
    """
)

HASHTAGS_PADRAO = [
    "versiculododia", "biblia", "fe", "deus", "palavradedeus",
    "jesus", "oracao", "esperanca", "devocional", "cristao",
]


def _texto_da_resposta(resposta) -> str | None:
    """
    Pega o primeiro bloco de texto da resposta.

    No Claude Opus 5 o raciocínio vem ligado por padrão, então `content` traz
    blocos de `thinking` (de texto vazio) antes do bloco de texto de verdade —
    ler `content[0].text` às cegas devolveria vazio.
    """
    for bloco in resposta.content:
        if bloco.type == "text" and bloco.text.strip():
            return bloco.text
    return None


def _padrao(referencia: str) -> str:
    """Legenda usada quando não há chave de API ou a chamada falha."""
    return (
        f"{referencia}\n\n"
        "Que esta palavra acompanhe o seu dia.\n\n"
        + " ".join("#" + h for h in HASHTAGS_PADRAO)
    )


def gerar(texto: str, referencia: str) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[legenda] sem ANTHROPIC_API_KEY — usando legenda padrão")
        return _padrao(referencia)

    try:
        import anthropic
    except ImportError:
        print("[legenda] pacote anthropic não instalado — usando legenda padrão")
        return _padrao(referencia)

    cliente = anthropic.Anthropic()
    try:
        resposta = cliente.messages.create(
            model=MODELO,
            # Folga grande: no Opus 5 o raciocínio vem ligado e divide o teto com
            # a resposta. A saída (2-4 frases + hashtags) é pequena, e token não
            # gerado não é cobrado — então um teto alto é só seguro contra
            # truncar o JSON, sem custo.
            max_tokens=8000,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": ESQUEMA},
            },
            system=INSTRUCAO,
            messages=[
                {
                    "role": "user",
                    "content": f"Versículo: “{texto}”\nReferência: {referencia}",
                }
            ],
        )
    except Exception as erro:
        print(f"[legenda] chamada falhou ({erro}) — usando legenda padrão")
        return _padrao(referencia)

    if resposta.stop_reason == "refusal":
        print("[legenda] recusada pelos classificadores — usando legenda padrão")
        return _padrao(referencia)

    bruto = _texto_da_resposta(resposta)
    if not bruto:
        print("[legenda] resposta sem texto — usando legenda padrão")
        return _padrao(referencia)

    try:
        dados = json.loads(bruto)
        reflexao = dados["reflexao"].strip()
        hashtags = [h.strip().lstrip("#") for h in dados["hashtags"] if h.strip()]
    except (json.JSONDecodeError, KeyError, TypeError) as erro:
        print(f"[legenda] JSON inesperado ({erro}) — usando legenda padrão")
        return _padrao(referencia)

    if not hashtags:
        hashtags = HASHTAGS_PADRAO

    return f"{reflexao}\n\n{referencia}\n\n" + " ".join("#" + h for h in hashtags[:12])
