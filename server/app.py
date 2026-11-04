"""API local de referência. Não exponha wsgiref à internet."""
import hmac,json,os,secrets
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from agenda import Agenda,AgendaError
from agent import Agent,GeminiIntentParser
from integrations import valid_meta_signature,enqueue_webhook

def create_app(agenda,token,meta_secret='',verify_token='',phone_number_id='',parser=None):
    agent=Agent(agenda,parser)
    def app(env,start_response):
        def response(status,data,plain=False):
            body=(str(data) if plain else json.dumps(data,ensure_ascii=False)).encode()
            start_response(status,[('Content-Type','text/plain; charset=utf-8' if plain else 'application/json; charset=utf-8'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]);return [body]
        path,method=env.get('PATH_INFO',''),env.get('REQUEST_METHOD','GET');query=parse_qs(env.get('QUERY_STRING',''))
        if path=='/health':return response('200 OK',{'status':'ok','mode':'local-pilot','external_send':False})
        try:
            size=int(env.get('CONTENT_LENGTH') or 0)
            if size<0 or size>32768:return response('413 Payload Too Large',{'error':'body_limit'})
            if path=='/webhooks/meta':
                if method=='GET':
                    supplied=query.get('hub.verify_token',[''])[0]
                    if verify_token and hmac.compare_digest(supplied,verify_token) and query.get('hub.mode')==['subscribe']:return response('200 OK',query.get('hub.challenge',[''])[0],True)
                    return response('403 Forbidden',{'error':'verification'})
                if method!='POST':return response('405 Method Not Allowed',{'error':'method'})
                raw=env['wsgi.input'].read(size)
                if not valid_meta_signature(raw,env.get('HTTP_X_HUB_SIGNATURE_256',''),meta_secret):return response('403 Forbidden',{'error':'signature'})
                if not phone_number_id:return response('503 Service Unavailable',{'error':'not_configured'})
                count=enqueue_webhook(agenda,json.loads(raw),phone_number_id)
                return response('200 OK',{'queued':count})
            if not token or not hmac.compare_digest(env.get('HTTP_AUTHORIZATION',''),'Bearer '+token):return response('401 Unauthorized',{'error':'unauthorized'})
            data=json.loads(env['wsgi.input'].read(size) or b'{}') if method=='POST' else {k:v[0] for k,v in query.items()}
            if not isinstance(data,dict):return response('400 Bad Request',{'error':'invalid_json'})
            owner=data.get('owner','')
            if path=='/api/catalog' and method=='GET':return response('200 OK',{'services':agenda.catalog()})
            if path=='/api/availability' and method=='GET':return response('200 OK',{'slots':agenda.slots(data['service'],data.get('professional','demo'),data['date'],owner,data.get('replace_id'))})
            if not isinstance(owner,str) or not owner:return response('400 Bad Request',{'error':'owner_required'})
            if path=='/api/bookings' and method=='GET':return response('200 OK',{'bookings':agenda.mine(owner)})
            if path=='/api/bookings' and method=='POST':return response('200 OK',agenda.book(owner,data['service'],data.get('professional','demo'),data['date'],data['time'],data['key'],data.get('confirmed'),data.get('replace_id')))
            if path=='/api/cancel' and method=='POST':
                if data.get('confirmed') is not True:return response('400 Bad Request',{'error':'confirmation_required'})
                return response('200 OK',agenda.cancel(owner,data['booking_id']))
            if path=='/api/agent' and method=='POST':return response('200 OK',{'reply':agent.handle(owner,data['text'],data['event_id'])})
            if path=='/api/release-handoff' and method=='POST':agenda.save_state(owner,{});return response('200 OK',{'released':True})
            return response('404 Not Found',{'error':'not_found'})
        except AgendaError as e:return response('409 Conflict' if e.code=='conflict' else '400 Bad Request',{'error':e.code,'message':str(e)})
        except (ValueError,KeyError,TypeError):return response('400 Bad Request',{'error':'invalid_request'})
        except Exception:return response('503 Service Unavailable',{'error':'temporarily_unavailable','message':'Não foi possível concluir. Nenhuma nova confirmação foi emitida.'})
    return app
if __name__=='__main__':
    Path('data').mkdir(exist_ok=True)
    agenda=Agenda('data/pilot.sqlite')
    if os.getenv('SEED_DEMO')=='true':agenda.seed_demo()
    token=os.getenv('BACKEND_TOKEN')
    if not token:raise SystemExit('Defina BACKEND_TOKEN no ambiente, com um segredo exclusivo. Não o coloque no navegador.')
    app=create_app(agenda,token,os.getenv('META_APP_SECRET',''),os.getenv('META_VERIFY_TOKEN',''),os.getenv('META_PHONE_NUMBER_ID',''),GeminiIntentParser() if os.getenv('ENABLE_AI')=='true' else None)
    print('Piloto local: http://127.0.0.1:8795. Site estático online não usa esta API.')
    make_server('127.0.0.1',8795,app).serve_forever()
