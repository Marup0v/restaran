import os
import re

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

API_BASE = os.getenv('RESTAURANT_API_URL', 'http://127.0.0.1:8000').rstrip('/')


class OrderFlow(StatesGroup):
    delivery_type = State()
    table_number = State()
    address = State()
    phone = State()
    note = State()
    confirmation = State()


def money(value):
    return f'{float(value):,.0f}'.replace(',', ' ')


def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🍽 Menyu', callback_data='menu')],
        [InlineKeyboardButton(text='🛒 Savat', callback_data='cart')],
        [InlineKeyboardButton(text='📦 Buyurtmalarim', callback_data='orders')],
        [InlineKeyboardButton(text='☎️ Aloqa', callback_data='contact')],
    ])


def cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='❌ Bekor qilish', callback_data='flow:cancel')],
    ])


class ApiClient:
    async def request(self, method, path, token=None, payload=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.request(method, f'{API_BASE}{path}', json=payload) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    detail = data.get('detail', 'Server xatosi.') if isinstance(data, dict) else 'Server xatosi.'
                    raise ValueError(detail)
                return data

    async def login(self, user):
        data = await self.request('POST', '/api/auth/telegram/', payload={
            'telegram_id': user.id,
            'ism': user.full_name,
            'username': user.username or '',
        })
        return data['token']

    async def menu(self, token):
        return await self.request('GET', '/api/menu/', token)

    async def cart(self, token):
        return await self.request('GET', '/api/cart/', token)

    async def add_to_cart(self, token, dish_id, quantity=1):
        return await self.request('POST', '/api/cart/items/', token, {'taom': dish_id, 'miqdor': quantity})

    async def change_cart(self, token, item_id, quantity):
        return await self.request('PATCH', f'/api/cart/items/{item_id}/', token, {'miqdor': quantity})

    async def orders(self, token):
        return await self.request('GET', '/api/orders/', token)

    async def create_order(self, token, payload):
        return await self.request('POST', '/api/orders/', token, payload)

    async def chef_login(self, user):
        data = await self.request('POST', '/api/auth/telegram/chef/', payload={'telegram_id': user.id})
        return data['access']

    async def kitchen_queue(self, token):
        return await self.request('GET', '/api/kitchen/queue/', token)

    async def change_status(self, token, order_id, status):
        return await self.request('POST', f'/api/orders/{order_id}/status/', token, {'holat': status})


api = ApiClient()


async def get_token_user(user, state: FSMContext):
    data = await state.get_data()
    if data.get('token'):
        return data['token']
    token = await api.login(user)
    await state.update_data(token=token)
    return token


async def get_token(message: Message, state: FSMContext):
    return await get_token_user(message.from_user, state)


def category_keyboard(categories):
    rows = [[InlineKeyboardButton(text=category['nom'], callback_data=f"cat:{category['slug']}")] for category in categories]
    rows.append([InlineKeyboardButton(text='🏠 Bosh menyu', callback_data='home')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dish_keyboard(dishes, slug):
    rows = [[InlineKeyboardButton(text=f"{dish['nom']} — {money(dish['narx'])} so'm", callback_data=f"dish:{dish['id']}:{slug}")] for dish in dishes]
    rows.append([InlineKeyboardButton(text='⬅️ Kategoriyalar', callback_data='menu')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_keyboard(items):
    rows = []
    for item in items:
        rows.append([
            InlineKeyboardButton(text=f"− {item['nom']}", callback_data=f"cart:dec:{item['id']}"),
            InlineKeyboardButton(text='+', callback_data=f"cart:inc:{item['id']}"),
            InlineKeyboardButton(text='🗑', callback_data=f"cart:del:{item['id']}"),
        ])
    rows.append([InlineKeyboardButton(text='✅ Buyurtma berish', callback_data='order:start')])
    rows.append([InlineKeyboardButton(text='🍽 Menyu', callback_data='menu')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_cart(data):
    items = data.get('items', [])
    if not items:
        return '🛒 Savatingiz bo‘sh.'
    lines = [f"{item['nom']} × {item['miqdor']} = {money(item['jami'])} so'm" for item in items]
    return '🛒 Savat\n\n' + '\n'.join(lines) + f"\n\nJami: {money(data['jami_summa'])} so'm"


def delivery_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🪑 Stolda', callback_data='delivery:stol')],
        [InlineKeyboardButton(text='🛵 Yetkazib berish', callback_data='delivery:manzil')],
        [InlineKeyboardButton(text='❌ Bekor qilish', callback_data='flow:cancel')],
    ])


def confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Tasdiqlash', callback_data='order:confirm')],
        [InlineKeyboardButton(text='❌ Bekor qilish', callback_data='flow:cancel')],
    ])


def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='📱 Telefon raqamimni yuborish', request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def kitchen_keyboard(order):
    rows = []
    if order['holat'] == 'yangi':
        rows.append([InlineKeyboardButton(text='👨‍🍳 Qabul qildim', callback_data=f"kitchen:take:{order['id']}")])
    if order['holat'] == 'tayyorlanmoqda':
        rows.append([InlineKeyboardButton(text='✅ Tayyor', callback_data=f"kitchen:ready:{order['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_kitchen_order(order):
    rows = '\n'.join(f"• {item['nom']} × {item['miqdor']} = {money(item['summa'])} so'm" for item in order.get('qatorlar', []))
    note = f"\nIzoh: {order['izoh']}" if order.get('izoh') else ''
    return (
        f"🍽 {order['raqam']}\nHolat: {order['holat']}\n"
        f"Kutish: {order['kutish_daqiqasi']} daqiqa\n"
        f"Yetkazish turi: {order['yetkazish_turi']}\n{rows}\n"
        f"Jami: {money(order['jami_summa'])} so'm{note}"
    )


def build_bot():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN topilmadi.')
    bot = Bot(token=token)
    dispatcher = Dispatcher()

    @dispatcher.message(CommandStart())
    async def start(message: Message, state: FSMContext, command: CommandObject = None):
        try:
            token = await get_token(message, state)
            if command and command.args == 'order':
                data = await api.menu(token)
                await message.answer(
                    f'Assalomu alaykum, {message.from_user.full_name}!\n'
                    f'Saytdan xush kelibsiz! Buyurtma berish uchun kategoriyani tanlang:',
                    reply_markup=category_keyboard(data['categories'])
                )
            else:
                await message.answer(f'Assalomu alaykum, {message.from_user.full_name}!\nRestoran botiga xush kelibsiz.', reply_markup=main_keyboard())
        except Exception as error:
            await message.answer(f'Xatolik: {error}')

    @dispatcher.callback_query(F.data == 'home')
    async def home(callback: CallbackQuery):
        await callback.message.edit_text('Asosiy menyu:', reply_markup=main_keyboard())
        await callback.answer()

    @dispatcher.callback_query(F.data == 'menu')
    async def menu(callback: CallbackQuery, state: FSMContext):
        try:
            data = await api.menu(await get_token_user(callback.from_user, state))
            await callback.message.edit_text('Kategoriyani tanlang:', reply_markup=category_keyboard(data['categories']))
        except Exception as error:
            await callback.answer(str(error), show_alert=True)
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith('cat:'))
    async def category(callback: CallbackQuery, state: FSMContext):
        slug = callback.data.split(':', 1)[1]
        data = await api.menu(await get_token_user(callback.from_user, state))
        category_data = next((row for row in data['categories'] if row['slug'] == slug), None)
        if not category_data:
            await callback.answer('Kategoriya topilmadi.', show_alert=True)
            return
        await callback.message.edit_text(category_data['nom'], reply_markup=dish_keyboard(category_data['taomlar'], slug))
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith('dish:'))
    async def dish(callback: CallbackQuery, state: FSMContext):
        _, dish_id, slug = callback.data.split(':', 2)
        data = await api.menu(await get_token_user(callback.from_user, state))
        category_data = next((row for row in data['categories'] if row['slug'] == slug), None)
        dish_data = next((row for row in category_data['taomlar'] if str(row['id']) == dish_id), None) if category_data else None
        if not dish_data:
            await callback.answer('Taom topilmadi.', show_alert=True)
            return
        await api.add_to_cart(await get_token_user(callback.from_user, state), int(dish_id))
        await callback.answer(f"{dish_data['nom']} savatga qo‘shildi", show_alert=True)

    @dispatcher.callback_query(F.data == 'cart')
    async def cart(callback: CallbackQuery, state: FSMContext):
        data = await api.cart(await get_token_user(callback.from_user, state))
        await callback.message.edit_text(format_cart(data), reply_markup=cart_keyboard(data.get('items', [])) if data.get('items') else main_keyboard())
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith('cart:'))
    async def edit_cart(callback: CallbackQuery, state: FSMContext):
        _, action, item_id = callback.data.split(':')
        token = await get_token_user(callback.from_user, state)
        current = await api.cart(token)
        item = next((row for row in current.get('items', []) if str(row['id']) == item_id), None)
        if not item:
            await callback.answer('Savat qatori topilmadi.', show_alert=True)
            return
        quantity = item['miqdor'] + (1 if action == 'inc' else -1)
        if action == 'del':
            quantity = 0
        await api.change_cart(token, int(item_id), quantity)
        updated = await api.cart(token)
        await callback.message.edit_text(format_cart(updated), reply_markup=cart_keyboard(updated.get('items', [])) if updated.get('items') else main_keyboard())
        await callback.answer()

    @dispatcher.callback_query(F.data == 'contact')
    async def contact(callback: CallbackQuery):
        await callback.message.answer('Aloqa: +998 90 123 45 67\nIsh vaqti: har kuni 10:00–23:00')
        await callback.answer()

    @dispatcher.callback_query(F.data == 'orders')
    async def orders(callback: CallbackQuery, state: FSMContext):
        data = await api.orders(await get_token_user(callback.from_user, state))
        rows = data.get('results', data if isinstance(data, list) else [])
        if not rows:
            await callback.message.edit_text('Sizda hali buyurtmalar yo‘q.', reply_markup=main_keyboard())
        else:
            text = '\n'.join(f"{row['raqam']} — {row['holat']} — {money(row['jami_summa'])} so'm" for row in rows[:10])
            await callback.message.edit_text('📦 Buyurtmalarim\n\n' + text, reply_markup=main_keyboard())
        await callback.answer()

    @dispatcher.callback_query(F.data == 'order:start')
    async def start_order(callback: CallbackQuery, state: FSMContext):
        await state.set_state(OrderFlow.delivery_type)
        await callback.message.answer('Yetkazish turini tanlang:', reply_markup=delivery_keyboard())
        await callback.answer()

    @dispatcher.callback_query(F.data.startswith('delivery:'))
    async def delivery(callback: CallbackQuery, state: FSMContext):
        delivery_type = callback.data.split(':', 1)[1]
        await state.update_data(yetkazish_turi=delivery_type)
        if delivery_type == 'stol':
            await state.set_state(OrderFlow.table_number)
            await callback.message.answer('Stol raqamingizni 1 dan 20 gacha yozing:', reply_markup=cancel_keyboard())
        else:
            await state.set_state(OrderFlow.address)
            await callback.message.answer('Yetkazib berish manzilini yozing:', reply_markup=cancel_keyboard())
        await callback.answer()

    @dispatcher.message(OrderFlow.table_number)
    async def table_number(message: Message, state: FSMContext):
        if not message.text or not message.text.isdigit() or not 1 <= int(message.text) <= 20:
            await message.answer('Faqat 1 dan 20 gacha bo‘lgan raqam kiriting.')
            return
        await state.update_data(stol_raqami=int(message.text), manzil='')
        await state.set_state(OrderFlow.phone)
        await message.answer('Telefon raqamingizni yuboring:', reply_markup=contact_keyboard())

    @dispatcher.message(OrderFlow.address)
    async def address(message: Message, state: FSMContext):
        if not message.text or len(message.text.strip()) < 10:
            await message.answer('Manzil kamida 10 ta belgidan iborat bo‘lsin.')
            return
        await state.update_data(manzil=message.text.strip(), stol_raqami=None)
        await state.set_state(OrderFlow.phone)
        await message.answer('Telefon raqamingizni yuboring:', reply_markup=contact_keyboard())

    @dispatcher.message(OrderFlow.phone)
    async def phone(message: Message, state: FSMContext):
        value = message.contact.phone_number if message.contact else (message.text or '').strip()
        normalized = value.replace(' ', '').replace('-', '')
        if not re.fullmatch(r'\+?998\d{9}', normalized):
            await message.answer('Telefonni +998901234567 ko‘rinishida yuboring.')
            return
        await state.update_data(telefon=normalized)
        await state.set_state(OrderFlow.note)
        await message.answer('Izoh yozing yoki “O‘tkazib yuborish” deb yozing:', reply_markup=ReplyKeyboardRemove())

    @dispatcher.message(OrderFlow.note)
    async def note(message: Message, state: FSMContext):
        note_value = '' if (message.text or '').lower() in ('o‘tkazib yuborish', "o'tkazib yuborish", 'skip') else (message.text or '')
        await state.update_data(izoh=note_value)
        data = await state.get_data()
        cart_data = await api.cart(data['token'])
        text = format_cart(cart_data) + f"\n\nYetkazish: {'Stolda' if data['yetkazish_turi'] == 'stol' else 'Manzilga'}\nTelefon: {data['telefon']}"
        await state.set_state(OrderFlow.confirmation)
        await message.answer('Buyurtmani tasdiqlaysizmi?\n\n' + text, reply_markup=confirm_keyboard())

    @dispatcher.callback_query(F.data == 'order:confirm')
    async def confirm_order(callback: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        payload = {key: data.get(key, '') for key in ('yetkazish_turi', 'stol_raqami', 'manzil', 'telefon', 'izoh')}
        try:
            result = await api.create_order(data['token'], payload)
            await state.clear()
            await callback.message.edit_text(f"✅ Buyurtmangiz qabul qilindi.\nRaqam: {result['raqam']}\nJami: {money(result['jami_summa'])} so'm", reply_markup=main_keyboard())
        except Exception as error:
            await callback.message.answer(f'Buyurtma yaratilmadi: {error}')
            await state.clear()
        await callback.answer()

    @dispatcher.callback_query(F.data == 'flow:cancel')
    async def cancel_flow(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.answer('Buyurtma berish bekor qilindi.', reply_markup=main_keyboard())
        await callback.answer()

    @dispatcher.message(Command('savat'))
    async def cart_command(message: Message, state: FSMContext):
        token = await get_token(message, state)
        data = await api.cart(token)
        await message.answer(format_cart(data), reply_markup=cart_keyboard(data.get('items', [])) if data.get('items') else main_keyboard())

    @dispatcher.message(Command('oshxona'))
    @dispatcher.message(Command('navbat'))
    async def kitchen(message: Message):
        try:
            chef_token = await api.chef_login(message.from_user)
            queue = await api.kitchen_queue(chef_token)
            orders = queue.get('orders', [])
            if not orders:
                await message.answer('Oshxona navbati bo‘sh.', reply_markup=main_keyboard())
                return
            for order in orders:
                await message.answer(format_kitchen_order(order), reply_markup=kitchen_keyboard(order))
        except Exception as error:
            await message.answer(f'Ruxsat yo‘q: {error}')

    @dispatcher.callback_query(F.data.startswith('kitchen:'))
    async def kitchen_status(callback: CallbackQuery):
        try:
            chef_token = await api.chef_login(callback.from_user)
            _, action, order_id = callback.data.split(':')
            next_status = 'tayyorlanmoqda' if action == 'take' else 'tayyor'
            result = await api.change_status(chef_token, int(order_id), next_status)
            await callback.message.edit_text(f"✅ Buyurtma {result['holat']} holatiga o‘tkazildi.")
            customer_message = (
                f"Buyurtmangiz {result['raqam']} tayyorlanmoqda."
                if next_status == 'tayyorlanmoqda'
                else f"Buyurtmangiz {result['raqam']} tayyor. Yoqimli ishtaha!"
            )
            try:
                await callback.bot.send_message(result['telegram_id'], customer_message)
            except Exception:
                pass
            await callback.answer('Holat yangilandi')
        except Exception as error:
            await callback.answer(str(error), show_alert=True)

    return bot, dispatcher


async def run():
    bot, dispatcher = build_bot()
    await dispatcher.start_polling(bot)
