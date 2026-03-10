from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from typing import List, Dict, Optional, Tuple, Set
from . import github

console = Console()

def print_header(title: str):
    """Print a styled header."""
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))

def first_launch_wizard() -> Dict[str, str]:
    """Prompt the user for global configuration on first launch."""
    print_header("First Launch Setup")
    console.print("Please configure your GitHub accounts.\n")
    
    available_users = github.get_available_users()
    if available_users:
        choices = available_users + ["Custom (type manually)..."]
        
        main_account = inquirer.select(
            message="Select your MAIN GitHub username (source repos):",
            choices=choices
        ).execute()
        
        if main_account == "Custom (type manually)...":
            main_account = inquirer.text(
                message="Enter your MAIN GitHub username (source repos):"
            ).execute()
            
        alt_choices = [c for c in available_users if c != main_account] + ["Custom (type manually)..."]
        
        alt_account = inquirer.select(
            message="Select your ALT GitHub username (target repos):",
            choices=alt_choices
        ).execute()
        
        if alt_account == "Custom (type manually)...":
            alt_account = inquirer.text(
                message="Enter your ALT GitHub username (target repos):"
            ).execute()
    else:
        main_account = inquirer.text(
            message="Enter your MAIN GitHub username (source repos):"
        ).execute()
        
        alt_account = inquirer.text(
            message="Enter your ALT GitHub username (target repos):"
        ).execute()
    
    # Try fetching the name and email from the alt account automatically
    console.print(f"\n[dim]Authenticating as {alt_account} to fetch identity info...[/dim]")
    try:
        github.switch_user(alt_account)
        new_name, new_email = github.get_user_info()
    except Exception:
        new_name = new_email = None

    if new_name and new_email:
        console.print(f"[green]Successfully fetched alt identity:[/green] {new_name} <{new_email}>")
        confirm = inquirer.confirm(
            message="Use these for anonymizing commits?",
            default=True
        ).execute()
        if not confirm:
            new_name = new_email = None
    
    if not new_name or not new_email:
        console.print("\n[yellow]Please provide the identity to use on the alt account:[/yellow]")
        new_name = inquirer.text(
            message="Enter the commit NAME for the alt account:",
            default=new_name or ""
        ).execute()
        
        new_email = inquirer.text(
            message="Enter the commit EMAIL for the alt account:",
            default=new_email or ""
        ).execute()
        
    return {
        "main_account": main_account.strip(),
        "alt_account": alt_account.strip(),
        "new_name": new_name.strip(),
        "new_email": new_email.strip()
    }

def select_repo_prompt(username: str, get_repos_func) -> Optional[Dict]:
    """
    Prompt to select a repository.
    Handles dynamic searching if the user doesn't see their repo.
    """
    repos = get_repos_func(username)
    
    while True:
        choices = []
        # Add search option at the top
        choices.append({"name": "🔍 [Search repositories...]", "value": "__SEARCH__"})
        
        for r in repos:
            vis = "🔒" if r.get('visibility', '').lower() == 'private' else "🌎"
            choices.append({
                "name": f"{vis} {r['name']} (updated {r.get('updatedAt', '')[:10]})",
                "value": r
            })
            
        choices.append({"name": "❌ [Cancel]", "value": "__CANCEL__"})

        selection = inquirer.fuzzy(
            message="Select a repository to process:",
            choices=choices,
            instruction="(Use arrow keys or start typing to search)",
            max_height="70%"
        ).execute()

        if selection == "__CANCEL__":
            return None
            
        if selection == "__SEARCH__":
            query = inquirer.text(message="Enter search term (or leave empty to go back):").execute().strip()
            if query:
                console.print("[dim]Searching...[/dim]")
                repos = github.search_user_repos(username, query)
                if not repos:
                    console.print("[yellow]No repositories found for that query. Showing original list.[/yellow]")
                    repos = get_repos_func(username)
            continue
            
        return selection

def repo_creation_prompt(repo_name: str) -> str:
    """Prompt user for repository creation visibility."""
    console.print(f"\n[yellow]Repository '{repo_name}' does not exist on the target account.[/yellow]")
    
    choice = inquirer.select(
        message="Create it now?",
        choices=[
            {"name": "🔒 Yes, as Private", "value": "private"},
            {"name": "🌎 Yes, as Public", "value": "public"},
            {"name": "❌ No, Cancel", "value": "cancel"}
        ]
    ).execute()
    
    return choice

def _format_identity_choices(identities: List[Dict], whitelist: List[str], blacklist: List[str]):
    """Format identities into InquirerPy choice objects."""
    choices = []
    
    whitelist_set = set(whitelist)
    blacklist_set = set(blacklist)
    
    for idx, ident in enumerate(identities):
        email = ident['email']
        name = ident['name']
        roles = ", ".join(ident['roles'])
        
        # Determine status
        if email in whitelist_set:
            status = "✅ WHITELISTED (Keep)"
            checked = True
        elif email in blacklist_set:
            status = "❌ BLACKLISTED (Replace)"
            checked = False
        else:
            status = "❓ UNCONFIGURED (Default: Replace)"
            checked = False
            
        display = f"{name} <{email}> [{roles}] -> {status}"
        
        choices.append({
            "name": display,
            "value": email,
            "enabled": checked  # If checked, it means they want to KEEP it.
        })
        
    return choices

def select_identities_prompt(identities: List[Dict], previous_whitelist: List[str], previous_blacklist: List[str]) -> Tuple[List[str], List[str]]:
    """
    Interactive prompt to select which identities to KEEP (whitelist).
    The unchecked ones will be replaced (blacklist).
    Returns (whitelist, blacklist)
    """
    print_header("Identity Filter Setup")
    console.print("Select which identities to [bold green]KEEP[/bold green] (whitelist) in the commit history.")
    console.print("Any unchecked identities will be [bold red]REPLACED[/bold red] with your alt identity.\n")

    choices = _format_identity_choices(identities, previous_whitelist, previous_blacklist)
    
    selected_emails = inquirer.checkbox(
        message="Select identities to KEEP (Space to toggle, Enter to confirm):",
        choices=choices,
        instruction="(Checked = Keep/Whitelist; Unchecked = Replace/Blacklist)"
    ).execute()
    
    new_whitelist = list(selected_emails)
    
    # Everything in identities that wasn't selected goes to the blacklist
    new_blacklist = []
    for ident in identities:
        email = ident["email"]
        if email not in new_whitelist:
            new_blacklist.append(email)
            
    # Print summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"[green]Keeping {len(new_whitelist)} identities.[/green]")
    console.print(f"[red]Replacing {len(new_blacklist)} identities.[/red]")
    
    return new_whitelist, new_blacklist
