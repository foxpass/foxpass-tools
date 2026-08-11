[CmdletBinding()]
param(
    [AllowEmptyString()]
    [string]$RadiusServerNames = '',
    [string]$ServerCaThumbprint = 'INSERT_SERVER_CA_THUMBPRINT_HERE',
    [ValidateRange(10,300)]
    [int]$ConnectionWaitSeconds = 60,
    [switch]$RequireImmediateConnection,
    [string]$LogPath = 'C:\ProgramData\Foxpass\Logs\Configure-INSERT_SSID_HERE-EAPTLS.log'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Ssid = 'INSERT_SSID_HERE'
$ClientAuthenticationOid = '1.3.6.1.5.5.7.3.2'

function Initialize-Log {
    $dir = Split-Path -Parent $LogPath
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -Path $dir -ItemType Directory -Force | Out-Null
    }
}

function Write-Log {
    param(
        [Parameter(Mandatory)][string]$Message,
        [ValidateSet('INFO','WARN','ERROR')][string]$Level='INFO'
    )

    $entry = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $entry
    Add-Content -LiteralPath $LogPath -Value $entry -Encoding UTF8
}

function ConvertTo-PlainString {
    param([AllowNull()][object]$Value)

    if ($null -eq $Value) { return $null }

    if ($Value -is [Security.SecureString]) {
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
        try { $Value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
        finally {
            if ($bstr -ne [IntPtr]::Zero) {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
            }
        }
    }

    if ($Value -is [System.Array]) {
        $parts = @(
            $Value |
                ForEach-Object { ConvertTo-PlainString -Value $_ } |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        )
        if ($parts.Count -eq 0) { return $null }
        return ($parts -join ';').Trim()
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }

    $text = $text.Trim()

    # NinjaOne URL/text fields can occasionally be returned as a JSON wrapper.
    if ($text.StartsWith('{') -and $text.EndsWith('}')) {
        try {
            $obj = $text | ConvertFrom-Json -ErrorAction Stop
            foreach ($propertyName in @('value','text','url','href')) {
                $property = $obj.PSObject.Properties[$propertyName]
                if ($null -ne $property) {
                    $candidate = ConvertTo-PlainString -Value $property.Value
                    if (-not [string]::IsNullOrWhiteSpace($candidate)) {
                        return $candidate
                    }
                }
            }
        }
        catch { }
    }

    return $text
}

function Get-NinjaFieldValue {
    param([Parameter(Mandatory)][string]$Name)

    # Prefer the command that is present in the NinjaOne agent scripting host.
    $legacyCommand = Get-Command -Name 'Ninja-Property-Get' -ErrorAction SilentlyContinue
    if ($legacyCommand) {
        try {
            $result = Ninja-Property-Get $Name
            $value = ConvertTo-PlainString -Value $result
            if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
        }
        catch {
            Write-Log "Ninja field '$Name' unavailable." 'WARN'
        }
    }

    $newCommand = Get-Command -Name 'Get-NinjaProperty' -ErrorAction SilentlyContinue
    if ($newCommand) {
        try {
            $result = Get-NinjaProperty -Name $Name
            $value = ConvertTo-PlainString -Value $result
            if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
        }
        catch {
            Write-Log "Ninja field '$Name' unavailable." 'WARN'
        }
    }

    return $null
}

function Resolve-Value {
    param(
        [string]$Explicit,
        [string]$EnvironmentVariable,
        [string]$FieldName,
        [string]$DisplayName
    )

    $explicitValue = ConvertTo-PlainString -Value $Explicit
    if (-not [string]::IsNullOrWhiteSpace($explicitValue)) {
        # Explicit parameter supplied; no additional log entry needed.
        return $explicitValue
    }

    # NinjaOne script variables are commonly exposed as process environment variables.
    $environmentValue = ConvertTo-PlainString -Value (
        [Environment]::GetEnvironmentVariable($EnvironmentVariable, 'Process')
    )
    if (-not [string]::IsNullOrWhiteSpace($environmentValue)) {
        Write-Log "Using Ninja variable '$EnvironmentVariable'."
        return $environmentValue
    }

    $fieldValue = Get-NinjaFieldValue -Name $FieldName
    if (-not [string]::IsNullOrWhiteSpace($fieldValue)) {
        Write-Log "Using Ninja field '$FieldName'."
        return $fieldValue
    }

    throw "$DisplayName is required. Supply parameter '-$EnvironmentVariable', map a NinjaOne script variable named '$EnvironmentVariable', or create an organization custom field with internal name '$FieldName' and grant Automation read access."
}

function Normalize-Thumbprint {
    param([Parameter(Mandatory)][string]$Thumbprint)
    $value = ($Thumbprint -replace '[^0-9A-Fa-f]','').ToUpperInvariant()
    if ($value.Length -ne 40) { throw 'Server CA thumbprint must be a 40-character SHA-1 certificate thumbprint.' }
    return $value
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-ClientAuthenticationEku {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [Security.Cryptography.X509Certificates.X509Certificate2]$Certificate
    )

    # PowerShell exposes EnhancedKeyUsageList differently across Windows and
    # .NET versions. In some environments ObjectId is already a string; in
    # others it is an Oid object. Parse both forms and then fall back to the
    # certificate's EKU extension directly.
    try {
        foreach ($usage in @($Certificate.EnhancedKeyUsageList)) {
            if ($null -eq $usage) { continue }

            $oid = $null

            if ($usage.PSObject.Properties.Name -contains 'ObjectId') {
                $objectId = $usage.ObjectId

                if ($objectId -is [string]) {
                    $oid = $objectId
                }
                elseif ($null -ne $objectId -and
                        $objectId.PSObject.Properties.Name -contains 'Value') {
                    $oid = [string]$objectId.Value
                }
            }

            if ([string]::IsNullOrWhiteSpace($oid) -and
                $usage -is [Security.Cryptography.Oid]) {
                $oid = [string]$usage.Value
            }

            if ($oid -eq $ClientAuthenticationOid) {
                return $true
            }
        }
    }
    catch {
        # Fall back to parsing the EKU extension.
    }

    try {
        $ekuExtension = $Certificate.Extensions |
            Where-Object { $_.Oid.Value -eq '2.5.29.37' } |
            Select-Object -First 1

        if ($null -eq $ekuExtension) {
            return $false
        }

        $typedEku = New-Object             -TypeName Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension             -ArgumentList @($ekuExtension, $ekuExtension.Critical)

        foreach ($oid in @($typedEku.EnhancedKeyUsages)) {
            if ($null -ne $oid -and [string]$oid.Value -eq $ClientAuthenticationOid) {
                return $true
            }
        }
    }
    catch {
        # Treat an unreadable EKU extension as not matching.
    }

    return $false
}

function Escape-XmlText {
    param(
        [Parameter()]
        [AllowNull()]
        [AllowEmptyString()]
        [string]$Text
    )

    if ([string]::IsNullOrEmpty($Text)) {
        return ''
    }

    return [Security.SecurityElement]::Escape($Text)
}

Initialize-Log
Write-Log "Deploying EAP-TLS profile for '$Ssid'."

try {
    if (-not (Test-IsAdministrator)) { throw 'This script must run as Administrator or SYSTEM.' }

    # Server-name validation is intentionally optional. An empty value keeps
    # certificate-chain validation enabled while disabling DNS-name matching.
    $RadiusServerNames = ConvertTo-PlainString -Value $RadiusServerNames
    if ([string]::IsNullOrWhiteSpace($RadiusServerNames)) {
        $RadiusServerNames = ''
        Write-Log 'Server-name matching disabled; CA pinning remains enabled.' 'WARN'
    }
    else {
        # Server names supplied explicitly; no additional log entry needed.
    }

    $ServerCaThumbprint = Resolve-Value -Explicit $ServerCaThumbprint -EnvironmentVariable 'ServerCaThumbprint' -FieldName 'foxpassServerCaThumbprint' -DisplayName 'Foxpass Server CA thumbprint'
    $ServerCaThumbprint = Normalize-Thumbprint -Thumbprint $ServerCaThumbprint
    # Windows WLAN XML profiles require the CA thumbprint as space-separated byte pairs.
    $ServerCaThumbprintXml = ($ServerCaThumbprint -replace '(..)', '$1 ').Trim()

    $serverCa = Get-ChildItem Cert:\LocalMachine\Root,Cert:\LocalMachine\CA -ErrorAction SilentlyContinue |
        Where-Object { ($_.Thumbprint -replace '\s','').ToUpperInvariant() -eq $ServerCaThumbprint } |
        Select-Object -First 1
    if (-not $serverCa) { throw "The Foxpass Server CA certificate '$ServerCaThumbprint' is not installed in LocalMachine\Root or LocalMachine\CA." }

    $serial = [string](Get-CimInstance Win32_BIOS -ErrorAction Stop).SerialNumber
    $serial = $serial.Trim()
    $expectedSubject = "CN=$serial"

    $clientCert = Get-ChildItem Cert:\LocalMachine\My |
        Where-Object {
            $_.Subject -eq $expectedSubject -and $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) -and (Test-ClientAuthenticationEku $_)
        } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1
    if (-not $clientCert) { throw "No valid machine EAP-TLS certificate with subject '$expectedSubject', private key, and Client Authentication EKU was found." }
    Write-Log "Client certificate ready: $expectedSubject."

    $wlanService = Get-Service -Name WlanSvc -ErrorAction Stop
    if ($wlanService.Status -ne 'Running') {
        Start-Service -Name WlanSvc
        $wlanService.WaitForStatus('Running',[TimeSpan]::FromSeconds(15))
    }

    $interfacesText = (& netsh.exe wlan show interfaces 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $interfacesText -match 'There is no wireless interface') {
        throw 'No usable Windows wireless interface was detected.'
    }

    $escapedSsid = Escape-XmlText -Text $Ssid

    $normalizedServerNames = @(
        $RadiusServerNames -split '[,;\r\n]+' |
            ForEach-Object { $_.Trim() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    ) -join ';'

    if ([string]::IsNullOrWhiteSpace($normalizedServerNames)) {
        $escapedServerNames = ''
    }
    else {
        $escapedServerNames = Escape-XmlText -Text $normalizedServerNames
    }

    $profileXml = @"
<?xml version="1.0" encoding="UTF-8"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>$escapedSsid</name>
  <SSIDConfig><SSID><name>$escapedSsid</name></SSID><nonBroadcast>false</nonBroadcast></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <autoSwitch>false</autoSwitch>
  <MSM>
    <security>
      <authEncryption><authentication>WPA2</authentication><encryption>AES</encryption><useOneX>true</useOneX></authEncryption>
      <OneX xmlns="http://www.microsoft.com/networking/OneX/v1">
        <authMode>machine</authMode>
        <EAPConfig>
          <EapHostConfig xmlns="http://www.microsoft.com/provisioning/EapHostConfig" xmlns:eapCommon="http://www.microsoft.com/provisioning/EapCommon" xmlns:baseEap="http://www.microsoft.com/provisioning/BaseEapMethodConfig">
            <EapMethod><eapCommon:Type>13</eapCommon:Type><eapCommon:AuthorId>0</eapCommon:AuthorId></EapMethod>
            <Config xmlns:baseEap="http://www.microsoft.com/provisioning/BaseEapConnectionPropertiesV1" xmlns:eapTls="http://www.microsoft.com/provisioning/EapTlsConnectionPropertiesV1">
              <baseEap:Eap>
                <baseEap:Type>13</baseEap:Type>
                <eapTls:EapType>
                  <eapTls:CredentialsSource><eapTls:CertificateStore><eapTls:SimpleCertSelection>true</eapTls:SimpleCertSelection></eapTls:CertificateStore></eapTls:CredentialsSource>
                  <eapTls:ServerValidation>
                    <eapTls:DisableUserPromptForServerValidation>true</eapTls:DisableUserPromptForServerValidation>
                    <eapTls:ServerNames>$escapedServerNames</eapTls:ServerNames>
                    <eapTls:TrustedRootCA>$ServerCaThumbprintXml</eapTls:TrustedRootCA>
                  </eapTls:ServerValidation>
                  <eapTls:DifferentUsername>false</eapTls:DifferentUsername>
                  <eapTls:PerformServerValidation xmlns:eapTlsV2="http://www.microsoft.com/provisioning/EapTlsConnectionPropertiesV2">true</eapTls:PerformServerValidation>
                  <eapTls:AcceptServerName xmlns:eapTlsV2="http://www.microsoft.com/provisioning/EapTlsConnectionPropertiesV2">false</eapTls:AcceptServerName>
                </eapTls:EapType>
              </baseEap:Eap>
            </Config>
          </EapHostConfig>
        </EAPConfig>
      </OneX>
    </security>
  </MSM>
</WLANProfile>
"@

    # Correct the V2 namespace prefixes generated above.
    $profileXml = $profileXml.Replace('<eapTls:PerformServerValidation xmlns:eapTlsV2=', '<eapTlsV2:PerformServerValidation xmlns:eapTlsV2=')
    $profileXml = $profileXml.Replace('</eapTls:PerformServerValidation>', '</eapTlsV2:PerformServerValidation>')
    $profileXml = $profileXml.Replace('<eapTls:AcceptServerName xmlns:eapTlsV2=', '<eapTlsV2:AcceptServerName xmlns:eapTlsV2=')
    $profileXml = $profileXml.Replace('</eapTls:AcceptServerName>', '</eapTlsV2:AcceptServerName>')

    $tempPath = Join-Path $env:TEMP 'INSERT_SSID_HERE-EAPTLS.xml'
    try {
        Set-Content -LiteralPath $tempPath -Value $profileXml -Encoding UTF8 -Force
        $addOutput = (& netsh.exe wlan add profile filename="$tempPath" user=all 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "Windows failed to import the '$Ssid' profile. $addOutput" }
        Write-Log "Profile installed: $Ssid."
    }
    finally { Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue }

    $networks = (& netsh.exe wlan show networks mode=bssid 2>&1 | Out-String)
    if ($networks -notmatch ('(?im)^\s*SSID\s+\d+\s*:\s*' + [regex]::Escape($Ssid) + '\s*$')) {
        Write-Log "SSID not visible; profile will auto-connect later." 'WARN'
        exit 0
    }

    $connectOutput = (& netsh.exe wlan connect name="$Ssid" ssid="$Ssid" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Windows could not start the connection to '$Ssid'. $connectOutput" }
    Write-Log "Connection requested: $Ssid."

    $deadline = (Get-Date).AddSeconds($ConnectionWaitSeconds)
    do {
        Start-Sleep -Seconds 2
        $status = (& netsh.exe wlan show interfaces 2>&1 | Out-String)
        if ($status -match '(?im)^\s*State\s*:\s*connected\s*$' -and $status -match ('(?im)^\s*SSID\s*:\s*' + [regex]::Escape($Ssid) + '\s*$')) {
            Write-Log "Connected: $Ssid."
            exit 0
        }
    } while ((Get-Date) -lt $deadline)

    $finalStatus = (& netsh.exe wlan show interfaces 2>&1 | Out-String).Trim()
    if (-not [string]::IsNullOrWhiteSpace($finalStatus)) {
        Write-Log 'Connection not completed; current WLAN status:' 'WARN'
        foreach ($line in ($finalStatus -split "`r?`n")) {
            if (-not [string]::IsNullOrWhiteSpace($line)) { Write-Log $line.Trim() 'WARN' }
        }
    }

    try {
        $recentWlanEvents = Get-WinEvent -FilterHashtable @{
            LogName   = 'Microsoft-Windows-WLAN-AutoConfig/Operational'
            StartTime = (Get-Date).AddMinutes(-5)
        } -ErrorAction Stop | Select-Object -First 8

        foreach ($event in $recentWlanEvents) {
            $message = ([string]$event.Message -replace "`r|`n", ' ' -replace '\s+', ' ').Trim()
            if ($message.Length -gt 500) { $message = $message.Substring(0,500) + '...' }
            Write-Log ("WLAN {0}: {1}" -f $event.Id,$message) 'WARN'
        }
    }
    catch {
        Write-Log "WLAN diagnostics unavailable: $($_.Exception.Message)" 'WARN'
    }

    if ($RequireImmediateConnection) {
        throw "The '$Ssid' connection did not reach the connected state within $ConnectionWaitSeconds seconds."
    }

    Write-Log "Profile installed; connection not completed within $ConnectionWaitSeconds seconds." 'WARN'
    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    if ($_.InvocationInfo.ScriptLineNumber) { Write-Log "Line $($_.InvocationInfo.ScriptLineNumber)." 'ERROR' }
    exit 1
}