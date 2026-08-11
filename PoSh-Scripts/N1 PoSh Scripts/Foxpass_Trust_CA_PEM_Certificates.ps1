[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$LogPath = 'C:\ProgramData\NinjaRMMAgent\logs\foxpass-ca-deployment.log'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# -----------------------------------------------------------------------------
# PASTE THE COMPLETE FOXPASS CA CERTIFICATES BELOW.
# Keep the BEGIN CERTIFICATE and END CERTIFICATE lines.
# Do not paste a client/device identity certificate or any private key.
# -----------------------------------------------------------------------------

$FoxpassClientCAPem = @'
-----BEGIN CERTIFICATE-----
INSERT_CLIENT_CA_PEM
-----END CERTIFICATE-----
'@

$FoxpassServerCAPem = @'
-----BEGIN CERTIFICATE-----
INSERT_SERVER_CA_PEM_HERE
-----END CERTIFICATE-----
'@

function Initialize-Log {
    $directory = Split-Path -Parent $script:LogPath
    if ([string]::IsNullOrWhiteSpace($directory)) {
        throw "The log path '$script:LogPath' does not include a valid parent directory."
    }

    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -Path $directory -ItemType Directory -Force | Out-Null
    }
}

function Write-Log {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,

        [Parameter(Mandatory = $false)]
        [ValidateSet('INFO', 'WARN', 'ERROR')]
        [string]$Level = 'INFO'
    )

    $entry = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $entry

    try {
        Add-Content -LiteralPath $script:LogPath -Value $entry -Encoding UTF8
    }
    catch {
        Write-Host "Unable to write to log file '$script:LogPath': $($_.Exception.Message)"
    }
}

function Test-IsElevated {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-PlaceholderPem {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PemText,

        [Parameter(Mandatory = $true)]
        [string]$FriendlyName
    )

    if ([string]::IsNullOrWhiteSpace($PemText) -or
        $PemText -match 'PASTE_COMPLETE_' -or
        $PemText -notmatch '-----BEGIN CERTIFICATE-----' -or
        $PemText -notmatch '-----END CERTIFICATE-----') {
        throw "$FriendlyName has not been populated. Paste the complete PEM certificate into the matching block near the top of the script."
    }
}

function Get-CertificatesFromPem {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PemText,

        [Parameter(Mandatory = $true)]
        [string]$SourceName
    )

    $matches = [regex]::Matches(
        $PemText,
        '-----BEGIN CERTIFICATE-----\s*(?<Data>[A-Za-z0-9+/=\r\n\t ]+?)\s*-----END CERTIFICATE-----',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    if ($matches.Count -eq 0) {
        throw "No valid PEM certificate blocks were found in $SourceName."
    }

    $certificates = New-Object System.Collections.Generic.List[System.Security.Cryptography.X509Certificates.X509Certificate2]

    foreach ($match in $matches) {
        try {
            $base64 = $match.Groups['Data'].Value -replace '\s', ''
            $rawData = [Convert]::FromBase64String($base64)
            $certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 -ArgumentList @(,$rawData)
            $certificates.Add($certificate)
        }
        catch {
            throw "A certificate in $SourceName could not be parsed. $($_.Exception.Message)"
        }
    }

    return $certificates
}

function Test-IsCertificateAuthority {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate
    )

    foreach ($extension in $Certificate.Extensions) {
        if ($extension.Oid.Value -eq '2.5.29.19') {
            $basicConstraints = New-Object System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension
            $basicConstraints.CopyFrom($extension)
            return $basicConstraints.CertificateAuthority
        }
    }

    return $false
}

function Install-CACertificate {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,

        [Parameter(Mandatory = $true)]
        [string]$SourceName
    )

    if (-not (Test-IsCertificateAuthority -Certificate $Certificate)) {
        throw "Certificate '$($Certificate.Subject)' from $SourceName is not marked as a CA certificate. It was not installed."
    }

    $isSelfSigned = ($Certificate.Subject -eq $Certificate.Issuer)
    $storeName = if ($isSelfSigned) {
        [System.Security.Cryptography.X509Certificates.StoreName]::Root
    }
    else {
        [System.Security.Cryptography.X509Certificates.StoreName]::CertificateAuthority
    }
    $storeDisplay = if ($isSelfSigned) { 'Cert:\LocalMachine\Root' } else { 'Cert:\LocalMachine\CA' }

    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store(
        $storeName,
        [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine
    )

    try {
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        $existing = $store.Certificates.Find(
            [System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,
            $Certificate.Thumbprint,
            $false
        )

        if ($existing.Count -gt 0) {
            Write-Log "Already installed: '$($Certificate.Subject)' [$($Certificate.Thumbprint)] in $storeDisplay."
            return 'Existing'
        }

        $store.Add($Certificate)
        Write-Log "Installed: '$($Certificate.Subject)' [$($Certificate.Thumbprint)] from $SourceName into $storeDisplay."
        return 'Installed'
    }
    finally {
        $store.Close()
    }
}

try {
    $script:LogPath = $LogPath
    Initialize-Log
    Write-Log 'Starting Foxpass CA certificate deployment.'

    if (-not (Test-IsElevated)) {
        throw 'This script must run as SYSTEM or from an elevated PowerShell session.'
    }

    Test-PlaceholderPem -PemText $FoxpassClientCAPem -FriendlyName 'Foxpass Client CA'
    Test-PlaceholderPem -PemText $FoxpassServerCAPem -FriendlyName 'Foxpass Server CA'

    $inputSets = @(
        [pscustomobject]@{ Name = 'Foxpass Client CA'; Pem = $FoxpassClientCAPem },
        [pscustomobject]@{ Name = 'Foxpass Server CA'; Pem = $FoxpassServerCAPem }
    )

    $seenThumbprints = @{}
    $installedCount = 0
    $existingCount = 0

    foreach ($inputSet in $inputSets) {
        $certificates = @(Get-CertificatesFromPem -PemText $inputSet.Pem -SourceName $inputSet.Name)
        Write-Log "Found $(@($certificates).Count) certificate(s) in $($inputSet.Name)."

        foreach ($certificate in @($certificates)) {
            try {
                if ($seenThumbprints.ContainsKey($certificate.Thumbprint)) {
                    Write-Log "Duplicate PEM input skipped: '$($certificate.Subject)' [$($certificate.Thumbprint)]." -Level 'WARN'
                    continue
                }

                $seenThumbprints[$certificate.Thumbprint] = $true
                $result = Install-CACertificate -Certificate $certificate -SourceName $inputSet.Name

                if ($result -eq 'Installed') { $installedCount++ }
                if ($result -eq 'Existing') { $existingCount++ }
            }
            finally {
                $certificate.Dispose()
            }
        }
    }

    Write-Log "Foxpass CA deployment completed successfully. Installed: $installedCount; already present: $existingCount."
    exit 0
}
catch {
    try {
        Write-Log $_.Exception.Message -Level 'ERROR'
        Write-Log 'Foxpass CA deployment failed.' -Level 'ERROR'
    }
    catch {
        Write-Host "Foxpass CA deployment failed: $($_.Exception.Message)"
    }
    exit 1
}