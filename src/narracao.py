"""
Narração do Reel (ElevenLabs), com a voz sintética própria do perfil — desenhada
do zero por descrição (ferramentas/desenhar_voz.py), não é a voz de ninguém.

Duas falas, para casar com a tela: o GANCHO (dura o tempo em que a frase está
na tela) e o CORPO (versículo + referência + pedido de envio). O vídeo usa a
duração real de cada uma.

Sem ELEVENLABS_API_KEY no ambiente, ou se a API falhar, `narrar` devolve None e
o post sai como antes, só com a trilha — nenhum dia fica sem post.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_VOZ = RAIZ / "dados" / "voz.json"  # {"vozes": [{nome, voice_id}], "modelo", "ajustes"} — não é segredo
API = "https://api.elevenlabs.io/v1"

FECHOS = [
    "Manda pra quem precisa ouvir isso hoje.",
    "Envia pra alguém que você ama.",
    "Guarda essa palavra e manda pra quem precisa.",
]


@dataclass
class Narracao:
    gancho: Path
    corpo: Path
    s_gancho: float
    s_corpo: float
    voz: str


def _duracao(arquivo: Path) -> float:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arquivo)],
        capture_output=True, text=True, check=True,
    )
    return float(saida.stdout.strip())


def referencia_falada(referencia: str) -> str:
    """'Salmos 62:1-2' → 'Salmos 62, versículos 1 a 2' (lido natural pela voz)."""
    m = re.match(r"^(.*?)\s+(\d+):(\d+)(?:-(\d+))?$", referencia.strip())
    if not m:
        return referencia
    livro, cap, v1, v2 = m.groups()
    if v2:
        return f"{livro} {cap}, versículos {v1} a {v2}"
    return f"{livro} {cap}, versículo {v1}"


def escolher_voz(config: dict, seed: str) -> dict:
    """Alterna as vozes: por dia quando o seed é uma data (um dia cada), senão pelo hash."""
    vozes = config["vozes"]
    try:
        n = date.fromisoformat(seed).toordinal()
    except ValueError:
        n = sum(map(ord, seed))
    return vozes[n % len(vozes)]


def _falar(texto: str, destino: Path, voz: dict, chave: str, ajustes: dict | None = None,
           antes: str | None = None, depois: str | None = None) -> Path:
    corpo = {
        "text": texto,
        "model_id": voz.get("modelo", "eleven_multilingual_v2"),
        "voice_settings": ajustes or voz.get("ajustes", {"stability": 0.55, "similarity_boost": 0.8, "speed": 0.92}),
    }
    # Contexto da fala vizinha: o modelo mantém o mesmo ritmo e entonação nas
    # duas partes, em vez de tratar cada uma como frase solta.
    if antes:
        corpo["previous_text"] = antes
    if depois:
        corpo["next_text"] = depois
    req = urllib.request.Request(
        f"{API}/text-to-speech/{voz['voice_id']}?output_format=mp3_44100_128",
        data=json.dumps(corpo).encode(), method="POST",
        headers={"xi-api-key": chave, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        destino.write_bytes(r.read())
    return destino


def narrar(gancho: str, texto: str, referencia: str, pasta: Path, seed: str) -> Narracao | None:
    chave = os.environ.get("ELEVENLABS_API_KEY")
    if not chave or not ARQ_VOZ.exists():
        return None
    config = json.loads(ARQ_VOZ.read_text(encoding="utf-8"))
    voz = {**config, **escolher_voz(config, seed)}
    fecho = FECHOS[sum(map(ord, seed)) % len(FECHOS)]
    frase = gancho.strip().rstrip(":").strip() + "."
    corpo = f"{texto.strip()} {referencia_falada(referencia)}. {fecho}"
    try:
        # Frase curta sozinha sai corrida (Gabriel, 29/10: "arrancou falando rápido
        # demais"): o gancho tem velocidade e estabilidade próprias.
        ajustes = voz.get("ajustes", {})
        a = _falar(frase, pasta / "fala-gancho.mp3", voz, chave,
                   ajustes={**ajustes, **voz.get("ajustes_gancho", {})}, depois=corpo)
        b = _falar(corpo, pasta / "fala-corpo.mp3", voz, chave, antes=frase)
        return Narracao(a, b, _duracao(a), _duracao(b), voz["nome"])
    except (urllib.error.URLError, subprocess.CalledProcessError, OSError, KeyError) as erro:
        print(f"::warning::Narração indisponível, seguindo só com a trilha: {erro}")
        return None
