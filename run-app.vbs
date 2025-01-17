Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
command = "make run"

psCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ""cd '" & scriptPath & "'; " & command & """"

WshShell.Run psCommand, 0, False
