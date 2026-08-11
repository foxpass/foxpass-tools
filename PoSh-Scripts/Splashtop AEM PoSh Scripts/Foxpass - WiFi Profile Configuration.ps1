[CmdletBinding()]
param(
    [string]$Ssid = 'INSERT_SSID_HERE',

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

$ClientAuthenticationOid = '1.3.6.1.5.5.7.3.2'

function Initialize-Log {
    $directory = Split-Path -Parent $LogPath
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -Path $directory -ItemType Directory -Force | Out-Null
    }
}

function Write-Log {
    param(
        [Parameter(Mandatory)]
        [string]$Message,

        [ValidateSet('INFO','WARN','ERROR')]
        [string]$Level = 'INFO'
    )

    $entry = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $entry
    Add-Content -LiteralPath $LogPath -Value $entry -Encoding UTF8
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Normalize-Thumbprint {
    param([Parameter(Mandatory)][string]$Thumbprint)

    $normalized = ($Thumbprint -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()
    if ($normalized.Length -ne 40) {
        throw 'Server CA thumbprint must be a 40-character SHA-1 certificate thumbprint.'
    }

    return $normalized
}

function Test-ClientAuthenticationEku {
    param(
        [Parameter(Mandatory)]
        [Security.Cryptography.X509Certificates.X509Certificate2]$Certificate
    )

    try {
        foreach ($usage in @($Certificate.EnhancedKeyUsageList)) {
            if ($null -eq $usage) { continue }

            $oid = $null
            if ($usage.PSObject.Properties.Name -contains 'ObjectId') {
                $objectId = $usage.ObjectId
                if ($objectId -is [string]) {
                    $oid = $objectId
                }
                elseif ($null -ne $objectId -and $objectId.PSObject.Properties.Name -contains 'Value') {
                    $oid = [string]$objectId.Value
                }
            }

            if ([string]::IsNullOrWhiteSpace($oid) -and $usage -is [Security.Cryptography.Oid]) {
                $oid = [string]$usage.Value
            }

            if ($oid -eq $ClientAuthenticationOid) {
                return $true
            }
        }
    }
    catch {
        # Fall through to direct EKU extension parsing.
    }

    try {
        $ekuExtension = $Certificate.Extensions |
            Where-Object { $_.Oid.Value -eq '2.5.29.37' } |
            Select-Object -First 1

        if ($null -eq $ekuExtension) {
            return $false
        }

        $typedEku = New-Object \
            -TypeName Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension \
            -ArgumentList @($ekuExtension, $ekuExtension.Critical)

        foreach ($oid in @($typedEku.EnhancedKeyUsages)) {
            if ($null -ne $oid -and [string]$oid.Value -eq $ClientAuthenticationOid) {
                return $true
            }
        }
    }
    catch {
        return $false
    }

    return $false
}

function Escape-XmlText {
    param(
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
    if (-not (Test-IsAdministrator)) {
        throw 'This script must run as Administrator or SYSTEM.'
    }

    if (-not [Environment]::Is64BitProcess) {
        throw 'Run this script from 64-bit Windows PowerShell.'
    }

    $ServerCaThumbprint = Normalize-Thumbprint -Thumbprint $ServerCaThumbprint
    $ServerCaThumbprintXml = ($ServerCaThumbprint -replace '(..)', '$1 ').Trim()

    if ([string]::IsNullOrWhiteSpace($RadiusServerNames)) {
        $RadiusServerNames = ''
        Write-Log 'Server-name matching disabled; CA pinning remains enabled.' 'WARN'
    }

    $serverCa = Get-ChildItem Cert:\LocalMachine\Root, Cert:\LocalMachine\CA -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.Thumbprint -replace '\s', '').ToUpperInvariant() -eq $ServerCaThumbprint
        } |
        Select-Object -First 1

    if (-not $serverCa) {
        throw "The Foxpass Server CA certificate '$ServerCaThumbprint' is not installed in LocalMachine\Root or LocalMachine\CA."
    }

    $serial = [string](Get-CimInstance -ClassName Win32_BIOS -ErrorAction Stop).SerialNumber
    $serial = $serial.Trim()
    if ([string]::IsNullOrWhiteSpace($serial)) {
        throw 'The machine BIOS serial number could not be determined.'
    }

    $expectedSubject = "CN=$serial"
    $clientCert = Get-ChildItem Cert:\LocalMachine\My |
        Where-Object {
            $_.Subject -eq $expectedSubject -and
            $_.HasPrivateKey -and
            $_.NotAfter -gt (Get-Date) -and
            (Test-ClientAuthenticationEku -Certificate $_)
        } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1

    if (-not $clientCert) {
        throw "No valid machine EAP-TLS certificate with subject '$expectedSubject', private key, and Client Authentication EKU was found."
    }

    Write-Log "Client certificate ready: $expectedSubject."

    $wlanService = Get-Service -Name WlanSvc -ErrorAction Stop
    if ($wlanService.Status -ne 'Running') {
        Start-Service -Name WlanSvc
        $wlanService.WaitForStatus('Running', [TimeSpan]::FromSeconds(15))
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
    $escapedServerNames = Escape-XmlText -Text $normalizedServerNames

    $profileXml = @"
<?xml version="1.0" encoding="UTF-8"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>$escapedSsid</name>
  <SSIDConfig>
    <SSID><name>$escapedSsid</name></SSID>
    <nonBroadcast>false</nonBroadcast>
  </SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <autoSwitch>false</autoSwitch>
  <MSM>
    <security>
      <authEncryption>
        <authentication>WPA2</authentication>
        <encryption>AES</encryption>
        <useOneX>true</useOneX>
      </authEncryption>
      <OneX xmlns="http://www.microsoft.com/networking/OneX/v1">
        <authMode>machine</authMode>
        <EAPConfig>
          <EapHostConfig xmlns="http://www.microsoft.com/provisioning/EapHostConfig" xmlns:eapCommon="http://www.microsoft.com/provisioning/EapCommon" xmlns:baseEap="http://www.microsoft.com/provisioning/BaseEapMethodConfig">
            <EapMethod>
              <eapCommon:Type>13</eapCommon:Type>
              <eapCommon:AuthorId>0</eapCommon:AuthorId>
            </EapMethod>
            <Config xmlns:baseEap="http://www.microsoft.com/provisioning/BaseEapConnectionPropertiesV1" xmlns:eapTls="http://www.microsoft.com/provisioning/EapTlsConnectionPropertiesV1">
              <baseEap:Eap>
                <baseEap:Type>13</baseEap:Type>
                <eapTls:EapType>
                  <eapTls:CredentialsSource>
                    <eapTls:CertificateStore>
                      <eapTls:SimpleCertSelection>true</eapTls:SimpleCertSelection>
                    </eapTls:CertificateStore>
                  </eapTls:CredentialsSource>
                  <eapTls:ServerValidation>
                    <eapTls:DisableUserPromptForServerValidation>true</eapTls:DisableUserPromptForServerValidation>
                    <eapTls:ServerNames>$escapedServerNames</eapTls:ServerNames>
                    <eapTls:TrustedRootCA>$ServerCaThumbprintXml</eapTls:TrustedRootCA>
                  </eapTls:ServerValidation>
                  <eapTls:DifferentUsername>false</eapTls:DifferentUsername>
                  <eapTlsV2:PerformServerValidation xmlns:eapTlsV2="http://www.microsoft.com/provisioning/EapTlsConnectionPropertiesV2">true</eapTlsV2:PerformServerValidation>
                  <eapTlsV2:AcceptServerName xmlns:eapTlsV2="http://www.microsoft.com/provisioning/EapTlsConnectionPropertiesV2">false</eapTlsV2:AcceptServerName>
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

    $tempPath = Join-Path $env:TEMP ("{0}-EAPTLS.xml" -f $Ssid)
    try {
        Set-Content -LiteralPath $tempPath -Value $profileXml -Encoding UTF8 -Force
        $addOutput = (& netsh.exe wlan add profile filename="$tempPath" user=all 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "Windows failed to import the '$Ssid' profile. $addOutput"
        }
        Write-Log "Profile installed: $Ssid."
    }
    finally {
        Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
    }

    $networks = (& netsh.exe wlan show networks mode=bssid 2>&1 | Out-String)
    if ($networks -notmatch ('(?im)^\s*SSID\s+\d+\s*:\s*' + [regex]::Escape($Ssid) + '\s*$')) {
        Write-Log "SSID '$Ssid' is not visible; the profile will auto-connect when available." 'WARN'
        exit 0
    }

    $connectOutput = (& netsh.exe wlan connect name="$Ssid" ssid="$Ssid" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Windows could not start the connection to '$Ssid'. $connectOutput"
    }

    Write-Log "Connection requested: $Ssid."

    $deadline = (Get-Date).AddSeconds($ConnectionWaitSeconds)
    do {
        Start-Sleep -Seconds 2
        $status = (& netsh.exe wlan show interfaces 2>&1 | Out-String)
        if ($status -match '(?im)^\s*State\s*:\s*connected\s*$' -and
            $status -match ('(?im)^\s*SSID\s*:\s*' + [regex]::Escape($Ssid) + '\s*$')) {
            Write-Log "Connected: $Ssid."
            exit 0
        }
    } while ((Get-Date) -lt $deadline)

    if ($RequireImmediateConnection) {
        throw "The '$Ssid' connection did not reach the connected state within $ConnectionWaitSeconds seconds."
    }

    Write-Log "Profile installed, but Windows did not connect within $ConnectionWaitSeconds seconds." 'WARN'
    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    if ($_.InvocationInfo.ScriptLineNumber) {
        Write-Log "Line $($_.InvocationInfo.ScriptLineNumber)." 'ERROR'
    }
    exit 1
}