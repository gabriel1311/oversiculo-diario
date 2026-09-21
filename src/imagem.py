"""Renderiza o post 1080x1080 a partir do versículo.

O visual varia por dia — paleta, ornamento e moldura — para o feed não ficar
engessado, mas a estrutura é sempre a mesma (versículo centralizado, referência,
assinatura, moldura dourada). A variação é semeada pela data: o mesmo dia sempre
sai igual (retry seguro), dias diferentes saem diferentes.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageStat


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
FOTOS_DIR = RAIZ / "fotos"

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

# Estilos que se alternam por dia:
#   classico = fundo escuro + serifada + dourado
#   livro    = cinza clean + serifada + última linha grifada de amarelo
#   foto     = paisagem escurecida + texto branco
#   luz      = paisagem clara + texto escuro + frase-chave em cursiva azul (21/09)
ESTILOS = ["classico", "livro", "foto", "luz"]  # bilhete aposentado 31/08; renderizador mantido p/ overrides antigos

# A cursiva do bilhete só fica boa em versículo curto/médio; acima disso o texto
# aperta e perde legibilidade, então versículos longos vão sempre no clássico.
LIMITE_BILHETE = 180

# Paleta do estilo bilhete.
BILHETE_CREME = (236, 228, 210)
BILHETE_CREME_BORDA = (206, 196, 176)
BILHETE_TINTA = (36, 44, 122)          # azul caneta
BILHETE_SOMBRA = (196, 190, 176)       # sombra suave (emboss)
BILHETE_HANDLE = (92, 98, 150)

# Paleta do estilo "livro" (cinza clean + serifada + grifo amarelo).
LIVRO_BG = (216, 214, 208)
LIVRO_BORDA = (196, 194, 188)
LIVRO_TEXTO = (38, 36, 34)
LIVRO_REF = (18, 18, 18)
LIVRO_GRIFO = (216, 228, 96)
LIVRO_HANDLE = (120, 120, 112)


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


def _papel(seed: str, W: int, H: int, base_cor=BILHETE_CREME, borda_cor=BILHETE_CREME_BORDA,
           forca_vin: float = 0.35) -> Image.Image:
    """Fundo de papel com grão sutil. Determinístico pela seed (retry seguro)."""
    pw, ph = W // 3, H // 3
    peq = Image.new("RGB", (pw, ph), base_cor)
    px = peq.load()
    rnd = random.Random(_fnv(seed + "papel"))
    for y in range(ph):
        for x in range(pw):
            n = rnd.randint(-8, 8)
            r, g, b = px[x, y]
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n - 2)))
    base = peq.resize((W, H), Image.Resampling.BILINEAR)
    vin = Image.radial_gradient("L").resize((W, H))
    escuro = Image.new("RGB", (W, H), borda_cor)
    return Image.composite(escuro, base, vin.point(lambda v: int(v * forca_vin)))


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
    """Estilo do dia. Se a inteligência já aprendeu (dados/inteligencia.json),
    a escolha é ponderada pelos estilos que mais rendem — determinística pela
    data e sempre com exploração. Sem aprendizado, rotação por hash puro."""
    from src import inteligencia
    estilo = inteligencia.escolher_estilo_ponderado(seed)
    if estilo is None:
        estilo = ESTILOS[_fnv(seed + "estiloD") % len(ESTILOS)]
    if estilo == "luz" and len(texto) > LIMITE_LUZ:
        estilo = "foto"  # versículo longo encolhe demais sobre o céu
    return estilo


def _render_livro(texto: str, referencia: str, seed: str, W: int, H: int) -> Image.Image:
    """Estilo 'livro': fundo cinza clean, serifada alinhada à esquerda, referência
    em negrito no topo e a última linha grifada de amarelo (marca-texto)."""
    imagem = _papel(seed, W, H, LIVRO_BG, LIVRO_BORDA, forca_vin=0.22)
    desenho = ImageDraw.Draw(imagem)

    margem_l = 130
    largura_util = W - 2 * margem_l

    fonte_ref = _fonte("EBGaramond.ttf", 70, "ExtraBold")
    ref_alt = 78
    gap = 46

    # Ajuste do corpo do texto (serifada), alinhado à esquerda.
    for tam in range(64, 33, -2):
        fonte = _fonte("EBGaramond.ttf", tam, "Regular")
        linhas = _quebrar(texto, fonte, largura_util, desenho)
        esp = round(tam * 1.5)
        if ref_alt + gap + len(linhas) * esp <= (1180 if H > W else 640):
            break

    bloco = ref_alt + gap + len(linhas) * esp
    y0 = (H - bloco) // 2
    desenho.text((margem_l, y0), referencia.upper(), font=fonte_ref, fill=LIVRO_REF, anchor="la")

    y = y0 + ref_alt + gap
    for idx, linha in enumerate(linhas):
        if idx == len(linhas) - 1:  # grifa a última linha (o "fecho")
            larg = desenho.textlength(linha, font=fonte)
            desenho.rectangle(
                [margem_l - 6, y + esp * 0.06, margem_l + larg + 10, y + esp * 0.92],
                fill=LIVRO_GRIFO,
            )
        desenho.text((margem_l, y), linha, font=fonte, fill=LIVRO_TEXTO, anchor="la")
        y += esp

    fonte_handle = _fonte("EBGaramond.ttf", 34, "Medium")
    desenho.text((W - margem_l, H - (150 if H > W else 120)), HANDLE, font=fonte_handle,
                 fill=LIVRO_HANDLE, anchor="ra")
    return imagem


# Estilo "foto": versículo em branco sobre uma foto livre, com escurecimento.
FOTOS = [
    "foto-campo.jpg", "foto-montanha-rosa.jpg", "foto-floresta.jpg",
    "foto-ceu-dourado.jpg", "foto-praia.jpg",
    # Leva de 03/09 (Pixabay _1280 ampliada p/ 1080x1920; ver fotos/CREDITOS.md):
    "foto-lago-nevoa.jpg", "foto-arvore-nevoa.jpg", "foto-ceu-estrelado.jpg",
    "foto-trigal.jpg", "foto-cachoeira.jpg",
    "foto-raios-floresta.jpg", "foto-girassois.jpg", "foto-montanha-sol.jpg",
    "foto-falesia.jpg", "foto-lavanda.jpg",
]
FOTO_TEXTO = (247, 246, 242)
FOTO_HANDLE = (232, 230, 224)


def _foto_fundo(seed: str, W: int, H: int) -> Image.Image:
    nomes = [f for f in FOTOS if (FOTOS_DIR / f).exists()]
    if not nomes:
        return Image.new("RGB", (W, H), (28, 28, 30))
    nome = nomes[_fnv(seed + "foto") % len(nomes)]
    im = Image.open(FOTOS_DIR / nome).convert("RGB")
    escala = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * escala), round(im.height * escala)), Image.Resampling.LANCZOS)
    x = (im.width - W) // 2
    y = (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H))
    # Esmaece: dessatura um pouco e escurece bastante, para o texto branco
    # contrastar bem sobre qualquer área da foto.
    cinza = ImageOps.grayscale(im).convert("RGB")
    im = Image.blend(im, cinza, 0.25)
    return Image.blend(im, Image.new("RGB", (W, H), (0, 0, 0)), 0.55)


def _foto_camadas(texto: str, referencia: str, seed: str, W: int, H: int) -> tuple[Image.Image, list[Image.Image]]:
    """Fundo (foto escurecida) + uma camada RGBA com todo o texto — no vídeo a
    foto se move devagar e o texto fica parado por cima."""
    fundo = _foto_fundo(seed, W, H)
    sombra, d_sombra = _camada(W, H, (0, 0, 0))
    frente, desenho = _camada(W, H, FOTO_TEXTO)
    vertical = H > W
    largura_util = W - 2 * MARGEM - 40
    altura_util = 820 if vertical else 500
    topo = 560 if vertical else 300

    fonte_texto, linhas, esp = _ajustar(texto, desenho, largura_util, altura_util, 84)
    bloco = len(linhas) * esp
    y = topo + (altura_util - bloco) // 2
    for linha in linhas:
        d_sombra.text((W // 2 + 2, y + 3), linha, font=fonte_texto, fill=(0, 0, 0), anchor="ma")
        desenho.text((W // 2, y), linha, font=fonte_texto, fill=FOTO_TEXTO, anchor="ma")
        y += esp

    desenho.line([W // 2 - 70, y + 42, W // 2 + 70, y + 42], fill=FOTO_TEXTO, width=2)
    fonte_ref = _fonte("Cinzel.ttf", 42 if vertical else 36, "SemiBold")
    desenho.text((W // 2, y + 74), referencia.upper(), font=fonte_ref, fill=FOTO_TEXTO, anchor="ma")
    fonte_handle = _fonte("Cinzel.ttf", 22, "Regular")
    desenho.text((W // 2, H - (150 if vertical else 118)), " ".join(HANDLE.upper()),
                 font=fonte_handle, fill=FOTO_HANDLE, anchor="ma")
    return fundo, [Image.alpha_composite(sombra, frente)]


def _render_foto(texto: str, referencia: str, seed: str, W: int, H: int) -> Image.Image:
    return _compor(*_foto_camadas(texto, referencia, seed, W, H))


# Estilo "luz": foto CLARA (sem escurecer), texto escuro serifado sobre o céu e
# uma frase-chave do versículo em cursiva azul; divisor com coração e o @.
# Só fotos com céu/topo claro — nas escuras o véu branco fica encardido.
FOTOS_LUZ = [
    "foto-campo.jpg", "foto-lago-nevoa.jpg", "foto-montanha-rosa.jpg",
    "foto-praia.jpg", "foto-trigal.jpg", "foto-lavanda.jpg",
    "foto-arvore-nevoa.jpg", "foto-montanha-sol.jpg", "foto-falesia.jpg",
]
LIMITE_LUZ = 200
LUZ_TEXTO = (30, 34, 44)
LUZ_AZUL = (34, 66, 108)
LUZ_HANDLE = (52, 58, 70)
_PONTUACAO = ",;.:!?"


def _quebrar_equilibrado(texto, fonte, largura_maxima, desenho) -> list[str]:
    """Mesma contagem de linhas do _quebrar, mas com larguras parecidas — evita
    linha órfã de uma palavra só ("e", "que") logo antes da cursiva."""
    linhas = _quebrar(texto, fonte, largura_maxima, desenho)
    for largura in range(largura_maxima - 40, largura_maxima // 3, -40):
        tentativa = _quebrar(texto, fonte, largura, desenho)
        if len(tentativa) > len(linhas) or any(
            desenho.textlength(l, font=fonte) > largura_maxima for l in tentativa
        ):
            break
        linhas = tentativa
    return linhas


def _enfase(texto: str, referencia: str) -> tuple[str, str, str]:
    """Divide o versículo em (antes, ênfase, depois). A ênfase vem de
    dados/enfases.json (pré-gerada, por referência); sem entrada válida, tenta a
    última oração se for curta — senão o versículo sai inteiro sem cursiva."""
    import json
    frase = ""
    try:
        frase = json.loads((RAIZ / "dados" / "enfases.json").read_text(encoding="utf-8")).get(referencia, "")
    except (OSError, ValueError):
        pass
    if not frase or frase not in texto:
        cauda = texto.rstrip(_PONTUACAO + " ")
        corte = max(cauda.rfind(c) for c in ",;:")
        frase = cauda[corte + 1:].strip() if corte >= 0 else ""
        if not 8 <= len(frase) <= 28:
            return texto, "", ""
    antes, depois = texto.split(frase, 1)
    # Pontuação colada depois da ênfase fica na linha dela (não abre a linha seguinte).
    while depois and depois[0] in _PONTUACAO:
        frase, depois = frase + depois[0], depois[1:]
    return antes.strip(), frase, depois.strip()


def _luz_fundo(seed: str, W: int, H: int, fim_bloco: int) -> Image.Image:
    nomes = [f for f in FOTOS_LUZ if (FOTOS_DIR / f).exists()]
    if not nomes:
        return Image.new("RGB", (W, H), (236, 232, 224))
    im = Image.open(FOTOS_DIR / nomes[_fnv(seed + "luz") % len(nomes)]).convert("RGB")
    escala = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * escala), round(im.height * escala)), Image.Resampling.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H))
    im = ImageEnhance.Color(im).enhance(1.12)
    # Véu claro e morno atrás do texto, só o quanto a foto precisa: céu já claro
    # quase não leva véu; topo escuro leva mais. Cheio até o fim do bloco, some em 360 px.
    lum = ImageStat.Stat(im.crop((0, 0, W, max(1, fim_bloco))).convert("L")).mean[0]
    alfa = min(215, max(70, round(255 * (222 - lum) / max(1, 252 - lum))))
    veu = Image.new("L", (1, H))
    px = veu.load()
    for yy in range(H):
        forca = 1.0 if yy <= fim_bloco else max(0.0, 1 - (yy - fim_bloco) / 360) ** 2
        px[0, yy] = int(alfa * forca)
    return Image.composite(Image.new("RGB", (W, H), (255, 250, 242)), im, veu.resize((W, H)))


def _camada(W: int, H: int, cor) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Camada transparente já "tingida" com a cor do texto: o antialias do PIL
    interpola os 4 canais, então fundo preto-transparente escureceria as bordas."""
    im = Image.new("RGBA", (W, H), tuple(cor) + (0,))
    return im, ImageDraw.Draw(im)


def _luz_camadas(texto: str, referencia: str, seed: str, W: int, H: int) -> tuple[Image.Image, list[Image.Image]]:
    """Fundo (RGB) + 3 camadas RGBA na ordem em que entram no vídeo: começo do
    versículo, frase-chave em cursiva, e o resto (fim do texto, divisor, referência, @)."""
    import math
    vertical = H > W
    largura_util = W - 2 * MARGEM - 40
    topo, altura_util = (290, 1020) if vertical else (90, 830)
    rodape = 250  # divisor + referência + @
    antes, frase, depois = _enfase(texto, referencia)

    rascunho = ImageDraw.Draw(Image.new("RGB", (W, H)))
    for tam in range(92 if vertical else 72, 33, -2):
        fonte = _fonte("EBGaramond.ttf", tam, "Medium")
        cursiva = _fonte("DancingScript.ttf", round(tam * 1.6), "Bold")
        esp, esp_c = round(tam * 1.34), round(tam * 1.6 * 1.18)
        l_antes = _quebrar_equilibrado(antes, fonte, largura_util, rascunho)
        l_frase = _quebrar_equilibrado(frase, cursiva, largura_util, rascunho)
        l_depois = _quebrar_equilibrado(depois, fonte, largura_util, rascunho)
        alto = (len(l_antes) + len(l_depois)) * esp + len(l_frase) * esp_c
        if alto + rodape <= altura_util:
            break

    y = topo + (altura_util - alto - rodape) // 2
    fundo = _luz_fundo(seed, W, H, y + alto + rodape)

    c_antes, d = _camada(W, H, LUZ_TEXTO)
    for linha in l_antes:
        d.text((W // 2, y), linha, font=fonte, fill=LUZ_TEXTO, anchor="ma")
        y += esp
    c_frase, d = _camada(W, H, LUZ_AZUL)
    for linha in l_frase:
        d.text((W // 2, y), linha, font=cursiva, fill=LUZ_AZUL, anchor="ma")
        y += esp_c
    c_texto, d = _camada(W, H, LUZ_TEXTO)
    for linha in l_depois:
        d.text((W // 2, y), linha, font=fonte, fill=LUZ_TEXTO, anchor="ma")
        y += esp

    # Divisor: traço — coração cheio — traço; referência; @.
    c_azul, d = _camada(W, H, LUZ_AZUL)
    cy = y + 62
    d.line([W // 2 - 150, cy, W // 2 - 44, cy], fill=LUZ_AZUL, width=2)
    d.line([W // 2 + 44, cy, W // 2 + 150, cy], fill=LUZ_AZUL, width=2)
    d.polygon([
        (W // 2 + 16 * math.sin(t) ** 3 * 1.15,
         cy + 2 - (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) * 1.15)
        for t in (math.radians(i) for i in range(0, 360, 5))
    ], fill=LUZ_AZUL)
    fonte_ref = _fonte("Cinzel.ttf", 44 if vertical else 38, "SemiBold")
    d.text((W // 2, cy + 44), referencia.upper(), font=fonte_ref, fill=LUZ_AZUL, anchor="ma")
    c_handle, d = _camada(W, H, LUZ_HANDLE)
    fonte_handle = _fonte("EBGaramond.ttf", 34 if vertical else 30, "Medium")
    d.text((W // 2, cy + 122), HANDLE, font=fonte_handle, fill=LUZ_HANDLE, anchor="ma")

    c_resto = Image.alpha_composite(Image.alpha_composite(c_texto, c_azul), c_handle)
    return fundo, [c_antes, c_frase, c_resto]


def _compor(fundo: Image.Image, camadas: list[Image.Image]) -> Image.Image:
    imagem = fundo.convert("RGBA")
    for camada in camadas:
        imagem = Image.alpha_composite(imagem, camada)
    return imagem.convert("RGB")


def _render_luz(texto: str, referencia: str, seed: str, W: int, H: int) -> Image.Image:
    return _compor(*_luz_camadas(texto, referencia, seed, W, H))


def _renderizar(texto: str, referencia: str, seed: str, W: int, H: int) -> Image.Image:
    estilo = escolher_estilo(texto, seed)
    if estilo == "luz":
        return _render_luz(texto, referencia, seed, W, H)
    if estilo == "bilhete":
        return _render_bilhete(texto, referencia, seed, W, H)
    if estilo == "livro":
        return _render_livro(texto, referencia, seed, W, H)
    if estilo == "foto":
        return _render_foto(texto, referencia, seed, W, H)
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


def gerar_camadas(texto: str, referencia: str, pasta: Path, seed: str | None = None) -> list[Path] | None:
    """Camadas do cartaz vertical para o vídeo animado: [fundo.jpg, camada1.png, …].
    Só os estilos com foto têm camadas; os demais devolvem None (vídeo parado)."""
    estilo = escolher_estilo(texto, seed or "")
    if estilo == "luz":
        fundo, camadas = _luz_camadas(texto, referencia, seed or "", VERT_W, VERT_H)
    elif estilo == "foto":
        fundo, camadas = _foto_camadas(texto, referencia, seed or "", VERT_W, VERT_H)
    else:
        return None
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = [_salvar(fundo, pasta / "fundo.jpg")]
    for i, camada in enumerate(camadas, 1):
        camada.save(pasta / f"camada{i}.png")
        caminhos.append(pasta / f"camada{i}.png")
    return caminhos


def gerar_quadrado(texto: str, referencia: str, destino: Path, seed: str | None = None) -> Path:
    """Cartaz QUADRADO 1080x1080 (para o carrossel do feed), estilo sorteado pela seed."""
    imagem = _renderizar(texto, referencia, seed or "", LADO, LADO)
    return _salvar(imagem, destino)
