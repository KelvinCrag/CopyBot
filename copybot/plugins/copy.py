# Copyright (C) 2024 @jithumon
#
# This file is part of copybot.
#
# copybot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# copybot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with copybot.  If not, see <https://www.gnu.org/licenses/>.

import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from sqlite3 import OperationalError

from copybot.db.db import get_dest_by_source, get_source_channels, init_database

SOURCE_CHATS = []
file_groups = {}
MEDIA_GROUP_TTL_SECONDS = 3600
MAX_TRACKED_MEDIA_GROUPS = 10000


def cleanup_file_groups(now):
    expiry = now - MEDIA_GROUP_TTL_SECONDS

    stale_group_ids = [
        group_id for group_id, seen_at in file_groups.items() if seen_at < expiry
    ]
    for group_id in stale_group_ids:
        del file_groups[group_id]

    overflow = len(file_groups) - MAX_TRACKED_MEDIA_GROUPS
    if overflow > 0:
        oldest_group_ids = sorted(file_groups.items(), key=lambda item: item[1])[:overflow]
        for group_id, _ in oldest_group_ids:
            del file_groups[group_id]


async def get_source():
    global SOURCE_CHATS
    while True:
        try:
            SOURCE_CHATS = await get_source_channels()
        except OperationalError:
            init_database()
        await asyncio.sleep(60)


@Client.on_message((filters.group | filters.channel), group=1)
async def file_copier(bot, message):
    curr_chat = message.chat.id
    if curr_chat in SOURCE_CHATS:
        dest_chats = await get_dest_by_source(curr_chat)
        for chat in dest_chats:
            if message.media_group_id:
                now = asyncio.get_running_loop().time()
                cleanup_file_groups(now)

                if message.media_group_id in file_groups:
                    return
                file_groups[message.media_group_id] = now
                messages = await message.get_media_group()
                for mess in messages:
                    await copy_message(mess, chat)
            else:
                await copy_message(message, chat)


async def copy_message(message, chat_id):
    while True:
        try:
            await message.copy(chat_id)
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)


loop = asyncio.get_event_loop()
loop.create_task(get_source())
