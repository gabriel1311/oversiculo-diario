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
TRILHA = RAIZ / "audio" / "trilha.wav"

LADO = 1080
ALTURA = 1920
DURACAO = 15  # segundos; a trilha (16s) cobre com folga, o -shortest corta no vídeo


class VideoIndisponivel(RuntimeError):
    pass


def disponivel() -> bool:
    return shutil.which("ffmpeg") is not None


def montar(imagem: Path, destino: Path, trilha: Path = TRILHA, duracao: int = DURACAO) -> Path:
    if not disponivel():
        raise VideoIndisponivel("ffmpeg não encontrado no PATH")
    if not trilha.exists():
        raise VideoIndisponivel(f"trilha não encontrada: {trilha}")

    destino.parent.mkdir(parents=True, exist_ok=True)

    # Fundo: a imagem esticada para cobrir 1080×1920, borrada e escurecida.
    # Frente: a imagem original 1080×1080 centralizada por cima.
    # split porque a mesma imagem alimenta duas cadeias (fundo borrado + frente
    # nítida); um rótulo de filtro só pode ser consumido uma vez.
    filtro = (
        "[0:v]split=2[base][frente];"
        "[base]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=32:2,eq=brightness=-0.10[bg];"
        "[frente]scale=1080:1080[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
    )

    comando = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(imagem),      # imagem parada
        "-stream_loop", "-1", "-i", str(trilha),  # trilha em laço
        "-filter_complex", filtro,
        "-map", "[v]", "-map", "1:a",
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
