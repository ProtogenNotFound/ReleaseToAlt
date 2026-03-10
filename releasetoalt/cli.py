import argparse
import sys
import shutil
import atexit
from pathlib import Path
from rich.console import Console

from . import config as config_mod
from . import github
from . import tui
from . import core

console = Console()
TEMP_DIR = Path("temp_OSSMApp")

original_user = None

def cleanup():
    """Cleanup temp directory and restore gh user."""
    if TEMP_DIR.exists():
        console.print(f"[dim]Cleaning up {TEMP_DIR}...[/dim]")
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        
    if original_user:
        console.print(f"[dim]Restoring gh auth to {original_user}...[/dim]")
        github.switch_user(original_user)
        console.print("[green]Restored original GitHub account.[/green]")

def main():
    global original_user
    
    parser = argparse.ArgumentParser(description="ReleaseToAlt: Anonymize and push GitHub repos to an alt account.")
    parser.add_argument("--config", type=str, help="Path to custom config file")
    parser.add_argument("--main-account", type=str, help="Override main account")
    parser.add_argument("--alt-account", type=str, help="Override alt account")
    parser.add_argument("--repo", type=str, help="Specific repository name to process")
    args = parser.parse_args()
    
    # Register cleanup
    original_user = github.get_active_user()
    atexit.register(cleanup)
    
    # Load config
    config_path = Path(args.config) if args.config else config_mod.DEFAULT_CONFIG_PATH
    config = config_mod.load_config(config_path)
    
    # Check if we need first launch wizard
    global_cfg = config["global"]
    if not global_cfg.get("main_account") or not global_cfg.get("alt_account"):
        wizard_res = tui.first_launch_wizard()
        global_cfg.update(wizard_res)
        config_mod.save_config(config, config_path)
        console.print(f"[green]Configuration saved to {config_path}[/green]\n")
        
    # Apply Overrides
    main_account = args.main_account or global_cfg["main_account"]
    alt_account = args.alt_account or global_cfg["alt_account"]
    new_name = global_cfg["new_name"]
    new_email = global_cfg["new_email"]

    # 1. Select repository
    repo_name = args.repo
    if not repo_name:
        console.print(f"[dim]Switching to main account: {main_account}...[/dim]")
        github.switch_user(main_account)
        console.print(f"Fetching repositories for [bold cyan]{main_account}[/bold cyan]...")
        
        selection = tui.select_repo_prompt(main_account, github.list_user_repos)
        if not selection:
            console.print("Operation cancelled.")
            sys.exit(0)
        repo_name = selection["name"]
        
    # Ensure URL formatting
    source_repo_url = f"https://github.com/{main_account}/{repo_name}.git"
    alt_repo_url = f"https://github.com/{alt_account}/{repo_name}.git"

    # 2. Check if repo exists on alt account
    console.print(f"\n[dim]Switching to alt account: {alt_account}...[/dim]")
    github.switch_user(alt_account)
    
    if not github.repo_exists(alt_account, repo_name):
        choice = tui.repo_creation_prompt(repo_name)
        if choice == "cancel":
            console.print("Operation cancelled.")
            sys.exit(0)
            
        console.print(f"[dim]Creating repository {repo_name} as {choice}...[/dim]")
        is_private = (choice == "private")
        github.create_repo(repo_name, private=is_private)
        
        # Update repo config with visibility
        repo_cfg = config_mod.get_repo_config(config, repo_name)
        repo_cfg["visibility"] = choice
        config_mod.update_repo_config(config, repo_name, repo_cfg)
        config_mod.save_config(config, config_path)
        
    # 3. Clone Repository
    console.print(f"\n[dim]Switching to main account: {main_account}...[/dim]")
    github.switch_user(main_account)
    
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        
    console.print(f"⬇️  Cloning {source_repo_url}...")
    core.clone_repo(source_repo_url, TEMP_DIR)
    
    # 4. Filter Identities
    repo_cfg = config_mod.get_repo_config(config, repo_name)
    identities = core.discover_identities(TEMP_DIR)
    
    # Only prompt if there are identities that are not configured
    # We'll just prompt anyway to ensure they see it, but pre-populate.
    whitelist, blacklist = tui.select_identities_prompt(
        identities, 
        repo_cfg.get("whitelist", []), 
        repo_cfg.get("blacklist", [])
    )
    
    # Save preferences
    repo_cfg["whitelist"] = whitelist
    repo_cfg["blacklist"] = blacklist
    config_mod.update_repo_config(config, repo_name, repo_cfg)
    config_mod.save_config(config, config_path)

    if blacklist:
        console.print("\n📝 Applying git filter-repo to anonymize history...")
        core.apply_filter(TEMP_DIR, blacklist, new_name, new_email)
        if not core.verify_filter(TEMP_DIR, blacklist):
            console.print("[red]❌ Verification failed. Aborting push.[/red]")
            sys.exit(1)
        console.print("[green]✅ Filtration successful.[/green]")
    else:
        console.print("\n[yellow]⚠️ No identities selected to replace. Skipping rewrite.[/yellow]")

    # 5. Push to Alt
    console.print(f"\n[dim]Switching to alt account: {alt_account}...[/dim]")
    github.switch_user(alt_account)
    
    console.print(f"🚀 Pushing to {alt_repo_url}...")
    core.push_to_remote(TEMP_DIR, alt_repo_url)
    
    console.print("\n[bold green]✨ Done! Your repository has been anonymized and published.[/bold green]")

if __name__ == "__main__":
    main()
