' TindaTrack Launcher - Hidden Window Version
Set WshShell = CreateObject("WScript.Shell")

' Get current directory
Dim currDir
currDir = WshShell.CurrentDirectory

' Run the batch file hidden
WshShell.Run Chr(34) & currDir & "\run_app.bat" & Chr(34), 0, False

' Show popup notification (non-blocking)
WshShell.Popup "TindaTrack is starting..." & vbCrLf & vbCrLf & "Open: http://127.0.0.1:8000", 3, "TindaTrack", 64