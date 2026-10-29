"""
Desenha a voz do perfil no ElevenLabs (Voice Design): gera prévias a partir de
uma DESCRIÇÃO — voz sintética nova, que não é de ninguém — e, depois da
escolha, salva a escolhida na conta. Uso único; roda no Mac.

    python3 ferramentas/desenhar_voz.py prever  <pasta_saida>
    python3 ferramentas/desenhar_voz.py salvar  <generated_voice_id> "<nome>"

A chave vem de ~/.elevenlabs-key (gravada com pbpaste; nunca no repositório).
"""

from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.elevenlabs.io/v1"
CHAVE = (Path.home() / ".elevenlabs-key").read_text().strip()

TEXTO = (
    "Se a ansiedade apertou hoje, escuta isso. "
    "Não andeis ansiosos de coisa alguma; em tudo, porém, sejam conhecidas, diante de Deus, "
    "as vossas petições, pela oração e pela súplica, com ações de graças. Filipenses quatro, seis. "
    "Manda pra quem precisa ouvir isso hoje."
)
VOZES = {
    "masculina": (
        "Brazilian Portuguese male narrator, around 45 years old, deep warm baritone, calm and "
        "gentle, slow unhurried pace, intimate and reassuring like a late-night Christian radio "
        "host reading Scripture, neutral Brazilian accent, studio quality, no reverb."
    ),
    "feminina": (
        "Brazilian Portuguese female narrator, around 40 years old, soft warm mid-low voice, "
        "calm, tender and confident, slow pace, like a devotional podcast host reading the Bible "
        "to a friend, neutral Brazilian accent, studio quality, no reverb."
    ),
}


def _post(caminho: str, corpo: dict) -> dict:
    req = urllib.request.Request(
        f"{API}/{caminho}", data=json.dumps(corpo).encode(), method="POST",
        headers={"xi-api-key": CHAVE, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} em {caminho}: {e.read().decode()[:500]}")


def prever(saida: Path) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    indice = []
    for nome, descricao in VOZES.items():
        r = _post("text-to-voice/design?output_format=mp3_44100_128",
                  {"voice_description": descricao, "text": TEXTO, "guidance_scale": 4})
        for i, p in enumerate(r["previews"], 1):
            arq = saida / f"{nome}-{i}.mp3"
            arq.write_bytes(base64.b64decode(p["audio_base_64"]))
            indice.append({"arquivo": arq.name, "voz": nome, "generated_voice_id": p["generated_voice_id"],
                           "descricao": descricao, "segundos": p.get("duration_secs")})
            print(arq)
    (saida / "previas.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2))


def salvar(gid: str, nome: str, descricao: str) -> None:
    r = _post("text-to-voice", {"voice_name": nome, "voice_description": descricao, "generated_voice_id": gid})
    print(r["voice_id"])


if __name__ == "__main__":
    if sys.argv[1] == "prever":
        prever(Path(sys.argv[2]))
    else:
        salvar(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Voz do @oversiculo.diario")
