# Copyright (c) 2015-present, Foxpass, Inc.
# All rights reserved.
#
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Allow the script to execute inline with parameter
[CmdletBinding()]
param (
  [string]$ApiUrl = "https://api.foxpass.com",
  [Parameter(Mandatory = $true)][string]$Email
)

# Main function
function Main() {
<#
  .SYNOPSIS
  A tool to quickly generate and upload ssh key to Foxpass

  .DESCRIPTION
  Generate an SSH key based on a pre-defined ssh key parameter and automatically uploading it to Foxpass.

  .INPUTS
  - Email - Foxpass email account
    E.g -Email bryan@foxpass.com
  - ApiUrl - Foxpass API endpoint
    E.g -ApiUrl https://api.foxpass.com

  .EXAMPLE
  .\foxpass-keygen.ps1

PS .\foxpass-keygen.ps1
Email: bryan@foxpass.com
Password: : **********

Generating SSH key...
Enter passphrase (empty for no passphrase):
Enter same passphrase again:
Uploading SSH key to Foxpass...
status data
------ ----
ok     {@{name=foxpass-ssh-20201111-10176.pub; signature=4d7d2c33ffc...; key=ssh-rsa AAAAB3NzaC1yc...
ok

  .EXAMPLE
.\foxpass-keygen.ps1 -Email bryan@foxpass.com -ApiUrl https://api.foxpass.com

PS .\foxpass-keygen.ps1 -Email bryan@foxpass.com -ApiUrl https://api.foxpass.com
Password: : **********

Generating SSH key...
Enter passphrase (empty for no passphrase):
Enter same passphrase again:
Uploading SSH key to Foxpass...
status data
------ ----
ok     {@{name=foxpass-ssh-20201111-10176.pub; signature=4d7d2c33ffc...; key=ssh-rsa AAAAB3NzaC1yc...
ok
#>

  param (
    [string]$ApiUrl,
    [Parameter(Mandatory = $true)][string]$Email,
    [SecureString]$Password = $( Read-Host -AsSecureString "Password: " )
  )

  Request-API $ApiUrl $Email $Password '/v1/my/sshkeys/'
  $Filename = Add-SSHKey $Email
  Add-SSHKeyFoxpass $ApiUrl $Email $Password $Filename 'v1/my/sshkeys/'
}

# Generate an SSH key and store it in the current user's $Home/.ssh directory
function Add-SSHKey() {
  param (
    [string]$Email
  )

  Write-Host "Generating SSH key..."

  $GenerateSSH = @(
    $DateStr = (Get-Date).ToString("yyyyMMdd-Hms")
    $Filename = "$Home\.ssh\foxpass-ssh-$DateStr"
    ssh-keygen.exe -t rsa -b 4096 -C $Email -f $Filename
  )

  return $Filename
}

# Upload the SSH key to Foxpass
# Prepares the data before uploading it to Foxpass
function Add-SSHKeyFoxpass() {
  param (
    [string]$ApiUrl,
    [string]$Email,
    [SecureString]$Password,
    [string]$Filename,
    [string]$Path
  )

  Write-Host "Uploading SSH key to Foxpass..."

  $RawContents = Get-Content -Raw "$Filename.pub"
  $RawContents = $RawContents -replace "`t|`n|`r", "" #Remove crlf
  $File = Split-Path "$Filename.pub" -leaf

  $PostParams = @{
    name = $File;
    key  = $RawContents;
  };
  $PostJson = $PostParams | ConvertTo-Json;
  Request-API $ApiUrl $Email $Password '/v1/my/sshkeys/' $PostJson
}

# Generic API request to Foxpass API
# Both handles the authentication and uploading of the SSH key to foxpass
function Request-API() {
  param (
    [string]$ApiUrl,
    [string]$Email,
    [SecureString]$Password,
    [string]$Path,
    [string]$PostBody
  )

  $FinalURL = $ApiUrl + $Path

  $BStr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password);
  $PlainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BStr);

  $CombineCredentials = "$($Email):$($PlainPassword)"
  $Credentials = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes($CombineCredentials))
  $Headers = @{ Authorization = "Basic $Credentials" }

  try {
    if ($PostBody) {
      Invoke-RestMethod -Method Post -Uri $FinalURL -Headers $Headers -Body $PostBody -ContentType "application/json"
    }
    else {
      Invoke-RestMethod -Method Get -Uri $FinalURL -Headers $Headers -ContentType "application/json"
    }
  }
  catch {
    Write-Host "StatusCode:" $_.Exception.Response.StatusCode.value__
    Write-Host "StatusDescription:" $_.Exception.Response.StatusDescription
    exit
  }

}

# Calling the main function
Main -ApiUrl $ApiUrl -Email $Email
