Option Explicit

Const EXIT_ALREADY_RUNNING = 20

Dim shell
Dim fso
Dim appDir
Dim exePath
Dim command
Dim exitCode

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
exePath = fso.BuildPath(appDir, "ContePersonas.exe")
shell.CurrentDirectory = appDir

Do
    If Not fso.FileExists(exePath) Then
        WScript.Quit 0
    End If

    command = Chr(34) & exePath & Chr(34)
    exitCode = shell.Run(command, 0, True)

    ' Si ya existe otra instancia valida, este watchdog duplicado termina.
    If exitCode = EXIT_ALREADY_RUNNING Then
        WScript.Quit 0
    End If

    WScript.Sleep 10000
Loop
