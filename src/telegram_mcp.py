import asyncio
import os
import logging
import json # Import json
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, UserNotParticipantError, UsernameNotOccupiedError, ChannelPrivateError, ChatAdminRequiredError
from telethon.tl.types import InputPeerUser, InputPeerChannel, User, Chat, Channel

# Use the custom MCP server base from src/mcp.py
from mcp import Server, McpError
# Assuming MCP types and transport might be needed, adjust if using official SDK later
# from MCP.types import CallToolRequestSchema
# from MCP.transports import StdioServerTransport

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Constants ---
# Define absolute path for session file to avoid ambiguity
SESSION_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'telegram_mcp.session'))
logger = logging.getLogger(__name__) # Define logger earlier

class TelegramMCP:
    def __init__(self, loop): # Accept the event loop
        self.loop = loop
        self.api_id_str = os.getenv("TELEGRAM_APP_API_ID")
        self.api_hash = os.getenv("TELEGRAM_APP_API_HASH")
        self.phone = os.getenv("TELEGRAM_PHONE_NUMBER") # Optional, for login prompt

        if not self.api_id_str or not self.api_hash:
            logger.error("TELEGRAM_APP_API_ID and TELEGRAM_APP_API_HASH must be set in .env")
            raise ValueError("Missing Telegram API credentials in .env file")

        try:
            self.api_id = int(self.api_id_str)
        except ValueError:
            logger.error("TELEGRAM_APP_API_ID must be an integer.")
            raise ValueError("Invalid TELEGRAM_APP_API_ID format")

        # Initialize Telegram Client (will connect in run)
        # Use the absolute path for the session file
        # Pass the loop to Telethon client
        logger.info(f"Initializing TelegramClient with session path: {SESSION_FILE_PATH}")
        self.client = TelegramClient(SESSION_FILE_PATH, self.api_id, self.api_hash, loop=self.loop)
        self._client_lock = asyncio.Lock() # Lock for client operations

        # Initialize MCP Server, passing the loop
        self.server = Server(
            {
                "name": "neura-router-telegram-mcp",
                "version": "1.1.0" # Incremented version
            },
            {}, # Capabilities can be empty if using setRequestHandler
            loop=self.loop
        )
        logger.info("MCP Server initialized")

        # Register handlers with the custom server
        # Tool names match the keys in the original __init__ definition
        self.server.setRequestHandler("initialize", self.initialize) # Add initialize handler
        self.server.setRequestHandler("list_chats", self.list_chats)
        self.server.setRequestHandler("send_message", self.send_message)
        logger.info("MCP request handlers registered")

    async def _ensure_connected(self):
        """Connects and authorizes the client if not already connected. Uses a lock."""
        # This lock prevents race conditions if multiple MCP requests arrive concurrently
        # before the client is fully initialized.
        async with self._client_lock:
            if not self.client.is_connected():
                logger.info("Connecting Telegram client...")
                try:
                    # Using start() handles connection and authorization based on session
                    # This might still fail non-interactively if session is invalid/missing
                    # and phone/code/2fa is needed.
                    await self.client.start(phone=self.phone)
                    logger.info("Telegram client started successfully via start().")

                except Exception as e:
                    logger.error(f"Failed to start/connect Telegram client: {e}")
                    # Attempting to provide more specific feedback if possible
                    if "database is locked" in str(e).lower():
                         logger.error("Database lock error - ensure only one instance is running.")
                         raise McpError(-32006, "Database lock error. Check for other running instances.")
                    raise McpError(-32001, f"Telegram connection/start error: {e}")

            if not await self.client.is_user_authorized():
                 # This state should ideally not be reached if start() requires login
                 logger.error("Client is connected but not authorized. Manual login likely required.")
                 # It's crucial the session file is valid for non-interactive use.
                 raise McpError(-32002, "Telegram authorization failed. Ensure session file is valid or run interactively first.")

    async def initialize(self, params):
        """Handle the MCP initialize request and return capabilities."""
        # Based on registered handlers
        logger.info("Handling initialize request")
        # The 'params' usually contain client info, which we aren't using here.
        # Construct the response according to MCP specification.
        return {
            "protocolVersion": "2024-11-05", # Use standard MCP protocol version format
            "serverInfo": self.server.info, # Required server info (name, version)
            "capabilities": {
                 # Tools should be an object mapping name to definition
                "tools": {
                    "list_chats": {
                        "name": "list_chats",
                        "description": "List recent Telegram chats with an optional limit.",
                        # Add inputSchema if defined/needed
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {
                                    "type": "number",
                                    "description": "Maximum number of chats to return (default 20)"
                                }
                            }
                        }
                    },
                    "send_message": {
                        "name": "send_message",
                        "description": "Send a message to a specified Telegram chat (user ID, username, phone, or link).",
                        # Add inputSchema if defined/needed
                         "inputSchema": {
                            "type": "object",
                            "properties": {
                                "chat_id": {
                                    "type": "string", # Can be int or string, but string covers all cases
                                    "description": "The target chat identifier (username, phone number, user ID, chat ID, or invite link)."
                                },
                                "message": {
                                    "type": "string",
                                    "description": "The text message content to send."
                                }
                            },
                            "required": ["chat_id", "message"]
                        }
                    }
                    # Add more tools here if they are implemented and registered
                },
                 # Resources should be an object mapping URI to definition (or empty)
                "resources": {} # No resources defined currently
            }
        }

    async def list_chats(self, params):
        """List recent chats with optional limit parameter."""
        await self._ensure_connected()
        limit = params.get('limit', 20)
        # Validate limit parameter
        try:
            limit = int(limit)
            if limit <= 0:
                limit = 20
        except (ValueError, TypeError):
            limit = 20

        logger.info(f"Executing list_chats tool with limit: {limit}")

        chats = []
        try:
            async for dialog in self.client.iter_dialogs(limit=limit):
                entity = dialog.entity
                # Basic info common to User, Chat, Channel
                chat_info = {
                    "id": dialog.id,
                    "name": dialog.name,
                    "type": entity.__class__.__name__,
                    "is_user": dialog.is_user,
                    "is_group": dialog.is_group,
                    "is_channel": dialog.is_channel,
                    "username": getattr(entity, 'username', None),
                    "last_message_date": dialog.date.isoformat() if dialog.date else None,
                    "unread_count": dialog.unread_count
                }
                # Add specific fields if needed
                # if isinstance(entity, User):
                #     chat_info['phone'] = entity.phone
                # elif isinstance(entity, Channel):
                #     chat_info['participants_count'] = entity.participants_count

                chats.append(chat_info)
            logger.info(f"Successfully retrieved {len(chats)} chats.")
            # Return format expected by MCP client
            return {
                "content": [
                    # Use application/json for structured data
                    { "type": "application/json", "text": json.dumps(chats, indent=2) }
                ]
            }
        except FloodWaitError as e:
             logger.error(f"Flood wait error listing chats: {e}")
             raise McpError(-32005, f"Telegram API rate limit hit (wait {e.seconds}s)")
        except Exception as e:
            logger.error(f"Error listing chats: {e}", exc_info=True) # Log traceback
            raise McpError(-32000, f"Failed to list chats: {type(e).__name__}")


    async def send_message(self, params):
        """Send a message to a chat."""
        await self._ensure_connected()
        chat_id_input = params.get('chat_id') # Can be username, phone, ID, link
        message_text = params.get('message')

        if not chat_id_input or not message_text:
             logger.error("send_message requires 'chat_id' and 'message' parameters.")
             raise McpError(-32602, "Missing 'chat_id' or 'message' parameter")

        logger.info(f"Executing send_message tool to '{chat_id_input}'")

        try:
            # Attempt to convert chat_id_input to integer if it looks like one
            try:
                 chat_id = int(chat_id_input)
                 logger.info(f"Interpreted chat_id '{chat_id_input}' as integer ID.")
            except ValueError:
                 chat_id = chat_id_input # Keep as string (username, phone, link)
                 logger.info(f"Interpreting chat_id '{chat_id_input}' as username/phone/link.")

            # Use get_entity to resolve username, phone, ID, or link
            target_entity = await self.client.get_entity(chat_id)

            sent_message = await self.client.send_message(target_entity, message_text)
            logger.info(f"Message successfully sent to '{chat_id_input}' (Resolved ID: {target_entity.id}, Message ID: {sent_message.id}).")
            return {
                 "content": [
                    { "type": "text", "text": f"Message sent successfully to '{chat_id_input}' (Message ID: {sent_message.id})." }
                 ]
            }
        except (ValueError, TypeError) as e:
             # ValueError: "Could not find the input entity for..." or "Cannot cast..."
             # TypeError: Often related to incorrect type passed internally
             logger.error(f"Could not find or resolve entity '{chat_id_input}': {e}")
             raise McpError(-32010, f"Could not find user/chat '{chat_id_input}'. Check username/ID.")
        except UsernameNotOccupiedError:
             logger.error(f"Username '{chat_id_input}' not occupied.")
             raise McpError(-32010, f"Username '{chat_id_input}' does not exist.")
        except (ChannelPrivateError, ChatAdminRequiredError) as e:
             logger.error(f"Cannot send message to '{chat_id_input}': {e}")
             raise McpError(-32011, f"Cannot send message to '{chat_id_input}': Permission denied ({type(e).__name__}).")
        except UserNotParticipantError:
             logger.error(f"Cannot send message: Not a participant in chat '{chat_id_input}'")
             raise McpError(-32011, f"Cannot send message: Not a participant in chat '{chat_id_input}'.")
        except FloodWaitError as e:
             logger.error(f"Flood wait error sending message: {e}")
             raise McpError(-32005, f"Telegram API rate limit hit (wait {e.seconds}s)")
        except Exception as e:
            # Catch other potential Telethon or network errors
            logger.error(f"Unexpected error sending message to '{chat_id_input}': {type(e).__name__}: {e}", exc_info=True)
            raise McpError(-32000, f"Failed to send message: {type(e).__name__}")


    async def run(self):
        """Connects the Telegram client and starts the MCP server."""
        logger.info("Starting Telegram MCP Server...")
        try:
            # Ensure client is connected before starting server loop
            # This handles the initial connection and session validation.
            await self._ensure_connected()
            logger.info(f"Telegram client running. Authorized: {await self.client.is_user_authorized()}")

            # Start the MCP server's synchronous message processing loop in a separate thread
            import threading
            import sys

            def run_server_sync():
                 logger.info("MCP message processing thread started.")
                 # The loop should already be set in __init__ and passed to Server
                 self.server._process_messages() # Call the blocking message loop
                 logger.info("MCP message processing thread finished.")

            # Pass transport info if needed by Server class (currently not used)
            self.server.transport = "stdio"

            server_thread = threading.Thread(target=run_server_sync, daemon=True)
            server_thread.start()
            logger.info("MCP server thread started.")

            # Keep main async thread alive while daemon thread processes stdin
            while server_thread.is_alive():
                 await asyncio.sleep(1)
            logger.info("MCP server thread stopped (stdin likely closed).")

        except McpError as e:
             # Handle MCP specific errors cleanly if possible
             logger.error(f"MCP Error during server run: {e.code} - {e.message}")
        except Exception as e:
            logger.error(f"Fatal error during server run: {e}", exc_info=True) # Log traceback
        finally:
            if self.client.is_connected():
                logger.info("Disconnecting Telegram client...")
                await self.client.disconnect()
            logger.info("Telegram MCP Server stopped.")


if __name__ == "__main__":
    # Get the current event loop or create one if needed for the main thread
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    instance = TelegramMCP(loop)
    try:
        loop.run_until_complete(instance.run())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user (KeyboardInterrupt).")
    finally:
         # Ensure loop closes cleanly
         # Close pending tasks if any
         tasks = asyncio.all_tasks(loop=loop)
         for task in tasks:
              task.cancel()
         # Gather cancelled tasks to allow them to process cancellation
         # loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True)) # Might be needed
         if loop.is_running():
             loop.stop() # Stop the loop if it's still running
         if not loop.is_closed():
             loop.close()
             logger.info("Event loop closed.")
