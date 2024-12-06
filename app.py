import json
import os
import platform
import subprocess
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, scrolledtext, simpledialog

# Directory constants
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
ENVS_DIR = os.path.join(BASE_DIR, "environments")

# Ensure directories exist
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(ENVS_DIR, exist_ok=True)

METADATA_FILE = os.path.join(BASE_DIR, "script_metadata.json")
script_metadata = {}
run_buttons = {}

# Load metadata from the file
if os.path.exists(METADATA_FILE):
    with open(METADATA_FILE, "r", encoding="utf-8") as metadata_file:
        script_metadata = json.load(metadata_file)


def add_pyenv_to_path():
    """Ensure pyenv is accessible by adding it to PATH."""
    home_dir = os.path.expanduser("~")
    pyenv_bin = os.path.join(home_dir, ".pyenv", "bin")
    pyenv_shims = os.path.join(home_dir, ".pyenv", "shims")

    # Add pyenv directories to PATH
    os.environ["PATH"] = pyenv_bin + os.pathsep + pyenv_shims + os.pathsep + os.environ["PATH"]


add_pyenv_to_path()


def save_metadata():
    """Save the metadata to the JSON file."""
    with open(METADATA_FILE, "w", encoding="utf-8") as metadata_file:
        json.dump(script_metadata, metadata_file)


def get_pyenv_python_path(python_version):
    """Get the path to the pyenv-managed Python3 executable."""
    try:
        result = subprocess.run(
            ["pyenv", "which", "python3"],  # Use python3 explicitly
            capture_output=True,
            text=True,
            env={"PATH": os.environ["PATH"], "PYENV_VERSION": python_version},
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError("pyenv is not installed or not in PATH.") from exc
    except Exception as exc:
        raise RuntimeError(
            f"Failed to locate pyenv-managed Python3 {python_version}:\n{exc}"
        ) from exc


def setup_venv(script_name, python_version="3.13.0", run_button=None):
    """Set up a virtual environment for the script using pyenv-managed Python."""
    env_path = os.path.join(ENVS_DIR, script_name)
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    requirements_file = os.path.join(script_path, "requirements.txt")

    def run_setup():
        # Disable the Run button and update the status
        if run_button:
            root.after(0, run_button.config, {"state": "disabled"})
        set_status("Setting up virtual environment...")

        def handle_error(error):
            root.after(0, lambda: messagebox.showerror("Error", str(error)))
            root.after(0, install_pyenv)

        try:
            # Get the pyenv-managed Python executable
            python_executable = get_pyenv_python_path(python_version)
            if not python_executable:
                raise FileNotFoundError(f"Could not find Python {python_version}")

            messagebox.showinfo(None, f"Creating virtual environment for {script_name}.")
            # Create the virtual environment
            if not os.path.exists(env_path):
                subprocess.run([python_executable, "-m", "venv", env_path], check=True)
            subprocess.run(
                [os.path.join(env_path, "bin", "pip"), "install", "-r", requirements_file],
                check=True,
            )
            messagebox.showinfo(
                "Success", f"Virtual environment for {script_name} created successfully!"
            )

        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            handle_error(e)
        finally:
            # Re-enable the Run button and reset the status
            if run_button:
                root.after(0, run_button.config, {"state": "normal"})
            reset_status()

    # Run the setup in a separate thread to avoid freezing the GUI
    threading.Thread(target=run_setup).start()


def is_pyenv_available():
    """Check if pyenv is installed and accessible."""
    try:
        result = subprocess.run(
            ["pyenv", "--version"],
            capture_output=True,
            text=True,
            env={"PATH": os.environ["PATH"]},  # Use the updated PATH
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_pyenv():
    """Guide the user to install pyenv based on their operating system."""
    system = platform.system()

    if system == "Darwin":  # macOS
        try:
            # First, check if Homebrew is installed
            subprocess.run(["brew", "--version"], capture_output=True, check=True)

            # Use a more direct installation command
            result = subprocess.run(
                ["brew", "install", "pyenv"],
                capture_output=True,
                text=True,
                timeout=60,  # Add a timeout to prevent hanging
            )

            if result.returncode == 0:
                messagebox.showinfo(
                    "Success",
                    "pyenv has been successfully installed. Please restart the application.",
                )
                return True
            else:
                messagebox.showerror(
                    "Installation Error", f"Failed to install pyenv:\n{result.stderr}"
                )

        except subprocess.TimeoutExpired:
            messagebox.showerror(
                "Installation Timeout", "Pyenv installation timed out. Please install manually."
            )
        except subprocess.CalledProcessError:
            messagebox.showinfo(
                "Install pyenv",
                "Homebrew installation failed. Please install Homebrew first:\n"
                '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
            )
        except FileNotFoundError:
            messagebox.showinfo(
                "Install Homebrew",
                "Homebrew is not installed. Install it with:\n"
                '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
            )

    return False


def rebuild_venv(script_name, run_button):
    """Rebuild the virtual environment for a script."""
    env_path = os.path.join(ENVS_DIR, script_name)

    # Prompt user for Python version
    python_version = simpledialog.askstring(
        "Python Version",
        f"Enter the Python version to use for rebuilding {script_name} (e.g., 3.13.0 or python3.13):",
    )
    if not python_version:
        messagebox.showerror("Error", "Python version is required!")
        return

    def run_rebuild():
        try:
            # Remove existing virtual environment
            if os.path.exists(env_path):
                for root_dir, dirs, files in os.walk(env_path, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root_dir, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root_dir, name))
                os.rmdir(env_path)

            # Create a new virtual environment
            setup_venv(script_name, python_version, run_button)
        except Exception as exc:
            root.after(
                0,
                lambda: messagebox.showerror(
                    "Error", f"Failed to rebuild virtual environment for {script_name}:\n{exc}"
                ),
            )

    # Start the rebuild in a separate thread
    threading.Thread(target=run_rebuild).start()


def update_script_list():
    run_buttons.clear()

    for widget in list_frame.winfo_children():
        widget.destroy()

    # Add the header
    header_font = tkfont.Font(weight="bold")
    header_label = tk.Label(list_frame, text="Scripts", font=header_font)
    header_label.pack(fill="x", pady=(0, 5))

    # Update metadata for added and deleted scripts
    scripts = os.listdir(SCRIPTS_DIR)
    for script in scripts:
        if script not in script_metadata:
            script_metadata[script] = 0  # Default to "never ran"
    for script in list(script_metadata.keys()):
        if script not in scripts:
            del script_metadata[script]  # Remove deleted scripts
    save_metadata()

    # Sort scripts by last runtime (descending)
    sorted_scripts = sorted(scripts, key=lambda s: script_metadata.get(s, 0), reverse=True)

    # Create the UI for each script
    for script in sorted_scripts:
        script_frame = tk.Frame(list_frame, relief="solid", borderwidth=1, padx=5, pady=5)
        script_frame.pack(fill="x", pady=5)

        # Frame for script name and buttons
        script_name_frame = tk.Frame(script_frame)
        script_name_frame.pack(fill="x")

        # Script Name Label
        last_run = (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(script_metadata[script]))
            if script_metadata[script]
            else "Never"
        )

        # Frame for script name and "Last ran at" text
        script_info_frame = tk.Frame(script_name_frame)
        script_info_frame.pack(side="left", fill="x", expand=True)

        # Script Name
        script_name_label = tk.Label(script_info_frame, text=script, anchor="w")
        script_name_label.pack(side="left")

        # "Last ran at" Text
        last_run_label = tk.Label(
            script_info_frame, text=f" (Last ran at: {last_run})", fg="grey", anchor="w"
        )
        last_run_label.pack(side="left")

        # Create the context menu (hamburger menu)
        context_menu = tk.Menu(root, tearoff=0)
        context_menu.add_command(
            label="Rebuild Env",
            command=lambda s=script: rebuild_venv(s, run_buttons[s]),
        )
        context_menu.add_command(
            label="Archive Script",
            command=lambda s=script: archive_script(s),
        )
        context_menu.add_command(
            label="Modify Requirements",
            command=lambda s=script: modify_requirements(s),
        )
        context_menu.add_command(
            label="Modify Script",
            command=lambda s=script: modify_script(s),
        )

        # Hamburger menu button with horizontal dots
        btn_hamburger = tk.Button(
            script_name_frame,
            text="⋯",  # Horizontal dots
            relief="flat",  # Optional: Flat style for modern look
            padx=5,  # Add horizontal padding for better clickability
        )

        # Configure the command after the button is created
        btn_hamburger.config(
            command=lambda menu=context_menu, btn=btn_hamburger: show_context_menu(menu, btn)
        )

        btn_hamburger.pack(side="right", padx=5, pady=5)  # Add vertical centering

        # Run Button
        btn_run = tk.Button(
            script_name_frame,
            text="Run",
            command=lambda s=script: run_script(s),
        )
        btn_run.pack(side="right", padx=5)

        # Store the button reference
        run_buttons[script] = btn_run


def show_context_menu(menu, button):
    """Display the context menu below the button."""
    x = button.winfo_rootx()
    y = button.winfo_rooty() + button.winfo_height()
    menu.tk_popup(x, y)


def modify_requirements(script_name):
    """Open the requirements.txt file for editing and rebuild the environment upon saving."""
    script_path = os.path.join(SCRIPTS_DIR, script_name, "requirements.txt")

    # Check if the requirements.txt file exists
    if not os.path.exists(script_path):
        with open(script_path, "w", encoding="utf-8") as req_file:
            req_file.write("")  # Create an empty requirements.txt file if it doesn't exist

    # Open a new window to edit requirements
    def save_changes():
        new_content = req_text.get("1.0", tk.END).strip()
        with open(script_path, "w", encoding="utf-8") as req_file:
            req_file.write(new_content)

        # Rebuild the environment
        edit_window.destroy()
        setup_venv(script_name)  # Rebuild the environment with the updated requirements

    # Create and configure the editing window
    edit_window = tk.Toplevel(root)
    edit_window.title(f"Modify Requirements - {script_name}")
    edit_window.geometry("600x400")  # Adjust size if needed

    # Use a grid layout for better control
    edit_window.rowconfigure(1, weight=1)  # Allow text widget to expand
    edit_window.columnconfigure(0, weight=1)  # Allow full width expansion

    # Add label
    tk.Label(edit_window, text=f"Editing requirements.txt for {script_name}:").grid(
        row=0, column=0, sticky="w", padx=5, pady=(5, 0)
    )

    # Frame to hold the text box and scrollbar
    text_frame = tk.Frame(edit_window)
    text_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    # Scrollbar
    scrollbar = tk.Scrollbar(text_frame, orient="vertical")

    # Requirements text box with integrated scrollbar
    req_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
    req_text.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=req_text.yview)
    scrollbar.pack(side="right", fill="y")

    # Load existing content into the text box
    with open(script_path, "r", encoding="utf-8") as req_file:
        req_text.insert("1.0", req_file.read())

    # Save button
    tk.Button(edit_window, text="Save and Rebuild Environment", command=save_changes).grid(
        row=2, column=0, pady=10
    )


def modify_script(script_name):
    """Open the main.py script for editing."""
    script_path = os.path.join(SCRIPTS_DIR, script_name, "main.py")

    # Check if the script exists
    if not os.path.exists(script_path):
        with open(script_path, "w", encoding="utf-8") as script_file:
            script_file.write(
                "# Your script starts here\n"
            )  # Create a default script if it doesn't exist

    # Open a new window to edit the script
    def save_changes():
        new_content = script_text.get("1.0", tk.END).strip()
        with open(script_path, "w", encoding="utf-8") as script_file:
            script_file.write(new_content)
        edit_window.destroy()
        messagebox.showinfo("Success", f"Updated script for {script_name}.")

    # Create and configure the editing window
    edit_window = tk.Toplevel(root)
    edit_window.title(f"Modify Script - {script_name}")
    edit_window.geometry("600x400")

    # Use a grid layout for better control
    edit_window.rowconfigure(1, weight=1)  # Allow text widget to expand
    edit_window.columnconfigure(0, weight=1)  # Allow full width expansion

    # Add label
    tk.Label(edit_window, text=f"Editing main.py for {script_name}:").grid(
        row=0, column=0, sticky="w", padx=5, pady=(5, 0)
    )

    # Frame to hold the text box and scrollbar
    text_frame = tk.Frame(edit_window)
    text_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    # Scrollbar
    scrollbar = tk.Scrollbar(text_frame, orient="vertical")

    # Script text box with integrated scrollbar
    script_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
    script_text.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=script_text.yview)
    scrollbar.pack(side="right", fill="y")

    # Load existing content into the text box
    with open(script_path, "r", encoding="utf-8") as script_file:
        script_text.insert("1.0", script_file.read())

    # Save button
    tk.Button(edit_window, text="Save Script", command=save_changes).grid(row=2, column=0, pady=10)


def archive_script(script_name):
    """Move the script and its environment to archived directories."""
    try:
        # Source and destination paths
        script_src = os.path.join(SCRIPTS_DIR, script_name)
        env_src = os.path.join(ENVS_DIR, script_name)
        script_dest = os.path.join(BASE_DIR, "archived_scripts", script_name)
        env_dest = os.path.join(BASE_DIR, "archived_environments", script_name)

        # Archive the script directory
        if os.path.exists(script_src):
            os.rename(script_src, script_dest)

        # Archive the environment directory
        if os.path.exists(env_src):
            os.rename(env_src, env_dest)

        # Update the UI
        messagebox.showinfo("Archived", f"Script '{script_name}' has been archived.")
        update_script_list()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to archive script '{script_name}': {e}")


# Function to run script
def run_script(script_name):
    # Record the current timestamp as the last runtime
    script_metadata[script_name] = time.time()
    save_metadata()

    env_path = os.path.join(ENVS_DIR, script_name)
    script_path = os.path.join(SCRIPTS_DIR, script_name, "main.py")
    if not os.path.exists(script_path):
        messagebox.showerror("Error", "Script not found!")
        return

    # Open the script in a new terminal
    system = platform.system()
    if system == "Windows":
        subprocess.Popen(
            [
                "start",
                "cmd",
                "/k",
                f"echo Running script {script_name} && echo. && echo. && {os.path.join(env_path, 'Scripts', 'python')} {script_path}",
            ],
            shell=True,
        )
    elif system == "Darwin":  # macOS
        temp_script_path = os.path.join(BASE_DIR, "run_script.sh")
        with open(temp_script_path, "w", encoding="utf-8") as temp_script:
            temp_script.write('rm -- "$0"\n')
            temp_script.write("#!/bin/bash\n")
            temp_script.write(f"echo 'Running script {script_name}'\n")
            temp_script.write("echo\n")
            temp_script.write("echo\n")
            temp_script.write(f"'{os.path.join(env_path, 'bin', 'python')}' '{script_path}'\n")
        os.chmod(temp_script_path, 0o755)
        subprocess.Popen(["open", "-a", "Terminal.app", temp_script_path])
    elif system == "Linux":
        subprocess.Popen(
            [
                "x-terminal-emulator",
                "-e",
                f"echo 'Running script {script_name}' && echo && echo && {os.path.join(env_path, 'bin', 'python')} {script_path}",
            ]
        )
    else:
        messagebox.showerror("Error", "Unsupported operating system!")


# GUI Functions
def add_script():
    script_name = simpledialog.askstring("New Script", "Enter a name for the new script:")
    if not script_name:
        return
    script_dir = os.path.join(SCRIPTS_DIR, script_name)
    if os.path.exists(script_dir):
        messagebox.showerror("Error", "A script with this name already exists!")
        return
    os.makedirs(script_dir, exist_ok=True)

    # Prompt for Python version
    python_version = simpledialog.askstring(
        "Python Version", "Enter the Python version to use (e.g., python3, python3.9):"
    )
    if not python_version:
        messagebox.showerror("Error", "Python version is required!")
        os.rmdir(script_dir)
        return

    # Prompt for script content
    def save_inputs():
        script_content = script_text.get("1.0", tk.END).strip()
        if not script_content.endswith("\n"):
            script_content += "\n"

        requirements_content = req_text.get("1.0", tk.END).strip()
        if not requirements_content.endswith("\n"):
            requirements_content += "\n"

        if not script_content:
            messagebox.showerror("Error", "Script content cannot be empty!")
            os.rmdir(script_dir)
            content_window.destroy()
            return

        with open(os.path.join(script_dir, "main.py"), "w", encoding="utf-8") as script_file:
            script_file.write(script_content)

        with open(os.path.join(script_dir, "requirements.txt"), "w", encoding="utf-8") as req_file:
            req_file.write(requirements_content)

        setup_venv(script_name, python_version)
        update_script_list()
        content_window.destroy()

    # Create content input window
    content_window = tk.Toplevel(root)
    content_window.title("Script and Requirements Input")
    content_window.geometry("600x400")

    # Script Input
    tk.Label(content_window, text="Script Content (main.py):").pack(anchor="w", padx=5, pady=5)
    script_text = scrolledtext.ScrolledText(content_window, wrap=tk.WORD, height=10)
    script_text.pack(fill="both", expand=True, padx=5, pady=5)

    # Requirements Input
    tk.Label(content_window, text="Requirements (requirements.txt):").pack(
        anchor="w", padx=5, pady=5
    )
    req_text = scrolledtext.ScrolledText(content_window, wrap=tk.WORD, height=5)
    req_text.pack(fill="both", expand=True, padx=5, pady=5)

    # Save Button
    tk.Button(content_window, text="Save and Create Environment", command=save_inputs).pack(pady=10)


def set_status(message):
    """Set the status message and style."""
    progress_label.config(text=message, fg=default_fg_color)


def reset_status():
    """Reset the status to its default greyed-out placeholder."""
    progress_label.config(text="Status", fg="grey")  # Greyed-out style


# Main Application
root = tk.Tk()
root.title("Script Manager")

# Layout
frame = tk.Frame(root)
frame.pack(fill="both", expand=True, padx=10, pady=10)

list_frame = tk.Frame(frame)
list_frame.pack(fill="both", expand=True)

# Button Frame
btn_frame = tk.Frame(root)
btn_frame.pack(fill="x", pady=5)

# Add Script Button
btn_add = tk.Button(btn_frame, text="Add Script", command=add_script)
btn_add.pack(side="left", padx=5)

# Refresh Script List Button
btn_refresh = tk.Button(btn_frame, text="Refresh Script List", command=update_script_list)
btn_refresh.pack(side="left", padx=5)  # Aligned to the left next to Add Script

# Progress Label Frame
progress_frame = tk.Frame(root, relief="solid", borderwidth=1, padx=10, pady=5)
progress_frame.pack(fill="x", pady=5, padx=10)

# Progress Label with placeholder text in italics
italic_font = tkfont.Font(slant="italic")  # Define an italic font
progress_label = tk.Label(progress_frame, font=italic_font, anchor="w")
progress_label.pack(fill="x")

# Capture the default foreground color after the label is created
default_fg_color = progress_label.cget("fg")

reset_status()

# Initialize script list
update_script_list()

# Start the app
root.mainloop()
