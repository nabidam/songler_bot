from datetime import datetime
import mysql.connector
from functools import wraps
import logging
from typing import Union, List
from telegram import InlineKeyboardMarkup, KeyboardButton, MenuButton, ReplyKeyboardMarkup, Update, InlineKeyboardButton
import telegram
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, filters, MessageHandler, CallbackQueryHandler
import re
import requests
from urllib.parse import unquote
from bs4 import BeautifulSoup
import eyed3
import json
import os
from dotenv import load_dotenv
from PIL import Image
load_dotenv()

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')
THUMBNAIL_SIZE = (128, 128)


def get_trends(page = 0):
    url = "https://www.radiojavan.com/mp3s/browse/trending/all"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    audio_lists = soup.findAll('div', class_="itemContainer")
    musics = []
    data_to_insert = []
    sql_string = "INSERT IGNORE INTO songs (song, artist, link, created_at) VALUES (%s, %s, %s, %s)"
    for a in audio_lists:
        atag = a.find('a')
        src = unquote(atag["href"])
        filename = src.split("/")[-1]
        artist = a.find('span', class_="artist").text
        song = a.find('span', class_="song").text
        link = f"https://host2.rj-mw1.com/media/mp3/mp3-320/{filename}.mp3"

        # db

        data_to_insert.append((song, artist, link, datetime.now()))

    try:
        db = mysql.connector.connect(
            host="localhost",
            user=DB_USERNAME,
            password=DB_PASSWORD,
            database=DB_DATABASE
        )
        dbcursor = db.cursor()
        dbcursor.executemany(sql_string, data_to_insert)

        db.commit()

        sql_select_query = "SELECT id, song, artist FROM songs ORDER BY created_at DESC LIMIT 5 OFFSET %s"
        dbcursor.execute(sql_select_query, [page * 5])
        # get all records
        records = dbcursor.fetchall()

        for row in records:
            item = {
                "id": row[0],
                "song": row[1],
                "artist": row[2],
            }

            musics.append(item)

    except mysql.connector.Error as error:
        logger.error(error)
    finally:
        if db.is_connected():
            dbcursor.close()
            db.close()
    return musics


def send_action(action):
    """Sends `action` while processing func command."""

    def decorator(func):
        @wraps(func)
        async def command_func(update, context, *args, **kwargs):
            await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
            return await func(update, context,  *args, **kwargs)
        return command_func

    return decorator


send_typing_action = send_action(telegram.constants.ChatAction.TYPING)
send_upload_video_action = send_action(
    telegram.constants.ChatAction.UPLOAD_VIDEO)
send_upload_photo_action = send_action(
    telegram.constants.ChatAction.UPLOAD_PHOTO)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

token = os.getenv('TOKEN')


def build_menu(
    buttons: List[InlineKeyboardButton],
    n_cols: int,
    header_buttons: Union[InlineKeyboardButton,
                          List[InlineKeyboardButton]] = None,
    footer_buttons: Union[InlineKeyboardButton,
                          List[InlineKeyboardButton]] = None
) -> List[List[InlineKeyboardButton]]:
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons if isinstance(
            header_buttons, list) else [header_buttons])
    if footer_buttons:
        menu.append(footer_buttons if isinstance(
            footer_buttons, list) else [footer_buttons])
    return menu


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[KeyboardButton("Trends 😎")]]
    # buttons = [[MenuButton("commands")]]
    reply_markup = ReplyKeyboardMarkup(buttons)
    name = update.message.from_user.first_name
    chat_buttons = await context.bot.get_chat_menu_button(chat_id=update.effective_chat.id)
    logger.info(chat_buttons)
    # await context.bot.set_chat_menu_button(chat_id=update.effective_chat.id, menu_button=MenuButton("commands"))
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello "+name+".\nI'm a bot created by @NabidaM for downloading musics!", reply_markup=reply_markup)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(text)


async def download_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    data = query.data

    if "like" in data:
        await query.answer(text='You liked this song', show_alert=True)
    elif "dislike" in data:
        await query.answer(text='You disliked this song', show_alert=True)
    elif "next" in data:
        page = int(data.split("_")[-1])
        musics = get_trends(page)
        button_list = [InlineKeyboardButton(
            music["artist"]+" - "+music["song"], callback_data=music["id"]) for music in musics]
        button_list.append(InlineKeyboardButton("More?", callback_data=f"next_{page + 1}"))
        reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))
        await query.edit_message_text(text="Trends ...", reply_markup=reply_markup)
        await query.answer()
    else:
        id = data
        try:
            db = mysql.connector.connect(
                host="localhost",
                user=DB_USERNAME,
                password=DB_PASSWORD,
                database=DB_DATABASE
            )
            dbcursor = db.cursor(dictionary=True)

            sql_select_query = "SELECT * FROM songs WHERE id = %s"
            dbcursor.execute(sql_select_query, [id])
            # get all records
            row = dbcursor.fetchall()[0]

            if row:
                filename = row["link"].split("/")[-1]
                filepath = f"mp3s/{filename}"
                text = row["artist"] + " - " + row["song"]
                await query.edit_message_text(text=text)
                if not os.path.isfile(filepath):
                    dl = requests.get(row["link"], stream=True)
                    with open(filepath, "wb") as f:
                        # print(dl)
                        f.write(dl.content)
                        f.close()

                # get thumbnail from audio
                audio_file = eyed3.load(filepath)
                thumbnail = f"thumbnails/{row['artist']} - {row['song']}.jpg"
                for image in audio_file.tag.images:
                    image_file = open(thumbnail, "wb")
                    image_file.write(image.image_data)
                    image_file.close()
                    break

                # resize the thumbnail
                thumbnail_file = Image.open(thumbnail)
                thumbnail_file.thumbnail(THUMBNAIL_SIZE)
                thumbnail_file.save(thumbnail)

                # emotion buttons
                buttons = [InlineKeyboardButton("👍", callback_data="like"),
                        InlineKeyboardButton("👎", callback_data="dislike")]

                reply_markup = InlineKeyboardMarkup(build_menu(buttons, n_cols=2))

                with open(filepath, "rb") as f:
                    thumbnail_file = open(thumbnail, "rb")
                    await context.bot.send_audio(chat_id=update.effective_chat.id, audio=f, caption=text, performer=row["artist"], title=row["song"], thumb=thumbnail_file, reply_markup=reply_markup)

            # logger.info(row)

        except mysql.connector.Error as error:
            logger.error(error)
        finally:
            if db.is_connected():
                dbcursor.close()
                db.close()

        # logger.info(query)
        await query.answer()
    

    # dl = requests.get(
    #     f"https://host2.rj-mw1.com/media/mp3/mp3-320/{query.data}.mp3", stream=True)
    # logger.info("Finished")
    # logger.info(dl)
    # await query.edit_message_text(text=query.data)
    # await context.bot.send_audio(chat_id=update.effective_chat.id, audio=dl.content)
    # await update.message.reply_text(f"https://host2.rj-mw1.com/media/mp3/mp3-320/{query}.mp3")


@send_typing_action
async def trends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    musics = get_trends()
    button_list = [InlineKeyboardButton(
        music["artist"]+" - "+music["song"], callback_data=music["id"]) for music in musics]
    button_list.append(InlineKeyboardButton("More?", callback_data="next_1"))
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Trends ...", reply_markup=reply_markup)
    # await context.bot.send_message(chat_id=update.effective_chat.id, text=text_caps)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display a help message"""
    await update.message.reply_text("Use /trends to test this bot.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(token).build()
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)

    start_handler = CommandHandler('start', start)
    trends_handler = CommandHandler('trends', trends)
    help_handler = CommandHandler('help', help)

    application.add_handler(start_handler)
    application.add_handler(trends_handler)
    application.add_handler(help_handler)
    application.add_handler(echo_handler)

    application.add_handler(CallbackQueryHandler(download_button))

    application.run_polling()
