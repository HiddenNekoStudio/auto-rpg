"""
plugins/stars_shop.py — Telegram Stars → Token Shop

Плагин для покупки токенов за Telegram Stars.
Курс: 1 токен = 50 Stars (настраивается в config.py)
"""
import logging
import time as time_module

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, PreCheckoutQueryHandler, MessageHandler, ContextTypes
from telegram.ext import filters as Filters

from db import Player, StarPurchase

logger = logging.getLogger(__name__)


def stars_t(lang: str, key: str, **kwargs) -> str:
    """Получить перевод для Stars магазина."""
    from i18n import t
    return t(lang, key, **kwargs)


def get_stars_rate() -> int:
    """Получить курс Stars → Token."""
    import config as cfg
    return getattr(cfg, 'STARS_SHOP_RATE', 50)


def get_max_tokens() -> int:
    """Получить максимум токенов за покупку."""
    import config as cfg
    return getattr(cfg, 'STARS_SHOP_MAX_PER_PURCHASE', 10)


def build_stars_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Построить клавиатуру выбора количества токенов."""
    max_tokens = get_max_tokens()
    buttons = []
    
    for i in range(1, max_tokens + 1):
        rate = get_stars_rate()
        price = i * rate
        btn_text = f"🎫 {i} {'tokens' if lang == 'en' else 'токенов'} = {price}⭐"
        buttons.append(
            InlineKeyboardButton(btn_text, callback_data=f"stars_buy_{i}")
        )
    
    rows = []
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            rows.append([buttons[i], buttons[i + 1]])
        else:
            rows.append([buttons[i]])
    
    rows.append([InlineKeyboardButton("🔙 Menu" if lang == "en" else "🔙 Меню", callback_data="menu_back")])
    
    return InlineKeyboardMarkup(rows)


async def cmd_starshop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /starshop."""
    user = update.effective_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    
    rate = get_stars_rate()
    max_tokens = get_max_tokens()
    
    text = stars_t(lang, "starshop_title", rate=rate, max_tokens=max_tokens)
    keyboard = build_stars_keyboard(lang)
    
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        from handlers.user import safe_edit
        await safe_edit(update.callback_query, text, parse_mode="HTML", reply_markup=keyboard)


async def handle_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback Stars магазина."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    player = await Player.objects.get_or_none(uid=user.id)
    lang = (player.lang or "ru") if player else "ru"
    
    if not player:
        await query.answer("Please register first!" if lang == "en" else "Сначала зарегистрируйтесь!", show_alert=True)
        return
    
    data = query.data
    
    if data == "starshop_menu":
        text = stars_t(lang, "starshop_title", rate=get_stars_rate(), max_tokens=get_max_tokens())
        keyboard = build_stars_keyboard(lang)
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        return
    
    if data.startswith("stars_buy_"):
        try:
            tokens = int(data.replace("stars_buy_", ""))
        except ValueError:
            await query.answer("Invalid amount" if lang == "en" else "Некорректная сумма", show_alert=True)
            return
        
        max_tokens = get_max_tokens()
        if tokens < 1 or tokens > max_tokens:
            await query.answer(stars_t(lang, "starshop_limit", max=max_tokens), show_alert=True)
            return
        
        rate = get_stars_rate()
        stars_price = tokens * rate
        
        text = stars_t(lang, "starshop_confirm", tokens=tokens, stars=stars_price)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"💳 Pay {stars_price}⭐" if lang == "en" else f"💳 Оплатить {stars_price}⭐",
                    callback_data=f"stars_pay_{tokens}"
                )
            ],
            [
                InlineKeyboardButton("🔙 Back" if lang == "en" else "🔙 Назад", callback_data="starshop_menu")
            ],
        ])
        
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        return
    
    if data.startswith("stars_pay_"):
        try:
            tokens = int(data.replace("stars_pay_", ""))
        except ValueError:
            await query.answer("Invalid amount" if lang == "en" else "Некорректная сумма", show_alert=True)
            return
        
        max_tokens = get_max_tokens()
        if tokens < 1 or tokens > max_tokens:
            await query.answer(stars_t(lang, "starshop_limit", max=max_tokens), show_alert=True)
            return
        
        rate = get_stars_rate()
        stars_price = tokens * rate
        
        payload = f"stars_{user.id}_{tokens}_{int(time_module.time())}"
        
        await query.message.reply_invoice(
            title=f"🎫 {tokens} {'tokens' if lang == 'en' else 'токенов'}",
            description=f"Purchase of {tokens} tokens for {stars_price} Telegram Stars" if lang == "en" else f"Покупка {tokens} игровых токенов за {stars_price} Telegram Stars",
            payload=payload,
            provider_token=None,
            currency="XTR",
            prices=[(f"🎫 {tokens} {'tokens' if lang == 'en' else 'токенов'}", stars_price)]
        )
        
        return


async def on_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик pre_checkout_query — валидация оплаты."""
    query = update.pre_checkout_query
    lang = "ru"
    
    payload = query.invoice_payload
    if not payload.startswith("stars_"):
        await query.answer(answer_text="Invalid payment" if lang == "en" else "Некорректный платёж", success=False)
        return
    
    try:
        parts = payload.split("_")
        if len(parts) < 3:
            raise ValueError("Invalid payload")
        
        user_id = int(parts[1])
        tokens = int(parts[2])

        player = await Player.objects.get_or_none(uid=user_id)
        if player:
            lang = player.lang or "ru"

        max_tokens = get_max_tokens()
        
        if tokens < 1 or tokens > max_tokens:
            await query.answer(answer_text="Invalid amount" if lang == "en" else "Некорректная сумма", success=False)
            return
        
        rate = get_stars_rate()
        expected_stars = tokens * rate
        
        if query.currency != "XTR":
            await query.answer(answer_text="Only XTR currency accepted" if lang == "en" else "Принимается только валюта XTR", success=False)
            return
        
        if query.total_amount != expected_stars:
            await query.answer(answer_text="Invalid amount" if lang == "en" else "Некорректная сумма", success=False)
            return
        
        await query.answer(success=True)
        
    except (ValueError, IndexError) as e:
        logger.error(f"Pre-checkout validation error: {e}")
        await query.answer(answer_text="Payment error" if lang == "en" else "Ошибка платежа", success=False)


async def on_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик успешной оплаты — начисление токенов."""
    message = update.message
    payment = message.successful_payment
    lang = "ru"
    
    payload = payment.invoice_payload
    if not payload.startswith("stars_"):
        logger.warning(f"Unknown payment payload: {payload}")
        return
    
    try:
        parts = payload.split("_")
        user_id = int(parts[1])
        tokens = int(parts[2])
        charge_id = payment.telegram_payment_charge_id
        
        player = await Player.objects.get_or_none(uid=user_id)
        if not player:
            logger.error(f"Player not found for payment: user_id={user_id}")
            await message.reply_text("❌ Error: player not found. Contact administrator." if lang == "en" else "❌ Ошибка: игрок не найден. Обратитесь к администратору.")
            return
        
        lang = player.lang or "ru"
        
        player.tokens += tokens
        await player.update(_columns=["tokens"])
        
        await StarPurchase.objects.create(
            user_id=user_id,
            tokens_amount=tokens,
            stars_amount=tokens * get_stars_rate(),
            telegram_payment_charge_id=charge_id,
            purchased_at=int(time_module.time()),
            created_at=int(time_module.time())
        )
        
        text = stars_t(lang, "starshop_bought", tokens=tokens, total_tokens=player.tokens)
        await message.reply_text(text, parse_mode="HTML")
        
        logger.info(f"Stars payment success: user={user_id}, tokens={tokens}, charge={charge_id}")
        
    except Exception as e:
        logger.error(f"Stars payment processing error: {e}")
        await message.reply_text("❌ An error occurred while processing the payment. Contact administrator." if lang == "en" else "❌ Произошла ошибка при обработке платежа. Обратитесь к администратору.")


def register_stars_handlers(app: Application):
    """Зарегистрировать обработчики Stars магазина."""
    app.add_handler(CommandHandler("starshop", cmd_starshop))
    app.add_handler(CallbackQueryHandler(handle_stars_callback, pattern="^(stars_|starshop_menu)$"))
    app.add_handler(PreCheckoutQueryHandler(on_pre_checkout))
    app.add_handler(MessageHandler(Filters.SUCCESSFUL_PAYMENT, on_successful_payment))


__all__ = [
    "register_stars_handlers",
    "cmd_starshop",
]