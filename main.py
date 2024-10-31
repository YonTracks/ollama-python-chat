# chat_demo.py

import shutil
import asyncio
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import ollama
from pathlib import Path
from datetime import datetime

# Load configuration from config.json
def load_config(config_file='config.json'):
    config_path = Path(config_file)
    if not config_path.is_file():
        print(f"Configuration file '{config_file}' not found.")
        return None
    with open(config_file, 'r') as file:
        return json.load(file)

# Setup logging with rotation based on configuration
def setup_logging(log_dir, log_level, max_bytes, backup_count):
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_filename = log_dir_path / "chat.log"
    
    handler = RotatingFileHandler(
        log_filename, maxBytes=max_bytes, backupCount=backup_count
    )
    handler.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logging.basicConfig(
        level=log_level,
        handlers=[handler, console_handler]
    )

# Text-to-speech function
async def speak(speaker, content):
    if speaker and content:
        try:
            p = await asyncio.create_subprocess_exec(speaker, content)
            await p.communicate()
        except Exception as e:
            logging.error(f"Error with TTS: {e}")

# Main chat function
async def main(config):
    parser = argparse.ArgumentParser(description="Asynchronous chat application with TTS and logging.")
    parser.add_argument('--model', type=str, default=config['app_settings']['model'], help="Model name to use for chat.")
    parser.add_argument('--temperature', type=float, default=config['app_settings']['temperature'], help="Temperature setting for the model.")
    parser.add_argument('--log-dir', type=str, default=config['app_settings']['log_directory'], help="Directory to store log files.")
    parser.add_argument('--max-log-size', type=int, default=5*1024*1024, help="Max size in bytes for each log file before rotation (default: 5MB).")
    parser.add_argument('--backup-count', type=int, default=3, help="Max number of log backup files (default: 3).")
    parser.add_argument('--speak', default=False, action='store_true', help="Enable text-to-speech for responses.")
    
    args = parser.parse_args()

    # Setup logging if enabled
    if config['app_settings'].get('logging_enabled', False):
        log_level = getattr(logging, config['app_settings'].get('log_level', 'INFO').upper(), logging.INFO)
        setup_logging(args.log_dir, log_level, args.max_log_size, args.backup_count)
        logging.info("Logging initialized.")
    else:
        logging.disable(logging.CRITICAL)

    # Use config settings for speaker
    speaker = None
    if args.speak:
        speaker = shutil.which('say') or shutil.which('espeak') or shutil.which('espeak-ng')

    client = ollama.AsyncClient()
    model_name = args.model
    model_options = config['model_options']
    
    messages = []
    exit_commands = config['exit_commands']
    prompt_symbol = config['app_settings'].get('prompt_symbol', '>>>')

    # Main interaction loop
    while True:
        try:
            content_in = input(prompt_symbol + ' ')
            if content_in.strip() in exit_commands:
                print("Exiting chat.")
                logging.info("User exited chat.")
                break
            if not content_in.strip():
                continue

            messages.append({'role': 'user', 'content': content_in})
            logging.info(f"User input: {content_in}")

            content_out = ''
            message = {'role': 'assistant', 'content': ''}
            try:
                async for response in await client.chat(model=model_name, messages=messages, stream=True, options=model_options):
                    if response.get('done'):
                        messages.append(message)
                        break

                    content = response['message']['content']
                    print(content, end='', flush=True)

                    content_out += content
                    if content in ['.', '!', '?', '\n']:
                        await speak(speaker, content_out)
                        content_out = ''

                    message['content'] += content

                if content_out:
                    await speak(speaker, content_out)
                print()
                logging.info(f"Assistant response: {message['content']}")

            except Exception as e:
                logging.error(f"Error during chat response: {e}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat.")
            logging.info("Chat terminated by user.")
            break
        except Exception as e:
            logging.error(f"Error in chat loop: {e}")

# Entry point
if __name__ == "__main__":
    config = load_config()
    if config:
        try:
            asyncio.run(main(config))
        except (KeyboardInterrupt, EOFError):
            print("Chat closed.")
            logging.info("Chat application closed.")
