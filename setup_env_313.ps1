Write-Host "=== Python 3.13 Environment Setup for Photo Organizer ==="

# 1. Confirm Python 3.13 is installed
$python313 = py -3.13 -V 2>$null
if (-not $python313) {
    Write-Host "❌ Python 3.13 is NOT installed."
    exit 1
}
Write-Host "✅ Found Python 3.13: $python313"

# 2. Remove old venv
if (Test-Path ".venv") {
    Write-Host "Removing old .venv..."
    Remove-Item -Recurse -Force ".venv"
}

# 3. Create venv
Write-Host "Creating new venv..."
py -3.13 -m venv .venv

# 4. Activate venv
Write-Host "Activating venv..."
& .\.venv\Scripts\activate

# 5. Upgrade pip
Write-Host "Upgrading pip..."
pip install --upgrade pip

# 6. Install dependencies
Write-Host "Installing dependencies..."
pip install flask pillow piexif pymediainfo pywin32

Write-Host "✅ Dependencies installed"

# 7. Locate pywin32 postinstall
Write-Host "Searching for pywin32_postinstall.py..."
$paths = @(
    ".\.venv\Scripts\pywin32_postinstall.py",
    ".\.venv\Lib\site-packages\pywin32_postinstall.py",
    ".\.venv\Lib\site-packages\pywin32_system32\pywin32_postinstall.py",
    ".\.venv\Lib\site-packages\win32\pywin32_postinstall.py"
)

$done = $false
foreach ($p in $paths) {
    if (Test-Path $p) {
        Write-Host "Running postinstall script: $p"
        python "$p" -install
        $done = $true
        break
    }
}

if (-not $done) {
    Write-Host "⚠ pywin32 postinstall script NOT found."
}

# 8. Test Win32 API
Write-Host "Testing win32api..."
$test = @'
import win32api
print("DriveType(C:):", win32api.GetDriveType("C:\\"))
print("Drives:", win32api.GetLogicalDriveStrings().split("\\000")[:-1])
'@

$test | python

Write-Host "✅ Python 3.13 environment setup complete!"
Write-Host "You can now run test_sd.py to verify SD detection."