import asyncio
from playwright.async_api import async_playwright


async def run(email, passwd, code='', host='https://cordcloud.us'):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"[+] 打开登录页: {host}/auth/login")
        await page.goto(f'{host}/auth/login', timeout=60000)
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(5)

        print("[+] 填写表单并登录")
        await page.fill('input[name="email"]', email)
        await page.fill('input[name="passwd"]', passwd)
        if code:
            await page.fill('input[name="code"]', code)
        await page.click('button[type="submit"]')

        await page.wait_for_url(f'{host}/user', timeout=15000)
        print("[+] 登录成功，开始签到")

        await page.goto(f'{host}/user/checkin', timeout=60000)
        content = await page.content()
        if 'msg' in content or '成功' in content:
            print("✔️ 签到成功")
        else:
            print("⚠️ 签到失败，页面内容可能有变化")

        await browser.close()


if __name__ == '__main__':
    import os
    asyncio.run(run(
        email=os.getenv("CORDCLOUD_EMAIL"),
        passwd=os.getenv("CORDCLOUD_PASSWD"),
        code=os.getenv("CORDCLOUD_CODE", ''),
        host=os.getenv("CORDCLOUD_HOST", 'https://cordcloud.us')
    ))
