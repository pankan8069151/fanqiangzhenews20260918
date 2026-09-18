import os, sys, json, re, html, smtplib
from datetime import datetime, timedelta, time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
from article_extractor import extract_article

BASE_URL='https://www.fanqiangzhe.com/news/'
TZ=ZoneInfo('Asia/Shanghai')
DATA='data'
PENDING=os.path.join(DATA,'pending.json')
SENT=os.path.join(DATA,'sent.json')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36'

def now_cn(): return datetime.now(TZ)
def load(path):
    if not os.path.exists(path): return []
    try:
        with open(path,'r',encoding='utf-8') as f: return json.load(f)
    except Exception: return []

def save(path,obj):
    os.makedirs(DATA,exist_ok=True)
    tmp=path+'.tmp'
    with open(tmp,'w',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False,indent=2)
    os.replace(tmp,path)

def normalize_url(url):
    p=urlsplit(url)
    qs=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not (k.lower().startswith('utm_') or k.lower() in {'fbclid','gclid'})]
    return urlunsplit((p.scheme,p.netloc,p.path,urlencode(qs),''))

def category(title):
    rules=[
      ('军事','战争|军事|导弹|军方|武器|舰|俄乌|乌克兰|俄罗斯|北约|伊朗|以色列'),
      ('中美','中国|美国|中美|特朗普|白宫|华盛顿|北京|关税|芯片'),
      ('日本','日本|东京|日元|自卫队|石破|高市'),
      ('财经','经济|股市|金融|银行|通胀|通货膨胀|美联储|央行|人民币|美元|欧元'),
      ('科技','科技|人工智能|AI|芯片|OpenAI|微软|苹果|谷歌|Meta|英伟达'),
      ('国际','欧洲|法国|德国|英国|韩国|印度|联合国|国际|外交'),
    ]
    for name,pat in rules:
        if re.search(pat,title,re.I): return name
    return '其他'

def parse_news(html_text):
    soup=BeautifulSoup(html_text,'lxml')
    found=[]
    date_re=re.compile(r'20\d{2}年\d{1,2}月\d{1,2}日')
    for a in soup.find_all('a',href=True):
        title=' '.join(a.get_text(' ',strip=True).split())
        if len(title)<6: continue
        href=a.get('href')
        if href.startswith('/'): url='https://www.fanqiangzhe.com'+href
        elif href.startswith('http'): url=href
        else: continue
        url=normalize_url(url)
        if 'fanqiangzhe.com/news' in url: continue
        parent=a.parent
        context=' '.join(parent.get_text(' ',strip=True).split()) if parent else title
        grand=parent.parent if parent else None
        if grand: context+=' '+' '.join(grand.get_text(' ',strip=True).split())
        m=date_re.search(context)
        if not m: continue
        pub=m.group(0)
        source=''
        sm=re.search(r'[（(]\s*([^（）()]{1,30})\s*[）)]\s*$',title)
        if sm: source=sm.group(1).strip()
        found.append({'title':title,'url':url,'published_date':pub,'source':source})
    unique={}
    for x in found: unique[x['url']]=x
    return list(unique.values())

def bucket_date(first_seen):
    dt=datetime.fromisoformat(first_seen).astimezone(TZ)
    d=dt.date()
    if dt.time()>=time(18,30): d+=timedelta(days=1)
    return d.isoformat()

def scrape():
    r=requests.get(BASE_URL,headers={'User-Agent':UA,'Accept-Language':'zh-CN,zh;q=0.9'},timeout=30)
    r.raise_for_status()
    items=parse_news(r.text)
    pending=load(PENDING); sent=load(SENT)
    known={x.get('url') for x in pending}|{x.get('url') for x in sent}
    first_run=not pending and not sent
    today=now_cn().date().isoformat()
    added=0
    for item in items:
        if item['url'] in known: continue
        if first_run and item['published_date']!=f'{now_cn().year}年{now_cn().month}月{now_cn().day}日': continue
        seen=now_cn().isoformat(timespec='seconds')
        rec={**item,'first_seen_at':seen,'bucket_date':bucket_date(seen),'category':category(item['title']),'content':'','content_ok':False}
        try:
            text,final_url=extract_article(item['url'])
            rec['content']=text; rec['content_ok']=True; rec['url']=normalize_url(final_url)
        except Exception as e:
            rec['extract_error']=str(e)
            rec['content']=item['title']
        pending.append(rec); known.add(item['url']); added+=1
    save(PENDING,pending)
    print(f'发现 {len(items)} 条，新增 {added} 条，待发送 {len(pending)} 条')

def make_email(items,day):
    groups={}
    for x in items: groups.setdefault(x.get('category','其他'),[]).append(x)
    order=['中美','国际','日本','财经','科技','军事','其他']
    body=['<html><body style="font-family:Arial,"Microsoft YaHei",sans-serif">',f'<h2>翻墙者新闻日报｜{day}</h2>',f'<p>共 {len(items)} 条。正文仅来自公开可访问页面；受访问限制的文章保留原文链接。</p>']
    for cat in order:
        if cat not in groups: continue
        body.append(f'<h3>{html.escape(cat)}（{len(groups[cat])}）</h3>')
        for x in groups[cat]:
            body.append(f'<h4>{html.escape(x["title"])}</h4>')
            body.append(f'<p>来源：{html.escape(x.get("source") or "未知")}　日期：{html.escape(x.get("published_date", ""))}</p>')
            if x.get('content_ok'):
                paras=[html.escape(p.strip()) for p in x['content'].split('\n') if p.strip()]
                body.append('<div>'+''.join('<p>'+p+'</p>' for p in paras)+'</div>')
            else:
                body.append('<p>未能自动取得公开正文，可能存在登录、付费、robots 或页面结构限制。</p>')
            body.append(f'<p><a href="{html.escape(x["url"],quote=True)}">查看原文</a></p><hr>')
    body.append('</body></html>')
    return ''.join(body)

def digest():
    user=os.getenv('SMTP_USER'); password=os.getenv('SMTP_PASSWORD'); to=os.getenv('MAIL_TO') or user
    if not user or not password or not to: raise RuntimeError('缺少 SMTP_USER / SMTP_PASSWORD / MAIL_TO Secrets')
    day=now_cn().date().isoformat(); pending=load(PENDING)
    items=[x for x in pending if x.get('bucket_date')==day]
    if not items:
        print(f'{day} 没有待发送新闻，不发空邮件'); return
    msg=MIMEMultipart('alternative'); msg['Subject']=f'翻墙者新闻日报｜{day}｜{len(items)}条'; msg['From']=user; msg['To']=to
    msg.attach(MIMEText(make_email(items,day),'html','utf-8'))
    with smtplib.SMTP_SSL('smtp.qq.com',465,timeout=30) as s:
        s.login(user,password); s.sendmail(user,[to],msg.as_string())
    sent=load(SENT); sent_urls={x.get('url') for x in sent}
    for x in items:
        if x.get('url') not in sent_urls: sent.append(x); sent_urls.add(x.get('url'))
    pending=[x for x in pending if x.get('bucket_date')!=day]
    save(SENT,sent); save(PENDING,pending)
    print(f'日报已发送：{len(items)} 条')

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in {'scrape','digest'}: raise SystemExit('用法：python news_monitor.py scrape|digest')
    scrape() if sys.argv[1]=='scrape' else digest()