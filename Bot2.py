import sqlite3
import datetime
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image, ImageDraw
import io
import os
import config

# Configuración de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Inicialización de la base de datos y creación de tablas
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            approved INTEGER,
            subscription_days INTEGER,
            approved_time TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            semaphore TEXT,
            stars INTEGER,
            main_button TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_categories (
            user_id INTEGER,
            category_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (category_name) REFERENCES categories(name)
        )
    ''')
    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# Funciones para manejar usuarios
def add_user(user_id, first_name, approved, subscription_days, approved_time):
    cursor.execute("INSERT OR REPLACE INTO users (user_id, first_name, approved, subscription_days, approved_time) VALUES (?, ?, ?, ?, ?)",
                   (user_id, first_name, approved, subscription_days, approved_time))
    conn.commit()

def get_user(user_id=None):
    if user_id:
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()

def update_user_approval(user_id, approved):
    cursor.execute("UPDATE users SET approved = ? WHERE user_id = ?", (approved, user_id))
    conn.commit()

def update_user_subscription(user_id, subscription_days, approved_time):
    cursor.execute("UPDATE users SET subscription_days = ?, approved_time = ? WHERE user_id = ?", (subscription_days, approved_time, user_id))
    conn.commit()

def add_user_category(user_id, category_name):
    cursor.execute("INSERT INTO user_categories (user_id, category_name) VALUES (?, ?)", (user_id, category_name))
    conn.commit()

def remove_user_category(user_id, category_name):
    cursor.execute("DELETE FROM user_categories WHERE user_id = ? AND category_name = ?", (user_id, category_name))
    conn.commit()

def get_user_categories(user_id):
    cursor.execute("SELECT category_name FROM user_categories WHERE user_id = ?", (user_id,))
    return [row[0] for row in cursor.fetchall()]

# Funciones para manejar tipsters
def add_category(name, semaphore, stars, main_button):
    cursor.execute("INSERT INTO categories (name, semaphore, stars, main_button) VALUES (?, ?, ?, ?)",
                   (name, semaphore, stars, main_button))
    conn.commit()

def get_categories(main_button):
    cursor.execute("SELECT * FROM categories WHERE main_button = ?", (main_button,))
    return cursor.fetchall()

def update_category_semaphore(name, semaphore):
    cursor.execute("UPDATE categories SET semaphore = ? WHERE name = ?", (semaphore, name))
    conn.commit()

def update_category_stars(name, stars):
    cursor.execute("UPDATE categories SET stars = ? WHERE name = ?", (stars, name))
    conn.commit()

def delete_category(name):
    cursor.execute("DELETE FROM categories WHERE name = ?", (name,))
    conn.commit()

# Inicializa el cliente de Pyrogram
def init_client():
    return Client("my_bot", api_id=config.api_id, api_hash=config.api_hash, bot_token=config.bot_token)

app = init_client()

# Diccionario para almacenar estados de los usuarios
user_states = {}

def set_user_state(user_id, state):
    user_states[user_id] = state

def get_user_state(user_id):
    return user_states.get(user_id)

def is_admin(user_id):
    return user_id in {config.admin_id, config.admin_id2}

def is_main_admin(user_id):
    return user_id == config.admin_id

# Funciones auxiliares para manejar los botones y categorías
async def send_buttons(client, callback_query, message, buttons):
    await callback_query.message.reply(message, reply_markup=InlineKeyboardMarkup(buttons))
    await callback_query.answer()

async def show_main_button_menu(client, message):
    buttons = [
        [InlineKeyboardButton("Tipster Nacionales 🇲🇽", callback_data="main_Button1_select")],
        [InlineKeyboardButton("Tipsters Americanos 🇺🇸", callback_data="main_Button2_select")],
        [InlineKeyboardButton("Tipsters Europeos 🇪🇺", callback_data="main_Button3_select")],
        [InlineKeyboardButton("Grupo Alta Efectividad 📊", callback_data="main_Button4_select")]
    ]
    if is_admin(message.from_user.id):  # Solo muestra este botón si el usuario es administrador
        buttons.append([InlineKeyboardButton("Revisar Usuarios 👥", callback_data="review_users")])
    await message.reply("Selecciona un Grupo de tipsters:", reply_markup=InlineKeyboardMarkup(buttons))

async def show_config_menu(client, message):
    buttons = [
        [InlineKeyboardButton("➕ Agregar Tipster", callback_data="add_category")],
        [InlineKeyboardButton("➖ Quitar Tipster", callback_data="remove_category")],
        [InlineKeyboardButton("📊 Configurar Efectividad", callback_data="configure_semaphore")],
        [InlineKeyboardButton("⭐ Configurar Racha", callback_data="configure_stars")],
        [InlineKeyboardButton("🔙 Volver", callback_data="select_main_button")]
    ]
    await message.reply("Aquí puedes configurar los tipsters:", reply_markup=InlineKeyboardMarkup(buttons))

button_names = {
    "Button1": "Tipster Nacionales 🇲🇽",
    "Button2": "Tipsters Americanos 🇺🇸",
    "Button3": "Tipsters Europeos 🇪🇺",
    "Button4": "Grupo Alta Efectividad 📊"
}

def get_button_name(button_key):
    return button_names.get(button_key, button_key)

# Manejar el comando /start
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    await message.reply(
        "Hola, soy el bot de TipstersBetVIP y seré el encargado de enviar los tipsters que me pidas. Espera la confirmación del administrador para activar tu membresía VIP.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Inicio", callback_data="inicio")]]
        )
    )
    await client.send_message(
        config.admin_id,
        f"El usuario {user_name} ({user_id}) quiere suscribirse. Aprobar?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Aprobar", callback_data=f"approve_{user_id}")],
            [InlineKeyboardButton("Rechazar", callback_data=f"reject_{user_id}")]
        ])
    )

# Manejar el botón de "Inicio"
@app.on_callback_query(filters.regex(r"inicio"))
async def handle_inicio(client, callback_query):
    await callback_query.answer("¡Bienvenido! Por favor espera la confirmación del administrador.")

# Manejar la aprobación del administrador
@app.on_callback_query(filters.regex(r"approve_"))
async def approve_user(client, callback_query):
    user_id = int(callback_query.data.split("_")[1])
    user = await client.get_users(user_id)
    approved_time = datetime.datetime.now().isoformat()
    add_user(user_id, user.first_name, 1, 0, approved_time)
    await client.send_message(user_id, "¡Felicidades! Has sido aprobado. Por favor, espera mientras configuramos tu suscripción.")
    await client.send_message(callback_query.from_user.id, f"Introduce el número de días de suscripción para {user.first_name}:")
    set_user_state(callback_query.from_user.id, f"awaiting_days_{user_id}")
    await callback_query.answer(f"Usuario {user.first_name} aprobado.")

# Nueva función para manejar el rechazo del administrador
@app.on_callback_query(filters.regex(r"reject_"))
async def reject_user(client, callback_query):
    user_id = int(callback_query.data.split("_")[1])
    user = await client.get_users(user_id)
    await client.send_message(user_id, "Lo sentimos, tu solicitud de suscripción ha sido rechazada.")
    await callback_query.answer(f"Usuario {user.first_name} rechazado.")

# Nueva función para calcular y notificar el tiempo restante de la membresía
async def calculate_time_left(client, user_id, total_time):
    time_left = total_time
    while time_left > 0:
        days_left = time_left // (24 * 3600)
        await client.send_message(user_id, f"Te quedan {days_left} días de membresía.")
        await asyncio.sleep(24 * 3600)
        time_left -= 24 * 3600
    await client.send_message(user_id, "Tu membresía ha expirado.")

# Función para eliminar usuarios después de cierto tiempo
async def remove_user_after_time(client, user_id, delay):
    await asyncio.sleep(delay)
    user = get_user(user_id)
    if user:
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        try:
            await client.send_message(user_id, "Tu suscripción ha terminado y has sido eliminado de la lista de suscriptores.")
        except Exception as e:
            logging.error(f"Error al enviar mensaje al usuario {user_id}: {e}")
        logging.info(f"Usuario {user_id} eliminado después de {delay} segundos.")

# Verificar si el usuario está aprobado
def is_user_approved(user_id):
    user = get_user(user_id)
    return user and user[0][2] == 1

# Menú de administración
@app.on_message(filters.command("admin") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def admin_menu(client, message):
    await show_main_button_menu(client, message)

# Manejar la selección del botón principal en administración
@app.on_callback_query(filters.regex(r"main_(Button[1-4])_select") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def handle_main_button_selection(client, callback_query):
    main_button = callback_query.data.split("_")[1]
    set_user_state(callback_query.from_user.id, f"selected_{main_button}")
    await show_config_menu(client, callback_query.message)
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"select_main_button") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def select_main_button(client, callback_query):
    await show_main_button_menu(client, callback_query.message)
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"add_category") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def add_category_callback(client, callback_query):
    main_button = get_user_state(callback_query.from_user.id).split("_")[1]
    await callback_query.message.reply("Envía el nombre del nuevo tipster.")
    set_user_state(callback_query.from_user.id, f"adding_category_" + main_button)
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"remove_category") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def remove_category(client, callback_query):
    main_button = get_user_state(callback_query.from_user.id).split("_")[1]
    categories_list = get_categories(main_button)
    if not categories_list:
        await callback_query.message.reply("No hay tipsters para quitar.")
        await show_config_menu(client, callback_query.message)
        return
    buttons = [[InlineKeyboardButton(f"{category[1]} {category[2]} {'🎖' * category[3]}", callback_data=f"remove_{category[1]}_{main_button}")] for category in categories_list]
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="show_config_menu")])
    await send_buttons(client, callback_query, "Selecciona un tipster para quitar:", buttons)

@app.on_callback_query(filters.regex(r"remove_(.+)_(Button[1-4])") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def handle_remove_category(client, callback_query):
    category = callback_query.data.split("_")[1]
    main_button = callback_query.data.split("_")[2]
    delete_category(category)
    await callback_query.message.reply(f"Tipster '{category}' eliminado de '{get_button_name(main_button)}'.")
    await show_config_menu(client, callback_query.message)
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"configure_semaphore") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def configure_semaphore(client, callback_query):
    main_button = get_user_state(callback_query.from_user.id).split("_")[1]
    categories_list = get_categories(main_button)
    if not categories_list:
        await callback_query.message.reply("No hay tipsters para configurar.")
        await show_config_menu(client, callback_query.message)
        return
    buttons = [[InlineKeyboardButton(f"{category[1]} {category[2]} {'🎖' * category[3]}", callback_data=f"set_semaphore_{category[1]}_{main_button}")] for category in categories_list]
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="show_config_menu")])
    await send_buttons(client, callback_query, "Selecciona un tipster para configurar su efectividad:", buttons)

@app.on_callback_query(filters.regex(r"set_semaphore_(.+)_(Button[1-4])") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def handle_set_semaphore(client, callback_query):
    category = callback_query.data.split("_")[2]
    main_button = callback_query.data.split("_")[3]
    buttons = [
        [InlineKeyboardButton("🔴", callback_data=f"semaphore_{category}_{main_button}_🔴")],
        [InlineKeyboardButton("🟡", callback_data=f"semaphore_{category}_{main_button}_🟡")],
        [InlineKeyboardButton("🟢", callback_data=f"semaphore_{category}_{main_button}_🟢")],
        [InlineKeyboardButton("🔙 Volver", callback_data=f"configure_semaphore_{main_button}")]
    ]
    await send_buttons(client, callback_query, f"Selecciona la efectividad para '{category}':", buttons)

@app.on_callback_query(filters.regex(r"semaphore_(.+)_(Button[1-4])_(.+)") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def set_semaphore(client, callback_query):
    category = callback_query.data.split("_")[1]
    main_button = callback_query.data.split("_")[2]
    semaphore = callback_query.data.split("_")[3]
    update_category_semaphore(category, semaphore)
    
    if semaphore == '🟢' and main_button != "Button4":
        add_category(category, semaphore, 0, "Button4")
    
    await callback_query.message.reply(f"Efectividad '{semaphore}' asignada al tipster '{category}' en '{get_button_name(main_button)}'.")
    await configure_semaphore(client, callback_query)

@app.on_callback_query(filters.regex(r"configure_stars") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def configure_stars(client, callback_query):
    main_button = get_user_state(callback_query.from_user.id).split("_")[1]
    categories_list = get_categories(main_button)
    if not categories_list:
        await callback_query.message.reply("No hay tipsters para configurar.")
        await show_config_menu(client, callback_query.message)
        return
    buttons = [[InlineKeyboardButton(f"{category[1]} {category[2]} {'🎖' * category[3]}", callback_data=f"set_stars_{category[1]}_{main_button}")] for category in categories_list]
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="show_config_menu")])
    await send_buttons(client, callback_query, "Selecciona un tipster para configurar su racha:", buttons)

@app.on_callback_query(filters.regex(r"set_stars_(.+)_(Button[1-4])") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def handle_set_stars(client, callback_query):
    category = callback_query.data.split("_")[2]
    main_button = callback_query.data.split("_")[3]
    buttons = [[InlineKeyboardButton(f"{i} 🎖", callback_data=f"stars_{category}_{main_button}_{i}") for i in range(1, 6)]]
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data=f"configure_stars_{main_button}")])
    await send_buttons(client, callback_query, f"Selecciona los días de racha para '{category}':", buttons)

@app.on_callback_query(filters.regex(r"stars_(.+)_(Button[1-4])_(\d)") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def set_stars(client, callback_query):
    category = callback_query.data.split("_")[1]
    main_button = callback_query.data.split("_")[2]
    stars = int(callback_query.data.split("_")[3])
    update_category_stars(category, stars)
    await callback_query.message.reply(f"{stars} Racha asignada al tipster '{category}' en '{get_button_name(main_button)}'.")
    await configure_stars(client, callback_query)

@app.on_message(filters.text & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def handle_text_messages(client, message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    if user_state and user_state.startswith("adding_category_"):
        main_button = user_state.split("_")[2]
        category_name = message.text.strip()
        if category_name in [cat[1] for cat in get_categories(main_button)]:
            await message.reply("Esta tipster ya existe.")
        else:
            add_category(category_name, "⚪", 0, main_button)
            await message.reply(f"Tipster '{category_name}' añadido al Grupo '{get_button_name(main_button)}'.")
        set_user_state(user_id, f"selected_{main_button}")
        await show_config_menu(client, message)
    elif user_state and user_state.startswith("awaiting_days_"):
        try:
            days = int(message.text.strip())
            target_user_id = int(user_state.split("_")[2])
            approved_time = datetime.datetime.now().isoformat()
            update_user_subscription(target_user_id, days, approved_time)
            await client.send_message(target_user_id, f"Tu suscripción ha sido configurada por {days} días. Usa el comando /categories para seleccionar los tipsters que deseas recibir.")
            await message.reply(f"Suscripción de {days} días configurada para el usuario {target_user_id}.")
            
            asyncio.create_task(remove_user_after_time(client, target_user_id, days * 24 * 60 * 60))
            asyncio.create_task(calculate_time_left(client, target_user_id, days * 24 * 60 * 60))
        except ValueError:
            await message.reply("Por favor, introduce un número válido de días.")
        finally:
            set_user_state(user_id, None)

@app.on_message(filters.command("categories") & filters.private)
async def show_main_buttons(client, message):
    user_id = message.from_user.id
    if is_user_approved(user_id):
        await show_main_button_menu(client, message)
    else:
        await message.reply("Tu cuenta aún no ha sido aprobada por el administrador. Por favor espera la confirmación.")

@app.on_callback_query(filters.regex(r"main_(Button[1-4])"))
async def show_categories(client, callback_query):
    user_id = callback_query.from_user.id
    if not is_user_approved(user_id):
        await callback_query.answer("Tu cuenta aún no ha sido aprobada por el administrador. Por favor espera la confirmación.", show_alert=True)
        return
    main_button = callback_query.data.split("_")[1]
    categories_list = get_categories(main_button)
    
    if main_button == "Button4":
        categories_list = [cat for cat in categories_list if cat[2] == '🟢']
    
    if not categories_list:
        await callback_query.message.reply("No hay tipsters disponibles en este grupo.")
        return
    
    user_categories = get_user_categories(user_id)
    buttons = []
    for category in categories_list:
        name = category[1]
        semaphore = category[2]
        stars = '🎖' * category[3]
        buttons.append([
            InlineKeyboardButton(
                f"{'✅' if name in user_categories else '❌'} {name} {semaphore} {stars}",
                callback_data=f"toggle_{name}_{main_button}_{user_id}"
            )
        ])
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="select_main_button_user")])
    await send_buttons(client, callback_query, f"Tipsters en {get_button_name(main_button)}:", buttons)

@app.on_callback_query(filters.regex(r"toggle_(.+)_(Button[1-4])_(\d+)"))
async def toggle_category(client, callback_query):
    user_id = callback_query.from_user.id
    if not is_user_approved(user_id):
        await callback_query.answer("Tu cuenta aún no ha sido aprobada por el administrador. Por favor espera la confirmación.", show_alert=True)
        return
    data = callback_query.data.split("_")
    category = data[1]
    main_button = data[2]
    user_id = int(data[3])
    user_categories = get_user_categories(user_id)
    
    if category in user_categories:
        remove_user_category(user_id, category)
        user_categories.remove(category)
        await callback_query.answer(f"{category} desactivada.")
    else:
        add_user_category(user_id, category)
        user_categories.append(category)
        await callback_query.answer(f"{category} activada.")
    
    buttons = []
    for cat in get_categories(main_button):
        name = cat[1]
        semaphore = cat[2]
        stars = '🎖' * cat[3]
        buttons.append([
            InlineKeyboardButton(
                f"{'✅' if name in user_categories else '❌'} {name} {semaphore} {stars}",
                callback_data=f"toggle_{name}_{main_button}_{user_id}"
            )
        ])
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="select_main_button_user")])
    await callback_query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.photo & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def handle_image(client, message):
    user_id = message.from_user.id  # Obtén el user_id del mensaje recibido

    if not message.caption:
        await message.reply("Por favor, añade el nombre del tipster a la imagen.")
        return
    category = message.caption.strip()
    
    # Verificar si la categoría es válida
    if category not in [cat[1] for cat in get_categories("Button1")] + [cat[1] for cat in get_categories("Button2")] + [cat[1] for cat in get_categories("Button3")] + [cat[1] for cat in get_categories("Button4")]:
        await message.reply("Tipster no encontrado.")
        return

    main_button = None
    for btn in ["Button1", "Button2", "Button3", "Button4"]:
        if category in [cat[1] for cat in get_categories(btn)]:
            main_button = btn
            break

    if not main_button:
        await message.reply("Tipster no encontrada.")
        return

    semaphore = next((cat[2] for cat in get_categories(main_button) if cat[1] == category), '⚪')
    stars = next((cat[3] for cat in get_categories(main_button) if cat[1] == category), 0)

    photo = await client.download_media(message.photo.file_id)
    
    watermarked_image = add_watermark(photo, "C:\\Users\\Administrator\\Bot\\watermark.png", semaphore, stars)
    
    user_categories = {cat[1]: True for cat in get_categories(main_button)}  # Definir user_categories
    
    for user in get_user():
        if user[2] and user_categories.get(category):
            await client.send_photo(user[0], watermarked_image, caption=f"Tipster: {category} {semaphore} {'🎖' * stars}")
    
    os.remove(photo)

def add_watermark(input_image_path, watermark_image_path, semaphore, stars):
    base_image = Image.open(input_image_path).convert("RGBA")
    watermark = Image.open(watermark_image_path).convert("RGBA")

    width_ratio = base_image.width / watermark.width
    height_ratio = base_image.height / watermark.height
    scale = min(width_ratio, height_ratio)

    new_size = (int(watermark.width * scale), int(watermark.height * scale))
    watermark = watermark.resize(new_size, Image.LANCZOS)

    position = ((base_image.width - watermark.width) // 2, (base_image.height - watermark.height) // 2)
    transparent = Image.new('RGBA', base_image.size, (0,0,0,0))
    transparent.paste(base_image, (0,0))
    transparent.paste(watermark, position, mask=watermark)
    
    draw = ImageDraw.Draw(transparent)
    text = f"{semaphore} {'🎖' * stars}"
    text_position = (10, 10)
    draw.text(text_position, text, fill=(255, 255, 255, 128))

    output = io.BytesIO()
    transparent.convert("RGB").save(output, format="JPEG")
    output.seek(0)

    return output

@app.on_callback_query(filters.regex(r"review_users") & filters.create(lambda _, __, m: is_main_admin(m.from_user.id)))
async def review_users(client, callback_query):
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    if not users:
        await callback_query.message.reply("No hay usuarios suscritos.")
        return
    
    buttons = []
    for user in users:
        subscription_days = user[3]
        approved_time = datetime.datetime.fromisoformat(user[4])
        days_left = (approved_time + datetime.timedelta(days=subscription_days) - datetime.datetime.now()).days
        buttons.append([InlineKeyboardButton(f"{user[1]} - {days_left} días restantes", callback_data=f"remove_{user[0]}")])
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="admin_menu")])
    
    await callback_query.message.reply("Usuarios suscritos:", reply_markup=InlineKeyboardMarkup(buttons))
    await callback_query.answer()

@app.on_message(filters.command("list_users") & filters.create(lambda _, __, m: is_main_admin(m.from_user.id)))
async def list_users(client, message):
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    if not users:
        await message.reply("No hay usuarios suscritos.")
        return
    buttons = []
    for user in users:
        subscription_days = user[3]
        approved_time = datetime.datetime.fromisoformat(user[4])
        days_left = (approved_time + datetime.timedelta(days=subscription_days) - datetime.datetime.now()).days
        buttons.append([InlineKeyboardButton(f"{user[1]} - {days_left} días restantes", callback_data=f"remove_{user[0]}")])
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="admin_menu")])
    
    await message.reply("Usuarios suscritos:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"remove_") & filters.create(lambda _, __, m: is_main_admin(m.from_user.id)))
async def remove_user(client, callback_query):
    user_id = int(callback_query.data.split("_")[1])
    user = get_user(user_id)
    if user:
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        await callback_query.answer(f"Usuario {user[0][1]} eliminado.")
        await client.send_message(user_id, "Tu membresia premium terminó. Has sido eliminado de la lista de suscriptores por el administrador.")
        await review_users(client, callback_query)  # Refresca la lista de usuarios después de eliminar uno
    else:
        await callback_query.answer("Usuario no encontrado.")

@app.on_callback_query(filters.regex(r"show_config_menu") & filters.create(lambda _, __, m: is_admin(m.from_user.id)))
async def return_to_config_menu(client, callback_query):
    await show_config_menu(client, callback_query.message)
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"admin_menu") & filters.create(lambda _, __, m: is_main_admin(m.from_user.id)))
async def return_to_admin_menu(client, callback_query):
    await admin_menu(client, callback_query.message)
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"select_main_button_user") & filters.private)
async def return_to_main_button_menu(client, callback_query):
    await show_main_button_menu(client, callback_query.message)
    await callback_query.answer()

app.run()
conn.close()
