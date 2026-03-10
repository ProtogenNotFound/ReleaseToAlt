# ReleaseToAlt

A fully modular and interactive CLI tool to securely pull repositories from a primary GitHub account, anonymize their commit history, and release them to an alternate GitHub account.

### Disclaimer

> This thing (including the README) is entirely vibecoded - I'll look over the code and fix issues I can find but some shit might not work that well. 

## Prerequisites

Before using this tool, you must ensure the following are installed:
1. **[GitHub CLI (`gh`)](https://cli.github.com/)**: You must log in to **both** your main and alt accounts. This tool manages switching between user contexts.
   ```bash
   gh auth login
   ```
2. **[Git Filter-Repo](https://github.com/newren/git-filter-repo)**: Used for rewriting commit history securely and efficiently.
   ```bash
   pip install git-filter-repo
   ```
3. **Python 3.7+**

## Installation

You can install the package directly in editable mode or as a regular installation:

```bash
git clone https://github.com/ProtogenNotFound/ReleaseToAlt.git
cd ReleaseToAlt
pip install -e .
```

This will link the CLI entry point so you can run `releasetoalt` from anywhere.

## Usage

```bash
releasetoalt
```
On the first launch, the interactive wizard will ask for your **Main** and **Alt** GitHub usernames. It will attempt to automatically fetch the alternate user's name and email to use as the target identity for rewritten commits.

### Interactive Features

- **Dynamic Repository Search**: Select repositories interactively from a list of your most recently updated projects. If the repository you want isn't in the immediate list, select the search option to query GitHub natively.
- **Identity Filtering Wizard**: An interactive checklist allows you to easily categorize commit authors into "Keep" (Whitelisted) and "Replace" (Blacklisted), ensuring all original identities you wish to anonymize are scrubbed effectively.
- **Auto-Provisioning**: If your target repo doesn't exist on your alt account, the tool will offer to securely provision it as a Private or Public repository on the fly.

### Command-Line Arguments

You can overwrite saved settings directly from the terminal for faster automation:

- `--config <path>`: Specify a custom configuration file path (default is `~/.config/releasetoalt/config.json`).
- `--main-account <user>`: Temporarily overwrite the main account.
- `--alt-account <user>`: Temporarily overwrite the alt account.
- `--repo <name>`: Bypass the repository selection menu and process a specific repository immediately.

### Configuration
By default, the global identity preferences and repository-specific whitelist/blacklists are stored in `~/.config/releasetoalt/config.json`. Once a repository has been configured during its first run, subsequent runs for that same repository will remember your identity choices, allowing rapid, non-interactive updating.
