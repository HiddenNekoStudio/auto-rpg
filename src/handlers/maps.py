"""
handlers/maps.py — /maps команда для отображения карты (viewport)
Поддержка:
- Готовые SVG карты из Second Brain
- Квесты и события на карте
"""
import io
import json
import re
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import CommandHandler, CallbackQueryHandler

from db import Player, Quest
from data.locations import format_location, find_location, load_locations, get_location_emoji

# Try multiple paths for server compatibility
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent
MAPS_DIR = _project_root / "maps"
MAP_IMAGES_DIR = MAPS_DIR / "images"

# Fallback: check if images dir exists, create if needed
if not MAP_IMAGES_DIR.exists():
    MAP_IMAGES_DIR = _project_root / "maps" / "images"
    if not MAP_IMAGES_DIR.exists():
        try:
            MAP_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Created images directory: {MAP_IMAGES_DIR}")
        except Exception as e:
            print(f"Could not create images directory: {e}")

MAP_SIZE = 1000
VIEWPORT_SIZES = [5, 10, 20]
BG_COLOR = (26, 26, 46)
GRID_COLOR = (74, 74, 106)
CROSS_COLOR = (42, 42, 74)
QUEST_COLOR = (255, 215, 0)
EVENT_COLOR = (255, 100, 100)


def get_location_image(location_id: str) -> io.BytesIO | None:
    """
    Загружает картинку локации (единая для всех языков).
    
    Пример:
        - K1-C1 → maps/images/K1-C1.png
    """
    if not location_id:
        return None
    
    print(f"DEBUG get_location_image: MAP_IMAGES_DIR={MAP_IMAGES_DIR}")
    print(f"DEBUG get_location_image: location_id={location_id}")
    print(f"DEBUG get_location_image: exists check = {MAP_IMAGES_DIR.exists()}")
    
    # Ищем картинку без языкового суффикса (единая для всех языков)
    for ext in ['png', 'jpg', 'jpeg']:
        filename = f"{location_id}.{ext}"
        image_path = MAP_IMAGES_DIR / filename
        print(f"DEBUG get_location_image: checking {filename}, exists={image_path.exists()}")
        if image_path.exists():
            try:
                with open(image_path, "rb") as f:
                    return io.BytesIO(f.read())
            except Exception as e:
                print(f"DEBUG get_location_image: error reading {filename}: {e}")
                continue
    
    return None


def t(key: str, lang: str = "ru", **kwargs) -> str:
    """Translate string."""
    from i18n import STRINGS
    s = STRINGS.get(lang, {}).get(key, key)
    if kwargs:
        s = s.format(**kwargs)
    return s


def lang_from_update(update, player=None) -> str:
    """Get language from update or player."""
    if player and player.lang:
        return player.lang
    return "ru"


def find_svg_map(cx: int, cy: int, size: int) -> tuple[Path, dict]:
    """
    Находит подходящую SVG карту для viewport.
    Возвращает (Path к SVG, dict с метаданными).
    """
    maps_dir = MAPS_DIR
    
    cx_start = cx
    cy_start = cy
    
    for svg_file in sorted(maps_dir.glob("*.svg")):
        json_file = svg_file.with_suffix(".json")
        if json_file.exists():
            try:
                with open(json_file) as f:
                    meta = json.load(f)
                    bounds = meta.get("viewport_bounds", [0, 0, 0, 0])
                    vp_size = meta.get("viewport_size", [20, 20])[0]
                    
                    if vp_size == size:
                        bx0, bx1, by0, by1 = bounds
                        if bx0 <= cx_start <= bx1 and by0 <= cy_start <= by1:
                            return svg_file, meta
            except Exception:
                continue
    
    return None, {}


async def get_viewport_svg(cx: int, cy: int, size: int, player, lang: str) -> tuple[bytes, str]:
    """
    Генерирует PNG карты viewport используя Pillow с отрисовкой
    игроков, квестов и событий поверх фона из SVG.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        pixel_size = size * 10
        img = Image.new('RGB', (pixel_size, pixel_size), BG_COLOR)
        draw = ImageDraw.Draw(img)
        
        for i in range(size + 1):
            x = i * 10
            color = CROSS_COLOR if i == size // 2 else GRID_COLOR
            width = 2 if i == size // 2 else 1
            draw.line([(x, 0), (x, pixel_size)], fill=color, width=width)
            draw.line([(0, x), (pixel_size, x)], fill=color, width=width)
        
        bounds = [cx, cx + size, cy, cy + size]
        try:
            nearby = await Player.objects.filter(
                x__gte=bounds[0], x__lte=bounds[1],
                y__gte=bounds[2], y__lte=bounds[3]
            ).all()
        except Exception:
            nearby = []
        
        for p in nearby:
            px = (p.x - cx) * 10
            py = (p.y - cy) * 10
            if 0 <= px < pixel_size and 0 <= py < pixel_size:
                color = (0, 255, 0) if player and p.uid == player.uid else (255, 200, 0)
                draw.ellipse([px-3, py-3, px+3, py+3], fill=color, outline=(255,255,255))
        
        try:
            quests = await Quest.objects.all()
            for q in quests:
                for p in nearby:
                    if p.onquest and p.qid == q.qid:
                        qx = (p.x - cx) * 10
                        qy = (p.y - cy) * 10
                        if 0 <= qx < pixel_size and 0 <= qy < pixel_size:
                            draw.rectangle([qx-4, qy-4, qx+4, qy+4], outline=QUEST_COLOR, width=2)
        except Exception:
            pass
        
        try:
            locations = load_locations()
            for loc in locations:
                lx = loc.get("x", 0)
                ly = loc.get("y", 0)
                if cx <= lx <= cx + size and cy <= ly <= cy + size:
                    px = (lx - cx) * 10
                    py = (ly - cy) * 10
                    if 0 <= px < pixel_size and 0 <= py < pixel_size:
                        loc_type = loc.get("type", "")
                        emoji = get_location_emoji(loc_type)
                        if loc_type in ["city", "village", "castle", "temple"]:
                            draw.rectangle([px-5, py-5, px+5, py+5], outline=(255, 215, 0), width=2)
                        else:
                            draw.ellipse([px-3, py-3, px+3, py+3], outline=(180, 180, 220))
        except Exception:
            pass
        
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue(), ""
    except Exception as e:
        return None, str(e)


async def render_viewport_text(cx: int, cy: int, size: int, player=None, lang: str = "ru") -> str:
    """Рендер viewport как текстовое представление."""
    bounds = [cx, cx + size, cy, cy + size]

    try:
        nearby = await Player.objects.filter(
            x__gte=bounds[0], x__lte=bounds[1],
            y__gte=bounds[2], y__lte=bounds[3]
        ).all()
    except Exception:
        nearby = []

    lines = [t("map_title", lang=lang, cx=cx, cy=cy), ""]

    has_player = False
    for p in nearby:
        if player and p.uid == player.uid:
            has_player = True
            lines.append(f"📍 {t('map_mypos', lang=lang)}: ({p.x}, {p.y})")
        elif len(lines) < 15:
            lines.append(f"  • {p.name} @ ({p.x}, {p.y})")

    if player and not has_player:
        lines.append(f"📍 {t('map_mypos', lang=lang)}: ({player.x}, {player.y})")

    try:
        active_quest = await Quest.objects.all()
        if active_quest:
            q = active_quest[0]
            quest_players = await Player.objects.filter(onquest=True).all()
            if quest_players:
                qp_names = ", ".join([p.name for p in quest_players[:3]])
                lines.append("")
                lines.append(f"🗺️ {t('quest_active', lang=lang, goal=q.goal[:30])}")
                lines.append(f"👥 {qp_names}")
    except Exception:
        pass

    lines.append("")
    lines.append(t("map_coords", lang=lang, x=bounds[0], y=bounds[2]) + " - " + t("map_coords", lang=lang, x=bounds[1], y=bounds[3]))

    return "\n".join(lines)


def build_map_keyboard(size: int, current_size: int) -> list:
    """Build keyboard with map controls."""
    return [
        [InlineKeyboardButton(t("map_refresh", "ru"), callback_data="map_refresh")],
    ]


async def cmd_maps(update, context):
    """Обработчик команды /maps."""
    player = await Player.objects.get_or_none(uid=update.effective_user.id)
    if not player:
        text = t("not_registered", "ru")
        await update.message.reply_text(text)
        return

    size = context.args[0] if context.args else None
    if size and size.isdigit():
        size = int(size)
        if size not in VIEWPORT_SIZES:
            size = 20
    else:
        size = 20
    
    lang = lang_from_update(update, player)
     
    cx = max(0, min(MAP_SIZE - size, player.x - size // 2))
    cy = max(0, min(MAP_SIZE - size, player.y - size // 2))

    loc = find_location(player.x, player.y)
    keyboard = build_map_keyboard(size, size)
    loc_id = loc.get("id", "") if loc else ""
    
    print(f"DEBUG cmd_maps: player_id={player.uid}, x={player.x}, y={player.y}")
    print(f"DEBUG cmd_maps: loc={loc}, loc_id={loc_id!r}, lang={lang!r}")
    
    location_image = get_location_image(loc_id)
    print(f"DEBUG cmd_maps: location_image={location_image}")

    if location_image and loc:
        loc_name = loc.get(f"name_{lang}", loc.get("name_en", "Локация"))
        caption = f"📍 *{loc_name}*\n\n📌 Координаты: `({player.x}, {player.y})`"
        await update.message.reply_photo(
            photo=location_image,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif loc:
        loc_name = loc.get(f"name_{lang}", loc.get("name_en", "Локация"))
        text = f"📍 *{loc_name}*\n📌 Координаты: `({player.x}, {player.y})`"
        await update.message.reply_text(text, parse_mode="Markdown",
                                         reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        text = f"📍 Позиция: `({player.x}, {player.y})`"
        await update.message.reply_text(text, parse_mode="Markdown",
                                         reply_markup=InlineKeyboardMarkup(keyboard))


async def callback_maps(update, context):
    """Обработчик callback для обновления карты/зума."""
    query = update.callback_query
    await query.answer()

    player = await Player.objects.get_or_none(uid=query.from_user.id)
    if not player:
        await query.message.delete()
        return

    lang = player.lang or "ru"

    size = 20
    cx = max(0, min(MAP_SIZE - size, player.x - size // 2))
    cy = max(0, min(MAP_SIZE - size, player.y - size // 2))

    loc = find_location(player.x, player.y)
    keyboard = build_map_keyboard(size, size)
    loc_id = loc.get("id", "") if loc else ""
    
    print(f"DEBUG callback_maps: player_id={player.uid}, x={player.x}, y={player.y}")
    print(f"DEBUG callback_maps: loc={loc}, loc_id={loc_id!r}, lang={lang!r}")
    
    location_image = get_location_image(loc_id)
    print(f"DEBUG callback_maps: location_image={location_image}")

    if location_image and loc:
        loc_name = loc.get(f"name_{lang}", loc.get("name_en", "Локация"))
        caption = f"📍 *{loc_name}*\n\n📌 Координаты: `({player.x}, {player.y})`"
        try:
            await query.message.reply_photo(
                photo=location_image,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            pass
    elif loc:
        loc_name = loc.get(f"name_{lang}", loc.get("name_en", "Локация"))
        text = f"📍 *{loc_name}*\n📌 Координаты: `({player.x}, {player.y})`"
        try:
            await query.message.reply_text(text, parse_mode="Markdown",
                                           reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass
    else:
        text = f"📍 Позиция: `({player.x}, {player.y})`"
        try:
            await query.message.reply_text(text, parse_mode="Markdown",
                                           reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass


async def send_map_view(query, player, lang: str = "ru"):
    """Отправка карты через callback query (inline menu)."""
    size = 20
    cx = max(0, min(MAP_SIZE - size, player.x - size // 2))
    cy = max(0, min(MAP_SIZE - size, player.y - size // 2))

    loc = find_location(player.x, player.y)
    keyboard = build_map_keyboard(size, size)
    loc_id = loc.get("id", "") if loc else ""
    
    print(f"DEBUG send_map_view: player_id={player.uid}, x={player.x}, y={player.y}")
    print(f"DEBUG send_map_view: loc={loc}, loc_id={loc_id!r}, lang={lang!r}")
    
    location_image = get_location_image(loc_id)
    print(f"DEBUG send_map_view: location_image={location_image}")

    if location_image and loc:
        loc_name = loc.get(f"name_{lang}", loc.get("name_en", "Локация"))
        caption = f"📍 *{loc_name}*\n\n📌 Координаты: `({player.x}, {player.y})`"
        try:
            await query.message.reply_photo(
                photo=location_image,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            pass
    elif loc:
        loc_name = loc.get(f"name_{lang}", loc.get("name_en", "Локация"))
        text = f"📍 *{loc_name}*\n📌 Координаты: `({player.x}, {player.y})`"
        try:
            await query.message.reply_text(text, parse_mode="Markdown",
                                           reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass
    else:
        text = f"📍 Позиция: `({player.x}, {player.y})`"
        try:
            await query.message.reply_text(text, parse_mode="Markdown",
                                           reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass


def register_handlers(app):
    """Регистрация обработчиков карты."""
    app.add_handler(CommandHandler("maps", cmd_maps))
    app.add_handler(CallbackQueryHandler(callback_maps, pattern="^map_"))