import concurrent.futures,datetime as dt,hashlib,json,os,re,threading,time,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
from engine import indicators
ROOT=Path(__file__).parent; CACHE=ROOT/'data';CACHE.mkdir(exist_ok=True)
ASSETS={'SPY':('美國大盤','指數'),'QQQ':('那斯達克 100','指數'),'AAPL':('Apple','科技'),'MSFT':('Microsoft','科技'),'NVDA':('NVIDIA','半導體'),'AMZN':('Amazon','消費'),'GOOGL':('Alphabet','通訊'),'META':('Meta','通訊'),'TSLA':('Tesla','消費'),'JPM':('JPMorgan','金融'),'XOM':('Exxon Mobil','能源'),'GLD':('黃金 ETF · PROXY','商品代理'),'USO':('原油 ETF · PROXY','商品代理'),'TLT':('長天期美債','債券'),'XLK':('科技','產業'),'XLF':('金融','產業'),'XLE':('能源','產業'),'XLV':('醫療','產業'),'XLI':('工業','產業'),'XLY':('非必需消費','產業'),'XLP':('必需消費','產業'),'XLU':('公用事業','產業'),'XLRE':('不動產','產業'),'XLB':('原物料','產業'),'XLC':('通訊服務','產業')}
lock=threading.RLock()
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def download(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 AlphaScope-Research/1.0'}),timeout=12) as r: return r.read()
def cached(key,loader,refresh=False):
    path=CACHE/(key+'.json')
    with lock:
        old=json.loads(path.read_text()) if path.exists() else None
    if old and not refresh and time.time()-path.stat().st_mtime<21600: return dict(old,cache_status='cached')
    try:
        value=loader();value['retrieved_at']=now()
        with lock: path.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False))
        return dict(value,cache_status='fresh')
    except Exception as e:
        if old: return dict(old,cache_status='stale',fetch_error=type(e).__name__+': '+str(e)[:160])
        return {'error':type(e).__name__+': '+str(e)[:160],'status':'unavailable','retrieved_at':None}
def prices(symbol,refresh=False):
    if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}',symbol): raise ValueError('Invalid symbol')
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=10y&interval=1d'
    def load():
        raw=json.loads(download(url)); x=raw['chart']['result'][0]; q=x['indicators']['quote'][0]; adj=x['indicators'].get('adjclose',[{}])[0].get('adjclose'); rows=[]
        for i,t in enumerate(x['timestamp']):
            # Only completed daily bars; timestamps are exchange-local calendar dates.
            zone=ZoneInfo(x['meta'].get('exchangeTimezoneName','America/New_York'))
            date=dt.datetime.fromtimestamp(t,zone).date()
            if date>=dt.datetime.now(zone).date(): continue
            c=(adj[i] if adj else q['close'][i])
            if c is None or c<=0: continue
            rows.append({'date':date.isoformat(),'close':float(c),'volume':q.get('volume',[None]*len(x['timestamp']))[i]})
        if len(rows)<2: raise ValueError('No completed bars')
        return {'symbol':symbol,'name':ASSETS.get(symbol,(symbol,'自選'))[0],'category':ASSETS.get(symbol,('','自選'))[1],'rows':rows,'provider':'Yahoo Finance chart API','url':f'https://finance.yahoo.com/quote/{symbol}/history/','request_url':url,'frequency':'daily','currency':x['meta'].get('currency','USD'),'timezone':x['meta'].get('exchangeTimezoneName'),'adjustment':'供應商調整收盤價（股息／拆股）' if adj else '未調整收盤價；非總報酬','caveat':'可能延遲、修訂；個人研究用途，非交易所即時報價。GLD／USO 為 ETF，非期貨損益。','sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()}
    return cached('price_'+symbol,load,refresh)
def summary(data):
    if 'rows' not in data:return data
    rows=data['rows'];p=[r['close'] for r in rows];x=indicators(p).iloc[-1]
    def number(v): return None if pd.isna(v) else float(v)
    age=(dt.datetime.now(dt.timezone.utc).date()-dt.date.fromisoformat(rows[-1]['date'])).days
    return {k:v for k,v in data.items() if k!='rows'}|{'last':p[-1],'date':rows[-1]['date'],'change':p[-1]/p[-2]-1,'month_return':p[-1]/p[-22]-1 if len(p)>21 else None,'rsi':number(x.rsi),'volatility':number(x.volatility),'sma20':number(x.sma20),'sma60':number(x.sma60),'momentum':number(x.momentum),'stale':age>5 or data.get('cache_status')=='stale','age_days':age,'spark':[r['close'] for r in rows[-40:]]}
def macro(refresh=False):
    series=['DFF','DGS2','DGS10','DFII10']
    def one(s):
        url=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}&cosd=2020-01-01'
        def load():
            import io
            frame=pd.read_csv(io.BytesIO(download(url)));frame.columns=['date','value'];frame.value=pd.to_numeric(frame.value,errors='coerce');frame=frame.dropna()
            if frame.empty:raise ValueError('Empty FRED series')
            return {'series':s,'provider':'FRED / Federal Reserve H.15','url':f'https://fred.stlouisfed.org/series/{s}','frequency':'daily','units':'percent','rows':frame.to_dict('records'),'caveat':'觀測日非發布時間；最新修訂版本，不作歷史交易訊號。'}
        return s,cached('macro_'+s,load,refresh)
    return dict(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(one,series))
def news(refresh=False):
    url='https://www.federalreserve.gov/feeds/press_monetary.xml'
    def load():
        root=ET.fromstring(download(url));items=[]
        for e in root.findall('.//item')[:15]:
            link=e.findtext('link','')
            if not link.startswith('https://www.federalreserve.gov/'):continue
            items.append({'title':e.findtext('title',''),'url':link,'published':e.findtext('pubDate',''),'source':'Federal Reserve','scope':'貨幣政策／利率','interpretation':'官方政策發布；請閱讀原文。此新聞不納入歷史回測訊號。'})
        if not items: raise ValueError('No RSS entries')
        return {'provider':'Federal Reserve official RSS','url':url,'items':items,'caveat':'僅官方政策新聞；未涵蓋所有企業／商品事件。無生成式 AI 摘要。'}
    return cached('news',load,refresh)
def overview():
    def one(s):return summary(prices(s))|{'symbol':s,'name':ASSETS[s][0],'category':ASSETS[s][1]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool: assets=list(pool.map(one,ASSETS))
    return {'assets':assets,'macro':macro(),'news':news(),'generated_at':now(),'mode':'REAL DATA / 真實來源；缺資料不補值'}
