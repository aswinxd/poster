from telethon import TelegramClient, events, Button
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.errors import FloodWaitError
import asyncio
import motor.motor_asyncio
import re

# Your API ID, API hash, and bot token
api_id = "22181658"
api_hash = '3138df6840cbdbc28c370fd29218139a'
bot_token = '7060907933:AAEChdksWb4ES_RS5Wz083XrcDySiyxiJ18'

# Initialize the Telegram client and bot
client = TelegramClient('user_session', api_id, api_hash)

# Start the bot session
bot = TelegramClient('bot_session', api_id, api_hash)

# Initialize MongoDB client
mongo_client = motor.motor_asyncio.AsyncIOMotorClient('mongodb+srv://forwd:forwdo@cluster0.nkmhi9a.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = mongo_client['telegram_bot']
collection = db['schedules']

# Dictionary to keep track of tasks
tasks = {}

# Function to start the user session
async def start_user_session():
    print("Starting user session...")
    await client.start()  # Will prompt for phone and OTP if needed

# Function to forward messages
async def forward_messages(user_id, schedule_name, source_channel_id, destination_channel_id, batch_size, delay):
    post_counter = 0

    async with client:
        async for message in client.iter_messages(int(source_channel_id), reverse=True):
            if post_counter >= batch_size:
                await asyncio.sleep(delay)
                post_counter = 0

            # Check if the message is a photo, video, or document
            if isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument)):
                try:
                    await client.send_message(int(destination_channel_id), message)
                    post_counter += 1
                except FloodWaitError as e:
                    print(f"FloodWaitError: Sleeping for {e.seconds} seconds")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"An error occurred: {e}")

            if schedule_name not in tasks[user_id] or tasks[user_id][schedule_name].cancelled():
                break

# Event handler for starting the bot
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id

    async with bot.conversation(user_id) as conv:
        await conv.send_message('Please provide a name for the schedule:')
        schedule_name = await conv.get_response()

        await conv.send_message('Please provide the source channel ID:')
        source_channel_id = await conv.get_response()
        if not source_channel_id.text.lstrip('-').isdigit():
            await conv.send_message('Invalid channel ID. Please restart the process with /start.')
            return

        await conv.send_message('Please provide the destination channel ID:')
        destination_channel_id = await conv.get_response()
        if not destination_channel_id.text.lstrip('-').isdigit():
            await conv.send_message('Invalid channel ID. Please restart the process with /start.')
            return

        await conv.send_message('How many posts do you want to forward in each batch?')
        post_limit = await conv.get_response()
        if not post_limit.text.isdigit():
            await conv.send_message('Invalid number of posts. Please restart the process with /start.')
            return

        await conv.send_message('What is the time interval between batches in seconds?')
        delay = await conv.get_response()
        if not delay.text.isdigit():
            await conv.send_message('Invalid delay. Please restart the process with /start.')
            return

        await conv.send_message(f'You have set up the following schedule:\nSchedule Name: {schedule_name.text}\nSource Channel ID: {source_channel_id.text}\nDestination Channel ID: {destination_channel_id.text}\nPost Limit: {post_limit.text}\nDelay: {delay.text} seconds\n\nDo you want to start forwarding? (yes/no)')
        confirmation = await conv.get_response()
        if confirmation.text.lower() != 'yes':
            await conv.send_message('Schedule setup cancelled.')
            return

        # Store the schedule in the MongoDB collection
        await collection.update_one(
            {'user_id': user_id},
            {'$push': {
                'schedules': {
                    'name': schedule_name.text,
                    'source_channel_id': int(source_channel_id.text),
                    'destination_channel_id': int(destination_channel_id.text),
                    'post_limit': int(post_limit.text),
                    'delay': int(delay.text)
                }
            }},
            upsert=True
        )

        await conv.send_message(f'Forwarding messages from {source_channel_id.text} to {destination_channel_id.text} every {delay.text} seconds...')

        if user_id not in tasks:
            tasks[user_id] = {}

        # Start forwarding messages
        task = asyncio.create_task(forward_messages(user_id, schedule_name.text, int(source_channel_id.text), int(destination_channel_id.text), int(post_limit.text), int(delay.text)))
        tasks[user_id][schedule_name.text] = task

# Run the user session and bot concurrently
async def main():
    # Start user session and bot
    await start_user_session()
    print("User session started successfully!")

    # Start the bot and wait for it to run indefinitely
    await bot.start(bot_token=bot_token)
    print("Bot session started!")

    # Keep both running
    await client.run_until_disconnected()
    await bot.run_until_disconnected()

# Run the event loop
if __name__ == '__main__':
    asyncio.run(main())
