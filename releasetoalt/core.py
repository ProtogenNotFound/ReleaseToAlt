import subprocess
import sys
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

class GitError(Exception):
    """Exception raised for errors in git operations."""
    pass

def run_git(command: List[str], cwd: Path, capture_output: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the specified directory."""
    try:
        cmd = ["git"] + command
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=capture_output
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"git command failed: {' '.join(cmd)}\nStderr: {e.stderr}")
        raise GitError(f"Git command failed: {e.stderr}")

def clone_repo(url: str, dest_dir: Path) -> None:
    """Clone a repository into the destination directory."""
    try:
        subprocess.run(
            ["git", "clone", url, str(dest_dir)],
            check=True,
            text=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone repository: {e.stderr}")
        raise GitError(f"Failed to clone repository: {e.stderr}")

def discover_identities(repo_path: Path) -> List[Dict]:
    """Discover all unique author/committer identities in the repository."""
    result = run_git(["log", "--all", "--format=%an|%ae|%cn|%ce"], cwd=repo_path)
    
    identities = set()
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split('|')
        if len(parts) == 4:
            identities.add((parts[0], parts[1], 'author'))
            identities.add((parts[2], parts[3], 'committer'))
            
    email_to_identity = {}
    for name, email, role in identities:
        if email not in email_to_identity:
            email_to_identity[email] = {"name": name, "email": email, "roles": set()}
        email_to_identity[email]["roles"].add(role)
        
    for identity in email_to_identity.values():
        identity["roles"] = list(identity["roles"])
        
    return list(email_to_identity.values())

def apply_filter(repo_path: Path, blacklist: List[str], new_name: str, new_email: str) -> None:
    """Apply the identity filter to the repository using git-filter-repo."""
    if not blacklist:
        return
        
    email_checks = [f'commit.author_email == b"{email}"' for email in blacklist]
    author_condition = ' or '.join(email_checks)
    committer_condition = author_condition.replace('author_email', 'committer_email')
    
    callback_code = f"""
if {author_condition}:
    commit.author_name = b"{new_name}"
    commit.author_email = b"{new_email}"
if {committer_condition}:
    commit.committer_name = b"{new_name}"
    commit.committer_email = b"{new_email}"
"""
    
    try:
        subprocess.run(
            [sys.executable, "-m", "git_filter_repo", "--force", "--commit-callback", callback_code],
            cwd=repo_path,
            check=True,
            text=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to apply filter-repo: {e.stderr}")
        raise GitError(f"Failed to apply filter-repo: {e.stderr}")

def verify_filter(repo_path: Path, blacklist: List[str]) -> bool:
    """Verify that blacklisted identities are gone from history."""
    if not blacklist:
        return True
        
    result = run_git(["log", "--all", "--format=%ae|%ce"], cwd=repo_path)
    
    for email in blacklist:
        if email in result.stdout:
            return False
            
    return True

def push_to_remote(repo_path: Path, remote_url: str) -> None:
    """Add a new remote and push the filtered history."""
    run_git(["remote", "add", "origin", remote_url], cwd=repo_path)
    
    try:
        # Push all branches, forcing overwrite
        subprocess.run(
            ["git", "push", "-u", "origin", "main", "--force"],
            cwd=repo_path,
            check=True,
            text=True,
            capture_output=False # We might want the user to see progress, but for API let's capture or pass through
        )
        # To make it more robust, we might want to push all branches:
        # subprocess.run(["git", "push", "--all", "--force", "origin"], cwd=repo_path)
        # subprocess.run(["git", "push", "--tags", "--force", "origin"], cwd=repo_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to push to remote: {e}")
        raise GitError("Failed to push to target repository.")
