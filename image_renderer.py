"""
将计算结果渲染为图片 — 紫色基调简约风格
"""

import os
from datetime import datetime
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

# ── 字体 ─────────────────────────────────────
import platform
_IS_WIN = platform.system() == "Windows"
if _IS_WIN:
    _FONT_DIR = "C:/Windows/Fonts"
    _FONT = "msyh.ttc"
    _FONT_BOLD = "msyhbd.ttc"
else:
    _FONT_DIR = "/usr/share/fonts/opentype/noto"
    _FONT = "NotoSansCJK-Regular.ttc"
    _FONT_BOLD = "NotoSansCJK-Bold.ttc"
FONT_PATH = os.environ.get("FONT_PATH", os.path.join(_FONT_DIR, _FONT))
FONT_BOLD_PATH = os.environ.get("FONT_BOLD_PATH", os.path.join(_FONT_DIR, _FONT_BOLD))
WATERMARK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon", "头像.png")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_images")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def _font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(FONT_BOLD_PATH if bold else FONT_PATH, size)
    except (OSError, IOError):
        # Linux 上可能没有粗体字体文件，降级
        return ImageFont.truetype(FONT_PATH, size)


def _draw_rounded_rect(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def render_text_to_image(title: str, lines: list[str],
                       query_info: Optional[dict] = None,
                       warning: str = "") -> str:
    title_font = _font(20, bold=True)
    line_font = _font(16)
    # 测量宽度
    pad = 28
    title_h = 56
    line_h = 30
    min_w = 360
    all_text = [title] + lines
    text_widths = []
    for t in all_text:
        bbox = line_font.getbbox(t)
        text_widths.append(bbox[2] - bbox[0])
    max_text_w = max(text_widths) if text_widths else 300
    canvas_w = max(max_text_w + pad * 2, min_w)
    body_h = len(lines) * line_h + 16

    # 底部留白：警告 + 装饰线 + 查询信息
    extra_bottom = 0
    if warning:
        # 测量警告文字宽度
        warn_font_tmp = _font(13, bold=True)
        warn_bbox = warn_font_tmp.getbbox(warning)
        warn_w = warn_bbox[2] - warn_bbox[0]
        canvas_w = max(canvas_w, warn_w + (pad + 8) * 2)
        extra_bottom += 10 + 13 + 8  # gap + warn_h + gap
    extra_bottom += 3 + 8  # line + gap
    if query_info:
        extra_bottom += 12 + 4  # footer_h + gap
        if "url" in query_info:
            url_font = _font(10)
            url_bbox = url_font.getbbox(query_info["url"])
            url_w = url_bbox[2] - url_bbox[0]
            canvas_w = max(canvas_w, url_w + pad * 2)
            extra_bottom += 30
    else:
        extra_bottom += 4  # final gap
    canvas_h = title_h + body_h + pad + extra_bottom

    # ── 紫色系配色方案 ──
    # 背景渐变：极深紫 → 深紫
    BG_TOP = "#0d0221"     # 近乎黑色的深紫（底）
    BG_BOT = "#1a0a3e"     # 深紫（顶）
    # 标题
    TITLE_BG = "#1a0844"   # 标题条背景（深紫，增强对比）
    TITLE_LINE = "#818cf8" # 装饰线（紫蓝/靛蓝，邻近色）
    TITLE_TEXT = "#f0e0ff" # 标题文字（极浅紫白，高对比度）
    # 正文
    COLOR_TEXT = "#fff7df"     # 统一正文颜色（暖白）
    COLOR_EVOLUTION = "#f472d6" # 进化链颜色（洋红色）
    COLOR_BOTTOM = "#2d1457"   # 底部线

    # ── 创建画布 ──
    img = Image.new("RGB", (canvas_w, canvas_h), (13, 2, 33))
    draw = ImageDraw.Draw(img)

    # ── 渐变背景（从上到下：BG_TOP → BG_BOT） ──
    r1, g1, b1 = _hex_to_rgb(BG_TOP)
    r2, g2, b2 = _hex_to_rgb(BG_BOT)
    for y in range(canvas_h):
        ratio = y / canvas_h
        r = int(r1 * (1 - ratio) + r2 * ratio)
        g = int(g1 * (1 - ratio) + g2 * ratio)
        b = int(b1 * (1 - ratio) + b2 * ratio)
        draw.line([(0, y), (canvas_w, y)], fill=(r, g, b))

    # ── 标题栏 ──
    draw.rectangle([(0, 16), (canvas_w, 16 + title_h)], fill=TITLE_BG)
    draw.rectangle([(0, 16 + title_h - 3), (canvas_w, 16 + title_h)], fill=TITLE_LINE)

    tw = title_font.getbbox(title)[2] - title_font.getbbox(title)[0]
    _, t_ymax = title_font.getbbox(title)[1], title_font.getbbox(title)[3]
    tx = (canvas_w - tw) // 2
    ty = 16 + (title_h - (t_ymax)) // 2 - 2
    draw.text((tx, ty), title, fill=TITLE_TEXT, font=title_font)

    # ── 正文 ──
    y = 16 + title_h + 8
    left_x = pad + 8

    for line in lines:
        stripped = line.lstrip()
        if not line:
            y += line_h // 2  # 空行只占一半高度
            continue
        is_heading = line.startswith("——") and "——" in line[2:]
        is_sub = line.startswith("   ") or line.startswith("  ") or line.startswith("\t")
        is_numbered = line[0].isdigit() and ". " in line[:4]
        is_evolution = line.startswith("进化链")
        is_spirit_name = is_sub and stripped.endswith(":")

        if is_heading:
            draw.text((left_x, y), line, fill=COLOR_TEXT, font=_font(15, bold=True))
        elif is_evolution:
            draw.text((left_x, y), line, fill=COLOR_EVOLUTION, font=_font(15, bold=True))
        elif is_numbered:
            draw.text((left_x, y), line, fill=COLOR_TEXT, font=_font(16, bold=True))
        elif is_spirit_name:
            draw.text((left_x + 12, y), stripped, fill=COLOR_TEXT, font=_font(16, bold=True))
        elif is_sub:
            draw.text((left_x + 12, y), stripped, fill=COLOR_TEXT, font=_font(15))
        else:
            draw.text((left_x, y), line, fill=COLOR_TEXT, font=line_font)

        y += line_h

    # ── 底部区域（从正文末尾往下排） ──
    bottom_y = 10 + title_h + 8 + len(lines) * line_h  # 正文结束位置

    if warning:
        bottom_y += 10  # gap
        draw.text((pad + 8, bottom_y), warning, fill="#ff4444", font=_font(11))
        bottom_y += 13  # 文字高度

    bottom_y += 8  # gap
    # 底部装饰线
    draw.line([(pad, bottom_y), (canvas_w - pad, bottom_y)], fill=_hex_to_rgb(COLOR_BOTTOM))
    bottom_y += 3  # 线厚度

    if query_info:
        bottom_y += 4  # gap
        parts = []
        if "time" in query_info:
            parts.append(query_info["time"])
        if "group" in query_info:
            parts.append(query_info["group"])
        if "user" in query_info:
            parts.append(query_info["user"])
        footer_text = "  |  ".join(parts)
        draw.text((pad, bottom_y), footer_text, fill="#8888aa", font=_font(12))
        if "url" in query_info:
            bottom_y += 20
            draw.text((pad, bottom_y), query_info["url"], fill="#8888aa", font=_font(10))

    # ── 水印（右下角，40% 透明度） ──
    if os.path.exists(WATERMARK_PATH):
        wm = Image.open(WATERMARK_PATH).convert("RGBA")
        wm_w = int(canvas_w * 0.5)  # 水印宽度 ≈ 画布宽度的 18%
        wm_h = int(wm.height * (wm_w / wm.width))  # 等比缩放高度
        wm = wm.resize((wm_w, wm_h), Image.LANCZOS)
        # 逐像素降低不透明度到 40%
        r, g, b, a = wm.split()
        a = a.point(lambda x: int(x * 0.3))
        wm = Image.merge("RGBA", (r, g, b, a))
        # 右下角坐标，留 12px 边距
        wx = canvas_w - wm_w - 12
        wy = canvas_h - wm_h - 12
        img.paste(wm, (wx, wy), wm)

    # ── 保存 ──
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    save_path = os.path.join(OUTPUT_DIR, filename)
    img.save(save_path, "PNG")
    return os.path.abspath(save_path)


PREDICT_WARNING = "数据未清洗，由公式精准计算得出，部分精灵不存在随机蛋，请自行判断"


def render_predict(height: int, weight: int, result_text: str,
                   query_info: Optional[dict] = None) -> str:
    title = f"蛋重预测  {height/100:.2f} / {weight/1000:.3f}"
    return render_text_to_image(title, result_text.split("\n"),
                                query_info=query_info, warning=PREDICT_WARNING)


def render_query(pet_name: str, result_text: str,
                 query_info: Optional[dict] = None) -> str:
    title = f"查询 · {pet_name}"
    return render_text_to_image(title, result_text.split("\n"), query_info=query_info)
