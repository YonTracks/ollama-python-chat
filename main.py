# main.py

import shutil
import asyncio
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
from datetime import datetime
import tkinter as tk
from gui import ChatGUI  # Import the GUI class from gui.py
import ollama

# Load configuration from config.json
def load_config(config_file='config.json'):
    config_path = Path(config_file)
    if not config_path.is_file():
        print(f"Configuration file '{config_file}' not found.")
        sys.exit(1)
    with open(config_file, 'r') as file:
        return json.load(file)

# Save configuration to config.json
def save_config(config, config_file='config.json'):
    config_path = Path(config_file)
    with open(config_path, 'w') as file:
        json.dump(config, file, indent=4)

# Setup logging with rotation based on configuration
def setup_logging(config):
    log_dir = config['app_settings'].get('log_directory', 'logs')
    log_level = config['app_settings'].get('log_level', 'INFO').upper()
    max_bytes = config['app_settings'].get('max_log_size', 5 * 1024 * 1024)
    backup_count = config['app_settings'].get('backup_count', 3)

    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_filename = log_dir_path / f"chat_{datetime.now().strftime('%Y%m%d')}.log"

    handler = RotatingFileHandler(
        log_filename, maxBytes=max_bytes, backupCount=backup_count
    )
    handler.setLevel(getattr(logging, log_level, logging.INFO))
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
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

# CLI Chat function
async def main_cli(config):
    parser = argparse.ArgumentParser(description="Ollama Chat Application")
    parser.add_argument('--model', type=str, help="Model name to use for chat.")
    parser.add_argument('--temperature', type=float, help="Temperature setting for the model.")
    parser.add_argument('--speak', default=False, action='store_true', help="Enable text-to-speech for responses.")
    parser.add_argument('--set', nargs=2, metavar=('KEY', 'VALUE'), action='append', help="Set configuration key to value.")
    parser.add_argument('--show-config', action='store_true', help="Display the current configuration.")
    args = parser.parse_args()

    # Update config with command-line arguments
    if args.model:
        config['app_settings']['model'] = args.model
    if args.temperature:
        config['app_settings']['temperature'] = args.temperature

    # Handle --set arguments to update config
    if args.set:
        for key, value in args.set:
            # Split the key into sections if nested
            keys = key.split('.')
            cfg = config
            for k in keys[:-1]:
                cfg = cfg.setdefault(k, {})
            # Attempt to parse the value to int or float if possible
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass  # Keep as string if not int or float
            cfg[keys[-1]] = value
        # Save updated config
        save_config(config)

    # Show configuration if requested
    if args.show_config:
        print(json.dumps(config, indent=4))
        sys.exit(0)

    # Setup logging if enabled
    if config['app_settings'].get('logging_enabled', False):
        setup_logging(config)
        logging.info("Logging initialized.")
    else:
        logging.disable(logging.CRITICAL)

    # Use config settings for speaker
    speaker = None
    if args.speak or config['app_settings'].get('speak', False):
        speaker = shutil.which('say') or shutil.which('espeak') or shutil.which('espeak-ng')

    client = ollama.AsyncClient()
    model_name = config['app_settings']['model']
    temperature = config['app_settings'].get('temperature', 0.7)
    model_options = config.get('model_options', {})
    model_options['temperature'] = temperature

    messages = []
    exit_commands = config.get('exit_commands', ['/bye', '/exit', '/quit'])
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
                # Await the coroutine to get the async iterator
                chat_iterator = await client.chat(
                    model=model_name,
                    messages=messages,
                    stream=True,
                    options=model_options
                )
                async for response in chat_iterator:
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

# Run GUI mode
def run_gui(config):
    try:
        root = tk.Tk()
        root.title(config['gui_settings'].get('window_title', 'Ollama Chat'))
        root.geometry(config['gui_settings'].get('window_size', '800x600'))
        min_size = config['gui_settings'].get('min_size', [400, 300])
        root.minsize(*min_size)

        app = ChatGUI(root, model=config['app_settings']['model'], temperature=config['app_settings']['temperature'])

        def on_closing():
            logging.info("Closing GUI application...")
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)

        logging.info("Starting GUI application...")
        root.mainloop()

    except Exception as e:
        logging.error(f"GUI error: {str(e)}")
        sys.exit(1)

# Main function to decide between CLI and GUI modes
def main():
    config = load_config()

    # Parse initial CLI argument to determine mode
    parser = argparse.ArgumentParser(description="Ollama Chat Application")
    parser.add_argument('--gui', action='store_true', help="Launch the chat application in GUI mode.")
    parser.add_argument('--mode', type=str, choices=['cli', 'gui'], help="Mode to run the application in.")
    args, unknown = parser.parse_known_args()

    # Determine the mode based on the argument or configuration
    if args.mode:
        mode = args.mode
    elif args.gui:
        mode = 'gui'
    else:
        # Use gui_enabled from config if no mode is specified
        if config['app_settings'].get('gui_enabled', False):
            mode = 'gui'
        else:
            mode = 'cli'

    if mode == 'gui':
        # Re-parse arguments with the unknown arguments
        sys.argv = [sys.argv[0]] + unknown
        run_gui(config)
    else:
        # Re-parse arguments with the unknown arguments
        sys.argv = [sys.argv[0]] + unknown
        asyncio.run(main_cli(config))

if __name__ == "__main__":
    main()
