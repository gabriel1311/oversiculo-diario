"""Monta o vídeo vertical (Reel/Story) a partir da imagem do dia + trilha.

Reel e Story são o MESMO arquivo — o Gabriel quis que o story fosse o post do
dia. O cartaz já é 1080×1920 (9:16). Nos estilos com foto (luz, foto) o vídeo é
animado: a foto se aproxima devagar e os textos entram em tempos; nos demais é o
cartaz parado. A duração acompanha o tempo de leitura do versículo.

Depende do ffmpeg (presente no runner do GitHub Actions). Sem ffmpeg — máquina
local, por exemplo — `montar` levanta VideoIndisponivel e o chamador segue sem
o vídeo.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AUDIO = RAIZ / "audio"
# Trilhas em rotação — faixas royalty-free reais (Pixabay), creditadas em
# audio/CREDITOS.md. Para variar mais, é só somar mais arquivos aqui.
TRILHAS = [
    "piano-atlas.mp3", "piano-monda.mp3", "piano-atlas2.mp3",
    "piano-nastel.mp3", "violao-jonas.mp3",
    "cinematic-leberch.mp3", "ambient-jonas.mp3", "cinematic-tunetank.mp3",
    # Leva de 03/09 (Pixabay, ver CREDITOS.md):
    "piano-atlas3.mp3", "piano-dmitry.mp3", "violao-lemon.mp3",
    "violao-universfield.mp3", "ambiente-jesse.mp3", "worship-andriig.mp3",
]
TRILHA = AUDIO / TRILHAS[0]

# Clima de cada trilha, para casar a música com o tema do versículo.
CLIMAS = {
    "piano-atlas.mp3": "piano", "piano-monda.mp3": "piano",
    "piano-atlas2.mp3": "piano", "piano-nastel.mp3": "piano",
    "violao-jonas.mp3": "violao",
    "cinematic-leberch.mp3": "cinematic", "cinematic-tunetank.mp3": "cinematic",
    "ambient-jonas.mp3": "ambiente",
    "piano-atlas3.mp3": "piano", "piano-dmitry.mp3": "piano",
    "violao-lemon.mp3": "violao", "violao-universfield.mp3": "violao",
    "ambiente-jesse.mp3": "ambiente", "worship-andriig.mp3": "ambiente",
}
# Tema do dia (weekday do Python: seg=0 … dom=6) → climas ACEITOS naquele dia.
# Escolhe entre todas as trilhas desses climas (com variedade). Casa com os temas
# de versiculos.TEMAS_DIA: seg=força, ter=esperança, qua=sabedoria, qui=amor,
# sex=paz, sáb=proteção, dom=louvor.
CLIMA_POR_DIA = {
    0: {"cinematic", "piano"},            # força e recomeço → mais grandioso
    1: {"cinematic", "piano"},            # fé e esperança
    2: {"piano", "violao"},               # sabedoria → intimista
    3: {"piano", "violao"},               # amor → quente
    4: {"ambiente", "piano", "violao"},   # paz e descanso → etéreo/calmo
    5: {"piano", "ambiente"},             # proteção e cuidado
    6: {"cinematic", "piano"},            # gratidão e louvor → grandioso
}

LADO = 1080
ALTURA = 1920
# Duração do Reel = tempo de LEITURA do versículo, não 30 s fixos (como foi até
# 21/09): com 30 s a pessoa lia em 6 s e ia embora, e retenção baixa é o que mais
# segura a distribuição de um Reel. Curto o bastante para ser visto inteiro e
# entrar em laço.
DURACAO = 8
DURACAO_MIN, DURACAO_MAX = 7, 15
# Entrada das camadas de texto no vídeo animado: (início em s, fade em s).
ENTRADAS = [(0.0, 0.6), (1.4, 0.8), (2.6, 0.8)]
ZOOM_FINAL = 0.07  # a foto de fundo cresce 7% ao longo do vídeo (aproximação lenta)


def duracao_para(texto: str) -> int:
    """Segundos para ler o versículo com calma (~22 caracteres/s) + respiro."""
    return max(DURACAO_MIN, min(DURACAO_MAX, round(6 + len(texto) / 22)))


def _fnv(texto: str) -> int:
    """FNV-1a 32 bits — mesmo hash portável usado em imagem.py."""
    h = 2166136261
    for ch in texto:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def escolher_trilha(seed: str | None) -> Path:
    """Escolhe a trilha do dia. Se o seed for uma data, casa o clima da música com
    o tema daquele dia da semana (com variedade dentro do clima); senão, sorteia."""
    existentes = [nome for nome in TRILHAS if (AUDIO / nome).exists()]
    if not existentes:
        return TRILHA
    if not seed:
        return AUDIO / existentes[0]

    # Casa pelo tema do dia quando o seed é uma data (post diário).
    try:
        dia = date.fromisoformat(seed)
    except (ValueError, TypeError):
        dia = None
    if dia is not None:
        climas_ok = CLIMA_POR_DIA.get(dia.weekday(), set())
        candidatos = [n for n in existentes if CLIMAS.get(n) in climas_ok]
        if candidatos:
            return AUDIO / candidatos[_fnv(seed + "trilha") % len(candidatos)]

    return AUDIO / existentes[_fnv(seed + "trilha") % len(existentes)]


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
    camadas: list[Path] | None = None,
) -> Path:
    """`camadas` = [fundo, camada1.png, …] (imagem.gerar_camadas): vídeo animado,
    com a foto em aproximação lenta e os textos entrando em tempos. Sem camadas,
    o vídeo é o cartaz parado."""
    if not disponivel():
        raise VideoIndisponivel("ffmpeg não encontrado no PATH")
    if trilha is None:
        trilha = escolher_trilha(seed)
    if not trilha.exists():
        raise VideoIndisponivel(f"trilha não encontrada: {trilha}")

    destino.parent.mkdir(parents=True, exist_ok=True)

    codificacao = [
        "-t", str(duracao),
        "-r", "30",
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",  # moov no início: o Instagram lê sem baixar tudo
        "-shortest",
        str(destino),
    ]
    if camadas:
        # Fundo ampliado 2x antes do zoompan: ele arredonda para pixel inteiro e,
        # sem a folga, a aproximação lenta treme. A capa do Reel vem do cover_url
        # (o cartaz completo), então o 1º quadro pode começar sem texto.
        quadros = duracao * 30
        filtros = [
            f"[0:v]scale={LADO * 2}:{ALTURA * 2},zoompan=z='1+{ZOOM_FINAL}*on/{quadros}'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={LADO}x{ALTURA}:fps=30[v0]"
        ]
        entradas = ["-loop", "1", "-framerate", "30", "-i", str(camadas[0])]
        for i, camada in enumerate(camadas[1:], 1):
            entradas += ["-loop", "1", "-framerate", "30", "-i", str(camada)]
            inicio, fade = ENTRADAS[min(i - 1, len(ENTRADAS) - 1)]
            filtros.append(f"[{i}:v]format=rgba,fade=t=in:st={inicio}:d={fade}:alpha=1[c{i}]")
            filtros.append(f"[v{i - 1}][c{i}]overlay=format=auto[v{i}]")
        n = len(camadas) - 1
        filtros.append(f"[v{n}]format=yuv420p[v]")
        comando = [
            "ffmpeg", "-y", *entradas,
            "-stream_loop", "-1", "-i", str(trilha),
            "-filter_complex", ";".join(filtros),
            "-map", "[v]", "-map", f"{n + 1}:a",
            *codificacao,
        ]
    else:
        # Estilos sem foto: o cartaz PARADO com a trilha por baixo — sem fade de
        # entrada, e a miniatura mostra o versículo.
        comando = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(imagem),      # cartaz parado 1080×1920
            "-stream_loop", "-1", "-i", str(trilha),  # trilha em laço
            "-map", "0:v", "-map", "1:a",
            *codificacao,
        ]
    proc = subprocess.run(comando, capture_output=True, text=True)
    if proc.returncode != 0:
        cauda = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise VideoIndisponivel(f"ffmpeg falhou ({proc.returncode}):\n{cauda}")
    return destino
