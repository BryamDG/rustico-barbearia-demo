"""Adaptadores preparados; chamadas reais desativadas por padrão."""
import hashlib,hmac,json,os,re,urllib.request
from datetime import datetime,timezone

def valid_meta_signature(raw,signature,secret):
    if not secret or not signature or not signature.startswith('sha256='):return False
    expected='sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature,expected)

def enqueue_webhook(agenda,payload,phone_number_id):
    # Apenas o número oficial configurado pode alimentar esta agenda.
    count=0
    with agenda.connect() as db:
        for entry in payload.get('entry',[]):
            for change in entry.get('changes',[]):
                value=change.get('value',{})
                if value.get('metadata',{}).get('phone_number_id')!=phone_number_id:continue
                for m in value.get('messages',[]):
                    if not m.get('id') or not re.fullmatch(r'\d{8,15}',m.get('from','')):continue
                    # Não copiamos contatos, perfis ou anexos. Áudio/mídia encaminha para revisão.
                    item={'id':m['id'],'from':m['from'],'text':m.get('text',{}).get('body','')[:500] if m.get('type')=='text' else 'humano','timestamp':m.get('timestamp','0')}
                    cur=db.execute('INSERT OR IGNORE INTO incoming(id,received_at,payload) VALUES(?,?,?)',(m['id'],int(agenda.clock().timestamp()),json.dumps(item)))
                    count+=cur.rowcount
    return count

def process_pending(agenda,agent):
    # Um único worker por SQLite. Persistência de idempotência na operação de reserva.
    with agenda.connect() as db:events=db.execute("SELECT * FROM incoming WHERE status='pending' ORDER BY received_at,id LIMIT 50").fetchall()
    for event in events:
        item=json.loads(event['payload'])
        try:body=agent.handle(item['from'],item['text'],item['id'])
        except Exception:body='Não foi possível concluir com segurança. Consulte o barbeiro. Nenhuma nova confirmação foi emitida.'
        with agenda.connect() as db:
            db.execute('INSERT OR IGNORE INTO outbox(event_key,recipient,body,created_at) VALUES(?,?,?,?)',(item['id'],item['from'],body,int(agenda.clock().timestamp())))
            db.execute("UPDATE incoming SET status='processed' WHERE id=?",(item['id'],))

class MetaSender:
    def send_text(self,recipient,text,last_customer_message):
        if os.getenv('ENABLE_EXTERNAL_SEND')!='true':raise RuntimeError('Envio real desativado')
        if datetime.now(timezone.utc).timestamp()-float(last_customer_message)>86400:raise RuntimeError('Janela encerrada: requer template aprovado, não texto livre')
        if not re.fullmatch(r'\d{8,15}',recipient):raise ValueError('Destinatário inválido')
        version=os.environ['META_GRAPH_VERSION'];phone=os.environ['META_PHONE_NUMBER_ID']
        if not re.fullmatch(r'v\d+\.\d+',version) or not phone.isdigit():raise ValueError('Configuração Meta inválida')
        payload={'messaging_product':'whatsapp','to':recipient,'type':'text','text':{'body':text[:4000]}}
        req=urllib.request.Request(f'https://graph.facebook.com/{version}/{phone}/messages',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+os.environ['META_ACCESS_TOKEN'],'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=15) as response:return json.load(response)
    def send_reminder(self,*args,**kwargs):
        raise NotImplementedError('Lembretes reais dependem de opt-in, template aprovado, scheduler, deduplicação e confirmação de entrega.')
