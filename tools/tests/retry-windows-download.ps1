param([Parameter(Mandatory)][int]$LauncherPid)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class RetryButton {
    [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr dialog, int id);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr button, uint message, IntPtr wParam, IntPtr lParam);
}
'@
$automation = [System.Windows.Automation.AutomationElement]
$scope = [System.Windows.Automation.TreeScope]
$deadline = [DateTime]::UtcNow.AddSeconds(90)
while ([DateTime]::UtcNow -lt $deadline) {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $LauncherPid AND Name = 'powershell.exe'"
    foreach ($child in $children) {
        $owner = [System.Windows.Automation.PropertyCondition]::new($automation::ProcessIdProperty, [int]$child.ProcessId)
        $windows = $automation::RootElement.FindAll($scope::Children, $owner)
        foreach ($window in $windows) {
            if ($window.Current.Name -ne 'SiMetropolis Edu setup') { continue }
            # Standard Win32 MessageBox control IDRETRY works for all Windows display languages.
            $button = [RetryButton]::GetDlgItem([IntPtr]$window.Current.NativeWindowHandle, 4)
            if ($button -ne [IntPtr]::Zero -and [RetryButton]::PostMessage($button, 0x00f5, [IntPtr]::Zero, [IntPtr]::Zero)) {
                exit 0
            }
        }
    }
    Start-Sleep -Milliseconds 200
}
throw 'The Windows launcher did not show its Retry button.'
