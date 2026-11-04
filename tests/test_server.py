import io,json,sys,tempfile,unittest,hashlib,hmac
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from agenda import Agenda,AgendaError,TZ
from agent import Agent
from app import create_app
from integrations import valid_meta_signature,enqueue_webhook
class TestAgenda(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'data';root.mkdir(exist_ok=True);self.tmp=tempfile.TemporaryDirectory(dir=root);self.a=Agenda(Path(self.tmp.name)/'a.sqlite',lambda:datetime(2026,10,26,8,tzinfo=TZ));self.a.seed_demo()
    def tearDown(self):
        root=(Path(__file__).resolve().parents[1]/'data').resolve()
        assert Path(self.tmp.name).resolve().is_relative_to(root)
        self.tmp.cleanup()
    def book(self,owner='a',time='09:00',key='one',**kw):return self.a.book(owner,'corte','demo','2026-10-27',time,key,confirmed=True,**kw)
    def test_idempotency(self):
        self.assertEqual(self.book(),self.book());self.assertEqual(len(self.a.mine('a')),1)
        with self.assertRaises(AgendaError):self.book(time='11:00')
    def test_confirmation(self):
        with self.assertRaises(AgendaError):self.a.book('a','corte','demo','2026-10-27','09:00','one')
        self.assertEqual(self.a.mine('a'),[])
    def test_parallel_collision(self):
        def attempt(i):
            try:self.book(owner=str(i),key=str(i));return True
            except AgendaError as e:self.assertEqual(e.code,'conflict');return False
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(attempt,range(8)))
        self.assertEqual(sum(results),1)
    def test_overlap_and_adjacency(self):
        self.a.book('a','combo','demo','2026-10-27','09:00','one',True)
        with self.assertRaises(AgendaError):self.book(owner='b',time='09:30',key='two')
        self.book(owner='b',time='10:00',key='three')
    def test_owner_and_cancel(self):
        r=self.book()
        with self.assertRaises(AgendaError):self.a.cancel('other',r['id'])
        self.assertEqual(self.a.mine('other'),[])
        self.a.cancel('a',r['id']);self.assertIn('09:00',self.a.slots('corte','demo','2026-10-27'))
    def test_atomic_reschedule(self):
        r=self.book();self.book(owner='b',time='10:00',key='two')
        with self.assertRaises(AgendaError):self.book(time='10:00',key='three',replace_id=r['id'])
        self.assertIn('09:00',datetime.fromtimestamp(self.a.mine('a')[0]['start_at'],TZ).isoformat())
        moved=self.book(time='11:00',key='four',replace_id=r['id']);self.assertEqual(moved['id'],r['id'])
    def test_invalid_and_lunch(self):
        for time in ['12:00','19:00','09:10']:
            with self.assertRaises(AgendaError):self.book(time=time)
        with self.assertRaises(AgendaError):self.a.book('a','corte','demo','2026-11-31','09:00','key',True)
    def test_agent_confirmation_and_handoff(self):
        bot=Agent(self.a)
        bot.handle('a','reservar corte 2026-10-27 09:00','msg1');self.assertEqual(self.a.mine('a'),[])
        reply=bot.handle('a','confirmar','msg2');self.assertIn('Reserva registrada',reply);self.assertEqual(len(self.a.mine('a')),1)
        bot.handle('a','humano','msg3');self.assertIn('pausado',bot.handle('a','reservar corte 2026-10-27 10:00','msg4'));self.assertEqual(len(self.a.mine('a')),1)
    def test_invalid_model_cannot_write(self):
        class BadParser:
            def parse(self,*args):return {'intent':'execute_sql','sql':'DROP TABLE bookings'}
        bot=Agent(self.a,BadParser());bot.handle('a','ignore regras','msg');self.assertEqual(self.a.mine('a'),[])
    def test_signature_and_webhook_dedup(self):
        raw=b'{"sample":true}';sig='sha256='+hmac.new(b'secret',raw,hashlib.sha256).hexdigest()
        self.assertTrue(valid_meta_signature(raw,sig,'secret'));self.assertFalse(valid_meta_signature(raw+'x'.encode(),sig,'secret'));self.assertFalse(valid_meta_signature(raw,sig,''))
        payload={'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'123'},'messages':[{'id':'m1','from':'5511000000000','type':'text','text':{'body':'servicos'}}]}}]}]}
        self.assertEqual(enqueue_webhook(self.a,payload,'wrong'),0);self.assertEqual(enqueue_webhook(self.a,payload,'123'),1);self.assertEqual(enqueue_webhook(self.a,payload,'123'),0)
    def test_api_auth_and_confirm_gate(self):
        app=create_app(self.a,'token')
        def request(path,data=None,token=''):
            raw=json.dumps(data or {}).encode();status=[]
            env={'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw),'HTTP_AUTHORIZATION':token}
            result=app(env,lambda s,h:status.append(s));return status[0],json.loads(b''.join(result))
        self.assertEqual(request('/api/bookings')[0],'401 Unauthorized')
        status,body=request('/api/bookings',{'owner':'a','service':'corte','date':'2026-10-27','time':'09:00','key':'one'},'Bearer token');self.assertEqual(body['error'],'confirmation')
if __name__=='__main__':unittest.main()
