import re
import time
import cloudscraper
import execjs
from typing import Tuple
import logging
import json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# 设置日志
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logger = logging.getLogger(__name__)

class CloudflareChallengeSolver:
    """专门处理 Cloudflare 挑战的类"""
    def __init__(self, scraper, host):
        self.scraper = scraper
        self.host = host
        self.timeout = 20
        self.retry_count = 3
    
    def solve(self, html):
        """解决 Cloudflare 挑战"""
        for attempt in range(self.retry_count):
            try:
                logger.info(f"尝试解决 Cloudflare 挑战 (尝试 {attempt+1}/{self.retry_count})")
                
                # 尝试使用 BeautifulSoup 解析
                soup = BeautifulSoup(html, 'html.parser')
                
                # 查找挑战表单
                challenge_form = soup.find('form', id='challenge-form')
                if not challenge_form:
                    logger.warning("未找到挑战表单")
                    return False
                
                # 提取必要参数
                jschl_vc = challenge_form.find('input', {'name': 'jschl_vc'})
                pass_field = challenge_form.find('input', {'name': 'pass'})
                
                if not jschl_vc or not pass_field:
                    logger.warning("无法提取挑战参数")
                    return False
                
                jschl_vc_value = jschl_vc.get('value', '')
                pass_value = pass_field.get('value', '')
                
                # 提取 JavaScript 挑战代码
                script_tag = soup.find('script', text=re.compile(r'setTimeout\(function\(\)'))
                if not script_tag:
                    logger.warning("未找到挑战脚本")
                    return False
                
                script_text = script_tag.string
                return self._solve_javascript_challenge(
                    script_text, 
                    jschl_vc_value, 
                    pass_value
                )
            except Exception as e:
                logger.error(f"挑战解决失败: {str(e)}")
                time.sleep(1)
        
        return False
    
    def _solve_javascript_challenge(self, script_text, jschl_vc, pass_value):
        """解决 JavaScript 挑战"""
        try:
            logger.info("解析 JavaScript 挑战代码")
            
            # 提取计算逻辑
            js_code_match = re.search(
                r'setTimeout\(function\(\)\s*{\s*(.*?a\.value\s*=.+?)\s*;',
                script_text, 
                re.DOTALL
            )
            
            if not js_code_match:
                logger.warning("无法提取挑战计算逻辑")
                return False
                
            js_code = js_code_match.group(1)
            
            # 清理代码
            js_code = re.sub(r"a\.value\s*=\s*(.+?);", r"\1", js_code)
            js_code = re.sub(r"t\s*=\s*document\.createElement\('div'\);.*?}\s*", "", js_code, flags=re.DOTALL)
            
            # 添加域名长度计算
            js_code += f";a = a + {len(self.host)};"
            
            # 使用 execjs 执行计算
            ctx = execjs.compile(f"""
                function solveChallenge() {{
                    {js_code}
                    return a;
                }}
            """)
            result = ctx.call("solveChallenge")
            
            # 构造验证 URL
            verify_url = f"https://{self.host}/cdn-cgi/l/chk_jschl"
            params = {
                'jschl_vc': jschl_vc,
                'pass': pass_value,
                'jschl_answer': result
            }
            
            # 等待 4 秒 (Cloudflare 要求)
            logger.info("等待挑战时间...")
            time.sleep(4)
            
            # 发送验证请求
            response = self.scraper.get(verify_url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                logger.info("Cloudflare 挑战通过成功")
                return True
            else:
                logger.warning(f"挑战验证失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"JavaScript 挑战解决失败: {str(e)}")
            return False


class Action:
    def __init__(self, email: str, passwd: str, code: str = '', host: str = 'cordcloud.us'):
        self.email = email
        self.passwd = passwd
        self.code = code
        self.host = host.replace('https://', '').replace('http://', '').strip()
        
        # 创建 cloudscraper 实例
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            },
            interpreter='nodejs'
        )
        self.timeout = 20
        self.retry_count = 3
    
    def format_url(self, path) -> str:
        return f'https://{self.host}/{path}'
    
    def _handle_cloudflare(self):
        """处理 Cloudflare 防护"""
        login_page = self.format_url('auth/login')
        
        for attempt in range(self.retry_count):
            try:
                logger.info(f"尝试通过 Cloudflare 防护 (尝试 {attempt+1}/{self.retry_count})")
                
                # 访问登录页面
                response = self.scraper.get(login_page, timeout=self.timeout)
                
                # 检查是否需要处理挑战
                if response.status_code == 403 or "jschl_vc" in response.text:
                    logger.info("检测到 Cloudflare 挑战")
                    solver = CloudflareChallengeSolver(self.scraper, self.host)
                    if solver.solve(response.text):
                        return True
                elif response.status_code == 200:
                    logger.info("已通过 Cloudflare 防护")
                    return True
                    
                logger.info("尝试重新请求页面")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Cloudflare 处理失败: {str(e)}")
        
        return False
    
    def login_with_playwright(self):
        """使用 Playwright 处理 Cloudflare 挑战"""
        try:
            logger.info("启动 Playwright 处理 Cloudflare 挑战")
            with sync_playwright() as p:
                # 启动浏览器
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--disable-setuid-sandbox',
                        '--no-sandbox'
                    ]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                page = context.new_page()
                
                # 访问登录页面
                page.goto(f"https://{self.host}/auth/login", wait_until="networkidle")
                
                # 检查是否在登录页面
                if "auth/login" not in page.url:
                    logger.info("已通过 Cloudflare 挑战")
                    return True
                
                # 尝试自动解决挑战
                try:
                    # 等待挑战完成
                    page.wait_for_selector("#challenge-form", timeout=10000)
                    
                    # 检查是否有需要手动解决的挑战
                    if page.is_visible("text=Verify you are human"):
                        logger.warning("需要手动验证，无法自动解决")
                        return False
                    
                    # 等待挑战自动解决
                    page.wait_for_load_state("networkidle", timeout=30000)
                    
                    # 检查是否成功通过挑战
                    if "auth/login" in page.url:
                        logger.info("成功通过 Cloudflare 挑战")
                        return True
                    
                    return False
                except Exception as e:
                    logger.error(f"Playwright 挑战处理失败: {str(e)}")
                    return False
                finally:
                    browser.close()
        except Exception as e:
            logger.error(f"Playwright 启动失败: {str(e)}")
            return False
    
    def login(self) -> dict:
        # 首先处理 Cloudflare 防护
        if not self._handle_cloudflare():
            # 如果标准方法失败，尝试使用 Playwright
            logger.info("尝试使用 Playwright 解决 Cloudflare")
            if not self.login_with_playwright():
                return {"ret": 0, "msg": "无法通过 Cloudflare 防护"}
        
        login_url = self.format_url('auth/login')
        form_data = {
            'email': self.email,
            'passwd': self.passwd + self.code
        }
        
        try:
            logger.info(f"正在登录: {self.email}")
            response = self.scraper.post(login_url, data=form_data, timeout=self.timeout)
            
            # 尝试解析 JSON 响应
            try:
                return response.json()
            except json.JSONDecodeError:
                return {
                    "ret": 0,
                    "msg": f"响应解析失败: {response.text[:200] if response.text else '空响应'}"
                }
        except Exception as e:
            return {"ret": 0, "msg": f"登录请求失败: {str(e)}"}
    
    def check_in(self) -> dict:
        check_in_url = self.format_url('user/checkin')
        try:
            logger.info("正在尝试签到")
            response = self.scraper.post(check_in_url, timeout=self.timeout)
            return response.json()
        except Exception as e:
            return {"ret": 0, "msg": f"签到请求失败: {str(e)}"}
    
    def info(self) -> Tuple:
        user_url = self.format_url('user')
        try:
            logger.info("正在获取账户信息")
            response = self.scraper.get(user_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 使用 BeautifulSoup 解析流量信息
            traffic_divs = soup.select('.traffic-info')
            results = []
            
            for div in traffic_divs:
                value_tag = div.find_next('code')
                if value_tag:
                    results.append(value_tag.get_text(strip=True))
                else:
                    results.append(None)
            
            if len(results) >= 3:
                return tuple(results[:3])
            return ()
        except Exception as e:
            logger.error(f"流量信息获取失败: {str(e)}")
            return ()
    
    def run(self):
        login_result = self.login()
        if login_result.get('ret') != 1:
            return login_result
        
        check_in_result = self.check_in()
        traffic_info = self.info()
        
        return {
            "login": login_result,
            "check_in": check_in_result,
            "traffic_info": traffic_info
        }
