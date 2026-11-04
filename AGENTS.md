# Contexto do projeto

Demonstração da Rústico Barbearia. Interface em português, visual grafite/areia/cobre. Dados comerciais fictícios. O fluxo da conversa e a agenda do barbeiro usam o mesmo estado em memória da aba.

## Trabalhar
- Node.js 24 LTS ou superior compatível. Sem dependências npm obrigatórias.
- npm test: testes de agenda e conversa.
- npm run build: saída estática dist/.
- npm run dev: prévia local na porta 8794.
- Python server/ é um piloto local separado e não é executado pelo GitHub Pages.

## Preservar
- Nome, serviço, data, horário e protocolo correspondem à mesma reserva.
- Consultar disponibilidade de novo antes de salvar. Sem confirmação sem gravação.
- Remarcação mantém nome/origem/protocolo e falhas mantêm o registro anterior.
- Sem dados reais ou chamadas externas no demonstrativo.
- Imagens da referência não devem ser substituídas por resultados de cortes inventados.
- Credenciais apenas no ambiente do servidor; nunca em public/ ou no navegador.

## Publicação
Apenas dist/ é enviado ao Pages. Não enviar banco, .env ou server/ como conteúdo do site. O workflow publica main após os testes e o build. GitHub Pages exibe o demonstrativo; não ativa WhatsApp, IA nem agenda remota. Para alterações, usar branch e revisão; evitar sobrescrever mudanças de outro computador.
