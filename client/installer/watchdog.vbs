Option Explicit

Const EXIT_OK = 0
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

    ' ContePersonas.exe esta compilado con --noconsole, por lo que usar
    ' ventana normal no abre CMD. Esto permite que OpenCV muestre la camara.
    exitCode = shell.Run(command, 1, True)

    ' Cierre normal = el usuario eligio Salir/Q. No debe reiniciarse.
    If exitCode = EXIT_OK Then
        WScript.Quit 0
    End If

    ' Si ya existe otra instancia valida, este watchdog duplicado termina.
    If exitCode = EXIT_ALREADY_RUNNING Then
        WScript.Quit 0
    End If

    ' Solo los errores reales vuelven a intentar el cliente.
    WScript.Sleep 10000
Loop
