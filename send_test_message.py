import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import InputPeerUser, InputPeerChannel
from telethon.tl.functions.contacts import ResolveUsernameRequest

# Load environment variables from .env file
load_dotenv()

api_id_str = os.getenv("TELEGRAM_APP_API_ID")
api_hash = os.getenv("TELEGRAM_APP_API_HASH")
phone = os.getenv("TELEGRAM_PHONE_NUMBER") # Assuming you might add this to .env for login
session_name = "telegram_mcp" # Use a session file name

# --- Configuration ---
recipient_username = "Roman Gall" # The username or name to search for
message_text = "Hey bro this message was sent from Neura Router MCP for Telegram, could be the first ever in the Cline store"
# --- End Configuration ---

if not api_id_str or not api_hash:
    print("Error: TELEGRAM_APP_API_ID and TELEGRAM_APP_API_HASH must be set in .env")
    exit(1)

try:
    api_id = int(api_id_str)
except ValueError:
    print("Error: TELEGRAM_APP_API_ID must be an integer.")
    exit(1)

async def main():
    print(f"Initializing Telegram client (Session: {session_name})...")
    client = TelegramClient(session_name, api_id, api_hash)

    try:
        print("Connecting to Telegram...")
        await client.connect()

        if not await client.is_user_authorized():
            print("Client not authorized. Attempting login...")
            if not phone:
                phone_input = input("Please enter your phone number (e.g., +1234567890): ")
            else:
                phone_input = phone
                print(f"Using phone number from .env: {phone}")

            await client.send_code_request(phone_input)
            try:
                await client.sign_in(phone_input, input('Enter the code you received: '))
            except SessionPasswordNeededError:
                await client.sign_in(password=input('Two-step verification password: '))
            print("Login successful!")
        else:
            print("Already authorized.")

        print(f"Attempting to find recipient: {recipient_username}")
        try:
            # Try resolving as username first
            resolved = await client(ResolveUsernameRequest(recipient_username))
            if isinstance(resolved.peer, (InputPeerUser, InputPeerChannel)):
                 target_entity = resolved.peer
                 print(f"Found user/channel by username: {recipient_username}")
            else:
                 raise ValueError("Resolved entity is not a user or channel")

        except Exception as e_resolve:
             print(f"Could not resolve '{recipient_username}' as username ({e_resolve}). Searching contacts/dialogs...")
             target_entity = None
             async for dialog in client.iter_dialogs():
                 # Simple name matching (case-insensitive)
                 if recipient_username.lower() in dialog.name.lower():
                     target_entity = dialog.input_entity
                     print(f"Found potential match by name: {dialog.name} (ID: {dialog.id})")
                     # You might want to add confirmation here if multiple matches are found
                     break

        if target_entity:
            print(f"Sending message to {recipient_username}...")
            await client.send_message(target_entity, message_text)
            print("Message sent successfully!")
        else:
            print(f"Error: Could not find recipient '{recipient_username}' by username or name match in recent dialogs.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Disconnecting client...")
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
