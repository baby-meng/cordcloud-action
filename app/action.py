import re
from typing import Tuple
import cloudscraper    # 新增
import urllib3

urllib3.disable_warnings()

class Action:
    def __init__(self, email: str, passwd: str, code: str = '', host: str = 'cordcloud.us'):
        self.email = email
        self.passwd = passwd
        self.code = code
        self.host = host.replace('https://', '').replace('http://', '').strip()
        # 使用 cloudscraper 会话，自动处理 Cloudflare 验证:contentReference[oaicite:5]{index=5}
        self.session = cloudscraper.create_scraper()
        self.timeout = 6

    def format_url(self, path) -> str:
        return f'https://{self.host}/{path}'

    def login(self) -> dict:
        login_url = self.format_url('auth/login')
        form_data = {'email': self.email, 'passwd': self.passwd, 'code': self.code}
        return self.session.post(login_url, data=form_data,
                                 timeout=self.timeout, verify=False).json()

    def check_in(self) -> dict:
        check_in_url = self.format_url('user/checkin')
        return self.session.post(check_in_url,
                                 timeout=self.timeout, verify=False).json()

    def info(self) -> Tuple:
        user_url = self.format_url('user')
        html = self.session.get(user_url, verify=False).text
        today_used = re.search(r'<span class="traffic-info">今日已用</span>.*?<code.*?>(.*?)</code>',
                               html, re.S)
        total_used = re.search(r'<span class="traffic-info">过去已用</span>.*?<code.*?>(.*?)</code>',
                                html, re.S)
        rest = re.search(r'<span class="traffic-info">剩余流量</span>.*?<code.*?>(.*?)</code>',
                         html, re.S)
        if today_used and total_used and rest:
            return today_used.group(1), total_used.group(1), rest.group(1)
        return ()

    def run(self):
        self.login()
        self.check_in()
        return self.info()
