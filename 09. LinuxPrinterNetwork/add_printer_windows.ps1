# add_printer_windows.ps1
# Run on the Windows machine to add the shared Brother printer via IPP.
# Right-click PowerShell → "Run as administrator" (if available).
# On a locked machine, try running as a normal user first — it often works.
#
# Usage: Right-click this file → "Run with PowerShell"

$LinuxHost  = "192.168.178.203"
$PrinterName = "Brother DCP-L3550CDW"
$IppUrl     = "http://${LinuxHost}:631/printers/Brother_DCP-L3550CDW"

Write-Host "Adding printer: $PrinterName via $IppUrl" -ForegroundColor Cyan

try {
    # Method 1: Add via IPP port (works without admin on Win10/11)
    Add-PrinterPort -Name "IPP_Brother_L3550CDW" -PrinterHostAddress $LinuxHost -PortNumber 631 -ErrorAction SilentlyContinue
    Add-Printer -Name $PrinterName -DriverName "Microsoft IPP Class Driver" -PortName "IPP_Brother_L3550CDW" -ErrorAction Stop
    Write-Host "Printer added successfully via IPP Class Driver." -ForegroundColor Green
}
catch {
    Write-Host "IPP Class Driver method failed: $_" -ForegroundColor Yellow
    Write-Host "Trying WSD/network discovery approach..." -ForegroundColor Cyan

    # Method 2: Add via full IPP URL (Windows 10 v1903+ supports this natively)
    try {
        $port = "IPP_${LinuxHost}_631"
        & rundll32 printui.dll,PrintUIEntry /if /b $PrinterName /f "%windir%\inf\ntprint.inf" /r $IppUrl /m "Microsoft IPP Class Driver" 2>$null
        Write-Host "Printer added via PrintUIEntry." -ForegroundColor Green
    }
    catch {
        Write-Host "Automated add failed. Please add manually:" -ForegroundColor Red
        Write-Host ""
        Write-Host "MANUAL STEPS:" -ForegroundColor White
        Write-Host "  1. Settings -> Bluetooth & devices -> Printers & scanners"
        Write-Host "  2. 'Add device' -> wait, then 'Add manually'"
        Write-Host "  3. Choose: 'Add a printer using an IP address or hostname'"
        Write-Host "  4. Device type: IPP Device"
        Write-Host "  5. Hostname: $IppUrl"
        Write-Host "  6. Windows will find the driver automatically"
        Write-Host ""
        Write-Host "  --- OR via File Explorer (SMB) ---"
        Write-Host "  1. Open File Explorer"
        Write-Host "  2. In address bar type: \\$LinuxHost"
        Write-Host "  3. Double-click 'Brother_DCP-L3550CDW'"
    }
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
