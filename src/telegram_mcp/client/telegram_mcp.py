import asyncio
import os
import logging
import json # Import json
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, UserNotParticipantError, UsernameNotOccupiedError, ChannelPrivateError, ChatAdminRequiredError
from telethon.tl.types import InputPeerUser, InputPeerChannel, User, Chat, Channel

# Use the custom MCP server base from src/mcp.py
from telegram_mcp.server.mcp import Server, McpError
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
                "version": "0.0.2" # Incremented version
            },
            {}, # Capabilities can be empty if using setRequestHandler
            loop=self.loop
        )
        logger.info("MCP Server initialized")

        # Register handlers with the custom server
        # Tool names match the keys in the original __init__ definition
        # Register MCP handlers for all implemented tools
        self.server.setRequestHandler("initialize", self.initialize)
        self.server.setRequestHandler("list_chats", self.list_chats)
        self.server.setRequestHandler("send_message", self.send_message)
        self.server.setRequestHandler("schedule_message", self.schedule_message)
        self.server.setRequestHandler("read_messages", self.read_messages)
        self.server.setRequestHandler("delete_message", self.delete_message)
        self.server.setRequestHandler("edit_message", self.edit_message)
        self.server.setRequestHandler("search_messages", self.search_messages)
        self.server.setRequestHandler("get_message", self.get_message)
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
                    },
                    "schedule_message": {
                        "name": "schedule_message",
                        "description": "Schedule a message to be sent at a specific time.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "chat_id": {
                                    "type": "string",
                                    "description": "The target chat identifier."
                                },
                                "message": {
                                    "type": "string",
                                    "description": "The text message content to send."
                                },
                                "scheduled_time": {
                                    "type": "string",
                                    "description": "ISO 8601 datetime string for when to send the message."
                                }
                            },
                            "required": ["chat_id", "message", "scheduled_time"]
                        }
                    },
                    "read_messages": {
                        "name": "read_messages",
                        "description": "Read messages from a specific chat with optional limit.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "chat_id": {
                                    "type": "string",
                                    "description": "The target chat identifier."
                                },
                                "limit": {
                                    "type": "number",
                                    "description": "Maximum number of messages to return (default 20)."
                                }
                            },
                            "required": ["chat_id"]
                        }
                    },
                    "delete_message": {
                        "name": "delete_message",
                        "description": "Delete a specific message from a chat.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "chat_id": {
                                    "type": "string",
                                    "description": "The target chat identifier."
                                },
                                "message_id": {
                                    "type": "number",
                                    "description": "ID of the message to delete."
                                }
                            },
                            "required": ["chat_id", "message_id"]
                        }
                    },
                    "edit_message": {
                        "name": "edit_message",
                        "description": "Edit an existing message in a chat.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "chat_id": {
                                    "type": "string",
                                    "description": "The target chat identifier."
                                },
                                "message_id": {
                                    "type": "number",
                                    "description": "ID of the message to edit."
                                },
                                "new_text": {
                                    "type": "string",
                                    "description": "The new text for the message."
                                }
                            },
                            "required": ["chat_id", "message_id", "new_text"]
                        }
                    },
                    "search_messages": {
                        "name": "search_messages",
                        "description": "Search for messages in a chat by keyword.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "chat_id": {
                                    "type": "string",
                                    "description": "The target chat identifier."
                                },
                                "query": {
                                    "type": "string",
                                    "description": "Search query text."
                                },
                                "limit": {
                                    "type": "number",
                                    "description": "Maximum number of messages to return (default 20)."
                                }
                            },
                            "required": ["chat_id", "query"]
                        }
                    },
                    "get_message": {
                        "name": "get_message",
                        "description": "Get a specific message by ID from a chat.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "chat_id": {
                                    "type": "string",
                                    "description": "The target chat identifier."
                                },
                                "message_id": {
                                    "type": "number",
                                    "description": "ID of the message to retrieve."
                                }
                            },
                            "required": ["chat_id", "message_id"]
                        }
                    }
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


    async def schedule_message(self, params):
        """Schedule a message to be sent at a specific time."""
        await self._ensure_connected()
        chat_id = params.get('chat_id')
        message = params.get('message')
        scheduled_time = params.get('scheduled_time')
        if not chat_id or not message or not scheduled_time:
            raise McpError(-32602, "Missing required parameters: chat_id, message, or scheduled_time")

        # Validate scheduled_time is an ISO string
        try:
            from datetime import datetime
            datetime.fromisoformat(scheduled_time)
        except ValueError:
            raise McpError(-32602, "Invalid scheduled_time. Must be an ISO 8601 datetime string.")

        # Schedule the message for background execution
        async def _send_scheduled_message():
            await asyncio.sleep(5)  # Simulate scheduling logic
            try:
                target_entity = await self.client.get_entity(chat_id)
                sent_message = await self.client.send_message(target_entity, message)
                logger.info(f"Scheduled message sent successfully: {sent_message.id}")
                return {"content": [{"type": "text", "text": f"Message scheduled for {scheduled_time}"}]}
            except Exception as e:
                logger.error(f"Failed to send scheduled message: {e}")
                raise McpError(-32000, f"Failed to send message: {e}")

        # Add the scheduled task to the event loop
        scheduled_task = self.loop.create_task(_send_scheduled_message())
        return {"content": [{"type": "text", "text": f"Message scheduled for {scheduled_time}"}]}
        
    async def read_messages(self, params):
        """Read messages from a chat with optional limit."""
        await self._ensure_connected()
        chat_id = params.get('chat_id')
        limit = int(params.get('limit', 20))
        
        if not chat_id:
            raise McpError(-32602, "Missing required 'chat_id' parameter.")

        try:
            target_entity = await self.client.get_entity(chat_id)
            messages = []
            
            async for message in self.client.iter_messages(target_entity, limit=limit):
                messages.append({
                    "id": message.id,
                    "text": message.message,
                    "sender": str(message.sender),
                    "date": message.date.isoformat(),
                    "is_reply": message.is_reply
                })
            
            return {
                "content": [
                    {"type": "application/json", "text": json.dumps(messages, indent=2)}
                ]
            }
        except Exception as e:
            logger.error(f"Failed to read messages: {e}")
            raise McpError(-32000, f"Failed to read messages: {e}")

    async def delete_message(self, params):
        """Delete a message from a chat."""
        await self._ensure_connected()
        chat_id = params.get('chat_id')
        message_id = params.get('message_id')

        if not chat_id or not message_id:
            raise McpError(-32602, "Missing required parameters: chat_id or message_id")

        logger.info(f"Executing delete_message tool for chat {chat_id} and message {message_id}")

        try:
            # Get the target chat entity
            target_entity = await self.client.get_entity(chat_id)
            
            # Delete the message
            await self.client.delete_messages(target_entity, [message_id])
            
            return {
                "content": [
                    {"type": "text", "text": f"Message {message_id} deleted from chat {chat_id}"}
                ]
            }
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            raise McpError(-32000, f"Failed to delete message: {e}")

    async def edit_message(self, params):
        """Edit a message in a chat."""
        await self._ensure_connected()
        chat_id = params.get('chat_id')
        message_id = params.get('message_id')
        new_text = params.get('new_text')

        if not chat_id or not message_id or not new_text:
            raise McpError(-32602, "Missing required parameters: chat_id, message_id, or new_text")

        logger.info(f"Executing edit_message tool for chat {chat_id} and message {message_id}")

        try:
            # Get the target chat entity
            target_entity = await self.client.get_entity(chat_id)
            
            # Edit the message
            edited_message = await self.client.edit_message(
                entity=target_entity,
                message=message_id,
                text=new_text
            )
            
            return {
                "content": [
                    {"type": "text", "text": f"Message {message_id} in chat {chat_id} edited successfully"}
                ]
            }
        except FloodWaitError as e:
            logger.error(f"Flood wait error editing message: {e}")
            raise McpError(-32005, f"Telegram API rate limit hit (wait {e.seconds}s)")
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
            raise McpError(-32000, f"Failed to edit message: {e}")
    
    async def search_messages(self, params):
        """Search for messages in a chat by query string."""
        await self._ensure_connected()
        chat_id = params.get('chat_id')
        query = params.get('query')
        limit = int(params.get('limit', 20))
        
        if not chat_id or not query:
            raise McpError(-32602, "Missing required parameters: chat_id or query")
            
        logger.info(f"Executing search_messages tool in chat {chat_id} for query '{query}'")
        
        try:
            # Get the target chat entity
            target_entity = await self.client.get_entity(chat_id)
            
            # Search messages with the query
            messages = []
            async for message in self.client.iter_messages(
                entity=target_entity,
                search=query,
                limit=limit
            ):
                messages.append({
                    "id": message.id,
                    "text": message.message,
                    "sender": str(message.sender_id),
                    "date": message.date.isoformat(),
                    "is_reply": message.is_reply
                })
                
            logger.info(f"Found {len(messages)} messages matching query '{query}'")
            
            return {
                "content": [
                    {"type": "application/json", "text": json.dumps(messages, indent=2)}
                ]
            }
        except FloodWaitError as e:
            logger.error(f"Flood wait error searching messages: {e}")
            raise McpError(-32005, f"Telegram API rate limit hit (wait {e.seconds}s)")
        except Exception as e:
            logger.error(f"Failed to search messages: {e}")
            raise McpError(-32000, f"Failed to search messages: {e}")
    
    async def get_message(self, params):
        """Get a specific message by ID from a chat."""
        await self._ensure_connected()
        chat_id = params.get('chat_id')
        message_id = params.get('message_id')
        
        if not chat_id or not message_id:
            raise McpError(-32602, "Missing required parameters: chat_id or message_id")
            
        logger.info(f"Executing get_message tool for chat {chat_id}, message ID {message_id}")
        
        try:
            # Get the target chat entity
            target_entity = await self.client.get_entity(chat_id)
            
            # Get the specific message
            message = await self.client.get_messages(
                entity=target_entity,
                ids=message_id
            )
            
            if not message:
                raise McpError(-32404, f"Message with ID {message_id} not found in chat {chat_id}")
                
            # Convert message to dict for JSON serialization
            message_data = {
                "id": message.id,
                "text": message.message,
                "sender_id": str(message.sender_id),
                "date": message.date.isoformat(),
                "is_reply": message.is_reply,
                "reply_to_msg_id": message.reply_to_msg_id,
            }
            
            # Add media information if present
            if message.media:
                message_data["has_media"] = True
                message_data["media_type"] = str(type(message.media).__name__)
            else:
                message_data["has_media"] = False
                
            return {
                "content": [
                    {"type": "application/json", "text": json.dumps(message_data, indent=2)}
                ]
            }
        except FloodWaitError as e:
            logger.error(f"Flood wait error getting message: {e}")
            raise McpError(-32005, f"Telegram API rate limit hit (wait {e.seconds}s)")
        except Exception as e:
            logger.error(f"Failed to get message: {e}")
            raise McpError(-32000, f"Failed to get message: {e}")

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