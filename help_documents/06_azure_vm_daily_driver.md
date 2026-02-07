# Azure VM — Daily Driver

> **Purpose:** Start your VM, connect Cursor, do your work, shut it down.  
> **When to use:** Every time you sit down to work. The VM already exists.  
> **First time?** Use [One-Time Setup](05a_azure_vm_one_time_setup.md) first.

---

## Quick Reference

| Item | Value |
|------|-------|
| VM Name | vm-mcmc-bayesian |
| Resource Group | rg-bayesian-elasticity |
| SSH Alias | azure-mcmc |
| Repo Path (on VM) | `/home/azureuser/tr-price-elasticity-bayesian` |
| Venv Path | `./venv312/bin/activate` |
| Auto-shutdown | 11:00 PM Mountain (safety net — don't rely on it) |

---

## Start Your Session

### 1. Start the VM

- Portal → **Virtual machines** → `vm-mcmc-bayesian` → **Start**
- Wait until status = **Running** (~1 min)
- **Check the Public IP** — it may change after each restart

> If IP changed, update `~/.ssh/config` → `HostName` field.  
> To avoid this permanently: set IP to **Static** (see One-Time Setup).

### 2. Connect Cursor

- `Ctrl+Shift+P` → **Remote-SSH: Connect to Host** → **azure-mcmc**
- Confirm **"SSH: azure-mcmc"** appears in bottom-left

### 3. Open a terminal and get current

```bash
cd /home/azureuser/tr-price-elasticity-bayesian
git pull --ff-only
source ./venv312/bin/activate
```

**That's it. You're ready to work.**

---

## Run Your Code

For long-running jobs (MCMC), **always use tmux** so the job survives disconnects:

```bash
tmux new -s mcmc
source ./venv312/bin/activate
python run_analysis.py --config my_config.yaml --dual-elasticity
```

Detach (leave it running): **`Ctrl+B` then `D`**

Come back later:
```bash
tmux attach -t mcmc
```

> Without tmux, a WiFi drop or laptop sleep **kills your run instantly**.

---

## End Your Session

### 1. Push your work

```bash
git add -A
git commit -m "describe what you did"
git push
```

### 2. Deallocate the VM

- Portal → your VM → **Stop**
- Verify status shows **"Stopped (deallocated)"** — not just "Stopped"

Or via CLI:
```bash
az vm deallocate --resource-group rg-bayesian-elasticity --name vm-mcmc-bayesian
```

> ⚠️ **"Stopped" ≠ "Deallocated."** Only deallocated stops billing.

---

## What Survives a Deallocate (and What Doesn't)

| ✅ Survives | ❌ Does NOT survive |
|---|---|
| All files and repos | tmux sessions |
| Python venv and packages | Running processes |
| OS packages (tmux, etc.) | Public IP (unless static) |
| VM config and settings | |

---

## Upload Data to the VM

From your **local machine** (PowerShell):
```powershell
scp -i C:/Users/<username>/.ssh/vm-mcmc-bayesian_key.pem `
  C:/path/to/file.csv `
  azureuser@<PUBLIC_IP>:/home/azureuser/tr-price-elasticity-bayesian/data/
```

Verify on the VM:
```bash
ls -lh ./data
```

---

## Download Results from the VM

From your **local machine**:
```bash
scp azureuser@<PUBLIC_IP>:/home/azureuser/tr-price-elasticity-bayesian/results/elasticity_report.html .
```

---

## tmux Cheat Sheet

| Action | Command |
|--------|---------|
| New session | `tmux new -s mcmc` |
| Detach | `Ctrl+B` then `D` |
| Reattach | `tmux attach -t mcmc` |
| List sessions | `tmux ls` |
| Kill session | `tmux kill-session -t mcmc` |
| Scroll up | `Ctrl+B` then `[` → arrow keys → `q` to exit |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| SSH connection refused | VM might be stopped — start it in Portal. Check if IP changed. |
| Permission denied (SSH) | Wrong key path. Verify `-i` flag or `IdentityFile` in config. |
| `git pull` fails with merge conflict | Your VM branch diverged. Run `git status` and decide: rebase or reset. |
| venv activate: "No such file" | Wrong directory. `cd /home/azureuser/tr-price-elasticity-bayesian` first. |
| MCMC job killed after disconnect | You forgot tmux. Always start tmux before long runs. |
