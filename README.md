# Telegram MCP Server with Go Bridge

A comprehensive Telegram integration using the MCP protocol, providing seamless communication between the Python MCP server and a Go-based bridge for enhanced functionality.

## Features

- **MCP Server**: Implements core Telegram functionality using Telethon.
- **Go Bridge**: Handles QR code-based authentication and session management.
- **Session Sharing**: Shares authentication data between Go and Python for unified operation.

## MCP Tools

The following tools are available through the MCP server:

1. **List Chats**: Retrieve a list of recent chats.
2. **Send Message**: Send a message to a specified chat.
3. **Schedule Message**: Schedule a message for future delivery.
4. **Read Messages**: Read recent messages from a chat.
5. **Delete Message**: Delete a specific message.
6. **Edit Message**: Edit an existing message.
7. **Search Messages**: Search for specific text in messages.
8. **Get Message**: Retrieve a specific message by ID.

## Go Bridge Features

The Go bridge provides:

- **QR Code Authentication**: Simplifies login using QR codes.
- **Session Management**: Stores and shares session data for seamless integration with the Python server.
- **Cross-Platform Compatibility**: Ensures smooth operation between Go and Python components.

## Setup Instructions

1. **Install Dependencies**:
   - Install Go and Python.
   - Install required packages:
     - Go: `go mod tidy`
     - Python: `pip install -r requirements.txt`

2. **Configuration**:
   - Update `config.ini` with your API ID and hash.
   - Ensure both the Python and Go services have access to the shared session directory.

3. **Run Services**:
   - Start the Go bridge.
   - Start the Python MCP server.

## Architecture

### Go Bridge
- **QR Code Generation**: Generates QR codes for easy authentication.
- **Session Export**: Exports session data to a JSON file for the Python server.

### Python MCP Server
- **Telethon Integration**: Uses Telethon for core Telegram operations.
- **Session Import**: Imports session data from the JSON file for continued sessions.

## Contributing

Contributions are welcome. Feel free to fork and improve the code.

## License

[Your License Here]
