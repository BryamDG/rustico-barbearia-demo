# Rústico Barbearia — demonstração

Site responsivo e demonstração de agendamento completo pela conversa: nome fictício → serviço → data → horário → resumo → confirmação → agenda do barbeiro.

O código foi preparado para GitHub em 03/11/2026. Ainda depende de conexão da conta, criação do repositório e configuração do Pages. Nenhuma URL GitHub é considerada publicada nesta preparação.

## Abrir localmente

Requer Node.js 24 LTS (ou versão compatível posterior). Não há pacotes npm a instalar para o site.

```text
npm test
npm run build
npm run dev
```

Abrir http://127.0.0.1:8794 . Use um nome fictício, escolha um serviço/data/horário e confirme. A agenda ao lado mostra o mesmo registro. Atualizar a página limpa a simulação. Nova conversa preserva os registros desta aba; Reiniciar demonstração limpa todos.

## Hospedar no GitHub Pages

1. Criar/selecionar um repositório e enviar estes arquivos para main, incluindo a pasta .github.
2. No repositório: Settings → Pages → Build and deployment → Source → GitHub Actions.
3. Em Actions, executar Testar e publicar demonstracao, ou fazer novo push em main.
4. Aguardar os jobs build e deploy concluírem. A URL verdadeira aparecerá em Settings → Pages e no ambiente github-pages.

Em GitHub Free, Pages exige repositório público. Em planos compatíveis, também pode usar repositório privado. A visibilidade precisa ser escolhida pelo proprietário antes do envio. O arquivo package.json com private=true só impede publicação acidental no npm; ele não define a visibilidade do GitHub.

O workflow usa somente Actions oficiais e o token temporário do próprio GitHub. Não precisa de senha ou token salvo no código. Apenas dist/ vira o site; server/, testes e documentos ficam no código-fonte, conforme a visibilidade do repositório.

## Continuar em outro computador

Após criar o repositório, clonar a URL real do GitHub e abrir a pasta no Codex. Antes de trabalhar, atualizar a branch. Usar uma branch para cada mudança e enviar commit/push para disponibilizar no outro computador. Copiar arquivos sem commit/push não sincroniza o projeto.

Para trabalhos via Codex Cloud, conectar o mesmo repositório a um ambiente e publicar esse ambiente. Para comandar o PC pelo celular, usar Remote e parear o dispositivo. O passo a passo está em [docs/GITHUB-E-CELULAR.md](docs/GITHUB-E-CELULAR.md).

## Arquivos

- public/index.html, style.css e site.js: página e apresentação da conversa.
- public/conversation-core.mjs: fluxo guiado por regras, sem IA externa.
- public/booking-core.mjs: agenda em memória e prevenção de sobreposição.
- public/config.js: catálogo e dados fictícios editáveis; WhatsApp vazio até confirmação.
- server/: piloto Python/SQLite separado, sem implantação neste Pages.
- tests/: verificações de agenda, conversa e piloto.
- .github/workflows/pages.yml: testes, build e publicação.

## Limites da demonstração

Não envia WhatsApp, não chama IA, não cria agenda real nem compartilha reservas entre visitantes. Usar apenas nomes fictícios. A integração de produção depende de número oficial, credenciais, catálogo/expediente reais, servidor, segurança e homologação.

As imagens foram fornecidas para a proposta; a utilização comercial deve ser aprovada pelo responsável. Origem em public/assets/SOURCES.md. Não foram inventadas avaliações, clientes ou fotografias de cortes.

## Referências

- GitHub Pages: https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
- Workflow: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- Remote: https://developers.openai.com/training/walkthroughs/working-on-your-phone
- Codex Cloud: https://learn.chatgpt.com/docs/cloud
