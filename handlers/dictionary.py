import random

from functools import partial
from tabulate import tabulate
from aiogram import Router, types, Bot
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from helpers import (
    edit_message,
    get_dictionaries,
)
from keyboards.dictionary.back_to_dictionary_keyboard import back_to_dict_kb
from keyboards.dictionary.dictionary_keyboard import choose_dict_kb
from keyboards.dictionary.incr_visible_words import incr_visible_words_kb
from keyboards.dictionary.table_style_keyboard import table_style_kb
from keyboards.add_dictionary.add_dictionary_keyboard import add_dictionary_kb
from keyboards.dictionary.no_words_in_dictionary_keyboard import no_words_in_dict_kb
from mongo_db import users


DASH_LENGTH = 52

ROOM_FOR_ONE_WORD = 31

first_word = "WORD"

second_word = "TRANSLATION"

router = Router()


class FSMDeleteWord(StatesGroup):
    print = State()
    number = State()


@router.callback_query(Text("dictionary"))
async def choose_dictionary_language(callback: types.CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    dictionaries = get_dictionaries(user_id)
    if not dictionaries:
        await edit_message(
            bot=bot,
            callback=callback,
            message="You don't have any dictionaries yet, please add some 🤷‍♂️",
            keyboard_fn=add_dictionary_kb,
        )
    else:
        await edit_message(
            bot=bot,
            callback=callback,
            message="Choose dictionary 👀",
            keyboard_fn=partial(choose_dict_kb, dictionaries),
        )


@router.callback_query(lambda message: message.data.startswith("choose_dict_to_get"))
async def get_words_dictionary(
    callback: types.CallbackQuery, bot: Bot, state: FSMContext
):
    language = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    user = users.find_one({"user_id": user_id})
    words = user["dictionaries"][language]
    if words:
        # Ability to get into the delete handler
        await state.set_state(FSMDeleteWord.print)
        await state.update_data(
            code=language, words=words, visible_translations=0, visible_words=0
        )
        await edit_message(
            bot=bot,
            callback=callback,
            message="Choose how to display the dictionary 🔍",
            keyboard_fn=table_style_kb,
        )

    else:
        await edit_message(
            bot=bot,
            callback=callback,
            message="There are no words in this dictionary 🤷‍♂️",
            keyboard_fn=partial(no_words_in_dict_kb, language),
        )


@router.callback_query(
    FSMDeleteWord.print, lambda message: message.data.startswith("print_words_")
)
async def print_words(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    print_style, incr_number = (
        callback.data.split("_")[-2],
        int(callback.data.split("_")[-1]),
    )
    words, code, visible_translations, visible_words = (
        data["words"],
        data["code"],
        data["visible_translations"],
        data["visible_words"],
    )
    match print_style:
        case "word":
            flag_hide_1, flag_hide_5 = False, False
            match incr_number:
                case 1:
                    visible_words += 1
                    await state.update_data(visible_words=visible_words)
                case 5:
                    visible_words += 5
                    await state.update_data(visible_words=visible_words)
                case 0:
                    random.shuffle(words)
            if len(words) - visible_words < 5:
                flag_hide_5 = True
            if len(words) == visible_words:
                flag_hide_1 = True
            text = ""
            for idx, word in enumerate(words):
                text += f'{word["word"] if idx < visible_words else "*" * 10} - {word["translate"]}\n'
            await edit_message(
                bot=bot,
                callback=callback,
                keyboard_fn=partial(
                    incr_visible_words_kb, code, "word", flag_hide_1, flag_hide_5
                ),
                message=text,
            )
        case "translate":
            flag_hide_1, flag_hide_5 = False, False
            match incr_number:
                case 1:
                    visible_translations += 1
                    await state.update_data(visible_translations=visible_translations)
                case 5:
                    visible_translations += 5
                    await state.update_data(visible_translations=visible_translations)
                case 0:
                    random.shuffle(words)
            if len(words) - visible_translations < 5:
                flag_hide_5 = True
            if len(words) == visible_translations:
                flag_hide_1 = True
            text = ""
            for idx, word in enumerate(words):
                text += f'{word["word"]} - {word["translate"] if idx < visible_translations else "*" * 10}\n'
            await edit_message(
                bot=bot,
                callback=callback,
                keyboard_fn=partial(
                    incr_visible_words_kb, code, "translate", flag_hide_1, flag_hide_5
                ),
                message=text,
            )
        case "table":
            await state.set_state(FSMDeleteWord.number)
            table = [[item["word"], item["translate"]] for item in words]
            await edit_message(
                bot=bot,
                callback=callback,
                keyboard_fn=partial(back_to_dict_kb, code),
                message=f'<pre>{tabulate(table, headers=["word", "translation"],  tablefmt="presto")}</pre>\n\nTo delete a word, write it',
            )
        case "plain":
            await state.set_state(FSMDeleteWord.number)
            message_to_print = ""
            for word in words:
                message_to_print += f'{word["word"]} - {word["translate"]}\n'
            await edit_message(
                bot=bot,
                callback=callback,
                keyboard_fn=partial(back_to_dict_kb, code),
                message=message_to_print,
            )
            


@router.message(FSMDeleteWord.number)
async def delete_word(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.from_user.id
    data = await state.get_data()
    words, word, code = data["words"], message.text, data["code"]
    word_to_delete = None
    for elem in words:
        if word == elem["word"]:
            word_to_delete = elem
            break
    if word_to_delete:
        words = list(filter(lambda a: a != word_to_delete, words))
        await state.update_data(words=words)
        users.update_one(
            {"user_id": user_id},
            {"$pull": {f"dictionaries.{code}": word_to_delete}},
        )
        await state.set_state(FSMDeleteWord.number)
        if words:
            table = [[item["word"], item["translate"]] for item in words]

            await message.answer(
                reply_markup=back_to_dict_kb(code),
                parse_mode="HTML",
                text=f'<pre>{tabulate(table, headers=["word", "translation"], tablefmt="presto")}</pre>\n\nTo delete a word, write it',
            )
        else:
            await message.answer(
                text="There are no words in this dictionary",
                reply_markup=no_words_in_dict_kb(code),
            )
    else:
        await message.answer(text="Wrong word ❌")
