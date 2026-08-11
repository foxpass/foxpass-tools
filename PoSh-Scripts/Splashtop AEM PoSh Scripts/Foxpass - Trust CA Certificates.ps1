$ErrorActionPreference = 'Stop'

$Certificates = @(
    @'
-----BEGIN CERTIFICATE-----
INSERT_CLIENT_CA_PEM_HERE
-----END CERTIFICATE-----
'@,
    @'
-----BEGIN CERTIFICATE-----
INSERT_SERVER_CA_PEM_HERE
-----END CERTIFICATE-----
'@
)

try {
    $admin = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run as SYSTEM or Administrator.' }

    $installed = 0
    $existing = 0

    foreach ($pem in $Certificates) {
        $base64 = ($pem -replace '-----BEGIN CERTIFICATE-----|-----END CERTIFICATE-----|\s','')
        $cert = New-Object Security.Cryptography.X509Certificates.X509Certificate2 -ArgumentList @(,[Convert]::FromBase64String($base64))

        try {
            $basicConstraints = $cert.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.19' } | Select-Object -First 1
            if (-not $basicConstraints) { throw "Certificate '$($cert.Subject)' is not marked as a CA." }

            $constraint = New-Object Security.Cryptography.X509Certificates.X509BasicConstraintsExtension
            $constraint.CopyFrom($basicConstraints)
            if (-not $constraint.CertificateAuthority) { throw "Certificate '$($cert.Subject)' is not marked as a CA." }

            $storeName = if ($cert.Subject -eq $cert.Issuer) { 'Root' } else { 'CA' }
            $store = New-Object Security.Cryptography.X509Certificates.X509Store($storeName,'LocalMachine')
            try {
                $store.Open('ReadWrite')
                if ($store.Certificates.Find('FindByThumbprint',$cert.Thumbprint,$false).Count) {
                    Write-Host "Already installed: $($cert.Subject)"
                    $existing++
                } else {
                    $store.Add($cert)
                    Write-Host "Installed: $($cert.Subject) -> LocalMachine\$storeName"
                    $installed++
                }
            } finally { $store.Close() }
        } finally { $cert.Dispose() }
    }

    Write-Host "Completed. Installed: $installed; already present: $existing."
    exit 0
} catch {
    Write-Error $_.Exception.Message
    exit 1
}