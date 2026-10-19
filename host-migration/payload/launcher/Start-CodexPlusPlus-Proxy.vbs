' Sole desktop-entry shim for Codex++.  Runs the controlled launch chain in
' a hidden window (no console flash on every launch) and shows an error
' dialog only when startup fails.  Never starts a watcher, never repairs,
' never touches ordinary Codex.

Dim shell, fso, scriptDir, command, exitCode
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

command = """@@POWERSHELL_EXE:win@@"" -NoProfile -NonInteractive -File """ & _
    scriptDir & "\Start-CodexPlusPlus.ps1"" -SkipConnectorSync -SkipOpenCliAdapterSync -SkipSessionPathTest"

' Window style 0 = hidden; True = wait for completion and capture exit code.
exitCode = shell.Run(command, 0, True)

If exitCode <> 0 Then
    MsgBox "Codex++ 启动失败（退出码 " & exitCode & "）。" & vbCrLf & vbCrLf & _
        "请查看排查手册，或在终端里强制重启：" & vbCrLf & _
        "& '@@POWERSHELL_EXE:win@@' -NoProfile -File '" & _
        scriptDir & "\Start-CodexPlusPlus.ps1' -Restart", _
        vbCritical + vbOKOnly, "Codex++ 启动失败"
End If
