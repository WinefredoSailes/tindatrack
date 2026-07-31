' TindaTrack Launcher - Hidden Window Version
Set WshShell = CreateObject("WScript.Shell")

' Get script location
Dim scriptPath
scriptPath = WScript.ScriptFullName
Dim appFolder
appFolder = Left(scriptPath, InStrRev(scriptPath, "\") - 1)

' Build command to run Django with venv
Dim cmd
cmd = "cmd /c cd /d " & appFolder & " && venv\Scripts\python.exe manage.py runserver --insecure"

' Run hidden (0), don't wait (False)
WshShell.Run cmd, 0, False

' Show popup notification (non-blocking)
WshShell.Popup "TindaTrack is starting..." & vbCrLf & vbCrLf & "Open: http://127.0.0.1:8000", 3, "TindaTrack", 64