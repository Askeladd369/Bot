from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image, ImageDraw
import io
import os
import config
import logging
import asyncio
import datetime  # Nuevo import

# Configuración de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Verificación de Configuración
required_config = ["api_id", "api_hash", "bot_token", "admin_id"]
for param in required_config:
    if not hasattr(config, param):
        raise ValueError(f"Config parameter {param} is missing")

# Inicializa el cliente de Pyrogram
def init_client():
    return Client("my_bot", api_id=config.api_id, api_hash=config.api_hash, bot_token=config.bot_token)

app = init_client()

# Diccionario para almacenar las preferencias de los usuarios y las categorías
user_preferences = {}
categories = {f"Button{i}": {} for i in range(1, 5)}
user_states = {}

def set_user_state(user_id, state):
    user_states[user_id] = state

def get_user_state(user_id):
    return user_states.get(user_id)


# Funciones auxiliares para manejar los botones y categorías
async def send_buttons(client, callback_query, message, buttons):
    await callback_query.message.reply(message, reply_markup=InlineKeyboardMarkup(buttons))
    await callback_query.answer()

async def show_main_button_menu(client, message):
    buttons = [
        [InlineKeyboardButton("Tipster Nacionales 🇲🇽", callback_data="main_Button1_select")],
        [InlineKeyboardButton("Tipsters Americanos 🇺🇸", callback_data="main_Button2_select")],
        [InlineKeyboardButton("Tipsters Europeos 🇪🇺", callback_data="main_Button3_select")],
        [InlineKeyboardButton("Grupo Alta Efectividad 📊", callback_data="main_Button4_select")],
        [InlineKeyboardButton("Revisar Usuarios 👥", callback_data="review_users")]  # Nuevo botón
    ]
    await message.reply("Selecciona un Grupo de tipsters:", reply_markup=InlineKeyboardMarkup(buttons))

async def show_config_menu(client, message):
    buttons = [
        [InlineKeyboardButton("➕ Agregar Tipster", callback_data="add_category")],
        [InlineKeyboardButton("➖ Quitar Tipster", callback_data="remove_category")],
        [InlineKeyboardButton("📊 Configurar Efectividad", callback_data="configure_semaphore")],
        [InlineKeyboardButton("⭐ Configurar Racha", callback_data="configure_stars")],
        [InlineKeyboardButton("🔙 Seleccionar Otro Grupo", callback_data="select_main_button")]
    ]
    await message.reply("Aquí puedes configurar los tipsters:", reply_markup=InlineKeyboardMarkup(buttons))

# Manejar el comando /start
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    # Mensaje de bienvenida con un botón de "Inicio"
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
        await asyncio.sleep(24 * 3600)  # Esperar un día antes de volver a calcular
        time_left -= 24 * 3600
    await client.send_message(user_id, "Tu membresía ha expirado.")

# Función para eliminar usuarios después de cierto tiempo
async def remove_user_after_time(client, user_id, delay):
    await asyncio.sleep(delay)
    if user_id in user_preferences:
        del user_preferences[user_id]
        try:
            await client.send_message(user_id, "Tu suscripción ha terminado y has sido eliminado de la lista de suscriptores.")
        except Exception as e:
            logging.error(f"Error al enviar mensaje al usuario {user_id}: {e}")
        logging.info(f"Usuario {user_id} eliminado después de {delay} segundos.")

# Verificar si el usuario está aprobado
def is_user_approved(user_id):
    return user_preferences.get(user_id, {}).get("approved", False)

# Menú de administración
@app.on_message(filters.command("admin") & filters.user(config.admin_id))
async def admin_menu(client, message):
    await show_main_button_menu(client, message)

# Manejar la selección del botón principal en administración
@app.on_callback_query(filters.regex(r"main_(Button[1-4])_select") & filters.user(config.admin_id))
async def handle_main_button_selection(client, callback_query):
    main_button = callback_query.data.split("_")[1]
    set_user_state(callback_query.from_user.id, f"selected_{main_button}")
    await show_config_menu(client, callback_query.message)
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"select_main_button") & filters.user(config.admin_id))
async def select_main_button(client, callback_query):
    await show_main_button_menu(client, callback_query.message)
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"add_category") & filters.user(config.admin_id))
async def add_category(client, callback_query):
    main_button = get_user_state(callback_query.from_user.id).split("_")[1]
    await callback_query.message.reply("Envía el nombre del nuevo tipster.")
    set_user_state(callback_query.from_user.id, f"adding_category_{main_button}")
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"remove_category") & filters.user(config.admin_id))
async def remove_category(client, callback_query):
    main_button = get_user_state(callback_query.from_user.id).split("_")[1]
    categories_list = categories.get(main_button, {})
    if not categories_list:
        await callback_query.message.reply("No hay tipsters para quitar.")
        await show_config_menu(client, callback_query.message)
        return
    buttons = [[InlineKeyboardButton(category, callback_data=f"remove_{category}_{main_button}")] for category in categories_list]
    await send_buttons(client, callback_query, "Selecciona un tipster para quitar:", buttons)

@app.on_callback_query(filters.regex(r"remove_(.+)_(Button[1-4])") & filters.user(config.admin_id))
async def handle_remove_category(client, callback_query):
    category = callback_query.data.split("_")[1]
    main_button = callback_query.data.split("_")[2]
    if category in categories[main_button]:
        del categories[main_button][category]
        await callback_query.message.reply(f"Tipster '{category}' eliminado de '{main_button}'.")
    else:
        await callback_query.message.reply("tipster no encontrado.")
    await show_config_menu(client, callback_query.message)
    await callback_query.answer()

@app.on_callback_query(filters.regex(r"configure_semaphore") & filters.user(config.admin_id))
async def configure_semaphore(client, callback_query):
    main_button = get_user_state(callback_query.from_user.id).split("_")[1]
    categories_list = categories.get(main_button, {})
    if not categories_list:
        await callback_query.message.reply("No hay tipsters para configurar.")
        await show_config_menu(client, callback_query.message)
        return
    buttons = [[InlineKeyboardButton(category, callback_data=f"set_semaphore_{category}_{main_button}")] for category in categories_list]
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="show_config_menu")])
    await send_buttons(client, callback_query, "Selecciona un tipster para configurar su efectividad:", buttons)

@app.on_callback_query(filters.regex(r"set_semaphore_(.+)_(Button[1-4])") & filters.user(config.admin_id))
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

@app.on_callback_query(filters.regex(r"semaphore_(.+)_(Button[1-4])_(.+)") & filters.user(config.admin_id))
async def set_semaphore(client, callback_query):
    category = callback_query.data.split("_")[1]
    main_button = callback_query.data.split("_")[2]
    semaphore = callback_query.data.split("_")[3]
    categories[main_button][category]['semaphore'] = semaphore
    
    # Mover el tipster a "Grupo Alta Efectividad" si su semáforo es verde
    if semaphore == '🟢' and category not in categories["Button4"]:
        categories["Button4"][category] = categories[main_button][category]
    
    await callback_query.message.reply(f"efectividad '{semaphore}' asignada al tipster '{category}' en '{main_button}'.")
    await configure_semaphore(client, callback_query)

@app.on_callback_query(filters.regex(r"configure_stars") & filters.user(config.admin_id))
async def configure_stars(client, callback_query):
    main_button = get_user_state(callback_query.from_user.id).split("_")[1]
    categories_list = categories.get(main_button, {})
    if not categories_list:
        await callback_query.message.reply("No hay tipsters para configurar.")
        await show_config_menu(client, callback_query.message)
        return
    buttons = [[InlineKeyboardButton(category, callback_data=f"set_stars_{category}_{main_button}")] for category in categories_list]
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data="show_config_menu")])
    await send_buttons(client, callback_query, "Selecciona un tipster para configurar su racha:", buttons)

@app.on_callback_query(filters.regex(r"set_stars_(.+)_(Button[1-4])") & filters.user(config.admin_id))
async def handle_set_stars(client, callback_query):
    category = callback_query.data.split("_")[2]
    main_button = callback_query.data.split("_")[3]
    buttons = [[InlineKeyboardButton(f"{i} 🎖", callback_data=f"stars_{category}_{main_button}_{i}") for i in range(1, 6)]]
    buttons.append([InlineKeyboardButton("🔙 Volver", callback_data=f"configure_stars_{main_button}")])
    await send_buttons(client, callback_query, f"Selecciona los dias de racha para '{category}':", buttons)

@app.on_callback_query(filters.regex(r"stars_(.+)_(Button[1-4])_(\d)") & filters.user(config.admin_id))
async def set_stars(client, callback_query):
    category = callback_query.data.split("_")[1]
    main_button = callback_query.data.split("_")[2]
    stars = int(callback_query.data.split("_")[3])
    categories[main_button][category]['stars'] = stars
    await callback_query.message.reply(f"{stars} Racha asignada al tipster '{category}' en '{main_button}'.")
    await configure_stars(client, callback_query)

@app.on_message(filters.text & filters.user(config.admin_id))
async def handle_text_messages(client, message):
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    if user_state and user_state.startswith("adding_category_"):
        main_button = user_state.split("_")[2]
        category_name = message.text.strip()
        if category_name in categories[main_button]:
            await message.reply("Esta tipster ya existe.")
        else:
            categories[main_button][category_name] = {"semaphore": "⚪", "stars": 0}
            await message.reply(f"Tipster '{category_name}' añadido al Grupo '{main_button}'.")
        set_user_state(user_id, f"selected_{main_button}")
        await show_config_menu(client, message)
    elif user_state and user_state.startswith("awaiting_days_"):
        try:
            days = int(message.text.strip())
            target_user_id = int(user_state.split("_")[2])
            user_preferences[target_user_id] = {
                "approved": True,
                "categories": {},
                "approved_time": datetime.datetime.now(),
                "subscription_days": days
            }
            await client.send_message(target_user_id, f"Tu suscripción ha sido configurada por {days} días. Usa el comando /categories para seleccionar los tipsters que deseas recibir.")
            await message.reply(f"Suscripción de {days} días configurada para el usuario {target_user_id}.")
            
            # Iniciar temporizador para eliminar usuario después del número de días especificado
            asyncio.create_task(remove_user_after_time(client, target_user_id, days * 24 * 60 * 60))
            
            # Notificar al usuario sobre el tiempo restante de su membresía
            asyncio.create_task(calculate_time_left(client, target_user_id, days * 24 * 60 * 60))
        except ValueError:
            await message.reply("Por favor, introduce un número válido de días.")
        finally:
            set_user_state(user_id, None)

# Verificar aprobación antes de acceder a opciones de usuario
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
    categories_list = categories.get(main_button, {})
    
    # Filtrar los tipsters con semáforo verde si se selecciona el botón "Grupo Alta Efectividad"
    if (main_button == "Button4"):
        categories_list = {k: v for k, v in categories_list.items() if v.get('semaphore') == '🟢'}
    
    if not categories_list:
        await callback_query.message.reply("No hay tipsters disponibles en este grupo.")
        return
    user_categories = user_preferences.get(user_id, {}).get("categories", {})
    buttons = []
    for category, info in categories_list.items():
        semaphore = info.get('semaphore', '⚪')
        stars = '🎖' * info.get('stars', 0)
        buttons.append([
            InlineKeyboardButton(
                f"{'✅' if user_categories.get(category) else '❌'} {category} {semaphore} {stars}",
                callback_data=f"toggle_{category}_{main_button}_{user_id}"
            )
        ])
    await send_buttons(client, callback_query, f"Tipsters en {main_button}:", buttons)

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
    if user_id not in user_preferences:
        user_preferences[user_id] = {"approved": True, "categories": {}}
    user_categories = user_preferences[user_id]["categories"]
    user_categories[category] = not user_categories.get(category, False)
    await callback_query.answer(f"{category} {'activada' if user_categories[category] else 'desactivada'}.")
    buttons = []
    for cat, info in categories[main_button].items():
        semaphore = info.get('semaphore', '⚪')
        stars = '🎖' * info.get('stars', 0)
        buttons.append([
            InlineKeyboardButton(
                f"{'✅' if user_categories.get(cat) else '❌'} {cat} {semaphore} {stars}",
                callback_data=f"toggle_{cat}_{main_button}_{user_id}"
            )
        ])
    await callback_query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.photo & filters.user(config.admin_id))
async def handle_image(client, message):
    if not message.caption:
        await message.reply("Por favor, añade el nombre del tipster a la imagen.")
        return
    category = message.caption.strip()
    if category not in [cat for sublist in categories.values() for cat in sublist]:
        await message.reply("Categoría no válida.")
        return

    main_button = None
    for btn, cats in categories.items():
        if category in cats:
            main_button = btn
            break

    if not main_button:
        await message.reply("Tipster no encontrada.")
        return

    semaphore = categories[main_button][category].get('semaphore', '⚪')
    stars = categories[main_button][category].get('stars', 0)

    # Descargar la imagen
    photo = await client.download_media(message.photo.file_id)
    
    # Añadir marca de agua
    watermarked_image = add_watermark(photo, "C:\\Users\\saidd\\OneDrive\\Escritorio\\Bot Mamado\\Original\\watermark.png", semaphore, stars)
    
    # Reenviar a los usuarios aprobados y que seleccionaron la categoría
    for user_id, prefs in user_preferences.items():
        if prefs["approved"] and prefs["categories"].get(category):
            await client.send_photo(user_id, watermarked_image, caption=f"Categoría: {category} {semaphore} {'🎖' * stars}")
    
    # Borrar la imagen descargada
    os.remove(photo)

# Función para añadir marca de agua al centro de la imagen
def add_watermark(input_image_path, watermark_image_path, semaphore, stars):
    base_image = Image.open(input_image_path)
    watermark = Image.open(watermark_image_path)

    # Calcular la escala y posición
    width_ratio = base_image.width / watermark.width
    height_ratio = base_image.height / watermark.height
    scale = min(width_ratio, height_ratio)

    new_size = (int(watermark.width * scale), int(watermark.height * scale))
    watermark = watermark.resize(new_size, Image.LANCZOS)

    # Posicionar la marca de agua en el centro
    position = ((base_image.width - watermark.width) // 2, (base_image.height - watermark.height) // 2)
    transparent = Image.new('RGBA', base_image.size, (0,0,0,0))
    transparent.paste(base_image, (0,0))
    transparent.paste(watermark, position, mask=watermark)
    
    # Añadir información de semáforo y estrellas
    draw = ImageDraw.Draw(transparent)
    text = f"{semaphore} {'🎖' * stars}"
    text_position = (10, 10)  # Ajusta esta posición según sea necesario
    draw.text(text_position, text, fill=(255, 255, 255, 128))  # Texto en blanco semi-transparente

    output = io.BytesIO()
    transparent.convert("RGB").save(output, format="JPEG")
    output.seek(0)

    return output

@app.on_callback_query(filters.regex(r"review_users") & filters.user(config.admin_id))  # Nueva función para manejar el botón "Revisar Usuarios"
async def review_users(client, callback_query):
    if not user_preferences:
        await callback_query.message.reply("No hay usuarios suscritos.")
        return
    for user_id in user_preferences:
        user = await client.get_users(user_id)
        subscription_days = user_preferences[user_id].get("subscription_days", 0)
        approved_time = user_preferences[user_id].get("approved_time")
        days_left = (approved_time + datetime.timedelta(days=subscription_days) - datetime.datetime.now()).days
        await callback_query.message.reply(f"Usuario: {user.first_name}\nDías restantes: {days_left} días")
    await callback_query.answer()

@app.on_message(filters.command("list_users") & filters.user(config.admin_id))
async def list_users(client, message):
    if not user_preferences:
        await message.reply("No hay usuarios suscritos.")
        return
    buttons = []
    for user_id in user_preferences:
        user = await client.get_users(user_id)
        subscription_days = user_preferences[user_id].get("subscription_days", 0)
        approved_time = user_preferences[user_id].get("approved_time")
        days_left = (approved_time + datetime.timedelta(days=subscription_days) - datetime.datetime.now()).days
        buttons.append([InlineKeyboardButton(f"{user.first_name} - {days_left} días restantes", callback_data=f"remove_{user_id}")])
    await message.reply("Usuarios suscritos:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"remove_") & filters.user(config.admin_id))
async def remove_user(client, callback_query):
    user_id = int(callback_query.data.split("_")[1])
    user = await client.get_users(user_id)
    if user_id in user_preferences:
        del user_preferences[user_id]
        await callback_query.answer(f"Usuario {user.first_name} eliminado.")
        await client.send_message(user_id, "Tu subscripcion termino. Has sido eliminado de la lista de suscriptores por el administrador.")
    else:
        await callback_query.answer("Usuario no encontrado.")

@app.on_callback_query(filters.regex(r"show_config_menu") & filters.user(config.admin_id))
async def return_to_config_menu(client, callback_query):
    await show_config_menu(client, callback_query.message)
    await callback_query.answer()

app.run()
