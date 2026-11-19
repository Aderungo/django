"""Генерация лёгких JPEG-иллюстраций для карточек меню (480×360, ~30 КБ)."""

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / 'static' / 'img' / 'dishes'
OUT.mkdir(parents=True, exist_ok=True)

PALETTES = {
    'Салаты': [(78, 122, 58), (123, 168, 90), (201, 217, 110), (178, 62, 34), (236, 226, 198)],
    'Горячее': [(122, 74, 43), (169, 102, 58), (209, 154, 91), (86, 108, 57), (240, 226, 202)],
    'Десерты': [(217, 140, 154), (242, 198, 207), (246, 233, 205), (107, 63, 42), (183, 120, 84)],
    'Фуршет': [(214, 178, 106), (178, 62, 34), (123, 168, 90), (236, 226, 198), (122, 74, 43)],
    'Закуски': [(230, 196, 110), (178, 62, 34), (123, 168, 90), (246, 233, 205), (150, 94, 58)],
    'Напитки': [(242, 193, 78), (181, 118, 58), (163, 43, 28), (236, 226, 198), (86, 108, 57)],
}

DISHES = [
    ('caesar', 'Салат «Цезарь»', 'Салаты'),
    ('tomato-salad', 'Салат с томатами', 'Салаты'),
    ('greek-salad', 'Салат «Греческий»', 'Салаты'),
    ('medallion', 'Медальон из говядины', 'Горячее'),
    ('chicken-vegetables', 'Куриное филе с овощами', 'Горячее'),
    ('pilaf', 'Плов с бараниной', 'Горячее'),
    ('grilled-vegetables', 'Овощи на гриле', 'Горячее'),
    ('rustic-potatoes', 'Картофель по-деревенски', 'Горячее'),
    ('salmon-steak', 'Стейк из лосося', 'Горячее'),
    ('mashed-potatoes', 'Пюре картофельное', 'Горячее'),
    ('bento', 'Бенто-торт', 'Десерты'),
    ('dessert-table', 'Десертный стол', 'Десерты'),
    ('profiteroles', 'Профитроли', 'Десерты'),
    ('fruit-plate', 'Фруктовая тарелка', 'Десерты'),
    ('furshet-light', 'Фуршет «Лёгкий»', 'Фуршет'),
    ('furshet-premium', 'Фуршет «Премиум»', 'Фуршет'),
    ('canapes', 'Канапе ассорти', 'Фуршет'),
    ('sushi-set', 'Роллы ассорти', 'Фуршет'),
    ('tartlets', 'Тарталетки с лососем', 'Закуски'),
    ('vegetables', 'Овощная нарезка', 'Закуски'),
    ('cheese-board', 'Сырная тарелка', 'Закуски'),
    ('bruschetta', 'Брускетты ассорти', 'Закуски'),
    ('business-coffee', 'Кофе-брейк', 'Напитки'),
    ('tea-station', 'Чайная станция', 'Напитки'),
    ('lemonade', 'Лимонад «Цитрус»', 'Напитки'),
    ('mors', 'Морс клюквенный', 'Напитки'),
]

SCALE = 2
W, H = 480, 360


def gradient(size, top, bottom):
    image = Image.new('RGB', size, top)
    draw = ImageDraw.Draw(image)
    width, height = size
    for y in range(height):
        t = y / height
        color = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return image


def draw_plate(draw, palette):
    cx, cy = W // 2, H // 2 + 18
    for offset, alpha in ((14, (205, 186, 166)), (8, (222, 205, 188))):
        draw.ellipse([cx - 158 + offset // 2, cy - 104 + offset, cx + 158 - offset // 2, cy + 104 + offset],
                     fill=alpha)
    draw.ellipse([cx - 158, cy - 108, cx + 158, cy + 100], fill=(252, 249, 244),
                 outline=(226, 214, 200), width=3)
    draw.ellipse([cx - 118, cy - 78, cx + 118, cy + 72], fill=(248, 243, 236),
                 outline=(235, 225, 212), width=2)


def draw_food(draw, palette, rng, category):
    cx, cy = W // 2, H // 2 + 18
    if category == 'Напитки':
        draw_drink(draw, palette, rng)
        return
    count = rng.randint(7, 11)
    for _ in range(count):
        angle = rng.uniform(0, math.tau)
        radius = rng.uniform(0, 92)
        x = cx + math.cos(angle) * radius
        y = cy + 6 + math.sin(angle) * radius * 0.62
        rx = rng.uniform(16, 34)
        ry = rx * rng.uniform(0.5, 0.95)
        color = rng.choice(palette)
        draw.ellipse([x - rx, y - ry, x + rx, y + ry], fill=color)
        draw.ellipse([x - rx * 0.55, y - ry * 0.6, x + rx * 0.5, y + ry * 0.15],
                     fill=tuple(min(255, c + 22) for c in color))
    for _ in range(18):
        x = cx + rng.uniform(-100, 100)
        y = cy + rng.uniform(-60, 62)
        r = rng.uniform(2, 5)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=rng.choice(palette))
    for _ in range(4):
        x = cx + rng.uniform(-70, 70)
        y = cy + rng.uniform(-40, 40)
        draw.arc([x - 26, y - 14, x + 26, y + 14], 20, 160, fill=(255, 255, 255), width=3)


def draw_drink(draw, palette, rng):
    cx, cy = W // 2, H // 2 + 10
    glass = [(cx - 66, cy - 96), (cx + 66, cy - 96), (cx + 50, cy + 82), (cx - 50, cy + 82)]
    draw.ellipse([cx - 88, cy + 78, cx + 88, cy + 104], fill=(214, 199, 182))
    draw.polygon(glass, fill=(250, 250, 248), outline=(214, 205, 194))
    liquid = rng.choice(palette[:3])
    draw.polygon([(cx - 58, cy - 30), (cx + 58, cy - 30), (cx + 46, cy + 74), (cx - 46, cy + 74)],
                 fill=liquid)
    draw.ellipse([cx - 58, cy - 44, cx + 58, cy - 18], fill=tuple(min(255, c + 18) for c in liquid))
    for _ in range(5):
        x = cx + rng.uniform(-40, 40)
        y = cy + rng.uniform(-10, 60)
        r = rng.uniform(4, 8)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))
    draw.line([(cx + 22, cy - 92), (cx + 34, cy - 140)], fill=(178, 62, 34), width=5)


def make(slug, category, index):
    rng = random.Random(f'{slug}-16')
    palette = PALETTES[category]
    size = (W * SCALE, H * SCALE)
    image = gradient(size, (247, 239, 229), (228, 211, 192))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, int(H * 0.78 * SCALE), size[0], size[1]], fill=(214, 195, 174))
    overlay = Image.new('RGBA', size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    draw = ImageDraw.Draw(image)
    # рисуем в масштабе, затем уменьшаем
    scaled = Image.new('RGB', size, (247, 239, 229))
    sdraw = ImageDraw.Draw(scaled)
    # повторяем фон в полном размере
    for y in range(size[1]):
        t = y / size[1]
        color = tuple(round(247 + (228 - 247) * t) for _ in range(3))
        sdraw.line([(0, y), (size[0], y)], fill=color)
    sdraw.rectangle([0, int(H * 0.78 * SCALE), size[0], size[1]], fill=(216, 197, 176))

    class ScaledDraw:
        def __init__(self, d):
            self.d = d

        def ellipse(self, box, **kw):
            self.d.ellipse([v * SCALE for v in box], **kw)

        def polygon(self, points, **kw):
            self.d.polygon([(x * SCALE, y * SCALE) for x, y in points], **kw)

        def arc(self, box, start, end, **kw):
            self.d.arc([v * SCALE for v in box], start, end, **kw)

        def line(self, points, **kw):
            if 'width' in kw:
                kw['width'] = kw['width'] * SCALE
            self.d.line([(x * SCALE, y * SCALE) for x, y in points], **kw)

    sd = ScaledDraw(sdraw)
    # виньетка
    glow = Image.new('L', size, 0)
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([size[0] * 0.1, size[1] * 0.05, size[0] * 0.9, size[1] * 0.9], fill=60)
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    warm = Image.new('RGB', size, (255, 246, 234))
    scaled = Image.composite(warm, scaled, glow)

    sdraw = ImageDraw.Draw(scaled)
    sd = ScaledDraw(sdraw)
    draw_plate(sd, palette)
    draw_food(sd, palette, rng, category)

    image = scaled.resize((W, H), Image.LANCZOS)
    image.save(OUT / f'{slug}.jpg', format='JPEG', quality=78, optimize=True, progressive=True)
    return (OUT / f'{slug}.jpg').stat().st_size


total = 0
for index, (slug, name, category) in enumerate(DISHES):
    size = make(slug, category, index)
    total += size
    print(f'{slug:24} {category:10} {size // 1024:3} КБ')

print(f'Всего: {len(DISHES)} файлов, {total // 1024} КБ')
