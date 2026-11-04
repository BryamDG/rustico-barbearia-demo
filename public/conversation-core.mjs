// Fluxo guiado, sem chamadas de IA. Compartilha a agenda em memória desta aba.
import {localDate,addDays} from './booking-core.mjs';
const normalize=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
export const brl=value=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(value);
export const dayLabel=day=>new Intl.DateTimeFormat('pt-BR',{weekday:'short',day:'2-digit',month:'short',timeZone:'America/Sao_Paulo'}).format(new Date(day+'T12:00:00-03:00'));
export function createConversation({agenda,services,now=()=>new Date(),newKey=()=>crypto.randomUUID()}){
 let stage='name',draft={},receipt=null,key='',dayPage=0,timePage=0;
 const service=()=>services.find(s=>s.id===draft.service);
 function dates(){const out=[],today=localDate(now());for(let i=0;i<=30;i++){const day=addDays(today,i);if(agenda.slots(draft.service,day).length)out.push(day);}return out;}
 function options(){
  if(stage==='name')return [{kind:'sample_name',value:'Rafael',label:'Usar Rafael (exemplo)'}];
  if(stage==='service')return services.map(s=>({kind:'service',value:s.id,label:s.name+' · '+brl(s.price)+' · '+s.duration+' min'}));
  if(stage==='date'){const list=dates();const start=dayPage*4;if(start>=list.length)dayPage=0;const page=list.slice(dayPage*4,dayPage*4+4).map(d=>({kind:'date',value:d,label:dayLabel(d)}));if(list.length>4)page.push({kind:'more_dates',label:'Outras datas'});page.push({kind:'edit_service',label:'Trocar serviço'});return page;}
  if(stage==='time'){const list=agenda.slots(draft.service,draft.date);if(timePage*6>=list.length)timePage=0;const page=list.slice(timePage*6,timePage*6+6).map(t=>({kind:'time',value:t,label:t}));if(list.length>6)page.push({kind:'more_times',label:'Mais horários'});page.push({kind:'edit_date',label:'Trocar data'});return page;}
  if(stage==='review')return [{kind:'confirm',label:'Confirmar agendamento simulado'},{kind:'edit_time',label:'Trocar horário'},{kind:'edit_service',label:'Trocar serviço'},{kind:'edit_name',label:'Corrigir nome'}];
  if(stage==='done')return [{kind:'view_agenda',label:'Ver na agenda do barbeiro'},{kind:'restart',label:'Agendar outro cliente'}];
  return [];
 }
 function result(text,extra={}){const live=receipt?agenda.rows().find(r=>r.id===receipt.id):null;return {stage,text,draft:{...draft},service:service()?{...service()}:null,options:options(),receipt:live?{...live}:null,...extra};}
 function askDate(){stage='date';draft.date='';draft.time='';dayPage=0;return result('Certo, '+draft.client+'! Para qual dia você prefere '+service().name.toLowerCase()+'? Escolha uma data abaixo ou digite no formato DD/MM. Os horários são fictícios.');}
 function chooseService(id){const s=services.find(s=>s.id===id);if(!s)return result('Escolha um dos serviços cadastrados abaixo.');draft.service=s.id;return askDate();}
 function chooseDate(day){const today=localDate(now());if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isFinite(Date.parse(day+'T12:00:00-03:00'))||localDate(new Date(day+'T12:00:00-03:00'))!==day||day<today||day>addDays(today,30))return result('Escolha uma data válida nos próximos 30 dias. Você pode usar os botões abaixo.');const times=agenda.slots(draft.service,day);if(!times.length){stage='date';return result('Não há horários para esse serviço em '+dayLabel(day)+'. Vou mostrar outras datas disponíveis na agenda simulada.');}draft.date=day;draft.time='';timePage=0;stage='time';return result('Em '+dayLabel(day)+', temos estes horários para '+service().name.toLowerCase()+'. Qual você prefere? Fuso de São Paulo.');}
 function chooseTime(time){if(!agenda.slots(draft.service,draft.date).includes(time))return result('Esse horário não está disponível. Escolha uma das opções consultadas na agenda.');draft.time=time;stage='review';key=newKey();return result('Antes de registrar, confira os dados abaixo. Posso confirmar este agendamento simulado? Ainda não há reserva criada.');}
 function confirm(){if(stage==='done'){const r=agenda.rows().find(r=>r.id===receipt?.id);return result(r?.status==='cancelled'?'Esta reserva foi cancelada na agenda da demonstração. Você pode iniciar outro agendamento.':'Esta simulação já foi registrada. Não criei uma segunda reserva.');}if(stage!=='review')return result('Vamos concluir nome, serviço, data e horário antes de confirmar.');try{receipt=agenda.reserve({service:draft.service,date:draft.date,time:draft.time,idempotencyKey:key,client:draft.client,origin:'conversation'});stage='done';return result('Pronto, '+draft.client+'! A agenda validou e registrou sua reserva simulada. O mesmo registro já aparece na agenda do barbeiro. Nenhuma mensagem foi enviada e este não é um agendamento real.',{saved:{...receipt}});}catch(error){if(error.code==='conflict'){stage='time';draft.time='';timePage=0;return result('Esse horário acabou de ser ocupado. Não confirmei a reserva. Escolha outra opção disponível abaixo.');}return result('Não foi possível concluir a gravação. Nenhuma nova reserva foi confirmada. Confira os dados e tente novamente.');}}
 function start(preselected){stage='name';draft={};receipt=null;key='';dayPage=0;timePage=0;if(services.some(s=>s.id===preselected))draft.suggested=preselected;return result('Olá! Sou o assistente virtual da Rústico em demonstração. Vamos simular seu agendamento inteiro por aqui. Como posso te chamar? Use um nome fictício, como Rafael. Não informe telefone ou outros dados pessoais.');}
 function choose(action){
  if(action.kind==='restart')return start();
  if(action.kind==='sample_name'&&stage==='name')return send(action.value);
  if(action.kind==='view_agenda')return result('A agenda do barbeiro mostra o mesmo registro, com nome, serviço, data, horário e protocolo.',{effect:'agenda'});
  if(action.kind==='confirm')return confirm();
  if(action.kind==='edit_name'&&draft.client){stage='name';return result('Qual nome fictício você quer usar? Depois vamos revisar as escolhas novamente.');}
  if(action.kind==='edit_service'&&draft.client){stage='service';draft.date='';draft.time='';return result('Qual serviço você prefere? Preços e durações ilustrativos.');}
  if(action.kind==='edit_date'&&service())return askDate();
  if(action.kind==='edit_time'&&draft.date){stage='time';draft.time='';timePage=0;return result('Escolha outro horário na mesma data. Vou consultar novamente antes de confirmar.');}
  if(action.kind==='more_dates'&&stage==='date'){dayPage++;return result('Mais opções de datas disponíveis na simulação:');}
  if(action.kind==='more_times'&&stage==='time'){timePage++;return result('Outros horários disponíveis para esta data:');}
  if(action.kind==='service'&&stage==='service')return chooseService(action.value);
  if(action.kind==='date'&&stage==='date')return chooseDate(action.value);
  if(action.kind==='time'&&stage==='time')return chooseTime(action.value);
  return result('Essa escolha pertence a uma etapa anterior. Use as opções atuais abaixo.');
 }
 function send(value){const text=String(value||'').trim(),n=normalize(text);if(!text)return result('Digite uma resposta ou escolha uma opção.');if(/^(reiniciar|recomecar|nova conversa|novo agendamento)$/.test(n))return start();if(/^(servicos|precos|ver servicos|quais (sao )?os servicos\??)$/.test(n))return result('Catálogo fictício: '+services.map(s=>s.name+' — '+brl(s.price)+' · '+s.duration+' min').join('; ')+'. Continuamos na etapa '+{name:'do nome',service:'do serviço',date:'da data',time:'do horário',review:'de conferência',done:'de confirmação'}[stage]+'.');if(/^(humano|atendente|falar com (o )?barbeiro)$/.test(n))return result('Na operação real, esse pedido será encaminhado ao barbeiro. Aqui é apenas uma demonstração; nenhum contato foi notificado. Você pode continuar ou começar outra conversa.');
  if(stage==='name'){let client=text.replace(/^(meu nome [eé]|me chamo|pode me chamar de)\s+/i,'').trim().replace(/\s+/g,' ');if(/^(oi|ola|bom dia|boa tarde|boa noite|sim|confirmar|quero agendar|agendar|reservar|quero um horario)$/i.test(normalize(client)))return result('Como posso te chamar? Use um nome fictício para a simulação.');if(client.length<2||client.length>60||!/^\p{L}[\p{L}\p{M} '’-]*$/u.test(client))return result('Use um nome fictício de 2 a 60 caracteres, sem telefone, números ou símbolos.');draft.client=client;if(draft.service&&draft.date&&draft.time){stage='review';key=newKey();return result('Nome atualizado. Confira os dados antes de confirmar a simulação.');}stage='service';return result('Prazer, '+client+'! '+(draft.suggested?'Você consultou '+services.find(s=>s.id===draft.suggested).name+'. ':'')+'Qual serviço você quer agendar? Estes preços e tempos são exemplos.');}
  if(stage==='service'){let s=services[Number(n)-1];if(!s){const combo=/combo|corte.*barba|barba.*corte/.test(n);s=services.find(s=>normalize(s.id)===(combo?'combo':/barba/.test(n)?'barba':/cort/.test(n)?'corte':n));}return s?chooseService(s.id):result('Não encontrei esse serviço. Escolha uma das opções cadastradas abaixo.');}
  if(stage==='date'){let day;if(n==='hoje')day=localDate(now());else if(n==='amanha')day=addDays(localDate(now()),1);else if(/^\d{4}-\d{2}-\d{2}$/.test(text))day=text;else{const m=text.match(/^(\d{1,2})\/(\d{1,2})(?:\/(\d{4}))?$/);if(m)day=(m[3]||localDate(now()).slice(0,4))+'-'+m[2].padStart(2,'0')+'-'+m[1].padStart(2,'0');}return day?chooseDate(day):result('Informe a data como DD/MM ou escolha um dia nos botões abaixo.');}
  if(stage==='time'){const m=n.replace(/^as\s+/,'').match(/^(\d{1,2})(?:(?::|h)(\d{2}))?h?$/);const time=m?m[1].padStart(2,'0')+':'+(m[2]||'00'):'';return time?chooseTime(time):result('Qual horário você prefere? Escolha uma opção abaixo ou digite, por exemplo, 14:30.');}
  if(stage==='review'){if(/^(confirmar|confirmo|sim|pode confirmar|confirmar agendamento)$/.test(n))return confirm();if(/trocar|alterar|corrigir/.test(n)){if(/nome/.test(n))return choose({kind:'edit_name'});if(/servico/.test(n))return choose({kind:'edit_service'});if(/data|dia/.test(n))return choose({kind:'edit_date'});if(/horario|hora/.test(n))return choose({kind:'edit_time'});}return result('Ainda não confirmei nada. Use “Confirmar agendamento simulado” ou escolha o que deseja corrigir.');}
  if(stage==='done')return confirm();
  return result('Escolha uma das opções para continuar.');
 }
 return {start,send,choose,snapshot:()=>result('')};
}
