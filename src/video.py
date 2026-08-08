"""Monta o vídeo vertical (Reel/Story) a partir da imagem do dia + trilha.

Reel e Story são o MESMO arquivo — o Gabriel quis que o story fosse o post do
dia. O layout é 1080×1920 (9:16): o próprio quadrado do versículo desfocado e
ampliado como fundo, e o quadrado nítido centralizado por cima. Assim a paleta
do dia continua mandando no visual, sem borda preta chapada.

Depende do ffmpeg (presente no runner do GitHub Actions). Sem ffmpeg — máquina
local, por exemplo — `montar` levanta VideoIndisponivel e o chamador segue sem
o vídeo.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AUDIO = RAIZ / "audio"
# Trilhas em rotação — o vídeo escolhe uma por dia (seed), para o feed não soar
# sempre igual. A primeira é o fallback quando nenhuma escolha é possível.
TRILHAS = ["trilha.wav", "trilha2.wav", "trilha3.wav"]
TRILHA = AUDIO / TRILHAS[0]

LADO = 1080
ALTURA = 1920
DURACAO = 30  # segundos; a trilha (16s, laço perfeito) repete suave para cobrir


def _fnv(texto: str) -> int:
    """FNV-1a 32 bits — mesmo hash portável usado em imagem.py."""
    h = 2166136261
    for ch in texto:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def escolher_trilha(seed: str | None) -> Path:
    existentes = [AUDIO / nome for nome in TRILHAS if (AUDIO / nome).exists()]
    if not existentes:
        return TRILHA
    if not seed:
        return existentes[0]
    return existentes[_fnv(seed + "trilha") % len(existentes)]


class VideoIndisponivel(RuntimeError):
    pass


def disponivel() -> bool:
    return shutil.which("ffmpeg") is not None


def montar(
    imagem: Path,
    destino: Path,
    seed: str | None = None,
    trilha: Path | None = None,
    duracao: int = DURACAO,
) -> Path:
    if not disponivel():
        raise VideoIndisponivel("ffmpeg não encontrado no PATH")
    if trilha is None:
        trilha = escolher_trilha(seed)
    if not trilha.exists():
        raise VideoIndisponivel(f"trilha não encontrada: {trilha}")

    destino.parent.mkdir(parents=True, exist_ok=True)

    # O cartaz já é 1080×1920 (enche a tela do Reel/Story). O vídeo é o cartaz
    # PARADO com a trilha por baixo — sem fade de entrada, senão o 1º quadro fica
    # preto e o Instagram usa esse preto como capa/thumbnail. Imagem constante =
    # laço perfeito e a miniatura mostra o versículo.
    comando = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(imagem),      # cartaz parado 1080×1920
        "-stream_loop", "-1", "-i", str(trilha),  # trilha em laço
        "-map", "0:v", "-map", "1:a",
        "-t", str(duracao),
        "-r", "30",
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",  # moov no início: o Instagram lê sem baixar tudo
        "-shortest",
        str(destino),
    ]
    proc = subprocess.run(comando, capture_output=True, text=True)
    if proc.returncode != 0:
        cauda = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise VideoIndisponivel(f"ffmpeg falhou ({proc.returncode}):\n{cauda}")
    return destino
