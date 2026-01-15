# Skylynx ERP API

## Auth + Tenant Users Examples (PowerShell)

Use `curl.exe` (not the PowerShell alias) for clean JSON requests.

```powershell
$base = "http://localhost:8000"

# Subscriber register
curl.exe -X POST "$base/subscriber/register" `
  -H "Content-Type: application/json" `
  -d "{`"company_name`":`"Acme Co`",`"first_name`":`"Ava`",`"last_name`":`"Ng`",`"email`":`"ava@acme.co`",`"password`":`"Password123!`"}"

# Subscriber login
curl.exe -X POST "$base/subscriber/login" `
  -H "Content-Type: application/json" `
  -d "{`"email`":`"ava@acme.co`",`"password`":`"Password123!`"}"

# Use the access token from login/register
$token = "<access_token>"

# Create tenant user (returns temp_password once)
curl.exe -X POST "$base/tenant/users" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d "{`"first_name`":`"Jamie`",`"last_name`":`"Lee`",`"email`":`"jamie@acme.co`"}"

# List tenant users
curl.exe -X GET "$base/tenant/users" `
  -H "Authorization: Bearer $token"

# Reset tenant user password (returns temp_password once)
$userId = "<user_id>"
curl.exe -X POST "$base/tenant/users/$userId/reset-password" `
  -H "Authorization: Bearer $token"
```

## Workspaces + Profile + Logo Examples (PowerShell)

```powershell
# List workspaces
curl.exe -X GET "$base/workspaces" `
  -H "Authorization: Bearer $token"

# Create a new workspace
curl.exe -X POST "$base/workspaces" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d "{`"company_name`":`"Orbit Labs`"}"

# Select a workspace (returns a new token)
$tenantId = "<tenant_id>"
curl.exe -X POST "$base/workspaces/select" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d "{`"tenant_id`":`"$tenantId`"}"

# Get profile
curl.exe -X GET "$base/profile" `
  -H "Authorization: Bearer $token"

# Update profile
curl.exe -X PUT "$base/profile" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d "{`"first_name`":`"Ava`",`"last_name`":`"Ng`",`"email`":`"ava@acme.co`"}"

# Change password
curl.exe -X POST "$base/profile/change-password" `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d "{`"old_password`":`"Password123!`",`"new_password`":`"NewPassword123!`",`"new_password_confirm`":`"NewPassword123!`"}"

# Upload company logo
curl.exe -X POST "$base/settings/company/logo" `
  -H "Authorization: Bearer $token" `
  -F "file=@C:\\path\\to\\logo.png"

# Download company logo
curl.exe -X GET "$base/settings/company/logo" `
  -H "Authorization: Bearer $token" `
  -o "logo.png"

# List employees without linked users
curl.exe -X GET "$base/employees/unlinked-users" `
  -H "Authorization: Bearer $token"
```
