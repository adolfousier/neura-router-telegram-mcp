import json
import sys
import logging
from typing import Any, Dict, List, Optional, Union

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class McpError(Exception):
    """MCP error class"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"MCP Error {code}: {message}")

import asyncio # Add asyncio import

import asyncio # Ensure asyncio is imported

class Server:
    """MCP Server implementation"""
    def __init__(self, info: Dict[str, str], capabilities: Dict[str, Dict], loop=None): # Add loop parameter
        self.info = info
        self.capabilities = capabilities
        self.request_handlers = {}
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
                result = handler(params) # Pass params directly
                if message_id is not None:
                    self._send_result(message_id, result)
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
            
    def setRequestHandler(self, method: str, handler):
        """Set a request handler for a method"""
        self.request_handlers[method] = handler
