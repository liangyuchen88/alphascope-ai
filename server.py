import argparse,json,mimetypes,os,traceback
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from data_service import prices,summary,overview,macro,news,ASSETS
from engine import backtest,indicators
ROOT=Path(__file__).parent
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u=urlparse(self.path);q=parse_qs(u.query);get=lambda k,d=None:q.get(k,[d])[0]
        try:
            if u.path=='/api/health':return self.send_json({'status':'ok'})
            if u.path=='/api/overview':return self.send_json(overview())
            if u.path=='/api/asset':
                d=prices(get('symbol','SPY').upper(),get('refresh')=='1')
                if 'rows' not in d:return self.send_json(d,503)
                x=indicators([r['close'] for r in d['rows']]);rows=[]
                for i,r in enumerate(d['rows']):
                    rows.append(r|{k:None if __import__('pandas').isna(x[k].iloc[i]) else float(x[k].iloc[i]) for k in ['sma20','sma60','rsi','volatility','momentum']})
                return self.send_json(d|{'rows':rows,'summary':summary(d)})
            if u.path=='/api/backtest':
                symbol=get('symbol','SPY').upper();d=prices(symbol)
                if 'rows' not in d:return self.send_json(d,503)
                result=backtest(d['rows'],get('strategy','trend'),float(get('fee','5')),float(get('slippage','5')),get('period','test'))
                return self.send_json(result|{'source':{k:v for k,v in d.items() if k!='rows'},'symbol':symbol,'strategy':get('strategy','trend')})
            if u.path=='/api/news':return self.send_json(news())
            if u.path=='/api/macro':return self.send_json(macro())
            if u.path=='/api/universe':return self.send_json(ASSETS)
            path=ROOT/'static'/('index.html' if u.path=='/' else u.path.lstrip('/'))
            if not path.resolve().is_relative_to((ROOT/'static').resolve()) or not path.is_file():return self.send_json({'error':'Not found'},404)
            data=path.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(path))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        except (ValueError,TypeError) as e:self.send_json({'error':str(e)},400)
        except Exception as e:traceback.print_exc();self.send_json({'error':str(e)},500)
    def send_json(self,obj,status=200):
        data=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=int(os.environ.get('PORT','8765')));a=p.parse_args();print(f'AlphaScope http://127.0.0.1:{a.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
