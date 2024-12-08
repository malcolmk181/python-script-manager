import json
import os
import platform
import shutil
import subprocess
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from tkinter import messagebox, scrolledtext, simpledialog

from packaging import version

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
    system = platform.system()

    if system == "Windows":
        pyenv_root = os.path.join(home_dir, ".pyenv", "pyenv-win")
        pyenv_bin = os.path.join(pyenv_root, "bin")
        pyenv_shims = os.path.join(pyenv_root, "shims")
    else:
        pyenv_root = os.path.join(home_dir, ".pyenv")
        pyenv_bin = os.path.join(pyenv_root, "bin")
        pyenv_shims = os.path.join(pyenv_root, "shims")

    # Add pyenv directories to PATH if not already present
    path_dirs = os.environ["PATH"].split(os.pathsep)
    if pyenv_bin not in path_dirs:
        path_dirs.insert(0, pyenv_bin)
    if pyenv_shims not in path_dirs:
        path_dirs.insert(0, pyenv_shims)
    os.environ["PATH"] = os.pathsep.join(path_dirs)


add_pyenv_to_path()


def save_metadata():
    """Save the metadata to the JSON file."""
    with open(METADATA_FILE, "w", encoding="utf-8") as metadata_json_file:
        json.dump(script_metadata, metadata_json_file)


def get_pyenv_python_path(python_version):
    """Get the path to the pyenv-managed Python executable."""
    try:
        system = platform.system()
        env = os.environ.copy()
        env["PYENV_VERSION"] = python_version

        if system == "Windows":
            command = "pyenv which python"
            shell = True
        else:
            command = ["pyenv", "which", "python3"]
            shell = False

        # For Windows, pass the command as a string when shell=True
        command_list = command if shell else command

        result = subprocess.run(
            command_list,
            capture_output=True,
            text=True,
            env=env,
            shell=shell,
            check=False,
        )

        if result.returncode != 0:
            error_message = (
                f"Command '{command}' returned non-zero exit status {result.returncode}.\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
            raise RuntimeError(error_message)
        return result.stdout.strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError("pyenv is not installed or not in PATH.") from exc
    except Exception as exc:
        raise RuntimeError(
            f"Failed to locate pyenv-managed Python {python_version}:\n{exc}"
        ) from exc


def get_available_python_versions():
    """Get the list of available Python versions from pyenv."""
    try:
        system = platform.system()
        env = os.environ.copy()
        if system == "Windows":
            command = "pyenv install --list"
            shell = True
        else:
            command = ["pyenv", "install", "--list"]
            shell = False

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            shell=shell,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to get available Python versions.\nSTDERR:\n{result.stderr}"
            )

        versions = result.stdout.strip().splitlines()
        # Clean up version strings
        cleaned_versions = []
        for v in versions:
            v = v.strip()
            # Skip empty lines and comments
            if not v or v.startswith("#"):
                continue
            # Skip non-standard versions (e.g., Stackless, Anaconda)
            if any(
                keyword in v for keyword in ["Anaconda", "Stackless", "Miniconda", "MicroPython"]
            ):
                continue
            cleaned_versions.append(v)
        return cleaned_versions
    except Exception as e:
        raise RuntimeError(f"Error fetching available Python versions: {e}")


def get_latest_available_python_version(prefix):
    """Get the latest available Python version matching the given prefix."""
    try:
        versions = get_available_python_versions()
        # Filter versions that start with the prefix
        matching_versions = [v for v in versions if v.startswith(prefix)]
        if not matching_versions:
            raise ValueError(f"No available Python versions found matching '{prefix}'.")

        # Remove pre-release and development versions if desired
        stable_versions = []
        for v in matching_versions:
            try:
                parsed_version = version.parse(v)
                if not parsed_version.is_prerelease and not parsed_version.is_devrelease:
                    stable_versions.append(v)
            except version.InvalidVersion:
                # Skip versions that cannot be parsed
                continue

        if not stable_versions:
            raise ValueError(f"No stable Python versions found matching '{prefix}'.")

        # Sort the versions using packaging.version
        stable_versions.sort(key=version.parse)
        latest_version = stable_versions[-1]
        return latest_version
    except Exception as e:
        raise RuntimeError(f"Error finding latest Python version matching '{prefix}': {e}")


def setup_venv(script_name, python_version_input="3", run_button=None):
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
            error_message = str(error)
            root.after(0, lambda: messagebox.showerror("Error", error_message))
            # Only prompt to install pyenv if the error suggests it's not installed
            if (
                "pyenv is not installed" in error_message
                or "pyenv: command not found" in error_message
            ):
                root.after(0, install_pyenv)

        try:
            # Get the latest available Python version matching the user's input
            try:
                python_version = get_latest_available_python_version(python_version_input)
            except ValueError as ve:
                root.after(0, lambda: messagebox.showerror("Error", str(ve)))
                return  # Exit the function if no matching version is found

            set_status(f"Using Python {python_version}")

            # Check if the requested Python version is installed
            if not is_python_version_installed(python_version):
                # Install the Python version
                set_status(f"Installing Python {python_version} via pyenv...")
                system = platform.system()
                env = os.environ.copy()
                if system == "Windows":
                    command = f"pyenv install {python_version}"
                    shell = True
                else:
                    command = ["pyenv", "install", python_version]
                    shell = False

                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    env=env,
                    shell=shell,
                    check=False,
                )
                if result.returncode != 0:
                    error_message = (
                        f"Failed to install Python {python_version} via pyenv.\n"
                        f"Command output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                    )
                    raise RuntimeError(error_message)

            # Get the pyenv-managed Python executable
            python_executable = get_pyenv_python_path(python_version)
            if not python_executable:
                raise FileNotFoundError(f"Could not find Python {python_version}")

            messagebox.showinfo(None, f"Creating virtual environment for {script_name}.")
            # Create the virtual environment
            if not os.path.exists(env_path):
                subprocess.run([python_executable, "-m", "venv", env_path], check=True)

            # Determine the path to pip in the virtual environment
            if platform.system() == "Windows":
                pip_executable = os.path.join(env_path, "Scripts", "pip.exe")
            else:
                pip_executable = os.path.join(env_path, "bin", "pip")

            subprocess.run(
                [pip_executable, "install", "-r", requirements_file],
                check=True,
            )
            messagebox.showinfo(
                "Success", f"Virtual environment for {script_name} created successfully!"
            )

        except Exception as e:
            handle_error(e)
        finally:
            # Re-enable the Run button and reset the status
            if run_button:
                root.after(0, run_button.config, {"state": "normal"})
            reset_status()

    # Run the setup in a separate thread to avoid freezing the GUI
    threading.Thread(target=run_setup).start()


def is_python_version_installed(python_version):
    """Check if the specified Python version is installed via pyenv."""
    try:
        system = platform.system()
        env = os.environ.copy()
        if system == "Windows":
            command = "pyenv versions --bare"
            shell = True
        else:
            command = ["pyenv", "versions", "--bare"]
            shell = False

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            shell=shell,
            check=False,
        )

        if result.returncode != 0:
            # Could not get versions; assume the version is not installed
            return False

        installed_versions = result.stdout.strip().splitlines()
        # Clean up version strings
        installed_versions = [v.strip().replace("*", "").strip() for v in installed_versions]
        return python_version in installed_versions

    except Exception:
        return False


def is_pyenv_available():
    """Check if pyenv is installed and accessible."""
    try:
        system = platform.system()
        if system == "Windows":
            # Specify full path to pyenv.bat
            home_dir = os.path.expanduser("~")
            pyenv_root = os.path.join(home_dir, ".pyenv", "pyenv-win")
            pyenv_executable = os.path.join(pyenv_root, "bin", "pyenv.bat")
            command = [pyenv_executable, "--version"]
            shell = False
        else:
            command = ["pyenv", "--version"]
            shell = False

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            shell=shell,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_pyenv():
    """Guide the user to install pyenv based on their operating system."""
    system = platform.system()

    # Common instructions and links for pyenv installation
    if system == "Windows":
        title = "Install pyenv-win"
        instructions = (
            "pyenv-win is not installed. Please install it by following the instructions at:\n\n"
        )
        link_text = "https://github.com/pyenv-win/pyenv-win#installation"
        after_instructions = "\n\nAfter installation, restart this application."
    else:
        title = "Install pyenv"
        instructions = (
            "pyenv is not installed. Please install it by following the instructions at:\n\n"
        )
        link_text = "https://github.com/pyenv/pyenv#installation"
        after_instructions = "\n\nAfter installation, restart this application."

    # Function to create the installation window
    def open_install_pyenv():
        install_window = tk.Toplevel(root)
        install_window.title(title)
        install_window.geometry("500x300")
        install_window.resizable(False, False)

        # Text widget to display instructions
        text_widget = tk.Text(install_window, wrap="word", height=10)
        text_widget.pack(expand=True, fill="both", padx=10, pady=10)

        # Insert instructions into the Text widget
        text_widget.insert("1.0", instructions)

        # Keep track of the link's start and end positions
        link_start = text_widget.index(tk.INSERT)
        text_widget.insert(tk.INSERT, link_text)
        link_end = text_widget.index(tk.INSERT)

        # Insert the remaining instructions
        text_widget.insert(tk.INSERT, after_instructions)

        # Configure the tag for the hyperlink
        text_widget.tag_add("link", link_start, link_end)
        text_widget.tag_config("link", foreground="blue", underline=True)

        # Event handler for clicking the link
        def open_link(event):
            webbrowser.open_new(link_text)

        text_widget.tag_bind("link", "<Button-1>", open_link)

        # Configure the Text widget to be read-only but allow text selection
        text_widget.config(state="disabled")
        text_widget.bind("<1>", lambda event: text_widget.focus_set())

        # Buttons frame
        buttons_frame = tk.Frame(install_window)
        buttons_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Copy Link Button
        def copy_link():
            root.clipboard_clear()
            root.clipboard_append(link_text)
            messagebox.showinfo("Copied", "Link copied to clipboard!")

        copy_button = tk.Button(buttons_frame, text="Copy Link", command=copy_link)
        copy_button.pack(side="left", padx=5)

        # Open Link Button
        open_link_button = tk.Button(
            buttons_frame, text="Open Link", command=lambda: webbrowser.open_new(link_text)
        )
        open_link_button.pack(side="left", padx=5)

        # Close Button
        close_button = tk.Button(buttons_frame, text="Close", command=install_window.destroy)
        close_button.pack(side="right", padx=5)

    # Schedule the function to run in the main thread
    root.after(0, open_install_pyenv)

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
                shutil.rmtree(env_path)

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
        context_menu.add_command(
            label="Edit .env Variables",
            command=lambda s=script: edit_env_variables(s),
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
        # Create archived directories if they don't exist
        os.makedirs(os.path.join(BASE_DIR, "archived_scripts"), exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, "archived_environments"), exist_ok=True)

        script_src = os.path.join(SCRIPTS_DIR, script_name)
        env_src = os.path.join(ENVS_DIR, script_name)

        script_dest = os.path.join(BASE_DIR, "archived_scripts", script_name)
        env_dest = os.path.join(BASE_DIR, "archived_environments", script_name)

        # Archive the script directory if it exists
        if os.path.exists(script_src):
            shutil.move(script_src, script_dest)
        else:
            os.makedirs(script_dest, exist_ok=True)

        # Archive the environment directory if it exists
        if os.path.exists(env_src):
            shutil.move(env_src, env_dest)
        else:
            os.makedirs(env_dest, exist_ok=True)

        # Update the UI
        messagebox.showinfo("Archived", f"Script '{script_name}' has been archived.")
        update_script_list()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to archive script '{script_name}': {e}")


def run_script(script_name):
    # Record the current timestamp as the last runtime
    script_metadata[script_name] = time.time()
    save_metadata()

    env_path = os.path.join(ENVS_DIR, script_name)
    script_path = os.path.join(SCRIPTS_DIR, script_name, "main.py")
    if not os.path.exists(script_path):
        messagebox.showerror("Error", "Script not found!")
        return

    # Determine the path to the Python executable in the virtual environment
    system = platform.system()
    if system == "Windows":
        python_executable = os.path.join(env_path, "Scripts", "python.exe")
    else:
        python_executable = os.path.join(env_path, "bin", "python")

    # Open the script in a new terminal
    if system == "Windows":
        command = f'start cmd /k "echo Running script {script_name} && echo. && echo. && "{python_executable}" "{script_path}""'
        subprocess.Popen(command, shell=True)
    elif system == "Darwin":  # macOS
        temp_script_path = os.path.join(BASE_DIR, "run_script.sh")
        with open(temp_script_path, "w", encoding="utf-8") as temp_script:
            temp_script.write('rm -- "$0"\n')
            temp_script.write("#!/bin/bash\n")
            temp_script.write(f"echo 'Running script {script_name}'\n")
            temp_script.write("echo\n")
            temp_script.write("echo\n")
            temp_script.write(f"'{python_executable}' '{script_path}'\n")
        os.chmod(temp_script_path, 0o755)
        subprocess.Popen(["open", "-a", "Terminal.app", temp_script_path])
    elif system == "Linux":
        subprocess.Popen(
            [
                "x-terminal-emulator",
                "-e",
                f"echo 'Running script {script_name}' && echo && echo && '{python_executable}' '{script_path}'",
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

    def save_inputs():
        script_content = script_text.get("1.0", tk.END).strip()
        if not script_content.endswith("\n"):
            script_content += "\n"

        requirements_content = req_text.get("1.0", tk.END).strip()
        if not requirements_content.endswith("\n"):
            requirements_content += "\n"

        # Environment variables content
        env_content = env_text.get("1.0", tk.END).strip()
        if not env_content.endswith("\n"):
            env_content += "\n"

        if not script_content:
            messagebox.showerror("Error", "Script content cannot be empty!")
            os.rmdir(script_dir)
            content_window.destroy()
            return

        # Write script file
        with open(os.path.join(script_dir, "main.py"), "w", encoding="utf-8") as script_file:
            script_file.write(script_content)

        # Write requirements file
        with open(os.path.join(script_dir, "requirements.txt"), "w", encoding="utf-8") as req_file:
            req_file.write(requirements_content)

        # Write .env file
        with open(os.path.join(script_dir, ".env"), "w", encoding="utf-8") as env_file:
            # Add disclaimers and example
            env_file.write(
                "# This is where you should define environment variables, if necessary.\n"
                "# For example, it might look like:\n"
                '# OPENAI_KEY="secret-openai-key-here"\n'
                '# API_TOKEN="your-api-token"\n\n'
            )
            # Add user-entered environment variables
            env_file.write(env_content)

        setup_venv(script_name, python_version)
        update_script_list()
        content_window.destroy()

    # Create content input window
    content_window = tk.Toplevel(root)
    content_window.title("Script, Requirements, and Environment Variables Input")
    content_window.geometry("600x600")

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

    # Environment Variables Input
    tk.Label(content_window, text="Environment Variables (.env):").pack(anchor="w", padx=5, pady=5)
    env_text = scrolledtext.ScrolledText(content_window, wrap=tk.WORD, height=5)
    env_text.pack(fill="both", expand=True, padx=5, pady=5)

    # Populate with default content
    env_text.insert(
        tk.END, """# Add your environment variables here\n# Example: API_KEY="your_secret_key"\n"""
    )

    # Save Button
    tk.Button(content_window, text="Save and Create Environment", command=save_inputs).pack(pady=10)


def edit_env_variables(script_name):
    """Open the .env file for editing."""
    env_path = os.path.join(SCRIPTS_DIR, script_name, ".env")

    # Check if the .env file exists, create it if not
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as env_file:
            env_file.write(
                "# This is where you should define environment variables, if necessary.\n"
                "# For example, it might look like:\n"
                '# OPENAI_KEY="secret-openai-key-here"\n'
                '# API_TOKEN="your-api-token"\n\n'
            )

    # Open a new window to edit the .env file
    def save_changes():
        new_content = env_text.get("1.0", tk.END).strip()
        with open(env_path, "w", encoding="utf-8") as env_file:
            env_file.write(new_content)
        edit_window.destroy()
        messagebox.showinfo("Success", f"Updated .env file for {script_name}.")

    # Create and configure the editing window
    edit_window = tk.Toplevel(root)
    edit_window.title(f"Edit .env - {script_name}")
    edit_window.geometry("600x400")

    # Use a grid layout for better control
    edit_window.rowconfigure(1, weight=1)  # Allow text widget to expand
    edit_window.columnconfigure(0, weight=1)  # Allow full width expansion

    # Add label
    tk.Label(edit_window, text=f"Editing .env for {script_name}:").grid(
        row=0, column=0, sticky="w", padx=5, pady=(5, 0)
    )

    # Frame to hold the text box and scrollbar
    text_frame = tk.Frame(edit_window)
    text_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    # Scrollbar
    scrollbar = tk.Scrollbar(text_frame, orient="vertical")

    # .env text box with integrated scrollbar
    env_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
    env_text.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=env_text.yview)
    scrollbar.pack(side="right", fill="y")

    # Load existing content into the text box
    with open(env_path, "r", encoding="utf-8") as env_file:
        env_text.insert("1.0", env_file.read())

    # Save button
    tk.Button(edit_window, text="Save .env File", command=save_changes).grid(
        row=2, column=0, pady=10
    )


def set_status(message):
    """Set the status message and style."""
    progress_label.config(text=message, fg=default_fg_color)


def reset_status():
    """Reset the status to its default greyed-out placeholder."""
    progress_label.config(text="Status", fg="grey")  # Greyed-out style


def generate_prompt():
    """Open a window to generate a script generation prompt."""

    def generate_prompt_text():
        short_desc = short_description.get()
        detailed_desc = detailed_description.get("1.0", tk.END).strip()

        if not short_desc or not detailed_desc:
            messagebox.showerror("Error", "Please fill in both description fields")
            return

        # Read the prompt template
        try:
            with open("prompt.txt", "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except FileNotFoundError:
            messagebox.showerror("Error", "prompt.txt file not found")
            return

        # Fill in the placeholders
        filled_prompt = prompt_template.format(
            short_description=short_desc, detailed_description=detailed_desc
        )

        # Open a new window to display the generated prompt
        prompt_window = tk.Toplevel(root)
        prompt_window.title("Generated Prompt")
        prompt_window.geometry("500x400")

        # Configure grid layout
        prompt_window.rowconfigure(0, weight=1)
        prompt_window.rowconfigure(1, weight=0)
        prompt_window.columnconfigure(0, weight=1)

        # Prompt text area
        prompt_text = tk.Text(prompt_window, wrap=tk.WORD)
        prompt_text.insert(tk.END, filled_prompt)
        prompt_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        prompt_text.config(state=tk.DISABLED)

        # Copy to clipboard function
        def copy_to_clipboard():
            root.clipboard_clear()
            root.clipboard_append(filled_prompt)
            messagebox.showinfo("Copied", "Prompt copied to clipboard!")

        # Button frame
        button_frame = tk.Frame(prompt_window)
        button_frame.grid(row=1, column=0, sticky="ew", pady=10)

        # Copy and Close buttons
        copy_button = tk.Button(button_frame, text="Copy to Clipboard", command=copy_to_clipboard)
        copy_button.pack(side="left", expand=True, padx=5)

        close_button = tk.Button(button_frame, text="Close", command=prompt_window.destroy)
        close_button.pack(side="right", expand=True, padx=5)

    # Create the prompt generation window
    prompt_gen_window = tk.Toplevel(root)
    prompt_gen_window.title("Generate Script Prompt")
    prompt_gen_window.geometry("500x400")

    # Short description input
    tk.Label(prompt_gen_window, text="Enter a one-line description of the task:").pack(
        anchor="w", padx=10, pady=(10, 0)
    )
    short_description = tk.Entry(prompt_gen_window, width=60)
    short_description.pack(padx=10, pady=5, fill="x")

    # Detailed description input
    tk.Label(prompt_gen_window, text="Enter a detailed description of the task:").pack(
        anchor="w", padx=10, pady=(10, 0)
    )
    detailed_description = tk.Text(prompt_gen_window, wrap=tk.WORD, height=10)
    detailed_description.pack(padx=10, pady=5, fill="x")

    # Generate button
    generate_button = tk.Button(
        prompt_gen_window, text="Generate Prompt", command=generate_prompt_text
    )
    generate_button.pack(pady=10)


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

# Modify the existing button frame creation to add the new button
btn_generate_prompt = tk.Button(btn_frame, text="Generate Prompt", command=generate_prompt)
btn_generate_prompt.pack(side="left", padx=5)

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
