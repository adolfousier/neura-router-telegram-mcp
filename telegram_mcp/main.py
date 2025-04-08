import asyncio
from client.telegram_mcp import TelegramMCP
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting main application...")
    try:
        loop = asyncio.get_running_loop()
        logger.info("Using existing event loop.")
    except RuntimeError:
        logger.info("Creating a new event loop.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    instance = TelegramMCP(loop)

    try:
        loop.run_until_complete(instance.run())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        logger.info("Main loop finished.")

if __name__ == "__main__":
    main()
