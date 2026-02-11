from typing import List, Optional
from hooks.base import BaseHook
from hooks.csdn import CSDNHook

class HookManager:
    def __init__(self):
        self.hooks: List[BaseHook] = [
            CSDNHook()
        ]

    def get_hook(self, url: str) -> Optional[BaseHook]:
        for hook in self.hooks:
            if hook.match(url):
                return hook
        return None
