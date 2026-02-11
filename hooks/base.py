from abc import ABC, abstractmethod
import nodriver as uc

class BaseHook(ABC):
    @abstractmethod
    def match(self, url: str) -> bool:
        """Check if this hook should handle the given URL."""
        pass

    @property
    @abstractmethod
    def patterns(self):
        """Return list of RequestPatterns to intercept."""
        pass

    @abstractmethod
    async def handle_request(self, event: uc.cdp.fetch.RequestPaused, page: uc.Tab):
        """Handle intercepted request."""
        pass

    @property
    def injection_script(self) -> str:
        """Return JavaScript to inject into the page."""
        return ""
