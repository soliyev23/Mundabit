"""Hayot statistikasi va "Hayot Kalendari" posteri (oq/sutrang, foto-uslub).

Har qator — bir kalendar yili (boshlanishi — tug'ilgan yil), har katak — bir
hafta. Yashalgan baholanmagan haftalar kulrang katak + qizil "x", samarali
hafta yashil, behuda qizil, joriy hafta losos rang, kelajak oq katak.
"""
import io
from dataclasses import dataclass
from functools import lru_cache
from datetime import date, timedelta

from PIL import Image, ImageDraw, ImageFont

from config import WEEKS_PER_YEAR
from texts import BOT, POSTER, age_label, fmt_date

# Palitra (foto-uslub, RGB)
BG = (250, 247, 242)          # sutrang fon
INK = (58, 58, 58)            # asosiy matn
ACCENT = (169, 68, 66)        # sarlavha urg'usi (qizg'ish)
META = (140, 138, 134)        # ikkinchi darajali matn
LABEL = (158, 154, 148)       # yil/yosh yozuvlari
CELL_GRAY = (216, 213, 208)   # yashalgan, baholanmagan katak
XMARK = (178, 84, 76)         # katak ichidagi "x"
GOOD = (123, 168, 143)        # samarali hafta
BAD = (194, 91, 84)           # behuda hafta
CURRENT = (232, 137, 107)     # joriy hafta
FUTURE_FILL = (255, 255, 255)
FUTURE_EDGE = (223, 219, 212)
OUT_FILL = (246, 243, 237)    # tug'ilishdan oldingi / umrdan keyingi kataklar
OUT_EDGE = (238, 234, 227)


@dataclass
class LifeStats:
    birth_date: date
    today: date
    expectancy_years: int
    total_weeks: int
    days_lived: int
    weeks_lived: int
    weeks_left: int
    years_lived: int
    pct_lived: float
    pct_left: float
    over_expectancy: bool


def life_stats(birth_date: date, expectancy_years: int,
               today: date | None = None) -> LifeStats:
    today = today or date.today()
    total_weeks = expectancy_years * WEEKS_PER_YEAR
    days_lived = (today - birth_date).days
    weeks_lived = days_lived // 7
    weeks_left = max(0, total_weeks - weeks_lived)

    pct_lived = min(100.0, weeks_lived / total_weeks * 100)
    years_lived = (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )
    return LifeStats(
        birth_date=birth_date,
        today=today,
        expectancy_years=expectancy_years,
        total_weeks=total_weeks,
        days_lived=days_lived,
        weeks_lived=weeks_lived,
        weeks_left=weeks_left,
        years_lived=years_lived,
        pct_lived=round(pct_lived, 1),
        pct_left=round(100 - pct_lived, 1),
        over_expectancy=weeks_lived >= total_weeks,
    )


def _load_font(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _serif(size: int, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    name = "Georgia"
    dv = "DejaVuSerif"
    if bold and italic:
        name, dv = "Georgia Bold Italic", "DejaVuSerif-BoldItalic"
    elif bold:
        name, dv = "Georgia Bold", "DejaVuSerif-Bold"
    elif italic:
        name, dv = "Georgia Italic", "DejaVuSerif-Italic"
    return _load_font(
        [
            f"/System/Library/Fonts/Supplemental/{name}.ttf",          # macOS
            f"/usr/share/fonts/dejavu-serif-fonts/{dv}.ttf",          # RHEL / Oracle Linux
            f"/usr/share/fonts/truetype/dejavu/{dv}.ttf",             # Debian / Ubuntu
            "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        ],
        size,
    )


def _mono(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Courier New Bold" if bold else "Courier New"
    dv = "DejaVuSansMono-Bold" if bold else "DejaVuSansMono"
    return _load_font(
        [
            f"/System/Library/Fonts/Supplemental/{name}.ttf",          # macOS
            f"/usr/share/fonts/dejavu-sans-mono-fonts/{dv}.ttf",      # RHEL / Oracle Linux
            f"/usr/share/fonts/truetype/dejavu/{dv}.ttf",             # Debian / Ubuntu
            "/System/Library/Fonts/Menlo.ttc",
        ],
        size,
    )


@lru_cache(maxsize=None)
def _cell_sprite(size: int, radius: int, fill: tuple, outline: tuple | None = None,
                 xmark: bool = False) -> Image.Image:
    """Bitta katakning tayyor rasmi. Burchaklari fon rangida: barcha kataklar bir
    xil shaklda va bir joyga tushgani uchun ustma-ust qo'yilganda ham burchak
    piksellari baribir fon bo'ladi — natija to'g'ridan-to'g'ri chizilgani bilan
    piksel-piksel bir xil, lekin chizish o'rniga tayyor nusxa qo'yiladi."""
    spr = Image.new("RGB", (size + 1, size + 1), BG)
    d = ImageDraw.Draw(spr)
    d.rounded_rectangle([0, 0, size, size], radius=radius, fill=fill, outline=outline)
    if xmark:
        d.line([4, 4, size - 4, size - 4], fill=XMARK, width=2)
        d.line([size - 4, 4, 4, size - 4], fill=XMARK, width=2)
    return spr


@lru_cache(maxsize=None)
def _empty_row(cell: int, gap: int, radius: int) -> Image.Image:
    """Bir yillik bo'sh qator (52 ta "umrdan tashqari" katak) — fon uchun
    3 800 ta katak o'rniga 73 ta qator tasmasi qo'yiladi."""
    pitch = cell + gap
    row = Image.new("RGB", (WEEKS_PER_YEAR * pitch - gap + 1, cell + 1), BG)
    spr = _cell_sprite(cell, radius, OUT_FILL, OUT_EDGE)
    for col in range(WEEKS_PER_YEAR):
        row.paste(spr, (col * pitch, 0))
    return row


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _draw_segments(img: Image.Image, y: int, segments: list[tuple], center_w: int) -> None:
    """[(matn, font, rang), ...] segmentlarni gorizontal markazlab chizadi."""
    d = ImageDraw.Draw(img)
    total = sum(d.textlength(s[0], font=s[1]) for s in segments)
    x = (center_w - total) / 2
    for text, font, color in segments:
        d.text((x, y), text, font=font, fill=color)
        x += d.textlength(text, font=font)


def render_life_poster(stats: LifeStats, ratings: dict[int, str] | None = None,
                       lang: str = "uz", gender: str | None = None) -> bytes:
    ratings = ratings or {}
    p = POSTER.get(lang, POSTER["uz"])

    cell, gap = 16, 4
    pitch = cell + gap
    grid_w = WEEKS_PER_YEAR * pitch - gap

    birth = stats.birth_date
    last_week_start = birth + timedelta(days=(stats.total_weeks - 1) * 7)
    n_rows = last_week_start.year - birth.year + 1
    grid_h = n_rows * pitch - gap

    ml, mr = 190, 56              # chapda yil/yosh yozuvlari uchun joy
    width = ml + grid_w + mr

    f_title = _serif(58, bold=True)
    f_title2 = _serif(58, bold=True, italic=True)
    f_meta = _mono(21)
    f_stats = _mono(24)
    f_stats_b = _mono(24, bold=True)
    f_label = _mono(15)

    title_y = 52
    meta_y = title_y + 82
    stats_y = meta_y + 44
    grid_y = stats_y + 60
    height = grid_y + grid_h + 64

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    # ── Sarlavha: "Hayot Kalendari" ──
    w1 = d.textlength(p["title1"], font=f_title)
    w2 = d.textlength(p["title2"], font=f_title2)
    tx = (width - w1 - w2) / 2
    d.text((tx, title_y), p["title1"], font=f_title, fill=INK)
    d.text((tx + w1, title_y), p["title2"], font=f_title2, fill=ACCENT)

    # ── Sanalar (jinsga mos "Родился/Родилась") ──
    born_label = p["born_f"] if gender == "f" else p["born_m"]
    line1 = (f"{born_label}: {fmt_date(birth, lang)}   ·   "
             f"{p['today']}: {fmt_date(stats.today, lang)}")
    lw = d.textlength(line1, font=f_meta)
    d.text(((width - lw) / 2, meta_y), line1, font=f_meta, fill=META)

    # ── Statistika: O'tgan: N hafta (X%) · Qoldi: M hafta (Y%) ──
    _draw_segments(img, stats_y, [
        (p["stats_past"], f_stats, INK),
        (_fmt(stats.weeks_lived), f_stats_b, ACCENT),
        (p["stats_week"], f_stats, INK),
        (f" ({stats.pct_lived}%)", f_stats, META),
        ("   ·   ", f_stats, META),
        (p["stats_left"], f_stats, INK),
        (_fmt(stats.weeks_left), f_stats_b, INK),
        (p["stats_week"], f_stats, INK),
        (f" ({stats.pct_left}%)", f_stats, META),
    ], width)

    # ── Katakchalar (kalendar bo'yicha) ──
    radius = 4
    sprites = {
        "future": _cell_sprite(cell, radius, FUTURE_FILL, FUTURE_EDGE),
        "gray": _cell_sprite(cell, radius, CELL_GRAY, xmark=True),
        "good": _cell_sprite(cell, radius, GOOD),
        "bad": _cell_sprite(cell, radius, BAD),
        "current": _cell_sprite(cell, radius, CURRENT),
    }

    def put(kind: str, row: int, col: int) -> None:
        img.paste(sprites[kind], (ml + col * pitch, grid_y + row * pitch))

    # Barcha kataklarni "umrdan tashqari" uslubda chizamiz, keyin ustiga
    # hayot haftalarini qo'yamiz (birinchi qatorda tug'ilishgacha bo'lgan va
    # oxirgi qatorda umrdan keyingi kataklar shu holicha qoladi).
    for row in range(n_rows):
        year = birth.year + row
        label = age_label(year, row, lang)
        lw = d.textlength(label, font=f_label)
        d.text((ml - 18 - lw, grid_y + row * pitch + 1), label, font=f_label, fill=LABEL)
        img.paste(_empty_row(cell, gap, radius), (ml, grid_y + row * pitch))

    for i in range(stats.total_weeks):
        ws = birth + timedelta(days=i * 7)
        row = ws.year - birth.year
        if row >= n_rows:
            break
        col = min(WEEKS_PER_YEAR - 1, (ws - date(ws.year, 1, 1)).days // 7)
        if i < stats.weeks_lived:
            put(ratings.get(i, "gray"), row, col)      # 'good' | 'bad' | 'gray'
        elif i == stats.weeks_lived and not stats.over_expectancy:
            put("current", row, col)
        else:
            put("future", row, col)

    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()


def stats_caption(stats: LifeStats, lang: str = "uz") -> str:
    tpl = BOT.get(lang, BOT["uz"])["caption"]
    return tpl.format(
        lived=_fmt(stats.weeks_lived),
        left=_fmt(stats.weeks_left),
        p=stats.pct_lived,
        q=stats.pct_left,
    )
