# utils/git_ops.py
import os
from pathlib import Path
from datetime import datetime

_env_vault = os.environ.get("MARIDIAN_VAULT_PATH")
VAULT_ROOT = Path(_env_vault) if _env_vault else Path(__file__).parent.parent


def git_commit(cycle: int, framework_count: int) -> bool:
    if not (VAULT_ROOT / ".git").exists():
        # Vault is not a git repo (post-migration data dir). Skip silently.
        return True
    try:
        import git
        repo = git.Repo(VAULT_ROOT)
        repo.git.add(A=True)
        if not repo.is_dirty(index=True, untracked_files=True):
            print("  [GIT] Nothing to commit.")
            return True
        msg = (f"Cycle {cycle}: {datetime.now().strftime('%Y-%m-%d %H:%M')} "
               f"| frameworks: {framework_count}")
        repo.index.commit(msg)
        print(f"  [GIT] Committed: {msg}")
        return True
    except Exception as e:
        print(f"  [GIT] Commit failed: {e}")
        return False
