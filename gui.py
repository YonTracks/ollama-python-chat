# gui.py

import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import threading
import asyncio
import logging
import sys
from datetime import datetime
import json
import ollama
from typing import Dict, List
from pathlib import Path

def setup_logging(log_dir: str, logging_enabled: bool, log_level: str) -> None:
    if logging_enabled:
        Path(log_dir).mkdir(exist_ok=True)
        log_file = Path(log_dir) / f"gui_{datetime.now().strftime('%Y%m%d')}.log"

        # Interpret log level from the config
        level = getattr(logging, log_level.upper(), logging.INFO)

        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)]
        )
    else:
        # Disable logging handlers if logging is disabled
        logging.getLogger().handlers = []

class Theme:
    def __init__(self, name: str, colors: Dict[str, str]):
        self.name = name
        self.colors = colors

THEMES = {
    'light': Theme('light', {
        'bg': '#FFFFFF',
        'fg': '#000000',
        'root_bg': '#F5F5F5',
        'button_bg': '#E0E0E0',
        'assistant_msg_bg': '#ECECEC',
        'entry_bg': '#FFFFFF',
        'scrollbar': '#C0C0C0'
    }),
    'dark': Theme('dark', {
        'bg': '#1E1E1E',
        'fg': '#FFFFFF',
        'root_bg': '#2C2C2C',
        'button_bg': '#404040',
        'entry_bg': '#333333',
        'scrollbar': '#505050'
    })
}

class ChatGUI:
    def __init__(
        self, 
        root: tk.Tk, 
        model: str = 'default',
        temperature: float = 0.7,
        config_path: str = "config.json"
    ):
        self.root = root
        self.model = model
        self.temperature = temperature
        self.messages: List[Dict[str, str]] = []
        self.config_path = config_path

        # Load config and set logging_enabled
        self.config = self.load_config()
        self.logging_enabled = self.config['app_settings'].get('logging_enabled', True)

        # Set up logging if enabled
        log_dir = self.config['app_settings'].get('log_directory', 'logs')
        log_level = self.config['app_settings'].get('log_level', 'INFO')
        setup_logging(log_dir, self.logging_enabled, log_level)

        if self.logging_enabled:
            logging.info("Configuration loaded successfully")

        self.setup_gui()
        self.apply_theme(self.config['gui_settings']['theme'])

    def load_config(self) -> Dict:
        """Load configuration with error handling and defaults."""
        try:
            with open(self.config_path) as f:
                config = json.load(f)
            return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Temporarily log errors without `self.logging_enabled`
            logging.error(f"Error loading config.json: {e}")
            return {
                'app_settings': {'model': self.model, 'temperature': self.temperature, 'logging_enabled': True},
                'gui_settings': {'theme': 'light', 'models': [self.model]}
            }

    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            if self.logging_enabled:
                logging.info("Configuration saved successfully")
        except Exception as e:
            if self.logging_enabled:
                logging.error(f"Error saving config: {e}")
            messagebox.showerror("Error", "Failed to save configuration")
    
    def setup_gui(self):
        """Initialize the GUI components with improved styling."""
        # Configure main window
        self.root.title(self.config['gui_settings'].get('window_title', 'Ollama Chat'))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        self.main_container.columnconfigure(0, weight=1)
        self.main_container.rowconfigure(0, weight=1)
        
        # Chat display with improved styling
        self.chat_display = scrolledtext.ScrolledText(
            self.main_container,
            wrap=tk.WORD,
            font=('Helvetica', 10),
            padx=10,
            pady=10,
            spacing3=10  # Add spacing between messages
        )
        self.chat_display.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        
        # Input area with status
        self.input_container = ttk.Frame(self.main_container)
        self.input_container.grid(row=1, column=0, sticky="ew")
        self.input_container.columnconfigure(1, weight=1)
        
        # Status indicator
        self.status_label = ttk.Label(
            self.input_container,
            text="●",
            font=('Helvetica', 10)
        )
        self.status_label.grid(row=0, column=0, padx=(0, 5))
        
        # Enhanced message entry
        self.message_entry = ttk.Entry(
            self.input_container,
            font=('Helvetica', 10)
        )
        self.message_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        self.message_entry.bind('<Control-KeyPress>', self.handle_keyboard_shortcuts)
        
        # Send button with icon (you can replace with actual icon)
        self.send_button = ttk.Button(
            self.input_container,
            text="↑",
            width=3,
            command=self.send_message
        )
        self.send_button.grid(row=0, column=2, padx=(5, 0))
        
        # Control panel
        self.control_panel = ttk.Frame(self.main_container)
        self.control_panel.grid(row=2, column=0, sticky="ew", pady=10)
        
        # Theme toggle
        self.theme_button = ttk.Button(
            self.control_panel,
            text="🌓",
            width=3,
            command=self.toggle_theme
        )
        self.theme_button.pack(side=tk.LEFT, padx=5)
        
        # Model selector
        self.model_var = tk.StringVar(value=self.model)
        self.model_selector = ttk.Combobox(
            self.control_panel,
            textvariable=self.model_var,
            values=self.config["gui_settings"].get("models", [self.model]),
            width=15
        )
        self.model_selector.pack(side=tk.LEFT, padx=5)
        
        # Temperature slider
        self.temp_scale = ttk.Scale(
            self.control_panel,
            from_=0.0,
            to=1.0,
            value=self.temperature,
            orient=tk.HORIZONTAL,
            length=100
        )
        self.temp_scale.pack(side=tk.LEFT, padx=5)
        
        # Clear button
        self.clear_button = ttk.Button(
            self.control_panel,
            text="🗑",
            width=3,
            command=self.clear_chat
        )
        self.clear_button.pack(side=tk.RIGHT, padx=5)
        
        # Create Model button
        self.create_model_button = ttk.Button(
            self.control_panel,
            text="Create Model",
            command=self.open_create_model_window
        )
        self.create_model_button.pack(side=tk.RIGHT, padx=5)
        
        # Settings button
        self.settings_button = ttk.Button(
            self.control_panel,
            text="Settings",
            command=self.open_settings_window
        )
        self.settings_button.pack(side=tk.RIGHT, padx=5)
        
        # Configure message styling
        self.setup_message_tags()

    def setup_message_tags(self):
        """Configure text tags for message styling."""
        self.chat_display.tag_configure(
            "user",
            justify='right',
            lmargin1=50,
            rmargin=10,
            spacing1=10,
            spacing3=10
        )
        self.chat_display.tag_configure(
            "assistant",
            justify='left',
            lmargin1=10,
            rmargin=50,
            spacing1=10,
            spacing3=10
        )
        self.chat_display.tag_configure(
            "timestamp",
            font=('Helvetica', 8),
            foreground='gray'
        )

    def apply_theme(self, theme_name: str):
        """Apply the specified theme to all GUI elements."""
        theme = THEMES[theme_name]
        colors = theme.colors
        
        # Update config
        self.config['gui_settings']['theme'] = theme_name
        self.save_config()
        
        # Apply colors to main window
        self.root.configure(bg=colors['root_bg'])
        
        # Chat display colors
        self.chat_display.configure(
            bg=colors['bg'],
            fg=colors['fg'],
            insertbackground=colors['fg']
        )
        
        # Update message colors
        self.chat_display.tag_configure(
            "user",
            justify='right',
            foreground=colors['fg']
        )
        self.chat_display.tag_configure(
            "assistant",
            justify='left',
            foreground=colors['fg']
        )
        
        # Style configuration
        style = ttk.Style()
        style.configure(
            "Custom.TEntry",
            fieldbackground=colors['entry_bg'],
            foreground=colors['fg'],
            bordercolor=colors['scrollbar']
        )
        
        style.configure(
            "Custom.TButton",
            background=colors['button_bg']
        )
        
        # Update status indicator
        self.status_label.configure(
            foreground='green' if theme_name == 'light' else '#00FF00'
        )

    def toggle_theme(self):
        """Toggle between light and dark themes."""
        current_theme = self.config['gui_settings']['theme']
        new_theme = 'dark' if current_theme == 'light' else 'light'
        self.apply_theme(new_theme)

    def handle_keyboard_shortcuts(self, event):
        """Handle keyboard shortcuts."""
        if event.keysym == 'l' and event.state & 0x4:  # Ctrl+L
            self.clear_chat()
        elif event.keysym == 't' and event.state & 0x4:  # Ctrl+T
            self.toggle_theme()

    async def _get_and_update_response(self):
        """Get and update response from Ollama with improved error handling."""
        # Schedule status label update in main thread
        self.root.after(0, self.status_label.configure, {'foreground': 'orange'})
        try:
            client = ollama.AsyncClient()
            message = {'role': 'assistant', 'content': ''}

            # Await client.chat() to get an async iterator
            async for response in await client.chat(
                model=self.model_var.get(),
                messages=self.messages,
                stream=True,
                options={'temperature': self.temp_scale.get()}
            ):
                if response['done']:
                    self.messages.append(message)
                    break

                # Append each content chunk to the display as it arrives
                content = response['message']['content']
                message['content'] += content  # Add to assistant's message history

                # Schedule GUI update in the main thread
                self.root.after(0, self.update_chat_display, content)

            # Schedule status label update in main thread
            self.root.after(0, self.status_label.configure, {'foreground': 'green'})

        except Exception as e:
            if self.logging_enabled:
                logging.error(f"Error getting response: {str(e)}")
            # Schedule GUI update in main thread
            self.root.after(0, self.update_chat_display,
                "Error: Unable to get response. Please check your connection and Ollama installation.",
                "assistant"
            )
            # Schedule status label update in main thread
            self.root.after(0, self.status_label.configure, {'foreground': 'red'})
            # Show error message in main thread
            self.root.after(0, messagebox.showerror, "Error", str(e))
        finally:
            # Ensure the asynchronous generators are properly closed
            await asyncio.sleep(0)  # This line is a workaround to allow the event loop to process pending tasks

    def send_message(self):
        """Send message with input validation."""
        message = self.message_entry.get().strip()
        if not message:
            return
            
        self.message_entry.delete(0, tk.END)
        self.update_chat_display(message, "user")

        # Insert initial label for the assistant's message with the assistant tag
        self.update_chat_display("", "assistant")
        
        self.messages.append({'role': 'user', 'content': message})

        # Use threading with a new event loop
        threading.Thread(target=self.run_async_get_response, daemon=True).start()

    def run_async_get_response(self):
        """Run the asynchronous method in a new event loop within a thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._get_and_update_response())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def update_chat_display(self, content: str, role: str = None):
        """Update the chat display with content. Tag is applied only at the start of a new message."""
        self.chat_display.config(state='normal')

        if role == "user":
            timestamp = datetime.now().strftime("%H:%M")
            self.chat_display.insert(tk.END, f"\nUser ({timestamp}): {content}\n", "user")
        elif role == "assistant":
            timestamp = datetime.now().strftime("%H:%M")
            self.chat_display.insert(tk.END, f"Assistant ({timestamp}):", "assistant \n")
            self.chat_display.insert(tk.END,  f" {content}")  # Insert initial content
        else:
            # Append content without any tags for incremental updates
            self.chat_display.insert(tk.END, content)

        self.chat_display.config(state='disabled')
        self.chat_display.see(tk.END)
        
    def clear_chat(self):
        """Clear chat with confirmation."""
        if self.messages and messagebox.askyesno("Clear Chat", "Are you sure you want to clear the chat history?"):
            self.chat_display.config(state='normal')
            self.chat_display.delete(1.0, tk.END)
            self.chat_display.config(state='disabled')
            self.messages.clear()

    # New methods for creating a model
    def open_create_model_window(self):
        """Open a new window to create a model."""
        self.create_model_window = tk.Toplevel(self.root)
        self.create_model_window.title("Create Model")
        self.create_model_window.geometry("500x500")

        # Model name label and entry
        tk.Label(self.create_model_window, text="Model Name:").pack(anchor='w', padx=10, pady=(10, 0))
        self.model_name_entry = tk.Entry(self.create_model_window, width=50)
        self.model_name_entry.pack(padx=10, pady=5)

        # Insert the placeholder Modelfile name
        placeholder_modelfile_name = "llama3.2-mario"
        self.model_name_entry.insert(tk.END, placeholder_modelfile_name)
        
        # Modelfile label and text area
        tk.Label(self.create_model_window, text="Modelfile Content:").pack(anchor='w', padx=10, pady=(10, 0))
        self.modelfile_text = tk.Text(self.create_model_window, width=60, height=20)
        self.modelfile_text.pack(padx=10, pady=5)

        # Insert the placeholder Modelfile content
        placeholder_modelfile = """FROM llama3.2
# sets the temperature to 1 [higher is more creative, lower is more coherent]
PARAMETER temperature 1
# sets the context window size to 4096, this controls how many tokens the LLM can use as context to generate the next token
PARAMETER num_ctx 4096

# sets a custom system message to specify the behavior of the chat assistant
SYSTEM You are Mario from super mario bros, acting as an assistant.
"""
        self.modelfile_text.insert(tk.END, placeholder_modelfile)

        # Create and Cancel buttons
        button_frame = tk.Frame(self.create_model_window)
        button_frame.pack(pady=10)

        create_button = tk.Button(button_frame, text="Create", command=self.create_model)
        create_button.pack(side=tk.LEFT, padx=5)

        cancel_button = tk.Button(button_frame, text="Cancel", command=self.create_model_window.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

    def create_model(self):
        """Create a model using the provided name and modelfile content."""
        model_name = self.model_name_entry.get().strip()
        modelfile_content = self.modelfile_text.get("1.0", tk.END).strip()

        if not model_name or not modelfile_content:
            messagebox.showerror("Error", "Please provide both model name and Modelfile content.")
            return

        # Close the create model window
        self.create_model_window.destroy()

        # Run the model creation in a separate thread to avoid freezing the GUI
        threading.Thread(target=self.run_create_model, args=(model_name, modelfile_content), daemon=True).start()

    def run_create_model(self, model_name: str, modelfile_content: str):
        """Run the model creation process."""
        try:
            # Show a progress message in the chat display
            self.root.after(0, self.update_chat_display, f"Creating model '{model_name}'...\n", "assistant")

            # Create the model using ollama.create()
            for response in ollama.create(model=model_name, modelfile=modelfile_content, stream=True):
                status = response.get('status', '')
                # Update status in chat display
                self.root.after(0, self.update_chat_display, f"{status}\n")

            # Update the models list in the GUI and config
            self.root.after(0, self.update_models_list, model_name)

            # Show success message
            self.root.after(0, self.update_chat_display, f"Model '{model_name}' created successfully.\n", "assistant")

            if self.logging_enabled:
                logging.info(f"Model '{model_name}' created successfully.")

        except Exception as e:
            if self.logging_enabled:
                logging.error(f"Error creating model: {e}")
            # Show error message in GUI
            self.root.after(0, messagebox.showerror, "Error", f"Failed to create model: {e}")

    def update_models_list(self, new_model: str):
        """Update the models list in the model selector and config."""
        # Update the models list in the combobox
        models = list(self.model_selector['values'])
        if new_model not in models:
            models.append(new_model)
            self.model_selector['values'] = models

        # Update the config file with the new model
        if 'models' not in self.config["gui_settings"]:
            self.config["gui_settings"]["models"] = models
        else:
            if new_model not in self.config["gui_settings"]["models"]:
                self.config["gui_settings"]["models"].append(new_model)
        self.save_config()

    # New methods for settings
    def open_settings_window(self):
        """Open a new window to adjust settings."""
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")
        self.settings_window.geometry("400x600")

        # Create notebook for tabbed settings
        notebook = ttk.Notebook(self.settings_window)
        notebook.pack(expand=True, fill='both')

        # App Settings tab
        app_settings_frame = ttk.Frame(notebook)
        notebook.add(app_settings_frame, text='App Settings')

        # GUI Settings tab
        gui_settings_frame = ttk.Frame(notebook)
        notebook.add(gui_settings_frame, text='GUI Settings')

        # Model Options tab
        model_options_frame = ttk.Frame(notebook)
        notebook.add(model_options_frame, text='Model Options')

        # Populate App Settings
        self.populate_app_settings(app_settings_frame)

        # Populate GUI Settings
        self.populate_gui_settings(gui_settings_frame)

        # Populate Model Options
        self.populate_model_options(model_options_frame)

        # Save and Cancel buttons
        button_frame = ttk.Frame(self.settings_window)
        button_frame.pack(pady=10)

        save_button = ttk.Button(button_frame, text="Save", command=self.save_settings)
        save_button.pack(side=tk.LEFT, padx=5)

        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.settings_window.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

    def populate_app_settings(self, frame):
        """Populate the App Settings tab."""
        self.app_settings_vars = {}

        row = 0
        for key, value in self.config['app_settings'].items():
            ttk.Label(frame, text=key).grid(row=row, column=0, sticky='w', padx=10, pady=5)
            if isinstance(value, bool):
                var = tk.BooleanVar(value=value)
                ttk.Checkbutton(frame, variable=var).grid(row=row, column=1, sticky='w')
            else:
                var = tk.StringVar(value=str(value))
                ttk.Entry(frame, textvariable=var).grid(row=row, column=1, sticky='ew', padx=10)
            self.app_settings_vars[key] = var
            row += 1

    def populate_gui_settings(self, frame):
        """Populate the GUI Settings tab."""
        self.gui_settings_vars = {}

        row = 0
        for key, value in self.config['gui_settings'].items():
            if key == 'models':
                continue  # Skip models list
            ttk.Label(frame, text=key).grid(row=row, column=0, sticky='w', padx=10, pady=5)
            if isinstance(value, list):
                var = tk.StringVar(value=', '.join(map(str, value)))
            else:
                var = tk.StringVar(value=str(value))
            ttk.Entry(frame, textvariable=var).grid(row=row, column=1, sticky='ew', padx=10)
            self.gui_settings_vars[key] = var
            row += 1

    def populate_model_options(self, frame):
        """Populate the Model Options tab."""
        self.model_options_vars = {}

        row = 0
        for key, value in self.config['model_options'].items():
            ttk.Label(frame, text=key).grid(row=row, column=0, sticky='w', padx=10, pady=5)
            var = tk.StringVar(value=str(value))
            ttk.Entry(frame, textvariable=var).grid(row=row, column=1, sticky='ew', padx=10)
            self.model_options_vars[key] = var
            row += 1

    def save_settings(self):
        """Save settings from the settings window."""
        # Update app_settings
        for key, var in self.app_settings_vars.items():
            value = var.get()
            if isinstance(self.config['app_settings'][key], bool):
                self.config['app_settings'][key] = var.get()
            elif isinstance(self.config['app_settings'][key], (int, float)):
                try:
                    self.config['app_settings'][key] = type(self.config['app_settings'][key])(value)
                except ValueError:
                    messagebox.showerror("Error", f"Invalid value for {key}")
                    return
            else:
                self.config['app_settings'][key] = value

        # Update gui_settings
        for key, var in self.gui_settings_vars.items():
            value = var.get()
            if key == 'min_size':
                try:
                    sizes = list(map(int, value.split(',')))
                    if len(sizes) != 2:
                        raise ValueError
                    self.config['gui_settings'][key] = sizes
                except ValueError:
                    messagebox.showerror("Error", f"Invalid value for {key}")
                    return
            else:
                self.config['gui_settings'][key] = value

        # Update model_options
        for key, var in self.model_options_vars.items():
            value = var.get()
            try:
                if isinstance(self.config['model_options'][key], int):
                    self.config['model_options'][key] = int(value)
                else:
                    self.config['model_options'][key] = float(value)
            except ValueError:
                messagebox.showerror("Error", f"Invalid value for {key}")
                return

        # Save config
        self.save_config()

        # Apply changes if necessary
        self.apply_theme(self.config['gui_settings']['theme'])
        self.root.title(self.config['gui_settings'].get('window_title', 'Ollama Chat'))
        self.root.geometry(self.config['gui_settings'].get('window_size', '800x600'))
        min_size = self.config['gui_settings'].get('min_size', [400, 300])
        self.root.minsize(*min_size)

        # Close settings window
        self.settings_window.destroy()

        messagebox.showinfo("Settings", "Settings saved successfully.")

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("800x600")
    app = ChatGUI(root)
    root.mainloop()
