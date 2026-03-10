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
    parser.add_argument("--save", type=str, nargs='?', const=str(config_mod.DEFAULT_CONFIG_PATH), 
                        help="Launch interactive experience and save configuration to the given json")
    parser.add_argument("--main-account", type=str, help="Override main account")
    parser.add_argument("--alt-account", type=str, help="Override alt account")
    parser.add_argument("--repo", type=str, help="Specific repository name to process")
    args = parser.parse_args()
    
    # Register cleanup
    original_user = github.get_active_user()
    atexit.register(cleanup)
    
    # Determine execution mode
    is_saving = args.save is not None
    is_batch = bool(args.config) and not args.repo and not is_saving
    
    if args.config:
        config_path = Path(args.config)
    elif is_saving:
        config_path = Path(args.save)
    else:
        config_path = config_mod.DEFAULT_CONFIG_PATH
        
    config_list = config_mod.load_config(config_path)
    
    if is_batch:
        if not config_list:
            console.print("[red]No repositories configured in the provided config file.[/red]")
            sys.exit(1)
            
        for repo_cfg in config_list:
            main_account = args.main_account or repo_cfg.get("main_account")
            alt_account = args.alt_account or repo_cfg.get("alt_account")
            new_name = repo_cfg.get("new_name")
            new_email = repo_cfg.get("new_email")
            repo_name = repo_cfg.get("repo_name")
            
            if not all([main_account, alt_account, new_name, new_email, repo_name]):
                console.print(f"[yellow]Skipping incomplete repository config: {repo_name}[/yellow]")
                continue
                
            console.print(f"\n[bold blue]--- Processing Repository: {repo_name} ---[/bold blue]")
            run_release(repo_name, main_account, alt_account, new_name, new_email, repo_cfg, config_list, config_path, interactive=False)
            
    else:
        global_defs = config_mod.get_global_defaults(config_list)
        
        main_account = args.main_account or global_defs.get("main_account")
        alt_account = args.alt_account or global_defs.get("alt_account")
        new_name = global_defs.get("new_name")
        new_email = global_defs.get("new_email")
        
        if not all([main_account, alt_account, new_name, new_email]):
            wizard_res = tui.first_launch_wizard()
            main_account = wizard_res["main_account"]
            alt_account = wizard_res["alt_account"]
            new_name = wizard_res["new_name"]
            new_email = wizard_res["new_email"]
            
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
            
        existing_cfg = config_mod.get_repo_config(config_list, repo_name)
        
        target_cfg = {
            "main_account": main_account,
            "alt_account": alt_account,
            "new_name": new_name,
            "new_email": new_email,
            "repo_name": repo_name,
            "whitelist": existing_cfg.get("whitelist", []) if existing_cfg else [],
            "blacklist": existing_cfg.get("blacklist", []) if existing_cfg else [],
            "visibility": existing_cfg.get("visibility", "private") if existing_cfg else "private"
        }
        
        save_action = "overwrite"
        if existing_cfg:
            save_action = tui.repo_exists_prompt(repo_name)
            if save_action == "ignore":
                is_saving = False
            elif save_action == "overwrite":
                target_cfg["whitelist"] = []
                target_cfg["blacklist"] = []
                target_cfg["visibility"] = "private"
                
        should_save = is_saving or (not args.config and save_action != "ignore")
        
        run_release(repo_name, main_account, alt_account, new_name, new_email, target_cfg, config_list, config_path, interactive=True, save_action=save_action, is_saving=should_save)

def run_release(repo_name, main_account, alt_account, new_name, new_email, repo_cfg, config_list, config_path, interactive, save_action="overwrite", is_saving=False):
    source_repo_url = f"https://github.com/{main_account}/{repo_name}.git"
    alt_repo_url = f"https://github.com/{alt_account}/{repo_name}.git"

    console.print(f"\n[dim]Switching to alt account: {alt_account}...[/dim]")
    github.switch_user(alt_account)
    
    if not github.repo_exists(alt_account, repo_name):
        if interactive:
            choice = tui.repo_creation_prompt(repo_name)
            if choice == "cancel":
                console.print("Operation cancelled.")
                sys.exit(0)
            new_visibility = choice
        else:
            new_visibility = repo_cfg.get("visibility", "private")
            
        is_private = (new_visibility == "private")
        console.print(f"[dim]Creating repository {repo_name} as {new_visibility}...[/dim]")
        github.create_repo(repo_name, private=is_private)
        
        if save_action == "merge" and interactive and "visibility" in repo_cfg and repo_cfg["visibility"] != new_visibility:
            final_vis = tui.merge_privacy_prompt(repo_name, repo_cfg["visibility"], new_visibility)
            repo_cfg["visibility"] = final_vis
        else:
            repo_cfg["visibility"] = new_visibility
            
    console.print(f"\n[dim]Switching to main account: {main_account}...[/dim]")
    github.switch_user(main_account)
    
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        
    console.print(f"⬇️  Cloning {source_repo_url}...")
    core.clone_repo(source_repo_url, TEMP_DIR)
    
    identities = core.discover_identities(TEMP_DIR)
    
    known_emails = set(repo_cfg.get("whitelist", [])) | set(repo_cfg.get("blacklist", []))
    all_identity_emails = {ident["email"] for ident in identities}
    has_unknown_identities = not all_identity_emails.issubset(known_emails)
    
    if interactive or has_unknown_identities:
        if has_unknown_identities and not interactive:
            console.print(f"\n[yellow]⚠️ New identities discovered in {repo_name}. Switching to interactive mode for identity configuration.[/yellow]")
            
        p_whitelist = repo_cfg.get("whitelist", []) if save_action != "overwrite" else []
        p_blacklist = repo_cfg.get("blacklist", []) if save_action != "overwrite" else []
        
        whitelist, blacklist = tui.select_identities_prompt(identities, p_whitelist, p_blacklist)
        
        if save_action == "merge":
            merged_whitelist = list(set(repo_cfg.get("whitelist", [])) | set(whitelist))
            merged_blacklist = list(set(repo_cfg.get("blacklist", [])) | set(blacklist))
            merged_blacklist = [e for e in merged_blacklist if e not in whitelist]
            merged_whitelist = [e for e in merged_whitelist if e not in blacklist]
            
            repo_cfg["whitelist"] = merged_whitelist
            repo_cfg["blacklist"] = merged_blacklist
        else:
            repo_cfg["whitelist"] = whitelist
            repo_cfg["blacklist"] = blacklist
            
        if is_saving or has_unknown_identities:
            config_mod.update_repo_config(config_list, repo_name, repo_cfg)
            config_mod.save_config(config_list, config_path)
    
    blacklist = repo_cfg.get("blacklist", [])
    if blacklist:
        console.print("\n📝 Applying git filter-repo to anonymize history...")
        core.apply_filter(TEMP_DIR, blacklist, new_name, new_email)
        if not core.verify_filter(TEMP_DIR, blacklist):
            console.print("[red]❌ Verification failed. Aborting push.[/red]")
            sys.exit(1)
        console.print("[green]✅ Filtration successful.[/green]")
    else:
        console.print("\n[yellow]⚠️ No identities selected to replace. Skipping rewrite.[/yellow]")

    console.print(f"\n[dim]Switching to alt account: {alt_account}...[/dim]")
    github.switch_user(alt_account)
    
    console.print(f"🚀 Pushing to {alt_repo_url}...")
    core.push_to_remote(TEMP_DIR, alt_repo_url)
    
    console.print(f"\n[bold green]✨ Done! Your repository {repo_name} has been anonymized and published.[/bold green]")

if __name__ == "__main__":
    main()
