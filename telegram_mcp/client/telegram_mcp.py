import asyncio
import os
import logging
import json
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, UserNotParticipantError,
    UsernameNotOccupiedError, ChannelPrivateError, ChatAdminRequiredError,
    PhoneNumberInvalidError, ApiIdInvalidError, AuthKeyError,
    UserDeactivatedError, UserBlockedError, PeerIdInvalidError,
    MessageIdInvalidError
)
from telethon.tl.types import InputPeerUser, InputPeerChannel, User, Chat, Channel
import base64

try:
    from server.mcp import Server, McpError
except ImportError:
    logging.error("Failed to import Server/McpError from server.mcp. Ensure the 'server' directory is accessible.")
    try:
        from ..server.mcp import Server, McpError
    except ImportError:
        logging.error("Relative import also failed. Please check your project structure.")
        raise

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

SESSION_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'telegram_mcp.session'))

class TelegramMCP:
    def __init__(self, loop):
        self.loop = loop
        self.api_id_str = os.getenv("TELEGRAM_APP_API_ID")
        self.api_hash = os.getenv("TELEGRAM_APP_API_HASH")
        self.phone = os.getenv("TELEGRAM_PHONE_NUMBER") 
        self.loaded_shared_session = False

        if not self.api_id_str or not self.api_hash:
            raise ValueError("Missing Telegram API credentials in .env")

        try:
            self.api_id = int(self.api_id_str)
        except ValueError:
            raise ValueError("Invalid TELEGRAM_APP_API_ID format")

        shared_session_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../telegram-bridge/store/shared_session.json'))
        try:
            with open(shared_session_path, 'r') as f:
                shared_data = json.load(f)
            required_keys = ['dc_id', 'addr', 'auth_key', 'user_id']
            if not all(key in shared_data for key in required_keys):
                raise ValueError("Shared session JSON is missing required keys.")

            auth_key_bytes = base64.b64decode(shared_data['auth_key'])
            self.client = TelegramClient(None, self.api_id, self.api_hash, loop=self.loop)
            self.client.session.set_dc(shared_data['dc_id'], shared_data['addr'], 443)
            self.client.session.auth_key = auth_key_bytes
            self.client.session.user_id = shared_data['user_id']
            self.loaded_shared_session = True
            logger.info("Initialized with shared session data.")
        except (FileNotFoundError, ValueError, json.JSONDecodeError, base64.binascii.Error):
            self.client = TelegramClient(SESSION_FILE_PATH, self.api_id, self.api_hash, loop=self.loop)
            self.loaded_shared_session = False
            logger.info("Using standard session file.")

        self._client_lock = asyncio.Lock()

        tools_capabilities = {
            "list_chats": {
                "name": "list_chats",
                "description": "List recent chats with optional limit.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of chats to return (default 20)."
                        }
                    }
                }
            },
            "send_message": {
                "name": "send_message",
                "description": "Send a message to a specified Telegram chat.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "chat_id": {
                            "type": "string",
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
        }

        self.server = Server(
            info={"name": "Telegram MCP Server", "version": "0.0.3"},
            capabilities={
                "tools": tools_capabilities,
                "resources": {}
            },
            loop=self.loop
        )
        self.server.transport = "stdio"
        logger.info("MCP Server initialized.")

        self.server.setRequestHandler("tools/call", self._handle_tool_call)
        self.server.setRequestHandler("tools/list", self._handle_list_tools)
        logger.info("Request handlers registered.")

    async def _handle_list_tools(self, params):
        tool_list = list(self.server.capabilities.get("tools", {}).keys())
        return {
            "content": [
                {
                    "type": "application/json",
                    "text": json.dumps(tool_list, indent=2)
                }
            ]
        }

    async def _handle_tool_call(self, params):
        tool_name = params.get('name')
        if not tool_name:
            raise McpError(-32602, "Missing 'name' parameter.")

        tool_handlers = {
            "list_chats": self.list_chats,
            "send_message": self.send_message
        }

        handler = tool_handlers.get(tool_name)
        if not handler:
            raise McpError(-32601, f"Method '{tool_name}' not found.")

        try:
            return await handler(params.get('parameters', {}))
        except McpError:
            raise
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            raise McpError(-32000, f"Internal error executing tool '{tool_name}'.")

    async def _ensure_connected(self):
        async with self._client_lock:
            if self.client.is_connected():
                if await self.client.is_user_authorized():
                    return
                else:
                    await self.client.disconnect()

            try:
                if self.loaded_shared_session:
                    await self.client.connect()
                    if await self.client.is_user_authorized():
                        return
                    else:
                        await self.client.disconnect()
                        raise McpError(-32002, "Shared session invalid.")
                else:
                    await self.client.start(phone=self.phone)
            except SessionPasswordNeededError:
                raise McpError(-32003, "2FA password required.")
            except (PhoneNumberInvalidError, ApiIdInvalidError):
                raise McpError(-32004, "Invalid credentials.")
            except AuthKeyError:
                raise McpError(-32004, "Invalid auth key.")
            except FloodWaitError as e:
                raise McpError(-32005, f"Flood wait: {e.seconds}s")

    async def list_chats(self, params):
        limit = params.get('limit', 20)

        chats = []
        async for dialog in self.client.iter_dialogs(limit=limit):
            entity = dialog.entity
            chat_info = {
                "id": dialog.id,
                "name": dialog.name,
                "type": dialog.entity.__class__.__name__,
                "is_user": dialog.is_user,
                "is_group": dialog.is_group,
                "is_channel": dialog.is_channel,
                "username": getattr(dialog.entity, 'username', None),
                "last_message_date": dialog.date.isoformat() if dialog.date else None,
                "unread_count": dialog.unread_count
            }
            chats.append(chat_info)

        logger.info(f"Retrieved {len(chats)} chats.")
        return {
            "content": [
                {
                    "type": "application/json",
                    "text": json.dumps(chats, indent=2)
                }
            ]
        }

    async def send_message(self, params):
        chat_id_input = params.get('chat_id')
        message_text = params.get('message')

        if not chat_id_input or not message_text:
            raise McpError(-32602, "Missing required parameters.")

        logger.info(f"Sending message to '{chat_id_input}'")

        try:
            target_entity = await self._resolve_chat_id(chat_id_input)
            sent_message = await self.client.send_message(target_entity, message_text)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Message sent successfully to '{chat_id_input}' (Message ID: {sent_message.id})."
                    }
                ]
            }
        except McpError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise McpError(-32000, f"Failed to send message: {type(e).__name__}")

    async def run(self):
        try:
            await self._ensure_connected()
            while True:
                await asyncio.sleep(1)
        except:
            await self.client.disconnect()
            logger.info("Telegram MCP Server stopped.")