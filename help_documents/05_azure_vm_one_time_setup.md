# Azure VM — One-Time Setup

> **Purpose:** Provision a new Azure VM for MCMC computing and connect it to Cursor IDE.  
> **When to use:** You are starting from scratch — no VM exists yet.  
> **After this:** Use the [Daily Driver](05b_azure_vm_daily_driver.md) for day-to-day work.

---

## Your Setup Reference

| Component | Value |
|-----------|-------|
| Subscription | tr-analytics |
| Resource Group | rg-bayesian-elasticity |
| VM Name | vm-mcmc-bayesian |
| Region | East US 2 |
| VM Size | Standard D16s v3 (16 vCPUs, 64 GB RAM) |
| OS | Ubuntu 24.04 LTS |
| SSH Key | vm-mcmc-bayesian_key.pem |
| SSH Config Alias | azure-mcmc |
| Auto-shutdown | 11:00 PM Mountain Time |

---

## Step 1: Request CPU Quota

Azure limits CPU cores per VM family per region. You need ≥16 vCPUs for D16s.

1. Portal → **Subscriptions** → your subscription → **Usage + quotas**
2. Filter: **Provider = Compute**, **Region = East US 2**
3. Search **"DSv3"** (or DSv5)
4. Click the **pencil icon** → set new limit to `16` (or `32`)
5. Justification: *"Bayesian MCMC simulations — sustained CPU-bound workloads"*
6. Submit — usually auto-approves in minutes
7. Verify: same page should now show the increased limit

> ⚠️ **Quota is per-region and per-VM-family.** DSv3 ≠ DSv5 ≠ DDSv5. Match exactly.

---

## Step 2: Create the VM

1. Portal → **Virtual machines** → **+ Create** → **Azure virtual machine**

2. **Basics tab:**

| Setting | Value |
|---------|-------|
| Resource group | `rg-bayesian-elasticity` (create new) |
| VM name | `vm-mcmc-bayesian` |
| Region | East US 2 (must match quota) |
| Image | Ubuntu Server 24.04 LTS - x64 Gen2 |
| Size | D16s_v3 (16 vCPUs, 64 GB) |
| Auth type | SSH public key |
| Username | `azureuser` |
| SSH key source | Generate new key pair |
| Key pair name | `vm-mcmc-bayesian_key` |

3. **Disks tab:** 64 GiB Premium SSD, "Delete with VM" checked

4. **Networking tab:** Defaults + allow SSH (port 22)

5. **Management tab:** Auto-shutdown **ON** → 11:00 PM → your timezone → email notification ON

6. **Review + Create** → **Create**

7. **⚡ CRITICAL:** Download the `.pem` key file when prompted. You cannot download it again.

8. Save it to: `C:\Users\<username>\.ssh\vm-mcmc-bayesian_key.pem`

9. Note the **Public IP** from the VM overview page

---

## Step 3: Connect Cursor IDE

### 3a. Install Remote-SSH extension

Cursor → `Ctrl+Shift+X` → search **"Remote - SSH"** → Install (by Anysphere)

### 3b. Place your SSH key

Copy the `.pem` to `C:\Users\<username>\.ssh\` (Windows) or `~/.ssh/` (Mac).

Mac/Linux only:
```bash
chmod 400 ~/.ssh/vm-mcmc-bayesian_key.pem
```

### 3c. Configure SSH

1. `Ctrl+Shift+P` → **Remote-SSH: Connect to Host** → **Add New SSH Host**
2. Enter:
   ```
   ssh -i C:\Users\<username>\.ssh\vm-mcmc-bayesian_key.pem azureuser@<PUBLIC_IP>
   ```
3. Save to the first config file option

4. Open your SSH config (`C:\Users\<username>\.ssh\config`) and verify it looks like:
   ```
   Host azure-mcmc
       HostName <PUBLIC_IP>
       User azureuser
       IdentityFile C:\Users\<username>\.ssh\vm-mcmc-bayesian_key.pem
   ```

### 3d. Connect

1. `Ctrl+Shift+P` → **Remote-SSH: Connect to Host** → select **azure-mcmc**
2. Platform = Linux → type **yes** if prompted
3. Wait 1–2 min for server-side install
4. You'll see **"SSH: azure-mcmc"** in the bottom-left corner

---

## Step 4: Set Up the VM Environment

Open a terminal in Cursor (`Ctrl+J`) and run:

```bash
# Install system packages
sudo apt update && sudo apt install -y python3-pip python3-venv build-essential g++ tmux

# Clone your repo
cd /home/azureuser
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### Set up Git SSH (so you can push from the VM)

```bash
# Generate key
ssh-keygen -t ed25519 -C "azure-vm" -f ~/.ssh/id_ed25519 -N ""

# Copy this output and add it as an SSH key in GitHub → Settings → SSH and GPG keys
cat ~/.ssh/id_ed25519.pub

# Register GitHub's host key
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts

# Switch remote to SSH
cd /home/azureuser/<your-repo>
git remote set-url origin git@github.com:<your-org>/<your-repo>.git

# Test
ssh -T git@github.com
```

### Set Python interpreter in Cursor

1. `Ctrl+Shift+X` → Install **Python extension** on the remote side
2. `Ctrl+Shift+P` → **Python: Select Interpreter** → select `.venv/bin/python`
3. **File → Open Folder** → `/home/azureuser/<your-repo>`

---

## Step 5 (Optional): Make Your Life Easier

### Static IP (avoid IP changes on restart)

VM → **Networking** → click the public IP → change to **Static** (~$3.65/month)

### Cost alerts

Portal → **Cost Management** → **Budgets** → create $100/month budget with alerts at 50%, 80%, 100%

### Upload data files

From your **local machine** (PowerShell):
```powershell
scp -i C:/Users/<username>/.ssh/vm-mcmc-bayesian_key.pem `
  C:/path/to/bjs.csv `
  C:/path/to/sams.csv `
  azureuser@<PUBLIC_IP>:/home/azureuser/<your-repo>/data/
```

---

## Cost Reference

| VM Size | vCPUs | RAM | $/Hour | $/Month (24/7) |
|---------|-------|-----|--------|----------------|
| D16s_v3 | 16 | 64 GB | ~$0.73 | ~$560 |
| D32s_v3 | 32 | 128 GB | ~$1.46 | ~$1,121 |

**You only pay when the VM is running.** Deallocate when done. With good habits, expect <$50/month.

---

*You're done. Move to the [Daily Driver](05b_azure_vm_daily_driver.md) for your everyday workflow.*
