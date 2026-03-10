import subprocess
import json
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class GitHubError(Exception):
    """Exception raised for errors in gh CLI operations."""
    pass

def run_gh(command: List[str], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
    """Run a gh CLI command and return the result."""
    try:
        # We assume `gh` is in the PATH.
        cmd = ["gh"] + command
        return subprocess.run(
            cmd,
            check=check,
            text=True,
            capture_output=capture_output
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"gh command failed: {' '.join(cmd)}\nStderr: {e.stderr}")
        if check:
            raise GitHubError(f"GitHub CLI command failed: {e.stderr}")
        return e

def get_active_user() -> Optional[str]:
    """Get the currently logged-in GitHub user."""
    res = run_gh(["auth", "status"], check=False)
    # gh auth status prints output conditionally to stdout or stderr depending on versions
    output = res.stdout + res.stderr
    for line in output.splitlines():
        if "Logged in to github.com account" in line or "Logged in to GitHub.com as" in line:
            parts = line.strip().split()
            # Handle format: "✓ Logged in to github.com account USERNAME"
            if "account" in parts:
                idx = parts.index("account") + 1
                return parts[idx].strip(" ()")
            # Handle format: "✓ Logged in to GitHub.com as USERNAME"
            elif "as" in parts:
                idx = parts.index("as") + 1
                return parts[idx].strip(" ()")
    return None

def get_available_users() -> List[str]:
    """Get all logged-in GitHub users."""
    res = run_gh(["auth", "status"], check=False)
    output = res.stdout + res.stderr
    users = []
    for line in output.splitlines():
        if "Logged in to github.com account" in line or "Logged in to GitHub.com as" in line:
            parts = line.strip().split()
            if "account" in parts:
                idx = parts.index("account") + 1
                users.append(parts[idx].strip(" ()"))
            elif "as" in parts:
                idx = parts.index("as") + 1
                users.append(parts[idx].strip(" ()"))
    return sorted(list(set(users)))


def switch_user(username: str) -> None:
    """Switch gh CLI to another user."""
    run_gh(["auth", "switch", "--user", username])

def get_user_info() -> Tuple[Optional[str], Optional[str]]:
    """
    Get the name and email of the currently authenticated GitHub user.
    Returns (name, email)
    """
    try:
        res = run_gh(["api", "user"])
        data = json.loads(res.stdout)
        
        name = data.get("name") or data.get("login")
        email = data.get("email")
        
        # If public email is missing, try fetching primary email
        if not email:
            try:
                email_res = run_gh(["api", "user/emails"])
                for em in json.loads(email_res.stdout):
                    if em.get("primary"):
                        email = em.get("email")
                        break
            except Exception:
                pass
                
        # Fallback to the GitHub-provided noreply email
        if not email and data.get("id") and data.get("login"):
            email = f"{data.get('id')}+{data.get('login')}@users.noreply.github.com"
            
        return name, email
    except Exception as e:
        logger.error(f"Failed to fetch user info: {e}")
        return None, None

def list_user_repos(username: str, limit: int = 1000) -> List[Dict]:
    """List repositories for a given user."""
    try:
        res = run_gh([
            "repo", "list", username,
            "--limit", str(limit),
            "--json", "name,nameWithOwner,updatedAt,visibility"
        ])
        return json.loads(res.stdout)
    except GitHubError:
        return []

def search_user_repos(username: str, query: str, limit: int = 100) -> List[Dict]:
    """Search repositories for a user by a query string."""
    try:
        # Using gh search repos
        res = run_gh([
            "search", "repos", f"user:{username} {query}",
            "--limit", str(limit),
            "--json", "name,nameWithOwner,updatedAt,visibility"
        ])
        return json.loads(res.stdout)
    except GitHubError:
        return []

def repo_exists(owner: str, name: str) -> bool:
    """Check if a repository exists."""
    owner_name = f"{owner}/{name}"
    res = run_gh(["repo", "view", owner_name], check=False)
    return res.returncode == 0

def create_repo(name: str, private: bool = True) -> str:
    """
    Create a new repository for the currently authenticated user.
    Returns the nameWithOwner (e.g., username/repo_name).
    """
    visibility_flag = "--private" if private else "--public"
    # Create the repo without cloning it
    res = run_gh(["repo", "create", name, visibility_flag])
    
    # Extract the repository name from standard output (often outputs URL)
    # The safest way is to query the latest repo, or assume "username/name"
    active_user = get_active_user()
    return f"{active_user}/{name}"
