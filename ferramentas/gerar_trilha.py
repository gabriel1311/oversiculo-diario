"""Gera uma trilha instrumental ORIGINAL (sintetizada) para os vídeos.

Nada de sample nem de música do catálogo do Instagram — cada nota é uma soma de
senoides calculada aqui. Por isso não há risco de direitos autorais: a faixa é
100% gerada. É um pad calmo (progressão I–V–vi–IV em Dó) pensado para ficar por
baixo do versículo, em volume de fundo.

    python3 ferramentas/gerar_trilha.py      # grava audio/trilha.wav

Se um dia o Gabriel quiser outra música, é só substituir audio/trilha.wav (ou
apontar TRILHA para outro arquivo) — o resto do pipeline não muda.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "audio" / "trilha.wav"

SR = 22050
SEG = 4.0          # segundos por acorde
CF = 1.2           # crossfade entre acordes (segundos)
TOTAL = 16.0       # 4 acordes × 4 s — laço perfeito para o Reel repetir

# Progressão I–V–vi–IV em Dó maior, em oitavas graves e quentes.
NOTAS = {
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61, "G3": 196.00,
    "A3": 220.00, "B3": 246.94, "C4": 261.63, "D4": 293.66, "E4": 329.63,
}
ACORDES = [
    ["C3", "E4", "G3"],   # C  (I)
    ["G3", "B3", "D4"],   # G  (V)
    ["A3", "C4", "E4"],   # Am (vi)
    ["F3", "A3", "C4"],   # F  (IV)
]

# Cada nota é fundamental + harmônicos suaves; o pad ganha corpo sem virar ruído.
PARCIAIS = [(0.5, 0.55), (1.0, 1.0), (2.0, 0.4), (3.0, 0.18)]


def _voz(freq: float, t: float) -> float:
    val = 0.0
    for mult, amp in PARCIAIS:
        # Duas senoides levemente desafinadas dão calor de coro (chorus).
        val += amp * math.sin(2 * math.pi * freq * mult * t)
        val += amp * 0.5 * math.sin(2 * math.pi * freq * mult * 1.004 * t)
    return val


def _envelope(t: float, dur: float) -> float:
    """Fade-in/fade-out em cosseno levantado; a sobreposição vira crossfade."""
    if t < CF:
        return 0.5 * (1 - math.cos(math.pi * t / CF))
    if t > dur - CF:
        return 0.5 * (1 - math.cos(math.pi * (dur - t) / CF))
    return 1.0


def gerar() -> Path:
    n_total = int(TOTAL * SR)
    buf = [0.0] * n_total
    dur_janela = SEG + CF
    n_janela = int(dur_janela * SR)

    for i, acorde in enumerate(ACORDES):
        freqs = [NOTAS[n] for n in acorde]
        inicio = int((i * SEG - CF / 2) * SR)  # pode ser negativo → dá a volta (laço)
        for n in range(n_janela):
            t = n / SR
            env = _envelope(t, dur_janela)
            if env <= 0:
                continue
            amostra = sum(_voz(f, t) for f in freqs) / len(freqs)
            buf[(inicio + n) % n_total] += env * amostra

    pico = max(abs(v) for v in buf) or 1.0
    ganho = 0.5 / pico  # deixa headroom; é trilha de fundo, não precisa estourar

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(DESTINO), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(
            b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v * ganho)) * 32767)) for v in buf)
        )
    return DESTINO


if __name__ == "__main__":
    caminho = gerar()
    print(f"[trilha] {caminho} ({caminho.stat().st_size // 1024} KB, {TOTAL:.0f}s)")
