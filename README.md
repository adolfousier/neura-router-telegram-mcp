![](https://badge.mcpx.dev 'MCP')
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green?style=flat-square)](https://opensource.org/licenses/Apache-2.0)
[![Dev LinkedIn](https://img.shields.io/badge/LinkedIn-blue)](https://www.linkedin.com/in/adolfousier/)

# Neura Router Telegram MCP Server

**Open Source Project**: This is an open-source conversational sandbox that allows users to interact with their contacts, groups, and channels on Telegram through the Model Context Protocol (MCP).

This project implements a Model Context Protocol (MCP) server that connects to a Telegram user account using the Telegram API. It utilizes Python and the `telethon` library to interact with Telegram and exposes tools via MCP for tasks like listing chats and sending messages.

## Prerequisites

*   Python 3.8+
*   pip (Python package installer)
*   A Telegram account
*   Telegram API Credentials:
    *   **API ID (apiId)**
    *   **API Hash (apiHash)**
    *   You can obtain these by logging into your Telegram account at [https://my.telegram.org/apps](https://my.telegram.org/apps).

## Setup

1.  **Clone Repository:** Get the project code.
    ```bash
    # git clone <repository_url> # Or download the files
    cd neura-router-telegram-mcp
    ```

2.  **Create & Activate Virtual Environment:** It's crucial to use a virtual environment to manage dependencies.
    ```bash
    # Create the virtual environment
    python3 -m venv .venv

    # Activate it (macOS/Linux)
    source .venv/bin/activate
    # Or (Windows CMD)
    # .venv\Scripts\activate
    # Or (Windows PowerShell)
    # .\.venv\Scripts\Activate.ps1
    ```
    *(You should see `(.venv)` at the beginning of your terminal prompt)*

3.  **Create `.env` File:** Create a file named `.env` in the project root (`neura-router-telegram-mcp/`) with the following content, replacing the placeholders with your actual Telegram API credentials:
    ```dotenv
    # Telegram Core API Credentials
    # Obtain from https://my.telegram.org/apps
    TELEGRAM_APP_API_ID=YOUR_API_ID_HERE
    TELEGRAM_APP_API_HASH=YOUR_API_HASH_HERE

    # Optional: Add your phone number if you want the script to pre-fill it during login
    # TELEGRAM_PHONE_NUMBER=+1234567890

    # Session string will be managed by Telethon in a .session file
    ```

4.  **Install Dependencies:** Make sure your virtual environment is active and run:
    ```bash
    pip install -r requirements.txt
    ```

## Running the MCP Server

This server is designed to be run via an MCP client (like the Claude Dev Tools VS Code extension).

1.  **Register the Server in your MCP Client (e.g., Cline):**
    *   Configure your client to run this server using the Python executable from the virtual environment.
    *   **Name:** `neura-router-telegram-mcp` (or choose your own)
    *   **Command:** `/Users/itsyourtime/Documents/Cline/MCP/neura-router-telegram-mcp/.venv/bin/python` (Full path to python inside the .venv)
    *   **Arguments:** `["/Users/itsyourtime/Documents/Cline/MCP/neura-router-telegram-mcp/src/main.py"]` (Full path to the main script)
    *   **Working Directory:** `/Users/itsyourtime/Documents/Cline/MCP/neura-router-telegram-mcp` (Optional, but good practice)
    *   **Environment Variables:** The server reads API ID/Hash from the `.env` file located in the working directory. Ensure the `.env` file is correctly placed and populated.

2.  **First Run & Authentication:**
    *   When the MCP client starts this server for the **first time**, `telethon` needs to authenticate your Telegram account.
    *   **Monitor the terminal/output channel where the MCP server runs.** You will likely be prompted interactively (by `telethon` itself, not the MCP server code directly yet) to enter:
        *   Your phone number (unless provided in `.env`).
        *   The login code sent to your Telegram account.
        *   Your Two-Step Verification password, if enabled.
    *   Follow these prompts. `telethon` will create a session file (e.g., `telegram_mcp.session` based on the current code, or potentially just the script name if not specified in the `TelegramClient` constructor within `src/telegram_mcp.py`) in the working directory to store login information for future runs.

## Available MCP Tools (Placeholders)

Once the server is running and connected (and the Python code in `src/telegram_mcp.py` is fully implemented), the following tools should become available via MCP:

*   **`list_chats`**:
    *   Description: List recent chats.
    *   Input: `{ "limit": number (optional, default 20) }`
*   **`send_message`**:
    *   Description: Send a message to a chat.
    *   Input: `{ "chat_id": string (username or ID), "message": string }`

*(Note: The actual implementation for these tools in `src/telegram_mcp.py` is currently placeholder logic and needs to be built using the `telethon` library.)*

## Go Bridge (Optional/Alternative)

This repository also contains a `telegram-bridge` directory with a Go application that connects to Telegram using the `gotd` library. This was part of the initial development but is currently separate from the Python MCP server. It requires its own setup (Go environment, `go mod tidy`) and configuration (`telegram-bridge/config.ini`). It is not directly used by the Python MCP server.

## Usage

Once integrated, your Telegram tools (`get_chats`, `get_messages`, and `send_message`) will become available within the Claude for Desktop UI or any other MCP-compatible client.

## License

This project is licensed under the [Apache 2.0 License](https://opensource.org/licenses/Apache-2.0).
