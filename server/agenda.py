"""Núcleo transacional para piloto local. Não publicado no site estático."""
import hashlib, json, secrets, sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
TZ=ZoneInfo('America/Sao_Paulo')
class AgendaError(Exception):
    def __init__(self, code, message): self.code=code; super().__init__(message)
SCHEMA="""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS services(id TEXT PRIMARY KEY,name TEXT NOT NULL,duration INTEGER NOT NULL CHECK(duration>0),price_cents INTEGER NOT NULL CHECK(price_cents>=0),active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS professionals(id TEXT PRIMARY KEY,name TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS bookings(id TEXT PRIMARY KEY,owner TEXT NOT NULL,professional TEXT NOT NULL,service TEXT NOT NULL,start_at INTEGER NOT NULL,end_at INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('confirmed','cancelled')),price_cents INTEGER NOT NULL,created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS busy ON bookings(professional,start_at,end_at,status);
CREATE TABLE IF NOT EXISTS blocks(id INTEGER PRIMARY KEY,professional TEXT NOT NULL,start_at INTEGER NOT NULL,end_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS operations(owner TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(owner,key));
CREATE TABLE IF NOT EXISTS sessions(owner TEXT PRIMARY KEY,state TEXT NOT NULL,updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS incoming(id TEXT PRIMARY KEY,received_at INTEGER NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY,event_key TEXT NOT NULL UNIQUE,recipient TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',provider_id TEXT,created_at INTEGER NOT NULL);
"""
class Agenda:
    def __init__(self,path,clock=None):
        self.path=str(path);self.clock=clock or (lambda:datetime.now(TZ))
        with self.connect() as db: db.executescript(SCHEMA)
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:yield db
        finally:db.close()
    def seed_demo(self):
        with self.connect() as db:
            db.executemany('INSERT OR IGNORE INTO services VALUES(?,?,?,?,1)',[('corte','Corte masculino',30,4000),('barba','Barba',30,3000),('combo','Corte + barba',60,6500)])
            db.execute("INSERT OR IGNORE INTO professionals VALUES('demo','Barbeiro de demonstração',1)")
    def catalog(self):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT id,name,duration,price_cents FROM services WHERE active=1')]
    def validate(self,db,service,professional,day,time):
        s=db.execute('SELECT * FROM services WHERE id=? AND active=1',(service,)).fetchone()
        p=db.execute('SELECT id FROM professionals WHERE id=? AND active=1',(professional,)).fetchone()
        if not s or not p:raise AgendaError('invalid','Serviço ou profissional não cadastrado.')
        try:
            start=datetime.strptime(day+' '+time,'%Y-%m-%d %H:%M').replace(tzinfo=TZ)
            if start.strftime('%Y-%m-%d')!=day or start.strftime('%H:%M')!=time:raise ValueError()
        except (ValueError,TypeError):raise AgendaError('invalid','Data ou horário inválido.')
        now=self.clock();end=start+timedelta(minutes=s['duration']);mins=start.hour*60+start.minute;finish=mins+s['duration']
        # Configuração ilustrativa do piloto: ter–sáb, 09–19h, intervalo 12–13h, grade de 30min.
        if start<=now or start.date()>now.date()+timedelta(days=30):raise AgendaError('past','Escolha horário futuro dentro de 30 dias.')
        if start.weekday() in (0,6) or mins<540 or finish>1140 or mins%30 or (mins<780 and finish>720):raise AgendaError('closed','Horário fora do expediente ilustrativo.')
        return int(start.timestamp()),int(end.timestamp()),s
    def conflict(self,db,professional,start,end,exclude=''):
        busy=db.execute("SELECT 1 FROM bookings WHERE professional=? AND status='confirmed' AND id!=? AND start_at<? AND end_at>? LIMIT 1",(professional,exclude,end,start)).fetchone()
        blocked=db.execute('SELECT 1 FROM blocks WHERE professional=? AND start_at<? AND end_at>? LIMIT 1',(professional,end,start)).fetchone()
        return bool(busy or blocked)
    def slots(self,service,professional,day,owner=None,replace_id=None):
        with self.connect() as db:
            if replace_id:self._owned(db,replace_id,owner)
            out=[]
            for minute in range(540,1140,30):
                time=f'{minute//60:02}:{minute%60:02}'
                try:start,end,_=self.validate(db,service,professional,day,time)
                except AgendaError:continue
                if not self.conflict(db,professional,start,end,replace_id or ''):out.append(time)
            return out
    def _owned(self,db,booking_id,owner):
        row=db.execute("SELECT * FROM bookings WHERE id=? AND owner=? AND status='confirmed'",(booking_id,owner)).fetchone()
        if not row:raise AgendaError('missing','Reserva não encontrada para este cliente.')
        return row
    def book(self,owner,service,professional,day,time,key,confirmed=False,replace_id=None):
        if confirmed is not True:raise AgendaError('confirmation','É necessária confirmação explícita do cliente.')
        if not owner or not key or len(key)>160:raise AgendaError('invalid','Identificador de operação inválido.')
        fingerprint=hashlib.sha256(json.dumps([service,professional,day,time,replace_id]).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE') # serialize a verificação + gravação, inclusive entre processos
            previous=db.execute('SELECT * FROM operations WHERE owner=? AND key=?',(owner,key)).fetchone()
            if previous:
                if previous['fingerprint']!=fingerprint:raise AgendaError('idempotency','Chave já usada com outros dados.')
                return json.loads(previous['result'])
            start,end,s=self.validate(db,service,professional,day,time)
            if replace_id:self._owned(db,replace_id,owner)
            if self.conflict(db,professional,start,end,replace_id or ''):raise AgendaError('conflict','Horário ocupado. Consulte outras opções.')
            booking_id=replace_id or secrets.token_hex(8)
            if replace_id:db.execute('UPDATE bookings SET professional=?,service=?,start_at=?,end_at=?,price_cents=? WHERE id=?',(professional,service,start,end,s['price_cents'],booking_id))
            else:db.execute("INSERT INTO bookings VALUES(?,?,?,?,?,?,'confirmed',?,?)",(booking_id,owner,professional,service,start,end,s['price_cents'],int(self.clock().timestamp())))
            result={'id':booking_id,'service':service,'professional':professional,'date':day,'time':time,'price_cents':s['price_cents'],'status':'confirmed'}
            db.execute('INSERT INTO operations VALUES(?,?,?,?)',(owner,key,fingerprint,json.dumps(result)))
            return result # with faz COMMIT antes de devolver ao chamador
    def cancel(self,owner,booking_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT status FROM bookings WHERE id=? AND owner=?',(booking_id,owner)).fetchone()
            if not row:raise AgendaError('missing','Reserva não encontrada para este cliente.')
            db.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND owner=?",(booking_id,owner))
        return {'id':booking_id,'status':'cancelled'}
    def mine(self,owner):
        with self.connect() as db:return [dict(r) for r in db.execute('SELECT id,service,start_at,end_at,status FROM bookings WHERE owner=? ORDER BY start_at',(owner,))]
    def state(self,owner):
        with self.connect() as db:
            r=db.execute('SELECT * FROM sessions WHERE owner=?',(owner,)).fetchone()
            return json.loads(r['state']) if r and int(self.clock().timestamp())-r['updated_at']<1800 else {}
    def save_state(self,owner,state):
        with self.connect() as db:db.execute('INSERT INTO sessions VALUES(?,?,?) ON CONFLICT(owner) DO UPDATE SET state=excluded.state,updated_at=excluded.updated_at',(owner,json.dumps(state),int(self.clock().timestamp())))
