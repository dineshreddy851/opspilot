# Start Here

This is the first session checklist for building OpsPilot on AWS.

## Current computer status

Verified on June 4, 2026:

| Tool | Status |
| --- | --- |
| Git | Installed: `2.51.0` |
| Python | Installed: `3.11.9` |
| Visual Studio Code | Installed |
| AWS CLI | Not installed |
| Terraform | Not installed |
| Git repository | Not initialized |

## Complete these actions first

### 1. Secure your AWS account

In the AWS console:

1. Enable root-user MFA.
2. Confirm that root access keys do not exist.
3. Create an AWS Budget with email alerts.
4. Enable IAM Identity Center.
5. Create your daily-use Identity Center user and enable MFA.

Do not continue until these are complete.

### 2. Install AWS CLI

Open PowerShell and run:

```powershell
winget install --exact --id Amazon.AWSCLI `
  --accept-package-agreements `
  --accept-source-agreements
```

Close and reopen PowerShell, then verify:

```powershell
aws --version
```

### 3. Install Terraform

```powershell
winget install --exact --id Hashicorp.Terraform `
  --accept-package-agreements `
  --accept-source-agreements
```

Close and reopen PowerShell, then verify:

```powershell
terraform -version
```

### 4. Configure temporary AWS credentials

```powershell
aws configure sso --profile opspilot-dev
aws sso login --profile opspilot-dev
aws sts get-caller-identity --profile opspilot-dev
```

Set the profile and Region for the current PowerShell session:

```powershell
$env:AWS_PROFILE = "opspilot-dev"
$env:AWS_REGION = "us-east-1"
aws configure set region us-east-1 --profile opspilot-dev
aws sts get-caller-identity
```

The final command must return your AWS account and assumed role.

### 5. Initialize the project

```powershell
cd C:\Users\DineshReddySirigiri\Documents\Codex\2026-06-04\i-would-like-to-create-one\outputs\opspilot
git init
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --editable .
python -m unittest discover -s tests -v
```

Expected test result:

```text
Ran 9 tests
OK
```

### 6. Create the first commit

```powershell
git add .
git commit -m "Create safety-first OpsPilot starter"
```

If Git asks for your name and email:

```powershell
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
git commit -m "Create safety-first OpsPilot starter"
```

## Stop point

Stop after the following all succeed:

```powershell
aws --version
terraform -version
aws sts get-caller-identity
python -m unittest discover -s tests -v
git status
```

After that, continue with **Checkpoint 3** in
[Build OpsPilot on AWS From Scratch](FROM_SCRATCH_AWS_GUIDE.md).

