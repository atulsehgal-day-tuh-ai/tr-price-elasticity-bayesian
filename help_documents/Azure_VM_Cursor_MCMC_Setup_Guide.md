# Complete Guide: Setting Up an Azure VM for MCMC Computing with Cursor IDE

## Why Do We Need This?

Running Bayesian MCMC (Markov Chain Monte Carlo) algorithms — such as PyMC, Stan, or NumPyro models — is extremely CPU-intensive. Each MCMC sampling chain needs a dedicated CPU core, and a typical analysis runs 4–8 chains in parallel for hours.

Your local laptop might have 4–8 cores shared with your OS, browser, and other apps. An Azure VM gives you **dedicated compute power** (16+ cores) in the cloud, so your models run faster and your laptop stays free.

By connecting **Cursor IDE** (an AI-powered code editor) to the VM via SSH, you get the best of both worlds: a familiar local editing experience with AI code assistance, while all code execution happens on the powerful remote machine.

---

## Architecture Overview

```
┌─────────────────────┐         SSH          ┌──────────────────────────┐
│   Your Local PC     │ ◄──────────────────► │   Azure VM (Ubuntu)      │
│                     │                       │                          │
│   Cursor IDE        │   You edit here,      │   16 vCPUs, 64 GB RAM   │
│   (Windows/Mac)     │   code runs there ──► │   Python + PyMC          │
│                     │                       │   Your MCMC models       │
└─────────────────────┘                       └──────────────────────────┘
```

---

## Prerequisites

- An **Azure account** with an active subscription
- **Cursor IDE** installed on your local machine ([cursor.com](https://cursor.com))
- Basic familiarity with terminal/command line

---

## Part 1: Azure Subscription Quota Setup

### Why Quotas Matter

Azure limits how many CPU cores you can use per VM family in each region. By default, many families are set to 0 or 10 vCPUs. If you want a 16-core VM, you need at least 16 vCPUs of quota for that VM family in your chosen region.

### Step 1.1: Check Your Current Quota

1. Go to [portal.azure.com](https://portal.azure.com)
2. In the top search bar, type **"Subscriptions"** and select your subscription
3. In the left sidebar, click **"Usage + quotas"** (under **Settings**)
4. Set filters at the top:
   - **Provider:** Compute
   - **Region:** Choose your preferred region (e.g., West US 3, East US 2)
5. In the search box within the quota list, type **"DSv5"** (or **"DSv3"** for older generation)
6. Find the row **"Standard DSv5 Family vCPUs"** (or DSv3)
7. Check the **Current Usage** column — it shows something like `0 of 10` meaning you're using 0 out of a limit of 10 vCPUs

### Step 1.2: Request a Quota Increase

If your limit is less than 16 (or 32 for a D32s machine):

1. Click the **pencil icon** (edit) on the right side of the quota row
2. Enter the **new limit**: `16` (for D16s) or `32` (for D32s)
3. In the justification field, enter something like:

> Need 16 vCPUs for Standard DSv5 family to run Bayesian statistical modeling and MCMC simulations for analytics. The DSv5 family is preferred for sustained CPU-bound statistical workloads. Requesting capacity in [your region] due to proximity to operations.

4. Submit the request
5. Standard compute families in US regions often **auto-approve within minutes**. You'll get an email notification.

### Step 1.3: Verify the Quota Was Applied

1. Go back to **Usage + quotas**
2. Filter to the **same region** you requested
3. Find the same VM family row
4. Confirm the limit has increased (e.g., `0 of 16` or `0 of 32`)

### Common Pitfalls

- **Wrong region:** Quotas are per-region. If you requested for East US 2 but try to create a VM in West US 3, the quota won't apply.
- **Wrong VM family:** DSv3, DSv5, Dv5, DDSv5 are all **different families**. Make sure you request for the exact family you plan to use.
- **Support ticket vs inline request:** The pencil icon gives a fast inline request. The "New Quota Request" button sometimes routes through the slower support ticket system.

---

## Part 2: Create the Virtual Machine

### Step 2.1: Start VM Creation

1. Go to [portal.azure.com](https://portal.azure.com)
2. Search **"Virtual machines"** → click **"+ Create"** → **"Azure virtual machine"**

### Step 2.2: Basics Tab

| Setting | Value |
|---------|-------|
| **Subscription** | Your subscription (e.g., `tr-analytics`) |
| **Resource group** | Click "Create new" → name it descriptively (e.g., `rg-bayesian-elasticity`) |
| **Virtual machine name** | e.g., `vm-mcmc-bayesian` |
| **Region** | Must match where your quota was approved (e.g., `(US) East US 2`) |
| **Availability options** | No infrastructure redundancy required |
| **Security type** | Standard |
| **Image** | Ubuntu Server 24.04 LTS - x64 Gen2 |
| **VM architecture** | x64 |
| **Size** | Click "See all sizes" → search for `D16s_v3` (16 vCPUs, 64 GB RAM) or `D32s_v3` (32 vCPUs, 128 GB RAM) |
| **Authentication type** | SSH public key |
| **Username** | `azureuser` |
| **SSH public key source** | Generate new key pair |
| **SSH Key Type** | RSA SSH Format (widest compatibility) |
| **Key pair name** | e.g., `vm-mcmc-bayesian_key` |

### Step 2.3: Disks Tab

| Setting | Value |
|---------|-------|
| **OS disk size** | 64 GiB is fine for most workloads; use 128 GiB if you have large datasets |
| **OS disk type** | Premium SSD (locally-redundant storage) |
| **Delete with VM** | Checked |

### Step 2.4: Networking Tab

| Setting | Value |
|---------|-------|
| **Virtual network** | Leave default (auto-creates new) |
| **Subnet** | Leave default |
| **Public IP** | Leave default (auto-creates new) |
| **NIC network security group** | Basic |
| **Public inbound ports** | Allow selected ports |
| **Select inbound ports** | SSH (22) |

> **Note:** Azure will show a warning that SSH port is open to the internet. This is fine for a dev/analytics VM. For extra security, you can restrict the source IP to your home/office IP.

### Step 2.5: Management Tab

| Setting | Value |
|---------|-------|
| **Auto-shutdown** | **On** ← Very important to avoid surprise bills |
| **Shutdown time** | e.g., 11:00 PM |
| **Time zone** | Your local timezone (e.g., Mountain Time) |
| **Email notification** | Turn on, enter your email |

### Step 2.6: Deploy

1. Skip the **Monitoring**, **Advanced**, and **Tags** tabs — defaults are fine
2. Click **Review + Create**
3. Review the summary, then click **Create**
4. **CRITICAL:** When prompted, **download the `.pem` private key file immediately**. Save it somewhere safe (e.g., `C:\Users\<username>\.ssh\vm-mcmc-bayesian_key.pem`). You will NOT be able to download it again.
5. Wait 1–2 minutes for deployment to complete
6. Click **"Go to resource"**
7. Note the **Public IP address** from the VM overview page (e.g., `20.94.79.51`)

### Understanding VM Costs

| VM Size | vCPUs | RAM | Approx. Cost/Hour | Approx. Cost/Month (24/7) |
|---------|-------|-----|-------------------|--------------------------|
| D16s_v3 | 16 | 64 GB | ~$0.73 | ~$560 |
| D32s_v3 | 32 | 128 GB | ~$1.46 | ~$1,121 |

**You only pay when the VM is running.** Deallocating stops all compute charges. With auto-shutdown and good habits, actual monthly costs can be under $50.

---

## Part 3: Connect Cursor IDE to the VM

### Step 3.1: Install Remote-SSH Extension in Cursor

1. Open **Cursor** on your local machine
2. Press `Ctrl+Shift+X` (Windows) or `Cmd+Shift+X` (Mac) to open Extensions
3. Search for **"Remote - SSH"**
4. Install the one by **Anysphere** (Cursor's publisher) — it's the top result
5. If it says "Restart Extensions", click that button

### Step 3.2: Place Your SSH Key

Copy the downloaded `.pem` file to your SSH directory:

**Windows:**
```
C:\Users\<your-username>\.ssh\vm-mcmc-bayesian_key.pem
```

**Mac:**
```
~/.ssh/vm-mcmc-bayesian_key.pem
```

On Mac/Linux, set correct permissions:
```bash
chmod 400 ~/.ssh/vm-mcmc-bayesian_key.pem
```

### Step 3.3: Configure the SSH Connection

1. In Cursor, press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type **"Remote-SSH: Connect to Host"** → select it
3. Click **"Add New SSH Host"**
4. Enter the connection string:

**Windows:**
```
ssh -i C:\Users\<your-username>\.ssh\vm-mcmc-bayesian_key.pem azureuser@<PUBLIC_IP>
```

**Mac:**
```
ssh -i ~/.ssh/vm-mcmc-bayesian_key.pem azureuser@<PUBLIC_IP>
```

Replace `<your-username>` with your actual username and `<PUBLIC_IP>` with your VM's public IP.

5. When asked which config file to save to, pick the first option (usually `~/.ssh/config`)

### Step 3.4: Edit the SSH Config (Recommended)

The auto-generated config may be on a single line. Open your SSH config file and format it properly:

**Windows:** `C:\Users\<your-username>\.ssh\config`
**Mac:** `~/.ssh/config`

```
Host azure-mcmc
    HostName <PUBLIC_IP>
    User azureuser
    IdentityFile C:\Users\<your-username>\.ssh\vm-mcmc-bayesian_key.pem
```

Replace `<PUBLIC_IP>` and `<your-username>` with your actual values. The `Host azure-mcmc` is a friendly alias — you can name it anything.

### Step 3.5: Connect

1. `Ctrl+Shift+P` → **"Remote-SSH: Connect to Host"**
2. Select **azure-mcmc** (your alias)
3. If asked for the platform, select **Linux**
4. If asked "Are you sure you want to continue connecting?", type **yes**
5. Wait 1–2 minutes for Cursor to install its server-side components on the VM
6. Once connected, you'll see **"SSH: azure-mcmc"** in the bottom-left corner of Cursor

### Step 3.6: Open Your Project Folder

1. **File → Open Folder**
2. Type `/home/azureuser` → OK

You are now editing files on the VM through Cursor. Everything you see in the file explorer, terminal, and editor is on the remote machine.

---

## Part 4: Set Up the Python Environment on the VM

### Step 4.1: Clone Your Repository

Open the terminal in Cursor (`Ctrl+J`) and run:

```bash
cd /home/azureuser
git clone https://github.com/<your-username>/<your-repo>.git
```

If it's a private repo, you'll need to authenticate with a [GitHub Personal Access Token](https://github.com/settings/tokens) as the password.

### Step 4.2: Verify Python

Ubuntu 24.04 comes with Python 3.12 pre-installed:

```bash
python3 --version
```

Expected output: `Python 3.12.3` (or similar 3.12.x)

> **Note:** On Ubuntu, the command is `python3`, not `python`.

### Step 4.3: Install Dependencies and Create Virtual Environment

```bash
cd ~/tr-price-elasticity-bayesian
```

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv
```

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

If you get a "Permission denied" error on activate:
```bash
chmod +x .venv/bin/activate
source .venv/bin/activate
```

You should see `(.venv)` at the beginning of your terminal prompt.

### Step 4.4: Install Python Packages

If you have a `requirements.txt`:
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install pymc arviz numpy pandas scikit-learn matplotlib
```

### Step 4.5: Set the Python Interpreter in Cursor

1. Install the **Python extension** on the remote side:
   - `Ctrl+Shift+X` → search "Python"
   - Click **"Install in SSH: azure-mcmc"** on the Python extension by Anysphere
2. `Ctrl+Shift+P` → **"Python: Select Interpreter"**
3. Select the `.venv` interpreter: `/home/azureuser/<your-project>/.venv/bin/python`

### Step 4.6: Open Project as Workspace

For the best experience, reopen Cursor pointed at your project:

1. **File → Open Folder**
2. Type `/home/azureuser/<your-project>` → OK

Now Cursor's file explorer, terminal, and AI features are all scoped to your project on the VM.

---

## Part 5: tmux — Keep Your Jobs Running

### What is tmux?

tmux is a **terminal multiplexer**. It creates persistent terminal sessions on the VM that survive SSH disconnections.

### Why Do You Need It?

Without tmux, if any of the following happen during a multi-hour MCMC run:
- Your laptop goes to sleep
- Your WiFi drops for a second
- Cursor disconnects
- You close Cursor accidentally

...your MCMC sampling process **dies immediately** and you lose all progress.

With tmux, your process keeps running on the VM regardless of your connection status. You can disconnect, go home, come back the next day, and reattach to see your results.

### Install tmux

```bash
sudo apt install -y tmux
```

### Essential tmux Workflow

**Start a new session:**
```bash
tmux new -s mcmc
```
This creates a named session called "mcmc" and drops you into it.

**Run your model inside tmux:**
```bash
source .venv/bin/activate
python3 run_analysis.py
```

**Detach from the session (leave it running in background):**
Press `Ctrl+B`, then press `D`

Your terminal returns to the normal prompt, but the MCMC job keeps running.

**Reattach to check on your job:**
```bash
tmux attach -t mcmc
```

**List all running sessions:**
```bash
tmux ls
```

**Kill a session (when completely done):**
```bash
tmux kill-session -t mcmc
```

### tmux Quick Reference

| Action | Command |
|--------|---------|
| New session | `tmux new -s <name>` |
| Detach | `Ctrl+B` then `D` |
| Reattach | `tmux attach -t <name>` |
| List sessions | `tmux ls` |
| Kill session | `tmux kill-session -t <name>` |
| Scroll up | `Ctrl+B` then `[` then arrow keys (press `q` to exit scroll mode) |

---

## Part 6: Daily Workflow

Here is your typical day-to-day workflow:

### Starting Your Work Session

1. **Start the VM:**
   - Go to [portal.azure.com](https://portal.azure.com)
   - Navigate to your VM → click **Start**
   - Wait until status shows "Running"
   - Note: The public IP may change each time you start. Check the VM overview for the current IP and update your SSH config if needed.

2. **Connect Cursor:**
   - Open Cursor
   - `Ctrl+Shift+P` → Remote-SSH: Connect to Host → `azure-mcmc`

3. **Start working:**
   - Open terminal → `tmux new -s mcmc` (or `tmux attach -t mcmc` if resuming)
   - Activate venv: `source .venv/bin/activate`
   - Run your code

### Ending Your Work Session

1. **Detach tmux** (if a job is still running): `Ctrl+B` then `D`
2. **Deallocate the VM** (very important — stops billing):
   - Azure Portal → your VM → click **Stop**
   - Make sure it says **"Stopped (deallocated)"**, not just "Stopped"
   - Alternatively, use Azure CLI: `az vm deallocate --resource-group rg-bayesian-elasticity --name vm-mcmc-bayesian`

> **Important:** Simply "stopping" a VM still incurs compute charges. You must **deallocate** to stop billing. The "Stop" button in the Azure portal typically deallocates, but verify the status shows "(deallocated)".

### Deallocated ≠ Deleted — Your VM Is Safe

When you deallocate a VM, it is **not deleted**. Everything is preserved:

- ✅ Your disk and all files on it
- ✅ Your cloned Git repos
- ✅ Your Python virtual environment and installed packages
- ✅ Your VM configuration, name, and network settings
- ✅ OS-level packages you installed (tmux, python3-venv, etc.)

The **only things that don't survive** a deallocate/restart cycle:

- ❌ **tmux sessions** — these reset on reboot, so you'll need to start a new tmux session
- ❌ **Running processes** — any active MCMC job will be terminated
- ❌ **Public IP address** — may change unless you set it to "Static" (see Cost Management Tips)

To **permanently delete** the VM and stop all charges (including disk storage), you would need to explicitly click **Delete** in the Azure Portal. The **Stop/Deallocate** button does not delete anything — it just pauses the VM and stops compute billing. A small storage charge for the disk (~$5–8/month for 64 GB Premium SSD) continues even when deallocated.

When you're ready to resume:

1. Azure Portal → Virtual machines → `vm-mcmc-bayesian` → click **Start**
2. Wait ~1 minute for it to boot
3. Check the **Public IP** on the VM overview page — update your SSH config if it changed
4. Cursor → `Ctrl+Shift+P` → Remote-SSH: Connect to Host → `azure-mcmc`
5. Start a new tmux session and activate your venv — everything else is exactly as you left it

### Syncing Code Changes

Since your code is in Git, use this flow:

- **Local edits → VM:** Push from local, pull on VM (`git pull`)
- **VM edits → Local:** Push from VM, pull locally (`git pull`)
- **Direct VM editing:** Just edit in Cursor (connected to VM) and push from there

---

## Part 7: Cost Management Tips

### Set Up Auto-Shutdown (Already Done)

Your VM is configured to auto-shutdown at 11:00 PM. This is a safety net — don't rely on it as your primary shutdown method.

### Set Up Cost Alerts

1. Azure Portal → **Cost Management** → **Budgets**
2. Create a budget (e.g., $100/month)
3. Set alerts at 50%, 80%, and 100%

### Monitor Spending

- Azure Portal → **Cost Management** → **Cost analysis**
- Filter by resource group `rg-bayesian-elasticity`

### Static IP (Optional)

By default, your public IP changes each time you deallocate and restart the VM. This means updating your SSH config each time. To avoid this:

1. Go to your VM's **Networking** settings
2. Click on the public IP resource
3. Change **Assignment** from "Dynamic" to **"Static"**

This costs a small amount (~$3.65/month) but saves the hassle of updating your SSH config.

---

## Troubleshooting

### "Permission denied" when activating venv
```bash
chmod +x .venv/bin/activate
source .venv/bin/activate
```

### SSH connection refused
- Check VM is running (not stopped/deallocated) in Azure Portal
- Verify the public IP hasn't changed
- Confirm port 22 is open in the VM's Network Security Group

### Cursor can't find "Remote-SSH: Connect to Host"
- Install the "Remote - SSH" extension by Anysphere in Cursor
- Click "Restart Extensions" if prompted

### "Python: Select Interpreter" not appearing
- Install the Python extension **on the remote side** (click "Install in SSH: azure-mcmc")

### MCMC job killed after SSH disconnect
- You forgot to use tmux. Start tmux first, then run your job inside it.

### VM size not available when creating
- Your quota for that VM family in that region is insufficient
- Go to Usage + quotas → request an increase for the correct family and region

### pip install fails with permission errors
- Make sure your virtual environment is activated (`(.venv)` in prompt)
- If installing system-wide: `pip install --break-system-packages <package>`

---

## Summary of Key Commands

```bash
# Connect via SSH (from local terminal)
ssh -i ~/.ssh/vm-mcmc-bayesian_key.pem azureuser@<PUBLIC_IP>

# Set up Python environment (first time only)
sudo apt update && sudo apt install -y python3-pip python3-venv tmux
cd ~/your-project
python3 -m venv .venv
chmod +x .venv/bin/activate
source .venv/bin/activate
pip install -r requirements.txt

# Daily workflow
tmux new -s mcmc                    # Start tmux session
source .venv/bin/activate           # Activate virtual environment
python3 run_analysis.py             # Run your MCMC model
# Press Ctrl+B then D to detach     # Leave job running

tmux attach -t mcmc                 # Reattach later to check results

# VM management (Azure CLI)
az vm start --resource-group rg-bayesian-elasticity --name vm-mcmc-bayesian
az vm deallocate --resource-group rg-bayesian-elasticity --name vm-mcmc-bayesian
```

---

## Your Specific Setup Reference

| Component | Value |
|-----------|-------|
| **Subscription** | tr-analytics |
| **Resource Group** | rg-bayesian-elasticity |
| **VM Name** | vm-mcmc-bayesian |
| **Region** | East US 2 |
| **VM Size** | Standard D16s v3 (16 vCPUs, 64 GB RAM) |
| **OS** | Ubuntu 24.04 LTS |
| **Python** | 3.12.3 |
| **SSH Key** | vm-mcmc-bayesian_key.pem |
| **SSH Config Alias** | azure-mcmc |
| **Public IP** | 20.94.79.51 (may change after deallocate/restart) |
| **Auto-shutdown** | 11:00 PM (Mountain Time) |
| **Quota Approved** | DSv3, 32 vCPUs, East US 2 |
| **Pending Quota Request** | DSv5, West US 3 (better performance when approved) |

---

*Guide created: February 5, 2026*
*For the Sparkling Ice Bayesian Price Elasticity Analysis Project*
