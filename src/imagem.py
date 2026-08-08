"""Renderiza o post 1080x1080 a partir do versículo.

O visual varia por dia — paleta, ornamento e moldura — para o feed não ficar
engessado, mas a estrutura é sempre a mesma (versículo centralizado, referência,
assinatura, moldura dourada). A variação é semeada pela data: o mesmo dia sempre
sai igual (retry seguro), dias diferentes saem diferentes.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _fnv(texto: str) -> int:
    """
    Hash FNV-1a de 32 bits — determinístico e **portável**: o mesmo cálculo em
    JavaScript dá o mesmo número. É o que faz a prévia no admin bater exatamente
    com o visual que o Python publica (o `random` do Python não é reproduzível
    no navegador).
    """
    h = 2166136261
    for ch in texto:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h

RAIZ = Path(__file__).resolve().parent.parent
FONTES = RAIZ / "fontes"

LADO = 1080
MARGEM = 96

# Paletas: fundo escuro + tinta clara + acento metálico. Todas são claro-sobre-
# escuro com contraste alto, então o texto fica sempre legível. O acento é uma
# variação de dourado/bronze que combina com cada fundo.
PALETAS = [
    {  # marinho (o original)
        "topo": (11, 29, 58), "base": (24, 52, 94), "vinheta": (4, 12, 26),
        "ouro": (206, 170, 106), "ouro_fraco": (150, 122, 76), "texto": (243, 240, 233),
    },
    {  # floresta
        "topo": (10, 40, 30), "base": (18, 60, 45), "vinheta": (4, 18, 12),
        "ouro": (200, 172, 108), "ouro_fraco": (142, 120, 78), "texto": (240, 240, 230),
    },
    {  # vinho
        "topo": (46, 16, 26), "base": (74, 28, 42), "vinheta": (22, 8, 14),
        "ouro": (208, 172, 112), "ouro_fraco": (152, 122, 82), "texto": (244, 236, 232),
    },
    {  # grafite (acento areia)
        "topo": (26, 28, 33), "base": (44, 47, 55), "vinheta": (10, 11, 14),
        "ouro": (212, 188, 152), "ouro_fraco": (150, 132, 106), "texto": (240, 238, 232),
    },
    {  # ameixa
        "topo": (36, 22, 52), "base": (58, 38, 80), "vinheta": (16, 10, 26),
        "ouro": (202, 172, 122), "ouro_fraco": (146, 122, 88), "texto": (242, 236, 240),
    },
    {  # petróleo
        "topo": (8, 38, 44), "base": (14, 60, 68), "vinheta": (4, 18, 20),
        "ouro": (200, 178, 124), "ouro_fraco": (140, 124, 88), "texto": (236, 240, 238),
    },
    {  # café
        "topo": (34, 24, 18), "base": (58, 42, 30), "vinheta": (16, 10, 6),
        "ouro": (214, 184, 130), "ouro_fraco": (154, 130, 92), "texto": (242, 236, 226),
    },
    {  # índigo
        "topo": (22, 24, 64), "base": (40, 44, 104), "vinheta": (8, 10, 30),
        "ouro": (198, 178, 126), "ouro_fraco": (138, 124, 88), "texto": (236, 238, 246),
    },
    {  # oliva
        "topo": (34, 36, 16), "base": (56, 60, 28), "vinheta": (14, 15, 6),
        "ouro": (208, 192, 124), "ouro_fraco": (148, 136, 90), "texto": (240, 240, 226),
    },
    {  # carmesim
        "topo": (54, 12, 22), "base": (92, 24, 38), "vinheta": (24, 6, 10),
        "ouro": (216, 170, 120), "ouro_fraco": (158, 120, 84), "texto": (246, 232, 230),
    },
    {  # ardósia (azul-ardósia)
        "topo": (22, 30, 42), "base": (38, 52, 72), "vinheta": (8, 12, 18),
        "ouro": (200, 186, 150), "ouro_fraco": (142, 130, 104), "texto": (236, 240, 244),
    },
    {  # cacau
        "topo": (28, 18, 16), "base": (50, 32, 26), "vinheta": (12, 7, 6),
        "ouro": (210, 178, 132), "ouro_fraco": (150, 126, 92), "texto": (240, 232, 226),
    },
]

MOLDURAS = ["dupla", "cantos", "linha"]
ORNAMENTOS = ["losango", "cruz", "pontos", "estrela"]

HANDLE = "@oversiculo.diario"

# Formato vertical do Reel/Story (enche a tela).
VERT_W, VERT_H = 1080, 1920

# Dois estilos que se alternam por dia. "classico" = fundo escuro + serifada +
# dourado; "bilhete" = papel creme + cursiva azul + coração (pedido do Gabriel).
ESTILOS = ["classico", "bilhete"]

# A cursiva do bilhete só fica boa em versículo curto/médio; acima disso o texto
# aperta e perde legibilidade, então versículos longos vão sempre no clássico.
LIMITE_BILHETE = 180

# Paleta do estilo bilhete.
BILHETE_CREME = (236, 228, 210)
BILHETE_CREME_BORDA = (206, 196, 176)
BILHETE_TINTA = (36, 44, 122)          # azul caneta
BILHETE_SOMBRA = (196, 190, 176)       # sombra suave (emboss)
BILHETE_HANDLE = (92, 98, 150)


def _fonte(arquivo: str, tamanho: int, peso: str = "Regular") -> ImageFont.FreeTypeFont:
    """
    Carrega uma fonte variável já fixada num peso.

    As duas fontes do projeto são variáveis (um arquivo cobre vários pesos), mas
    não oferecem os mesmos: EB Garamond vai de Regular a ExtraBold, Cinzel tem só
    Regular/Bold/Black. Pedir um peso inexistente levanta ValueError, então
    caímos no mais próximo disponível em vez de quebrar o render.
    """
    fonte = ImageFont.truetype(str(FONTES / arquivo), tamanho)
    try:
        disponiveis = [
            n.decode() if isinstance(n, bytes) else n for n in fonte.get_variation_names()
        ]
    except OSError:
        return fonte  # fonte estática — o peso já é o do arquivo

    if peso not in disponiveis:
        escala = ["Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"]
        alvo = escala.index(peso) if peso in escala else 0
        peso = min(
            disponiveis,
            key=lambda n: abs((escala.index(n) if n in escala else 0) - alvo),
        )
    fonte.set_variation_by_name(peso)
    return fonte


def _fundo(pal: dict, largura: int = LADO, altura: int = LADO) -> Image.Image:
    """Gradiente vertical suave com vinheta, montado pequeno e ampliado."""
    passos = 256
    gradiente = Image.new("RGB", (1, passos))
    pixels = gradiente.load()
    for y in range(passos):
        proporcao = y / (passos - 1)
        pixels[0, y] = tuple(
            round(pal["topo"][c] + (pal["base"][c] - pal["topo"][c]) * proporcao)
            for c in range(3)
        )
    base = gradiente.resize((largura, altura), Image.Resampling.BICUBIC)

    # Vinheta: escurece os cantos para o texto ganhar peso no centro.
    vinheta = Image.radial_gradient("L").resize((largura, altura), Image.Resampling.BICUBIC)
    escuro = Image.new("RGB", (largura, altura), pal["vinheta"])
    return Image.composite(escuro, base, vinheta.point(lambda v: int(v * 0.55)))


def _moldura(desenho: ImageDraw.ImageDraw, pal: dict, estilo: str, W: int = LADO, H: int = LADO) -> None:
    if estilo == "linha":
        # Uma linha só, fina e dourada — moldura minimalista.
        desenho.rectangle([52, 52, W - 53, H - 53], outline=pal["ouro"], width=1)
        return

    if estilo == "cantos":
        # Só cantos: quatro cotovelos dourados, sem retângulo fechado.
        m, braco = 54, 70
        for cx, cy, sx, sy in [
            (m, m, 1, 1),
            (W - m, m, -1, 1),
            (m, H - m, 1, -1),
            (W - m, H - m, -1, -1),
        ]:
            desenho.line([cx, cy, cx + sx * braco, cy], fill=pal["ouro"], width=2)
            desenho.line([cx, cy, cx, cy + sy * braco], fill=pal["ouro"], width=2)
        return

    # dupla (padrão): duas linhas concêntricas.
    externa, interna = 44, 60
    desenho.rectangle(
        [externa, externa, W - externa - 1, H - externa - 1],
        outline=pal["ouro_fraco"], width=2,
    )
    desenho.rectangle(
        [interna, interna, W - interna - 1, H - interna - 1],
        outline=pal["ouro"], width=1,
    )


def _quebrar(
    texto: str, fonte: ImageFont.FreeTypeFont, largura_maxima: int, desenho: ImageDraw.ImageDraw
) -> list[str]:
    linhas: list[str] = []
    atual = ""
    for palavra in texto.split():
        tentativa = f"{atual} {palavra}".strip()
        if desenho.textlength(tentativa, font=fonte) <= largura_maxima:
            atual = tentativa
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _ajustar(
    texto: str, desenho: ImageDraw.ImageDraw, largura: int, altura: int, maximo: int = 72
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """
    Encolhe a fonte até o versículo caber na área reservada.

    Versículos longos existem no pool (1 Coríntios 13:4-7 tem 315 caracteres),
    então isto não é um caso hipotético — sem o ajuste o texto vaza da moldura.
    """
    for tamanho in range(maximo, 29, -2):
        fonte = _fonte("EBGaramond.ttf", tamanho, "Regular")
        linhas = _quebrar(texto, fonte, largura, desenho)
        espacamento = round(tamanho * 1.42)
        if len(linhas) * espacamento <= altura:
            return fonte, linhas, espacamento
    fonte = _fonte("EBGaramond.ttf", 30, "Regular")
    return fonte, _quebrar(texto, fonte, largura, desenho), 43


def _ornamento(desenho: ImageDraw.ImageDraw, centro_y: int, pal: dict, estilo: str, meio: int = LADO // 2) -> None:
    largura = 90
    # Os dois traços laterais aparecem em todos os estilos.
    desenho.line([meio - largura, centro_y, meio - 16, centro_y], fill=pal["ouro_fraco"], width=1)
    desenho.line([meio + 16, centro_y, meio + largura, centro_y], fill=pal["ouro_fraco"], width=1)

    if estilo == "estrela":
        # Estrela de 4 pontas (sparkle), preenchida.
        pontos = [
            (meio, centro_y - 9), (meio + 2, centro_y - 2), (meio + 9, centro_y),
            (meio + 2, centro_y + 2), (meio, centro_y + 9), (meio - 2, centro_y + 2),
            (meio - 9, centro_y), (meio - 2, centro_y - 2),
        ]
        desenho.polygon(pontos, fill=pal["ouro"])
    elif estilo == "cruz":
        desenho.line([meio, centro_y - 8, meio, centro_y + 8], fill=pal["ouro"], width=2)
        desenho.line([meio - 6, centro_y - 2, meio + 6, centro_y - 2], fill=pal["ouro"], width=2)
    elif estilo == "pontos":
        for dx in (-8, 0, 8):
            desenho.ellipse(
                [meio + dx - 2, centro_y - 2, meio + dx + 2, centro_y + 2], fill=pal["ouro"]
            )
    else:  # losango
        desenho.polygon(
            [(meio, centro_y - 6), (meio + 6, centro_y), (meio, centro_y + 6), (meio - 6, centro_y)],
            outline=pal["ouro"],
        )


def _papel(seed: str, W: int, H: int) -> Image.Image:
    """Fundo de papel creme com grão sutil. Determinístico pela seed (retry seguro)."""
    pw, ph = W // 3, H // 3
    peq = Image.new("RGB", (pw, ph), BILHETE_CREME)
    px = peq.load()
    rnd = random.Random(_fnv(seed + "papel"))
    for y in range(ph):
        for x in range(pw):
            n = rnd.randint(-8, 8)
            r, g, b = px[x, y]
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n - 2)))
    base = peq.resize((W, H), Image.Resampling.BILINEAR)
    vin = Image.radial_gradient("L").resize((W, H))
    escuro = Image.new("RGB", (W, H), BILHETE_CREME_BORDA)
    return Image.composite(escuro, base, vin.point(lambda v: int(v * 0.35)))


def _coracao(desenho: ImageDraw.ImageDraw, cx: int, cy: int, escala: float, cor) -> None:
    import math
    pts = []
    for i in range(0, 361, 5):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * escala, cy - y * escala))
    desenho.line(pts, fill=cor, width=4, joint="curve")


def _render_classico(texto: str, referencia: str, seed: str, W: int, H: int) -> Image.Image:
    pal = PALETAS[_fnv(seed + "pal") % len(PALETAS)]
    estilo_moldura = MOLDURAS[_fnv(seed + "mol") % len(MOLDURAS)]
    estilo_ornamento = ORNAMENTOS[_fnv(seed + "orn") % len(ORNAMENTOS)]

    # Layout depende do formato (quadrado do carrossel x vertical do Reel).
    vertical = H > W
    quote_y, quote_sz = (300, 210) if vertical else (150, 190)
    topo_texto, altura_util = (560, 820) if vertical else (300, 500)
    handle_y = H - 150 if vertical else H - 118
    font_max = 92 if vertical else 72

    imagem = _fundo(pal, W, H)
    desenho = ImageDraw.Draw(imagem)
    _moldura(desenho, pal, estilo_moldura, W, H)

    largura_util = W - 2 * MARGEM - 60
    aspas = _fonte("EBGaramond.ttf", quote_sz, "Medium")
    desenho.text((MARGEM + 18, quote_y), "“", font=aspas, fill=pal["ouro_fraco"])

    fonte_texto, linhas, esp = _ajustar(texto, desenho, largura_util, altura_util, font_max)
    bloco = len(linhas) * esp
    y = topo_texto + (altura_util - bloco) // 2
    for linha in linhas:
        desenho.text((W // 2, y), linha, font=fonte_texto, fill=pal["texto"], anchor="ma")
        y += esp

    _ornamento(desenho, y + 46, pal, estilo_ornamento, W // 2)
    fonte_referencia = _fonte("Cinzel.ttf", 44 if vertical else 40, "SemiBold")
    desenho.text((W // 2, y + 92), referencia.upper(), font=fonte_referencia, fill=pal["ouro"], anchor="ma")
    fonte_handle = _fonte("Cinzel.ttf", 23 if vertical else 21, "Regular")
    desenho.text((W // 2, handle_y), " ".join(HANDLE.upper()), font=fonte_handle, fill=pal["ouro_fraco"], anchor="ma")
    return imagem


def _render_bilhete(texto: str, referencia: str, seed: str, W: int, H: int) -> Image.Image:
    imagem = _papel(seed, W, H)
    desenho = ImageDraw.Draw(imagem)

    # Moldura fininha discreta (como no modelo).
    desenho.rectangle([26, 26, W - 27, H - 27], outline=BILHETE_TINTA, width=2)

    largura_util = W - 2 * (MARGEM + 24)
    altura_util = 900 if H > W else 620
    topo_texto = 470 if H > W else 250

    # Cursiva grande (Dancing Script). Entrelinha mais folgada.
    for tam in range(104, 51, -3):
        f = _fonte("DancingScript.ttf", tam, "SemiBold")
        linhas = _quebrar(texto, f, largura_util, desenho)
        esp = round(tam * 1.24)
        if len(linhas) * esp <= altura_util:
            break

    bloco = len(linhas) * esp
    y = topo_texto + (altura_util - bloco) // 2
    for linha in linhas:
        desenho.text((W // 2 + 2, y + 3), linha, font=f, fill=BILHETE_SOMBRA, anchor="ma")  # emboss
        desenho.text((W // 2, y), linha, font=f, fill=BILHETE_TINTA, anchor="ma")
        y += esp

    _coracao(desenho, W // 2, y + 58, 2.3, BILHETE_TINTA)

    fref = _fonte("DancingScript.ttf", 52 if H > W else 46, "Medium")
    desenho.text((W // 2, H - 180 if H > W else H - 150), referencia, font=fref, fill=BILHETE_TINTA, anchor="ma")
    fh = _fonte("DancingScript.ttf", 44 if H > W else 40, "Medium")
    desenho.text((W // 2, H - 108 if H > W else H - 90), HANDLE, font=fh, fill=BILHETE_HANDLE, anchor="ma")
    return imagem


def escolher_estilo(texto: str, seed: str) -> str:
    """Estilo do dia; versículo longo cai sempre no clássico (a cursiva aperta)."""
    estilo = ESTILOS[_fnv(seed + "estilo") % len(ESTILOS)]
    if estilo == "bilhete" and len(texto) > LIMITE_BILHETE:
        return "classico"
    return estilo


def _renderizar(texto: str, referencia: str, seed: str, W: int, H: int) -> Image.Image:
    if escolher_estilo(texto, seed) == "bilhete":
        return _render_bilhete(texto, referencia, seed, W, H)
    return _render_classico(texto, referencia, seed, W, H)


def _salvar(imagem: Image.Image, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    # JPEG (a Graph API só aceita JPEG). Subsampling 4:4:4 mantém o traço fino nítido.
    imagem.save(destino, "JPEG", quality=93, subsampling=0, optimize=True, progressive=False)
    return destino


def gerar(texto: str, referencia: str, destino: Path, seed: str | None = None) -> Path:
    """Cartaz VERTICAL 1080x1920 do post do dia (Reel/Story), estilo sorteado pela seed."""
    imagem = _renderizar(texto, referencia, seed or "", VERT_W, VERT_H)
    return _salvar(imagem, destino)


def gerar_quadrado(texto: str, referencia: str, destino: Path, seed: str | None = None) -> Path:
    """Cartaz QUADRADO 1080x1080 (para o carrossel do feed), estilo sorteado pela seed."""
    imagem = _renderizar(texto, referencia, seed or "", LADO, LADO)
    return _salvar(imagem, destino)
