# Build OpsPilot on AWS Using Linux

This guide covers the Linux-specific setup and commands for the OpsPilot AWS
project. Follow it together with
[Build OpsPilot on AWS From Scratch](FROM_SCRATCH_AWS_GUIDE.md).

Ubuntu 24.04 LTS or a recent Ubuntu LTS release is the recommended beginner
environment. Debian, Fedora, and Amazon Linux commands are also included.

## Recommended setup

You can use any of these:

- Ubuntu installed on a computer
- Ubuntu in a virtual machine
- Ubuntu through WSL 2 on Windows
- A Linux cloud development machine

Do not use an EC2 instance as your main development computer at first. It adds
cost, networking, and credential-management work before the application is
ready.

## Important Linux differences

| Windows command | Linux equivalent |
| --- | --- |
| `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| `$env:AWS_PROFILE = "opspilot-dev"` | `export AWS_PROFILE=opspilot-dev` |
| `$env:AWS_REGION = "us-east-1"` | `export AWS_REGION=us-east-1` |
| `where.exe aws` | `which aws` |
| PowerShell `Invoke-RestMethod` | `curl` |
| Backtick line continuation | Backslash `\` |

Linux paths and commands are case-sensitive.

---

# Linux Checkpoint 1: Identify your distribution

Open a terminal and run:

```bash
cat /etc/os-release
uname -m
```

Common architecture results:

```text
x86_64   Intel or AMD 64-bit
aarch64  ARM 64-bit
```

You need the architecture value when installing AWS CLI.

---

# Linux Checkpoint 2: Install base development tools

Use only the section for your Linux distribution.

## Ubuntu or Debian

```bash
sudo apt update
sudo apt install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  curl \
  unzip \
  wget \
  gnupg \
  lsb-release \
  ca-certificates
```

## Fedora

```bash
sudo dnf install -y \
  git \
  python3 \
  python3-pip \
  curl \
  unzip \
  wget \
  gnupg2
```

## Amazon Linux 2023

```bash
sudo dnf update -y
sudo dnf install -y \
  git \
  python3 \
  python3-pip \
  curl \
  unzip \
  wget \
  gnupg2 \
  yum-utils \
  shadow-utils
```

## Verify

```bash
git --version
python3 --version
curl --version
unzip -v
```

Every command must succeed.

---

# Linux Checkpoint 3: Install AWS CLI version 2

AWS provides separate installers for x86-64 and ARM 64-bit Linux.

## For x86-64

Run this when `uname -m` returns `x86_64`:

```bash
mkdir -p /tmp/opspilot-tools
cd /tmp/opspilot-tools
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
  -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

## For ARM 64-bit

Run this when `uname -m` returns `aarch64`:

```bash
mkdir -p /tmp/opspilot-tools
cd /tmp/opspilot-tools
curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" \
  -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

## Verify

```bash
which aws
aws --version
```

The version must begin with `aws-cli/2`.

If Amazon Linux already has an older `yum` AWS CLI package, follow the official
AWS documentation to remove it before installing AWS CLI version 2.

---

# Linux Checkpoint 4: Install Terraform

Use only the section for your Linux distribution.

## Ubuntu or Debian

```bash
wget -O - https://apt.releases.hashicorp.com/gpg \
  | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(grep -oP '(?<=UBUNTU_CODENAME=).*' /etc/os-release || lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/hashicorp.list

sudo apt update
sudo apt install -y terraform
```

## Fedora

```bash
wget -O- https://rpm.releases.hashicorp.com/fedora/hashicorp.repo \
  | sudo tee /etc/yum.repos.d/hashicorp.repo
sudo dnf install -y terraform
```

## Amazon Linux

```bash
sudo yum-config-manager \
  --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo
sudo yum install -y terraform
```

## Verify

```bash
which terraform
terraform -version
```

---

# Linux Checkpoint 5: Configure Git

Set the identity used in your commits:

```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
git config --global init.defaultBranch main
```

Verify:

```bash
git config --global --list
```

Do not put AWS credentials in Git configuration.

---

# Linux Checkpoint 6: Configure AWS authentication

First complete the AWS account-security steps in the main guide:

1. Enable root-user MFA.
2. Create an AWS Budget.
3. Enable IAM Identity Center.
4. Create your daily-use user and enable MFA.

Then configure AWS CLI:

```bash
aws configure sso --profile opspilot-dev
aws sso login --profile opspilot-dev
aws configure set region us-east-1 --profile opspilot-dev
aws sts get-caller-identity --profile opspilot-dev
```

Set the profile and Region in the current terminal:

```bash
export AWS_PROFILE=opspilot-dev
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
```

Verify:

```bash
aws sts get-caller-identity
aws configure get region
```

The identity command must return your account and assumed role.

## Optional shell convenience

You can add only the non-secret profile and Region settings to your shell
configuration:

```bash
printf '\nexport AWS_PROFILE=opspilot-dev\nexport AWS_REGION=us-east-1\nexport AWS_DEFAULT_REGION=us-east-1\n' \
  >> ~/.bashrc
source ~/.bashrc
```

Do not add access keys, tokens, or passwords to `.bashrc`.

---

# Linux Checkpoint 7: Put the project on Linux

Choose one method.

## Method A: Clone from GitHub

This is the recommended approach after you publish the repository:

```bash
mkdir -p ~/projects
cd ~/projects
git clone <your-github-repository-url> opspilot
cd opspilot
```

## Method B: Create a fresh local project folder

```bash
mkdir -p ~/projects/opspilot
cd ~/projects/opspilot
git init
```

Then create or move the project files into that directory.

Avoid developing inside `/root`, `/usr/local`, or another system directory.

---

# Linux Checkpoint 8: Create the Python environment

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --editable .
python -m unittest discover -s tests -v
```

Expected result:

```text
Ran 9 tests
OK
```

The terminal prompt normally displays `(.venv)` while the virtual environment
is active.

To leave the environment:

```bash
deactivate
```

To return later:

```bash
cd ~/projects/opspilot
source .venv/bin/activate
```

---

# Linux Checkpoint 9: Test the local OpsPilot CLI

```bash
opspilot tools
opspilot ask "show docker container status" --plan-only
opspilot ask "delete everything" --plan-only
```

Expected behavior:

- The first request shows an approved read-only plan.
- The destructive request is refused.

Create the first commit:

```bash
git status
git add .
git commit -m "Create safety-first OpsPilot starter"
```

---

# Linux Checkpoint 10: Build and deploy the AWS MVP

Continue with Checkpoint 3 and Checkpoint 4 in the
[main from-scratch guide](FROM_SCRATCH_AWS_GUIDE.md).

The application and Terraform files are identical on Windows and Linux. Use
the Linux commands below when testing and deploying.

## Validate Python

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Validate Terraform

```bash
cd infra/dev
terraform fmt -recursive
terraform init
terraform validate
terraform plan -out=tfplan
```

Read the plan before applying:

```bash
terraform show tfplan
terraform apply tfplan
```

Capture Terraform outputs:

```bash
API_URL="$(terraform output -raw api_url)"
AUDIT_TABLE="$(terraform output -raw audit_table_name)"
```

## Test the API with curl

Safe request:

```bash
curl --fail-with-body \
  --request POST \
  --header "Content-Type: application/json" \
  --data '{"request":"show cloudwatch alarms"}' \
  "${API_URL}/requests"
```

Destructive request:

```bash
curl --fail-with-body \
  --request POST \
  --header "Content-Type: application/json" \
  --data '{"request":"delete everything"}' \
  "${API_URL}/requests"
```

The destructive request must be refused.

Inspect audit events:

```bash
aws dynamodb scan --table-name "$AUDIT_TABLE"
```

Inspect Lambda logs:

```bash
aws logs tail /aws/lambda/opspilot-api-dev --since 10m
```

Confirm Terraform has no unexpected changes:

```bash
terraform plan
```

---

# Daily Linux workflow

Start each session:

```bash
cd ~/projects/opspilot
source .venv/bin/activate
export AWS_PROFILE=opspilot-dev
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
aws sso login --profile opspilot-dev
aws sts get-caller-identity
python -m unittest discover -s tests -v
```

Before deploying:

```bash
cd infra/dev
terraform fmt -recursive
terraform validate
terraform plan
```

After completing a checkpoint:

```bash
git status
git add .
git commit -m "Describe the completed checkpoint"
git push
```

---

# Linux permissions and security

- Run application and Terraform commands as your normal user.
- Use `sudo` only for installing system packages.
- Do not run Terraform with `sudo`.
- Do not run the application with `sudo`.
- Do not store AWS access keys in the repository.
- Keep `.aws`, `.ssh`, `.gnupg`, and shell history private.
- Use IAM Identity Center temporary credentials.
- Inspect scripts before executing them.

Check that secret files are not staged:

```bash
git status
git diff --cached
```

The project `.gitignore` should include:

```text
.venv/
.terraform/
*.tfstate
*.tfstate.*
tfplan
.env
```

---

# Cleanup

When you no longer need the development environment:

```bash
cd ~/projects/opspilot/infra/dev
terraform plan -destroy
terraform destroy
```

Verify the remaining AWS resources in the console. Terraform state, audit logs,
CloudTrail logs, or deliberately retained resources may remain depending on
your configuration.

Do not delete Terraform state before destroying the infrastructure it manages.

---

# First Linux session checklist

Complete these commands before building AWS application code:

```bash
cat /etc/os-release
uname -m
git --version
python3 --version
aws --version
terraform -version
aws sts get-caller-identity --profile opspilot-dev
```

Then, from the project:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
git status
```

After all commands succeed, begin Checkpoint 3 in the main from-scratch guide.

## Official references

- [Install AWS CLI on Linux](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [Configure AWS CLI with IAM Identity Center](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)
- [Install Terraform on Linux](https://developer.hashicorp.com/terraform/install)
- [Set up Git](https://docs.github.com/en/get-started/git-basics/set-up-git)

