import asyncio
import logging
from playwright.async_api import async_playwright
from utils import try_hosts, login_and_checkin

logging.basicConfig(level=logging.INFO, format="%(message)s")

async def run(email: str, password: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True
        )

        page = await context.new_page()

        for host in try_hosts:
            try:
                login_url = f"{host}/auth/login"
                logging.info(f"[+] 打开登录页: {login_url}")
                await page.goto(login_url, timeout=60000)

                try:
                    # Cloudflare页面绕过处理：等待表单加载
                    await page.wait_for_selector("form", timeout=15000)
                except Exception as e:
                    logging.warning("[-] 页面加载超时，可能卡在 Cloudflare 验证页")
                    content = await page.content()
                    logging.warning(f"[!] 页面内容预览（前1000字）：\n{content[:1000]}")
                    continue  # 尝试下一个 host

                success = await login_and_checkin(page, email, password)
                if success:
                    break

            except Exception as e:
                logging.warning(f"[!] 尝试 {host} 失败：{str(e)}")

        await browser.close()

if __name__ == "__main__":
    import os

    email = os.getenv("CORDCLOUD_EMAIL", "")
    password = os.getenv("CORDCLOUD_PASSWORD", "")

    if not email or not password:
        raise ValueError("请设置环境变量 CORDCLOUD_EMAIL 和 CORDCLOUD_PASSWORD")

    asyncio.run(run(email, password))

