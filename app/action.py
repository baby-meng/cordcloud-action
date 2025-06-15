import re
from typing import Tuple
import cloudscraper  # 用于绕过 Cloudflare 验证
import urllib3

urllib3.disable_warnings()

class Action:
    def __init__(self, email: str, passwd: str, code: str = '', host: str = 'cordcloud.us'):
        self.email = email
        self.passwd = passwd
        self.code = code
        self.host = host.replace('https://', '').replace('http://', '').strip()
        self.session = cloudscraper.create_scraper()  # 自动绕过 Cloudflare
        self.timeout = 6

    def format_url(self, path) -> str:
        return f'https://{self.host}/{path}'

    def login(self) -> dict:
        login_url = self.format_url('auth/login')
        form_data = {'email': self.email, 'passwd': self.passwd, 'code': self.code}
        response = self.session.post(login_url, data=form_data, timeout=self.timeout)
        return response.json()

    def check_in(self) -> dict:
        check_in_url = self.format_url('user/checkin')
        response = self.session.post(check_in_url, timeout=self.timeout)
        return response.json()

    def info(self) -> Tuple:
        user_url = self.format_url('user')
        html = self.session.get(user_url, timeout=self.timeout).text
        today_used = re.search(
            r'<span class="traffic-info">今日已用</span>.*?<code.*?>(.*?)</code>',
            html, re.S)
        total_used = re.search(
            r'<span class="traffic-info">过去已用</span>.*?<code.*?>(.*?)</code>',
            html, re.S)
        rest = re.search(
            r'<span class="traffic-info">剩余流量</span>.*?<code.*?>(.*?)</code>',
            html, re.S)

        if today_used and total_used and rest:
            return today_used.group(1), total_used.group(1), rest.group(1)
        return ()

    def run(self):
        self.login()
        self.check_in()
        return self.info()
