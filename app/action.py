from playwright.sync_api import sync_playwright

class Action:
    def login_with_playwright(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # 访问登录页面
            page.goto(f"https://{self.host}/auth/login", wait_until="networkidle")
            
            # 填写登录表单
            page.fill("input[name=email]", self.email)
            page.fill("input[name=passwd]", self.passwd + self.code)
            page.click("button[type=submit]")
            
            # 等待登录完成
            try:
                page.wait_for_selector("#checkin-div", timeout=15000)
            except:
                # 检查是否已登录
                if "auth/login" in page.url:
                    return {"ret": 0, "msg": "登录失败"}
            
            # 获取登录后的 cookies
            cookies = page.context.cookies()
            browser.close()
            
            # 将 cookies 设置到 session
            for cookie in cookies:
                self.scraper.cookies.set(
                    cookie['name'], 
                    cookie['value'],
                    domain=cookie['domain'],
                    path=cookie['path']
                )
            
            return {"ret": 1, "msg": "登录成功"}
    
    def login(self) -> dict:
        try:
            return self.login_with_playwright()
        except Exception as e:
            return {"ret": 0, "msg": f"Playwright 登录失败: {str(e)}"}
