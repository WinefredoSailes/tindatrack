' TindaTrack - Simple Launcher
Set WshShell = CreateObject("WScript.Shell")

' Get script location and change to that directory
Dim scriptPath
scriptPath = WScript.ScriptFullName
Dim appFolder
appFolder = Left(scriptPath, InStrRev(scriptPath, "\") - 1)

' Build command to run Django with venv
Dim cmd
cmd = "cmd /c cd /d " & appFolder & " && venv\Scripts\python.exe manage.py runserver"

' Run hidden (0), don't wait (False)
WshShell.Run cmd, 0, False

' Quick notification (3 seconds)
WshShell.Popup "TindaTrack starting..." & vbCrLf & "Go to http://127.0.0.1:8000", 3, "TindaTrack", 64