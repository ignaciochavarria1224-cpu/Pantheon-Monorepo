# utils/registry.py
from pathlib import Path
from utils.vault import VAULT_ROOT, FINAL_FOLDERS, get_all_notes


class NoteRegistry:
    def __init__(self):
        self._notes: list = []
        self._by_id: dict = {}
        self.count: int = 0

    def build(self):
        self._notes = get_all_notes()
        self._by_id = {}
        for n in self._notes:
            nid = n["frontmatter"].get("id")
            if nid:
                self._by_id[nid] = n
        self.count = len(self._notes)
        return self

    def get_all(self, exclude_flagged: bool = False) -> list:
        if exclude_flagged:
            return [n for n in self._notes
                    if not n["frontmatter"].get("flagged_for_pruning", False)]
        return list(self._notes)

    def get_by_id(self, note_id: str) -> dict | None:
        return self._by_id.get(note_id)

    def get_by_stage(self, stage: str) -> list:
        folder_map = {"seed": "00-Seeds", "sprout": "01-Sprouts", "tree": "02-Trees"}
        target = folder_map.get(stage, stage)
        return [n for n in self._notes if target in str(n["path"])]

    def get_framework_eligible(self) -> list:
        return [n for n in self._notes
                if n["frontmatter"].get("framework_eligible", False)
                and not n["frontmatter"].get("published", False)]
