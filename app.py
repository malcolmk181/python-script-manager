import os
import platform
import subprocess
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog

# Directory constants
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
ENVS_DIR = os.path.join(BASE_DIR, "environments")

# Ensure directories exist
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(ENVS_DIR, exist_ok=True)


def add_pyenv_to_path():
    """Ensure pyenv is accessible by adding it to PATH."""
    home_dir = os.path.expanduser("~")
    pyenv_bin = os.path.join(home_dir, ".pyenv", "bin")
    pyenv_shims = os.path.join(home_dir, ".pyenv", "shims")

    # Add pyenv directories to PATH
    os.environ["PATH"] = pyenv_bin + os.pathsep + pyenv_shims + os.pathsep + os.environ["PATH"]


add_pyenv_to_path()


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


def setup_venv(script_name, python_version="3.13.0"):
    """Set up a virtual environment for the script using pyenv-managed Python."""
    env_path = os.path.join(ENVS_DIR, script_name)
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    requirements_file = os.path.join(script_path, "requirements.txt")

    # Get the pyenv-managed Python executable
    python_executable = get_pyenv_python_path(python_version)
    if not python_executable:
        messagebox.showerror("Error", f"Failed to find Python {python_version}")
        return

    try:
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
    except subprocess.CalledProcessError as e:
        messagebox.showerror(
            "Error", f"Failed to set up virtual environment for {script_name}:\n{e}"
        )


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

    if system == "Windows":
        messagebox.showinfo(
            "Install pyenv",
            "pyenv is not installed. Please visit the following link to install pyenv for Windows:\n\n"
            "https://github.com/pyenv-win/pyenv-win",
        )

    elif system == "Darwin":  # macOS
        try:
            result = subprocess.run(
                ["brew", "--version"], capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                subprocess.run(["brew", "install", "pyenv"], check=True)
                return True

            raise FileNotFoundError("Homebrew not found")

        except FileNotFoundError:
            messagebox.showinfo(
                "Install pyenv",
                "pyenv is not installed, and Homebrew is unavailable.\n"
                "Install pyenv manually with: curl https://pyenv.run | bash\n",
            )

    elif system == "Linux":
        messagebox.showinfo(
            "Install pyenv",
            "pyenv is not installed. Install it using: curl https://pyenv.run | bash\n",
        )

    else:
        messagebox.showerror("Error", "Unsupported operating system for pyenv installation.")

    return False


def rebuild_venv(script_name):
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
        setup_venv(script_name, python_version)
        messagebox.showinfo(
            "Success",
            f"Virtual environment for {script_name} has been rebuilt successfully.",
        )
    except Exception as e:
        messagebox.showerror(
            "Error", f"Failed to rebuild virtual environment for {script_name}:\n{e}"
        )


def update_script_list():
    """Update the list of scripts displayed in the UI."""
    for widget in list_frame.winfo_children():
        widget.destroy()
    scripts = os.listdir(SCRIPTS_DIR)
    for script in scripts:
        script_frame = tk.Frame(list_frame)
        script_frame.pack(fill="x", pady=2)

        # Run Script Button
        btn_run = tk.Button(
            script_frame, text=f"Run {script}", command=lambda s=script: run_script(s)
        )
        btn_run.pack(side="left", padx=5)

        # Rebuild Environment Button
        btn_rebuild = tk.Button(
            script_frame, text="Rebuild Env", command=lambda s=script: rebuild_venv(s)
        )
        btn_rebuild.pack(side="right", padx=5)


# Function to run script
def run_script(script_name):
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
        # Create a temporary shell script to execute the command
        temp_script_path = os.path.join(BASE_DIR, "run_script.sh")
        with open(temp_script_path, "w", encoding="utf-8") as temp_script:
            temp_script.write("#!/bin/bash\n")
            temp_script.write(f"echo 'Running script {script_name}'\n")
            temp_script.write("echo\n")
            temp_script.write("echo\n")
            temp_script.write(f"'{os.path.join(env_path, 'bin', 'python')}' '{script_path}'\n")
        os.chmod(temp_script_path, 0o755)
        # Open the shell script in a new terminal
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
        requirements_content = req_text.get("1.0", tk.END).strip()

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


# Main Application
root = tk.Tk()
root.title("Script Manager")

# Layout
frame = tk.Frame(root)
frame.pack(fill="both", expand=True, padx=10, pady=10)

list_frame = tk.Frame(frame)
list_frame.pack(fill="both", expand=True)

btn_frame = tk.Frame(root)
btn_frame.pack(fill="x", pady=5)

btn_add = tk.Button(btn_frame, text="Add Script", command=add_script)
btn_add.pack(side="left", padx=5)

btn_refresh = tk.Button(btn_frame, text="Refresh", command=update_script_list)
btn_refresh.pack(side="right", padx=5)

# Initialize script list
update_script_list()

# Start the app
root.mainloop()
