import nodriver as uc
import asyncio
import logging
import sys
import os
import platform
from hooks.manager import HookManager

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def find_browser_executable():
    """
    Finds a supported browser executable (Chrome, Edge, Brave, Chromium).
    Returns the path to the executable or raises FileNotFoundError.
    """
    system = platform.system()
    candidates = []

    if system == "Darwin": # macOS
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif system == "Windows":
        # Common Windows paths
        program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
        local_app_data = os.environ.get("LOCALAPPDATA", "C:\\Users\\%USERNAME%\\AppData\\Local")
        
        candidates = [
            os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files_x86, "Microsoft\\Edge\\Application\\msedge.exe"),
            os.path.join(program_files, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
            os.path.join(local_app_data, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
        ]
    elif system == "Linux":
        # Common Linux binaries
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/microsoft-edge",
            "/usr/bin/brave-browser",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]

    for path in candidates:
        if os.path.exists(path) and os.access(path, os.X_OK):
            logger.info(f"Found browser executable: {path}")
            return path
    
    return None

# Initial URL to test
url = 'https://blog.csdn.net/acm_pn/article/details/144218481'

async def main():
    logger.info("Starting browser...")
    
    # Use a persistent user_data_dir to save login state
    current_dir = os.path.dirname(os.path.abspath(__file__))
    user_data_dir = os.path.join(current_dir, "browser_data")
    
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        logger.info(f"Created user data directory: {user_data_dir}")
    else:
        logger.info(f"Using existing user data directory: {user_data_dir}")

    # Auto-detect browser
    browser_path = find_browser_executable()
    if not browser_path:
        error_msg = "No supported browser found (Chrome, Edge, Brave, Chromium)."
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        # Pass the detected browser path to nodriver
        browser = await uc.start(
            user_data_dir=user_data_dir,
            browser_executable_path=browser_path
        )
    except Exception as e:
        logger.error(f"Failed to start browser: {e}")
        raise e

    hook_manager = HookManager()

    async def setup_interception(target_page):
        # We need to know the URL to select the hook.
        # But target_page.target.url might be available
        current_url = target_page.target.url
        hook = hook_manager.get_hook(current_url)

        if not hook:
            logger.info(f"No hook found for {current_url}")
            return

        logger.info(f"Applying hook for {current_url}")

        async def handle_request_paused(event: uc.cdp.fetch.RequestPaused):
            await hook.handle_request(event, target_page)

        # Disable cache
        await target_page.send(uc.cdp.network.set_cache_disabled(cache_disabled=True))
        
        # Enable Fetch interception with patterns from the hook
        try:
            await target_page.send(uc.cdp.fetch.enable(patterns=hook.patterns))
        except Exception as e:
            logger.error(f"Failed to enable fetch interception: {e}")
            return
        
        target_page.add_handler(uc.cdp.fetch.RequestPaused, handle_request_paused)
        logger.info(f"Interception enabled for {current_url}")

    page = await browser.get('about:blank')
    logger.info("Browser started.")
    
    logger.info(f"Navigating to {url}")
    await page.get(url)
    
    monitored_target_ids = set()

    # Continuous monitoring loop
    while True:
        try:
            targets = browser.targets
            for tab in targets:
                # Check if it's a page and not already monitored
                if hasattr(tab, 'target') and tab.target.type_ == 'page':
                    tid = tab.target.target_id
                    current_url = tab.target.url
                    
                    # If we haven't seen this target ID, set up interception
                    if tid not in monitored_target_ids:
                        logger.info(f"New tab detected: {tid} - {current_url}")
                        
                        hook = hook_manager.get_hook(current_url)
                        if hook:
                            try:
                                await setup_interception(tab)
                                monitored_target_ids.add(tid)
                                # Initial injection for existing content
                                await tab.evaluate(hook.injection_script)
                            except Exception as e:
                                logger.error(f"Failed to setup interception for tab {tid}: {e}")
                        else:
                            # Mark as monitored even if no hook, so we don't keep checking
                            monitored_target_ids.add(tid) 

                    # Periodic re-injection for dynamic content on all monitored pages
                    # Only if a hook applies
                    hook = hook_manager.get_hook(current_url)
                    if hook:
                        try:
                            await tab.evaluate(hook.injection_script)
                        except Exception:
                            pass # Tab might be closed or detached


            await asyncio.sleep(2)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await asyncio.sleep(2) 

if __name__ == '__main__':
    uc.loop().run_until_complete(main())

