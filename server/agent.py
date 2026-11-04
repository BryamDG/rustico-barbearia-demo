"""Interpretação separada das ações. Modelo não tem acesso direto ao banco."""
import json, os, re, urllib.request
from datetime import datetime
from agenda import AgendaError,TZ
class RuleParser:
    def parse(self,text,catalog):
        low=text.lower().strip()
        if low in ('servicos','serviços','preços','precos'):return {'intent':'services'}
        if low.startswith('cancelar '):return {'intent':'cancel','booking_id':text.split()[-1]}
        if low in ('minhas reservas','reservas'):return {'intent':'mine'}
        if any(w in low for w in ('humano','atendente','barbeiro')):return {'intent':'handoff'}
        # Comandos explícitos para testar sem API. Datas ISO, horário HH:MM.
        m=re.fullmatch(r'(horarios|reservar|remarcar) (corte|barba|combo) (\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?(?: ([a-z0-9]+))?',low)
        if m:return {'intent':{'horarios':'availability','reservar':'propose','remarcar':'reschedule'}[m[1]],'service':m[2],'date':m[3],'time':m[4] or '','booking_id':m[5] or ''}
        return {'intent':'help'}
class GeminiIntentParser:
    """Adaptador opcional, sem chamada até ENABLE_AI=true e chave no servidor."""
    def parse(self,text,catalog):
        if os.getenv('ENABLE_AI')!='true' or not os.getenv('GEMINI_API_KEY'):raise RuntimeError('IA não configurada')
        model=os.getenv('GEMINI_MODEL','gemini-2.5-flash-lite')
        if not re.fullmatch(r'[a-zA-Z0-9.-]+',model):raise RuntimeError('Modelo inválido')
        prompt='Extraia somente intenção e dados fornecidos. Nunca invente serviço, data, hora ou protocolo. Não confirme reservas. Intenções: services, availability, propose, cancel, reschedule, mine, handoff, help. Datas relativas usam a data de referência. Em ambiguidade use help. Campo ausente: string vazia. Catálogo: '+json.dumps(catalog,ensure_ascii=False)+'. Data São Paulo: '+datetime.now(TZ).isoformat()
        schema={'type':'OBJECT','properties':{k:{'type':'STRING'} for k in ('intent','service','date','time','booking_id')},'required':['intent','service','date','time','booking_id']}
        payload={'systemInstruction':{'parts':[{'text':prompt}]},'contents':[{'role':'user','parts':[{'text':text[:500]}]}],'generationConfig':{'temperature':0,'maxOutputTokens':400,'responseMimeType':'application/json','responseSchema':schema}}
        req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','x-goog-api-key':os.environ['GEMINI_API_KEY']})
        with urllib.request.urlopen(req,timeout=15) as r:result=json.load(r)
        data=json.loads(result['candidates'][0]['content']['parts'][0]['text'])
        if not isinstance(data,dict) or any(not isinstance(v,str) for v in data.values()):raise RuntimeError('Resposta de IA inválida')
        return {k:data.get(k,'') for k in ('intent','service','date','time','booking_id')}
class Agent:
    def __init__(self,agenda,parser=None):self.agenda=agenda;self.parser=parser or RuleParser()
    def handle(self,owner,text,event_id):
        if not owner or len(text)>500:raise AgendaError('invalid','Mensagem inválida.')
        state=self.agenda.state(owner)
        if state.get('handoff'):return 'Atendimento encaminhado para revisão humana. O robô está pausado para esta conversa.'
        if text.strip().casefold()=='confirmar':
            proposal=state.get('proposal')
            if not proposal:return 'Não há uma proposta recente para confirmar. Consulte os horários primeiro.'
            if proposal['action']=='cancel':
                row=self.agenda.cancel(owner,proposal['booking_id']);result='Cancelamento registrado: '+row['id']
            else:
                row=self.agenda.book(owner,proposal['service'],'demo',proposal['date'],proposal['time'],proposal['key'],confirmed=True,replace_id=proposal.get('booking_id') or None)
                result='Reserva registrada: '+row['id']+' · '+row['date']+' às '+row['time']
            self.agenda.save_state(owner,{})
            return result+' (ambiente de piloto; catálogo e expediente ilustrativos).'
        try:intent=self.parser.parse(text,self.agenda.catalog())
        except Exception:
            self.agenda.save_state(owner,{'handoff':True});return 'Não consegui interpretar com segurança. Encaminhei a conversa para revisão humana; não confirmei um horário.'
        action=intent.get('intent')
        if action=='handoff':self.agenda.save_state(owner,{'handoff':True});return 'Conversa sinalizada para o barbeiro. O assistente ficará pausado até a revisão humana.'
        if action=='services':return 'Sou o assistente virtual em piloto. Serviços ilustrativos: '+ '; '.join(f"{s['name']}: R$ {s['price_cents']/100:.2f}, {s['duration']} min".replace('.',',') for s in self.agenda.catalog())
        if action=='mine':return json.dumps(self.agenda.mine(owner),ensure_ascii=False)
        if action=='cancel':
            booking_id=intent.get('booking_id','')
            if not any(b['id']==booking_id and b['status']=='confirmed' for b in self.agenda.mine(owner)):raise AgendaError('missing','Reserva não encontrada para este cliente.')
            self.agenda.save_state(owner,{'proposal':{'action':'cancel','booking_id':booking_id}})
            return 'Deseja cancelar a reserva '+booking_id+'? Responda exatamente CONFIRMAR para concluir.'
        if action in ('availability','propose','reschedule'):
            service,day,time=intent.get('service',''),intent.get('date',''),intent.get('time','')
            if not service or not day:return 'Informe serviço e data. Não vou escolher por você.'
            replace=intent.get('booking_id') if action=='reschedule' else None
            if action=='reschedule' and not replace:return 'Informe o protocolo da sua reserva para remarcar.'
            available=self.agenda.slots(service,'demo',day,owner,replace)
            if action=='availability' or not time:return 'Horários disponíveis no piloto: '+(', '.join(available) or 'nenhum nesta data')+'.'
            if time not in available:return 'Este horário não está disponível. Opções reais do piloto: '+(', '.join(available) or 'nenhuma nesta data')+'.'
            self.agenda.save_state(owner,{'proposal':{'action':'book','service':service,'date':day,'time':time,'booking_id':replace,'key':'proposal:'+event_id}})
            return f'Proposta de {service}, {day} às {time}, em São Paulo. Responda exatamente CONFIRMAR para salvar. Ainda não há nova reserva.'
        return 'Sou o assistente virtual em piloto. Envie servicos; horarios corte AAAA-MM-DD; reservar corte AAAA-MM-DD HH:MM; minhas reservas; cancelar PROTOCOLO; remarcar corte AAAA-MM-DD HH:MM PROTOCOLO; ou humano. A IA natural depende de configuração.'
