import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36'

SITE_SELECTORS = {
    'bbc.com': ['article', '[data-component="text-block"]'],
    'bbc.co.uk': ['article', '[data-component="text-block"]'],
    'rfi.fr': ['article', 'main'],
    'dw.com': ['article', 'main'],
    'voachinese.com': ['article', 'main'],
    'voanews.com': ['article', 'main'],
    'nytimes.com': ['section[name="articleBody"]', 'article'],
    'udn.com': ['article', 'main'],
    'zaobao.com.sg': ['article', 'main'],
    'mingpao.com': ['article', 'main'],
    'asahi.com': ['article', 'main'],
    'kyodonews.net': ['article', 'main'],
    'cna.com.tw': ['article', 'main'],
}

BAD_RE = re.compile(r'^(导航|菜单|分享|广告|推荐|相关阅读|热门|登录|注册|订阅|版权|免责声明)', re.I)

def host_matches(host, domain):
    return host == domain or host.endswith('.' + domain)

def clean_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_from_container(node):
    if not node:
        return ''
    for bad in node.select('script,style,noscript,nav,footer,header,form,aside,figure,figcaption,button,svg'):
        bad.decompose()
    paragraphs=[]
    for p in node.select('p'):
        t=clean_text(p.get_text(' ', strip=True))
        if len(t)>=20 and not BAD_RE.match(t):
            paragraphs.append(t)
    if len(paragraphs)>=2:
        out=[]
        seen=set()
        for p in paragraphs:
            if p not in seen:
                seen.add(p); out.append(p)
        return '\n\n'.join(out)
    return clean_text(node.get_text(' ', strip=True))

def extract_article(url):
    r=requests.get(url, headers={'User-Agent':UA,'Accept-Language':'zh-CN,zh;q=0.9,en;q=0.8'}, timeout=25, allow_redirects=True)
    r.raise_for_status()
    soup=BeautifulSoup(r.text, 'lxml')
    host=urlparse(r.url).netloc.lower().split(':')[0]
    for bad in soup.select('script,style,noscript,nav,footer,header,form,aside')[:]:
        bad.decompose()
    selectors=[]
    for domain, sels in SITE_SELECTORS.items():
        if host_matches(host, domain):
            selectors=sels; break
    for sel in selectors:
        node=soup.select_one(sel)
        text=extract_from_container(node)
        if len(text)>=300:
            return text, r.url
    for sel in ['article','main','[role="main"]']:
        node=soup.select_one(sel)
        text=extract_from_container(node)
        if len(text)>=300:
            return text, r.url
    candidates=soup.find_all(['div','section'])
    best=''
    for node in candidates:
        ps=node.find_all('p')
        if len(ps)<3: continue
        text='\n\n'.join(clean_text(p.get_text(' ',strip=True)) for p in ps if len(clean_text(p.get_text(' ',strip=True)))>=20)
        if len(text)>len(best): best=text
    if len(best)>=300:
        return best, r.url
    raise RuntimeError('未找到足够的公开正文；可能是登录墙、付费墙、robots 或页面结构不兼容')