import re
import time
import cloudscraper
import execjs
from typing import Tuple
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logger = logging.getLogger(__name__)

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
            # 禁用 SSL 警告
            interpreter='nodejs'
        )
        self.timeout = 20  # 增加超时时间
        self.retry_count = 3  # 重试次数
    
    def format_url(self, path) -> str:
        return f'https://{self.host}/{path}'
    
    def _handle_cloudflare(self):
        """处理 Cloudflare 防护"""
        for attempt in range(self.retry_count):
            try:
                logger.info(f"尝试通过 Cloudflare 防护 (尝试 {attempt+1}/{self.retry_count})")
                
                # 访问登录页面触发 Cloudflare 验证
                login_page = self.format_url('auth/login')
                resp = self.scraper.get(login_page, timeout=self.timeout)
                
                # 检查是否需要处理 Cloudflare 挑战
                if resp.status_code == 403 or "jschl_vc" in resp.text:
                    return self._solve_cloudflare_challenge(resp.text)
                elif resp.status_code == 200:
                    logger.info("已通过 Cloudflare 防护")
                    return True
            except Exception as e:
                logger.error(f"Cloudflare 处理失败: {str(e)}")
        
        return False
    
    def _solve_cloudflare_challenge(self, html):
        """解决 Cloudflare 的 JavaScript 挑战"""
        try:
            logger.info("开始处理 Cloudflare JavaScript 挑战")
            
            # 使用更健壮的正则表达式匹配
            jschl_vc_match = re.search(r'name="jschl_vc"\s+value="(\w+)"', html)
            pass_field_match = re.search(r'name="pass"\s+value="(.+?)"', html)
            
            if not jschl_vc_match or not pass_field_match:
                logger.warning("无法提取 Cloudflare 挑战参数")
                return False
                
            jschl_vc = jschl_vc_match.group(1)
            pass_field = pass_field_match.group(1)
            
            # 提取 JavaScript 计算逻辑
            js_script_match = re.search(
                r'setTimeout\(function\(\)\s*{\s+(.*?a\.value\s*=.+?)\s*;',
                html, re.DOTALL
            )
            
            if not js_script_match:
                logger.warning("无法提取 Cloudflare JavaScript 挑战代码")
                return False
                
            js_script = js_script_match.group(1)
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
            logger.info(f"计算出的 Cloudflare 挑战答案: {answer}")
            
            # 构造验证 URL
            verify_url = f"https://{self.host}/cdn-cgi/l/chk_jschl?jschl_vc={jschl_vc}&pass={pass_field}&jschl_answer={answer}"
            
            # 等待 4 秒 (Cloudflare 要求)
            logger.info("等待 Cloudflare 挑战时间...")
            time.sleep(5)
            
            # 发送验证请求
            response = self.scraper.get(verify_url, timeout=self.timeout)
            if response.status_code == 200:
                logger.info("Cloudflare 挑战通过成功")
                return True
            else:
                logger.warning(f"Cloudflare 挑战验证失败: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Cloudflare 挑战解决失败: {str(e)}")
            return False
    
    def login(self) -> dict:
        # 首先处理 Cloudflare 防护
        if not self._handle_cloudflare():
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
                json_response = response.json()
                return json_response
            except:
                # 如果 JSON 解析失败，返回原始文本
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
            html = response.text
            
            # 使用更健壮的正则表达式解析流量信息
            patterns = [
                r'<span class="traffic-info">今日已用</span>.*?<code[^>]*>(.*?)</code>',
                r'<span class="traffic-info">过去已用</span>.*?<code[^>]*>(.*?)</code>',
                r'<span class="traffic-info">剩余流量</span>.*?<code[^>]*>(.*?)</code>'
            ]
            
            results = []
            for pattern in patterns:
                match = re.search(pattern, html, re.S)
                # 修复括号未闭合的问题
                if match:
                    results.append(match.group(1))
                else:
                    results.append(None)
            
            if all(results):
                logger.info("成功获取流量信息")
                return tuple(results)
            
            logger.warning("部分流量信息获取失败")
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
