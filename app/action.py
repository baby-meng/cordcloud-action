import re
import time
import cloudscraper
import execjs
from typing import Tuple

class Action:
    def __init__(self, email: str, passwd: str, code: str = '', host: str = 'cordcloud.us'):
        self.email = email
        self.passwd = passwd
        self.code = code
        self.host = host.replace('https://', '').replace('http://', '').strip()
        
        # 使用 cloudscraper 代替 requests
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.timeout = 15  # 增加超时时间
    
    def format_url(self, path) -> str:
        return f'https://{self.host}/{path}'
    
    def _handle_cloudflare(self):
        """处理 Cloudflare 防护"""
        try:
            # 访问登录页面触发 Cloudflare 验证
            login_page = self.format_url('auth/login')
            resp = self.scraper.get(login_page, timeout=self.timeout)
            
            # 检查是否需要处理 Cloudflare 挑战
            if resp.status_code == 403 or "jschl_vc" in resp.text:
                self._solve_cloudflare_challenge(resp.text)
                
                # 重新请求登录页面确保通过验证
                self.scraper.get(login_page, timeout=self.timeout)
                return True
        except Exception as e:
            print(f"Cloudflare处理失败: {str(e)}")
        return False
    
    def _solve_cloudflare_challenge(self, html):
        """解决 Cloudflare 的 JavaScript 挑战"""
        try:
            # 提取必要的验证参数
            jschl_vc = re.search(r'name="jschl_vc" value="(\w+)"', html).group(1)
            pass_field = re.search(r'name="pass" value="(.+?)"', html).group(1)
            
            # 提取 JavaScript 计算逻辑
            js_script = re.search(r'setTimeout\(function\(\){\s+(.*?a\.value\s*=.+?)\s+;', html, re.DOTALL).group(1)
            js_script = re.sub(r"a\.value\s*=\s*(.+?);", r"\1", js_script)
            js_script = re.sub(r"t\s*=\s*document\.createElement\('div'\);.*?}\s*", "", js_script, flags=re.DOTALL)
            
            # 使用 execjs 执行 JavaScript 计算
            ctx = execjs.compile(f"""
                function solveChallenge() {{
                    {js_script}
                    return a;
                }}
            """)
            result = ctx.call("solveChallenge")
            
            # 计算最终答案 (需要加上域名的长度)
            answer = float(result) + len(self.host)
            
            # 构造验证 URL
            verify_url = f"https://{self.host}/cdn-cgi/l/chk_jschl?jschl_vc={jschl_vc}&pass={pass_field}&jschl_answer={answer}"
            
            # 等待 4 秒 (Cloudflare 要求)
            time.sleep(4)
            
            # 发送验证请求
            self.scraper.get(verify_url, timeout=self.timeout)
            return True
        except Exception as e:
            raise Exception(f"Cloudflare挑战解决失败: {str(e)}")
    
    def login(self) -> dict:
        # 首先处理 Cloudflare 防护
        self._handle_cloudflare()
        
        login_url = self.format_url('auth/login')
        form_data = {
            'email': self.email,
            'passwd': self.passwd + self.code
        }
        try:
            response = self.scraper.post(login_url, data=form_data, timeout=self.timeout)
            return response.json()
        except Exception as e:
            return {"ret": 0, "msg": f"登录请求失败: {str(e)}"}
    
    def check_in(self) -> dict:
        check_in_url = self.format_url('user/checkin')
        try:
            response = self.scraper.post(check_in_url, timeout=self.timeout)
            return response.json()
        except Exception as e:
            return {"ret": 0, "msg": f"签到请求失败: {str(e)}"}
    
    def info(self) -> Tuple:
        user_url = self.format_url('user')
        try:
            response = self.scraper.get(user_url)
            html = response.text
            
            # 使用正则表达式解析流量信息
            today_used = re.search(
                r'<span class="traffic-info">今日已用</span>(.*?)<code class="card-tag tag-red">(.*?)</code>',
                html, re.S
            )
            total_used = re.search(
                r'<span class="traffic-info">过去已用</span>(.*?)<code class="card-tag tag-orange">(.*?)</code>',
                html, re.S
            )
            rest = re.search(
                r'<span class="traffic-info">剩余流量</span>(.*?)<code class="card-tag tag-green" id="remain">(.*?)</code>',
                html, re.S
            )
            
            if today_used and total_used and rest:
                return today_used.group(2), total_used.group(2), rest.group(2)
            return ()
        except Exception as e:
            print(f"流量信息获取失败: {str(e)}")
            return ()
    
    def run(self):
        self.login()
        self.check_in()
        return self.info()
