# Creates one Cognito user per demo collection point (username = collector ID).
# Usage (PowerShell, from the repo root):
#   .\infra\create_collectors.ps1 -UserPoolId ap-south-1_XXXXXXXXX -Password "YourStrongPass1"
param(
  [Parameter(Mandatory = $true)] [string] $UserPoolId,
  [Parameter(Mandatory = $true)] [string] $Password,
  [string] $Region = "ap-south-1"
)
$ids = "demo-dwarka", "demo-rohini", "demo-saket", "demo-noida", "demo-gurugram"
foreach ($id in $ids) {
  aws cognito-idp admin-create-user --region $Region --user-pool-id $UserPoolId --username $id --message-action SUPPRESS | Out-Null
  aws cognito-idp admin-set-user-password --region $Region --user-pool-id $UserPoolId --username $id --password $Password --permanent
  Write-Host "ready: $id"
}
