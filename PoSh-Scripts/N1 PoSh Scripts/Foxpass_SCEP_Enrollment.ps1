[CmdletBinding()]
param(
    [string]$FoxpassScepEndpoint,
    [string]$FoxpassScepChallengePass,
    [string]$CertificateSubject,
    [ValidateRange(1,3650)][int]$RenewalDays = 30,
    [ValidateSet(2048,4096)][int]$KeyLength = 4096,
    [bool]$CleanupSupersededCertificates = $true,
    [string]$FriendlyName = 'Foxpass EAP-TLS Device Certificate',
    [string]$LogPath = 'C:\ProgramData\Foxpass\Logs\Enroll-FoxpassSCEP.log'
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$ClientAuthOid = '1.3.6.1.5.5.7.3.2'
$Sha256Oid = '2.16.840.1.101.3.4.2.1'
$StorePath = 'Cert:\LocalMachine\My'

function Write-Log {
    param([string]$Message,[ValidateSet('INFO','WARN','ERROR')][string]$Level='INFO')
    $dir = Split-Path -Parent $LogPath
    if (-not (Test-Path $dir)) { New-Item $dir -ItemType Directory -Force | Out-Null }
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),$Level,$Message
    Write-Host $line
    Add-Content $LogPath $line -Encoding UTF8
}

function ConvertTo-Text {
    param([AllowNull()][object]$Value)
    if ($null -eq $Value) { return $null }
    if ($Value -is [Security.SecureString]) {
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
        try { $Value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) } }
    }
    if ($Value -is [Array]) {
        $Value = @($Value | ForEach-Object { ConvertTo-Text $_ } | Where-Object { $_ }) -join [Environment]::NewLine
    }
    $text = [Convert]::ToString($Value,[Globalization.CultureInfo]::InvariantCulture).Trim()
    if (-not $text) { return $null }
    if ($text.StartsWith('{') -and $text.EndsWith('}')) {
        try {
            $json = $text | ConvertFrom-Json -ErrorAction Stop
            foreach ($name in 'value','Value','text','Text','url','Url','href','Href') {
                $property = $json.PSObject.Properties[$name]
                if ($property -and ($candidate = ConvertTo-Text $property.Value)) { return $candidate }
            }
        } catch {}
    }
    return $text
}

function Get-NinjaValue {
    param([string]$Name)
    foreach ($cmd in 'Ninja-Property-Get','Get-NinjaProperty') {
        if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { continue }
        try {
            $value = if ($cmd -eq 'Get-NinjaProperty') { Get-NinjaProperty -Name $Name } else { Ninja-Property-Get $Name }
            if ($value = ConvertTo-Text $value) { return $value }
        } catch {}
    }
}

function Resolve-Value {
    param([AllowNull()][object]$Explicit,[string]$EnvironmentName,[string]$NinjaField,[switch]$Required)
    $value = ConvertTo-Text $Explicit
    if (-not $value) { $value = ConvertTo-Text ([Environment]::GetEnvironmentVariable($EnvironmentName,'Process')) }
    if (-not $value) { $value = Get-NinjaValue $NinjaField }
    if ($Required -and -not $value) { throw "Missing '$NinjaField'. Supply it as a parameter, script variable, or NinjaOne custom field." }
    return $value
}

function Get-ClientAuthOids {
    param([Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)
    $ext = $Certificate.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.37' } | Select-Object -First 1
    if (-not $ext) { return @() }
    try {
        $eku = New-Object Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension
        $eku.CopyFrom($ext)
        return @($eku.EnhancedKeyUsages | ForEach-Object Value)
    } catch {
        return @($Certificate.EnhancedKeyUsageList | ForEach-Object {
            if ($_.ObjectId -is [string]) { $_.ObjectId } elseif ($_.ObjectId) { $_.ObjectId.Value }
        })
    }
}

function Get-MatchingCertificates {
    param([string]$Subject)
    @(Get-ChildItem $StorePath | Where-Object {
        $_.Subject -ieq $Subject -and $_.HasPrivateKey -and ((Get-ClientAuthOids $_) -contains $ClientAuthOid)
    })
}

function New-ScepRequest {
    param([string]$Subject,[string]$Challenge,[int]$Length)
    $request = New-Object -ComObject X509Enrollment.CX509CertificateRequestPkcs10
    $request.Initialize(2)
    $dn = New-Object -ComObject X509Enrollment.CX500DistinguishedName
    $dn.Encode($Subject)
    $request.Subject = $dn
    $request.PrivateKey.Length = $Length
    $request.PrivateKey.ExportPolicy = 0
    $request.PrivateKey.ProviderName = 'Microsoft Software Key Storage Provider'
    $request.KeyContainerNamePrefix = "FoxpassSCEP-$($env:COMPUTERNAME)-"
    $request.ChallengePassword = $Challenge
    $hash = New-Object -ComObject X509Enrollment.CObjectId
    $hash.InitializeFromValue($Sha256Oid)
    $request.HashAlgorithm = $hash
    $keyUsage = New-Object -ComObject X509Enrollment.CX509ExtensionKeyUsage
    $keyUsage.InitializeEncode(0xA0)
    $request.X509Extensions.Add($keyUsage)
    $oids = New-Object -ComObject X509Enrollment.CObjectIds
    $oid = New-Object -ComObject X509Enrollment.CObjectId
    $oid.InitializeFromValue($ClientAuthOid)
    $oids.Add($oid)
    $eku = New-Object -ComObject X509Enrollment.CX509ExtensionEnhancedKeyUsage
    $eku.InitializeEncode($oids)
    $request.X509Extensions.Add($eku)
    return $request
}

function Invoke-ScepEnrollment {
    param([string]$Endpoint,[__ComObject]$Request)
    $helper = New-Object -ComObject X509Enrollment.CX509SCEPEnrollmentHelper
    $helper.Initialize($Endpoint,[string]::Empty,$Request,[string]::Empty)
    $result = [int]$helper.Enroll(0)
    if ($result -eq 0) { return }
    $message = [string]$helper.ResultMessageText
    switch ($result) {
        2 { throw "Foxpass rejected the request. $message" }
        3 { throw "Foxpass returned a pending response. $message" }
        11 { throw "Foxpass requested another challenge. $message" }
        default { throw "Unexpected SCEP disposition '$result'. $message" }
    }
}

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not (($identity.User -and $identity.User.Value -eq 'S-1-5-18') -or $identity.Name -eq 'NT AUTHORITY\SYSTEM')) {
        throw 'Run this NinjaOne automation as NT AUTHORITY\SYSTEM.'
    }

    $FoxpassScepEndpoint = Resolve-Value $FoxpassScepEndpoint 'FoxpassScepEndpoint' 'foxpassScepEndpoint' -Required
    $endpointMatch = [regex]::Match([Net.WebUtility]::HtmlDecode($FoxpassScepEndpoint),'https://api\.foxpass\.com/scep/[A-Za-z0-9-]+/?','IgnoreCase')
    if ($endpointMatch.Success) { $FoxpassScepEndpoint = $endpointMatch.Value }
    $uri = $null
    if (-not [Uri]::TryCreate($FoxpassScepEndpoint,[UriKind]::Absolute,[ref]$uri) -or $uri.Scheme -ne 'https') { throw 'Invalid Foxpass SCEP HTTPS endpoint.' }
    $FoxpassScepEndpoint = $uri.AbsoluteUri

    $FoxpassScepChallengePass = [Net.WebUtility]::HtmlDecode((Resolve-Value $FoxpassScepChallengePass 'FoxpassScepChallengePass' 'foxpassScepChallengePass' -Required))
    $FoxpassScepChallengePass = ($FoxpassScepChallengePass -replace '[\uFEFF\u200B-\u200D\u2060\x00-\x1F\x7F]','').Trim().Trim([char[]]@([char]34,[char]39))
    if (-not $FoxpassScepChallengePass -or $FoxpassScepChallengePass -match '[^\x20-\x7E]') { throw 'Invalid Foxpass SCEP challenge.' }

    $serial = ConvertTo-Text (Get-CimInstance Win32_BIOS -ErrorAction Stop).SerialNumber
    if (-not $serial -or $serial -in @('Default String','System Serial Number','To Be Filled By O.E.M.','To Be Filled By OEM','Unknown','None','Not Specified','Not Applicable')) { throw "Invalid BIOS serial number: '$serial'." }
    $serial = ($serial -replace '[\uFEFF\u200B-\u200D\u2060\x00-\x1F\x7F]','' -replace '\\','\\' -replace '([,+"<>;=])','\$1').Trim()

    if (-not $CertificateSubject) { $CertificateSubject = Resolve-Value $null 'FoxpassCertificateSubject' 'foxpassCertificateSubject' }
    if (-not $CertificateSubject) { $CertificateSubject = "CN=$serial" }
    else {
        foreach ($token in '{{SerialNumber}}','{{SERIALNUMBER}}','%SERIALNUMBER%','$serialNumber') { $CertificateSubject = $CertificateSubject.Replace($token,$serial) }
        if ($CertificateSubject -notmatch '^\s*[A-Za-z][A-Za-z0-9.]*\s*=') { $CertificateSubject = "CN=$CertificateSubject" }
    }

    if ($raw = Resolve-Value $null 'FoxpassRenewalDays' 'foxpassRenewalDays') {
        $parsed = 0
        if (-not [int]::TryParse($raw,[ref]$parsed) -or $parsed -lt 1 -or $parsed -gt 3650) { throw 'foxpassRenewalDays must be 1-3650.' }
        $RenewalDays = $parsed
    }

    $existing = Get-MatchingCertificates $CertificateSubject | Where-Object { $_.NotBefore -le (Get-Date) -and $_.NotAfter -gt (Get-Date) } | Sort-Object NotAfter -Descending | Select-Object -First 1
    if ($existing -and $existing.NotAfter -gt (Get-Date).AddDays($RenewalDays)) {
        Write-Log "Certificate valid until $($existing.NotAfter.ToString('u')); no renewal needed."
        exit 0
    }

    Write-Log "Enrolling $CertificateSubject."
    $before = @(Get-ChildItem $StorePath | ForEach-Object Thumbprint)
    $request = New-ScepRequest $CertificateSubject $FoxpassScepChallengePass $KeyLength
    Invoke-ScepEnrollment $FoxpassScepEndpoint $request
    $FoxpassScepChallengePass = $null

    $newCertificate = $null
    for ($i=0; $i -lt 5 -and -not $newCertificate; $i++) {
        Start-Sleep 2
        $newCertificate = Get-MatchingCertificates $CertificateSubject | Where-Object { $before -notcontains $_.Thumbprint } | Sort-Object NotAfter -Descending | Select-Object -First 1
    }
    if (-not $newCertificate) { throw 'SCEP completed, but no usable new client-authentication certificate was found.' }

    try { $newCertificate.FriendlyName = $FriendlyName } catch { Write-Log 'Certificate installed; friendly name could not be set.' 'WARN' }
    if ($CleanupSupersededCertificates) {
        Get-MatchingCertificates $CertificateSubject | Where-Object {
            $_.Thumbprint -ne $newCertificate.Thumbprint -and $_.NotAfter -le $newCertificate.NotAfter
        } | ForEach-Object {
            try { Remove-Item (Join-Path $StorePath $_.Thumbprint) -Force } catch { Write-Log "Could not remove old certificate $($_.Thumbprint)." 'WARN' }
        }
    }

    Write-Log "Enrollment complete: $($newCertificate.Thumbprint), expires $($newCertificate.NotAfter.ToString('u'))."
    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    exit 1
}
finally {
    $FoxpassScepChallengePass = $null
    $request = $null
}