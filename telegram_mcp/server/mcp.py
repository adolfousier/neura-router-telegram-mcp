import json
import sys
import logging
from typing import Any, Dict, List, Optional, Union
import asyncio # Add asyncio import

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class McpError(Exception):
    """MCP error class"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"MCP Error {code}: {message}")



class Server:
    """MCP Server implementation"""
    def __init__(self, info: Dict[str, str], capabilities: Dict[str, Dict], loop=None):
        self.info = info
        self.capabilities = capabilities
        self.request_handlers = {
            "tools/call": self._handle_tool_call,
            "initialize": self._handle_initialize
        }
        self.onerror = None
        
        # Get the loop passed or the current running loop
        self.loop = loop
        if self.loop is None:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.warning("No running event loop found, creating a new one for Server.")
                # This might be problematic if the main app runs its own loop later
                self.loop = asyncio.new_event_loop()
                # asyncio.set_event_loop(self.loop) # Avoid setting global loop if possible
        
        # Register default handler
        self.setRequestHandler("tools/call", self._handle_tool_call)
        # Don't run the loop here - it would block 

    def connect(self, transport):
        """Connect to the transport"""
        self.transport = transport
        self._process_messages()
        
    async def close(self):
        """Close the server"""
        pass
        
    def _process_messages(self):
        """Process incoming messages from stdin"""
        try:
            for line in sys.stdin:
                if not line.strip():
                    continue
                    
                try:
                    message = json.loads(line)
                    self._handle_message(message)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse message: {line}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    if self.onerror:
                        self.onerror(e)
        except KeyboardInterrupt:
            logger.info("Server shutting down")
            
    def _handle_message(self, message: Dict):
        """Handle an incoming message"""
        if "jsonrpc" not in message or message["jsonrpc"] != "2.0":
            self._send_error(message.get("id"), -32600, "Invalid Request")
            return
            
        if "method" not in message:
            self._send_error(message.get("id"), -32600, "Invalid Request")
            return
            
        method = message["method"]
        params = message.get("params", {})
        message_id = message.get("id")
        
        handler = self.request_handlers.get(method)
        if not handler:
            self._send_error(message_id, -32601, f"Method not found: {method}")
            return

        # Check if handler is async
        if asyncio.iscoroutinefunction(handler):
            if not self.loop or not self.loop.is_running():
                 logger.error("Event loop not available or not running to execute async handler")
                 self._send_error(message_id, -32603, "Internal error: Server loop not ready")
                 return

            # Schedule the coroutine to run on the loop from this synchronous thread
            future = asyncio.run_coroutine_threadsafe(handler(params), self.loop)
            try:
                # Wait for the future to complete. Add a timeout?
                # This blocks the message handling thread until the async task is done.
                result = future.result()
                if message_id is not None:
                    self._send_result(message_id, result)
            except McpError as e:
                 self._send_error(message_id, e.code, e.message)
            except Exception as e:
                 logger.error(f"Error in async handler for {method}: {e}")
                 self._send_error(message_id, -32603, f"Internal error: {str(e)}")
        else:
            # Handle synchronous handlers (if any)
            try:
                result = handler(params)
                if message_id is not None:
                    self._send_result(message_id, result)
                else:
                    logger.info(f"Notification-only request completed successfully")
            except McpError as e:
                self._send_error(message_id, e.code, e.message)
            except Exception as e:
                logger.error(f"Error in sync handler for {method}: {e}")
                self._send_error(message_id, -32603, f"Internal error: {str(e)}")

    def _send_result(self, id: Union[str, int], result: Any):
        """Send a successful result"""
        response = {
            "jsonrpc": "2.0",
            "id": id,
            "result": result
        }
        self._send_message(response)
        
    def _send_error(self, id: Optional[Union[str, int]], code: int, message: str):
        """Send an error response"""
        response = {
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "code": code,
                "message": message
            }
        }
        self._send_message(response)
        
    def _send_message(self, message: Dict):
        """Send a message to stdout"""
        try:
            json_str = json.dumps(message)
            print(json_str, flush=True)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            
    def _handle_tool_call(self, params: Dict):
        """Default handler for tool calls"""
        try:
            # Add your tool call handling logic here
            logger.info(f"Received tool call with parameters: {params}")
            return {"status": "success", "message": "Tool call handled successfully"}
        except Exception as e:
            logger.error(f"Error handling tool call: {e}")
            raise McpError(-32000, f"Error executing tool call: {str(e)}")

    def _handle_initialize(self, params):
        """Handle initialize request from the client"""
        logger.info(f"Handling initialize request with params: {params}")
        
        # Ensure serverInfo has the required name field
        server_info = {
            "name": self.info.get("name", "Neura Telegram MCP"),
            "version": self.info.get("version", "0.0.3"),
            # Add any other required fields here
        }
        
        # Return the response in the expected format according to MCP protocol
        return {
            "protocolVersion": "2024-11-05",  # Use the specified MCP protocol version
            "serverInfo": server_info,        # This is the server info object with required fields
            "capabilities": self.capabilities
        }

    def setRequestHandler(self, method: str, handler):
        """Set a request handler for a method"""
        self.request_handlers[method] = handler
        # Remove this line that causes the circular reference:
        # self.register_request_handler(method, handler)