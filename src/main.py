import asyncio
from telegram_mcp import TelegramMCP # Assuming TelegramMCP is in telegram_mcp.py
import logging # Add logging

# Setup basic logging for the main entry point as well
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting main application...")
    # Get the current event loop or create one if needed
    try:
        loop = asyncio.get_running_loop()
        logger.info("Using existing event loop.")
    except RuntimeError:
        logger.info("No running event loop found, creating a new one.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Instantiate TelegramMCP with the loop
    instance = TelegramMCP(loop)

    try:
        # Run the main async function of the instance
        loop.run_until_complete(instance.run())
    except KeyboardInterrupt:
        logger.info("Main loop interrupted by user (KeyboardInterrupt).")
    except Exception as e:
         logger.error(f"An unexpected error occurred in main: {e}", exc_info=True)
    finally:
        # Cleanup logic moved to TelegramMCP.run's finally block and __main__
        logger.info("Main function finished.")
        # Loop closing is handled in TelegramMCP __main__ block now

if __name__ == "__main__":
    main()
