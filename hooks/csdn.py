from .base import BaseHook
import nodriver as uc
import base64
import logging

logger = logging.getLogger(__name__)

class CSDNHook(BaseHook):
    TARGET_JS = "pc_wap_commontools"
    TARGET_HTML = "article/details"
    OLD_CODE = "$('.vipmaskclassname').length > 0"
    NEW_CODE = "$('.vipmaskclassname').length < 0"
    
    UNLOCK_SCRIPT = """
(function() {
    console.log(">>> [Unlocker] Starting unlock process...");
    
    // 1. Remove Mask
    var mask = document.querySelector(".hide-article-box");
    if(mask) { mask.remove(); console.log("Removed .hide-article-box"); }
    
    // 2. Remove Dark Mask & Follow Mask
    var darkMask = document.querySelector(".mask-dark");
    if(darkMask) { darkMask.remove(); console.log("Removed .mask-dark"); }

    var followMask = document.querySelector(".hide-article-pos");
    if(followMask) { followMask.remove(); console.log("Removed .hide-article-pos"); }

    // 3. Expand Content
    var content = document.getElementById("article_content") || document.querySelector(".article_content");
    if (content) {
        content.style.height = "auto";
        content.style.maxHeight = "none";
        content.style.overflow = "visible";
        content.classList.remove("hide-article-box");
        console.log("Expanded article content style");
    }
    
    // 4. Remove other potential blockers
    document.querySelectorAll(".vip-mask").forEach(el => el.remove());

    // 5. Remove Login Modal & Overlays
    var loginSelectors = [
        ".passport-login-container",
        ".passport-login-box",
        "#passportbox",
        ".passport-background",
        ".modal-backdrop",
        ".passport-overlay",
        ".login-mark",
        ".login-box", 
        ".login-mask"
    ];
    
    loginSelectors.forEach(selector => {
        document.querySelectorAll(selector).forEach(el => {
            el.remove();
            console.log("Removed login element: " + selector);
        });
    });
})();
"""

    def match(self, url: str) -> bool:
        return "blog.csdn.net" in url or "csdn.net" in url

    @property
    def patterns(self):
        return [
            uc.cdp.fetch.RequestPattern(
                url_pattern=f"*{self.TARGET_JS}*",
                resource_type=uc.cdp.network.ResourceType.SCRIPT,
                request_stage=uc.cdp.fetch.RequestStage.RESPONSE
            ),
            uc.cdp.fetch.RequestPattern(
                url_pattern=f"*{self.TARGET_HTML}*",
                request_stage=uc.cdp.fetch.RequestStage.RESPONSE
            )
        ]

    @property
    def injection_script(self) -> str:
        return self.UNLOCK_SCRIPT

    async def handle_request(self, event: uc.cdp.fetch.RequestPaused, page: uc.Tab):
        req_url = event.request.url
        try:
            if self.TARGET_JS in req_url:
                logger.info(f"[CSDN] Target JS Intercepted: {req_url}")
                try:
                    response = await page.send(uc.cdp.fetch.get_response_body(event.request_id))
                    body_b64, success = response
                    
                    if success: 
                        body_str = base64.b64decode(body_b64).decode('utf-8', errors='ignore')
                        
                        if self.OLD_CODE in body_str:
                            logger.info("[CSDN] Found target code in JS. Replacing...")
                            body_str = body_str.replace(self.OLD_CODE, self.NEW_CODE)
                        else:
                            logger.warning("[CSDN] Target code NOT found in JS.")

                        new_body_b64 = base64.b64encode(body_str.encode('utf-8')).decode('utf-8')
                        await page.send(uc.cdp.fetch.fulfill_request(
                            request_id=event.request_id,
                            response_code=200,
                            body=new_body_b64,
                            response_headers=event.response_headers
                        ))
                    else:
                        logger.warning("[CSDN] Success flag false in get_response_body")
                        await page.send(uc.cdp.fetch.continue_request(request_id=event.request_id))

                except Exception as e:
                    logger.error(f"[CSDN] Error fetching JS body: {e}")
                    await page.send(uc.cdp.fetch.continue_request(request_id=event.request_id))

            elif self.TARGET_HTML in req_url:
                logger.info(f"[CSDN] Target HTML Intercepted: {req_url}")
                await page.send(uc.cdp.fetch.continue_request(request_id=event.request_id))
                
                # INJECT SCRIPT NOW
                try:
                    await page.evaluate(self.UNLOCK_SCRIPT)
                    logger.info("[CSDN] Injected unlock script via evaluate.")
                except Exception as e:
                    logger.warning(f"[CSDN] Injection failed (DOM not ready?): {e}")

            else:
                await page.send(uc.cdp.fetch.continue_request(request_id=event.request_id))

        except Exception as e:
            try:
                await page.send(uc.cdp.fetch.continue_request(request_id=event.request_id))
            except:
                pass
