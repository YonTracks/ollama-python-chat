# chat_demo.py

import shutil
import asyncio
import argparse

import ollama


async def speak(speaker, content):
    if speaker:
        try:
            p = await asyncio.create_subprocess_exec(speaker, content)
            await p.communicate()
        except Exception as e:
            print(f"Error with TTS: {e}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--speak', default=False, action='store_true')
    args = parser.parse_args()

    speaker = None
    if args.speak:
        speaker = shutil.which('say') or shutil.which('espeak') or shutil.which('espeak-ng')

    client = ollama.AsyncClient()

    messages = []

    while True:
        try:
            content_in = input('>>> ')
            if not content_in.strip():
                continue

            messages.append({'role': 'user', 'content': content_in})

            content_out = ''
            message = {'role': 'assistant', 'content': ''}
            async for response in await client.chat(model='llama3.1', messages=messages, stream=True):
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

        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat.")
            break
        except Exception as e:
            print(f"Error in chat loop: {e}")


try:
  asyncio.run(main())
except (KeyboardInterrupt, EOFError):
  ...