# Configuração após as correções de segurança

Atualizado em 2 de novembro de 2026.

## Autenticação pela Core

O contrato do banco determina que a segunda API consulte a Core para autenticação.
O chatbot não compartilha a conta PostgreSQL da Core e não cria um login alternativo.

O endpoint confirmado no [Swagger da Core](https://tvkgo0evuj.execute-api.us-east-1.amazonaws.com/swagger-ui/index.html)
é `GET /api/v1/auth/session`. A URL HTTPS padrão no chatbot é:

```text
https://tvkgo0evuj.execute-api.us-east-1.amazonaws.com/api/v1/auth/session
```

`CORE_AUTH_URL` pode substituir essa URL para outro ambiente. Valor vazio ou URL
insegura impede a inicialização. Não existe alternativa que aceite identidade do
cliente. Se a Core não puder validar o acesso, o chatbot recusa a requisição.

O adaptador em `app/security.py` encaminha `Authorization: Bearer <access token>`
em um GET para essa URL fixa. Redirecionamentos e proxies do ambiente são
desabilitados. A resposta tem limite de 16 KiB e prazo total de 5 segundos.

Contrato `SessionIdentity` publicado pela Core, com HTTP 200:

```json
{
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "sessionId": "550e8400-e29b-41d4-a716-446655440001",
  "userType": "CITIZENS",
  "sessionExpiresAt": "2026-12-01T12:00:00Z"
}
```

`sessionId` nessa resposta é a sessão de LOGIN (sid), distinta da conversa.
O Swagger descreve a consulta como verificação de identidade e revogação online,
autenticada por Bearer JWT. Perfis documentados: ADMIN, CITIZENS e ESTABLISHMENT.
O chatbot exige os quatro campos válidos, data com fuso e sessão ainda não expirada.
Não espera `active`, que não existe nesse contrato. 401/403 recusam o login;
respostas incompatíveis, redirecionamentos e indisponibilidade retornam 503.

A validação de assinatura e expiração do access token e do vínculo com a sessão
continua sendo responsabilidade da Core. A integração não autentica um usuário
apenas por decodificar o JWT. A documentação foi conferida sem usar credenciais
reais; o fluxo de login válido ainda requer teste integrado no ambiente autorizado.
O servidor HTTP gerado no campo `servers` do Swagger não é usado: tokens seguem
exclusivamente pelo endereço HTTPS acima ou por substituição HTTPS explícita.

O corpo do chat agora contém somente `session_id` (UUID da conversa) e `pergunta`.
Campos extras, incluindo `user_id`, retornam 422. As rotas de iniciar e encerrar
também obtêm o titular exclusivamente da autenticação. A identidade autenticada
é a única usada nas ferramentas de banco e memória. No modelo atual, o próprio
usuário ESTABLISHMENT identifica o estabelecimento; não há seleção livre de
empresa nem delegação de acesso a outro estabelecimento.

## Limites aplicados

Os valores estão centralizados em `app/limits.py`.

| Recurso | Limite |
|---|---|
| Pergunta | 4.000 caracteres |
| Corpo HTTP, inclusive envio em blocos | 32 KiB |
| Envio do corpo | 10 segundos |
| Validação de login | 5 segundos |
| Aquisição das reservas | 10 segundos |
| Processamento do chat ou encerramento | 60 segundos |
| Requisição inteira | 90 segundos |
| Cálculo de trajetos | 10 destinos, DRIVE e WALK, 30 segundos por execução da ferramenta |
| Resposta de cada modelo | 2.048 tokens; timeout de 15 segundos; sem retries |
| Conversa | 40 turnos; até 12 mensagens de contexto |
| Operações do chat e de sessões por usuário | 10/minuto e 200/dia |
| Operações totais do chat e de sessões | 1.000/dia |
| Concorrência de operações | 1 por usuário, 8 no total |
| Requisições HTTP simultâneas antes da autenticação | 32 por processo |

As cotas usam janelas fixas de minuto/dia com referência UTC e contam tentativas
autenticadas, inclusive operações rejeitadas. Não são estimativas da fatura.
Reservas e contadores usam escritas condicionais atômicas em `limites_api` no
mesmo MongoDB de todos os workers. Não usar bancos diferentes entre réplicas.
A indisponibilidade do controle de uso bloqueia as operações com 503.

As reservas expiram em 120 segundos e são liberadas ao terminar normalmente.
Em timeout ou cancelamento, permanecem até expirar para cobrir chamadas síncronas
ainda terminando em segundo plano. Os provedores também possuem timeouts próprios.
As cotas não substituem proteção de conexões e tráfego volumétrico no servidor HTTP.

## Conversas antigas e MongoDB

Não foi realizada migração ou alteração em bancos reais.

A aplicação exige índice único `session_id_unique_v2` em `sessoes.session_id`.
Se houver duplicatas antigas, a criação falha: revisar e resolver a migração
preservando os dados, antes de disponibilizar a nova versão. Não ignorar o erro.
A conta técnica do chatbot precisa criar os índices e ler/escrever somente suas
coleções de conversa e limites; não compartilhar credenciais da Core.

Conversas novas usam `security_version=2`, proprietário imutável e estado
aberta/encerrando/encerrada. Conversas anteriores não podem ser retomadas e não
entram na recuperação de memória. O cliente precisa iniciar outro UUID; os dados
anteriores permanecem armazenados para uma migração revisada. Não basta alterar
o marcador de versão: conteúdo anteriormente bloqueado precisa ser tratado.

O grafo não mantém checkpoints globais. Cada turno carrega somente o contexto
limitado da conversa pertencente ao usuário autenticado. Conteúdo bloqueado não
é salvo nem resumido. Somente mensagens aprovadas e respostas finais revisadas
são persistidas. Encerrar novamente uma conversa encerrada devolve o resumo já
existente, sem nova inferência.

Se um processo morrer durante o resumo e deixar estado `encerrando`, um operador
deve verificar a operação interrompida antes de recuperar esse estado. Ele não
é reaberto automaticamente, para evitar trabalho duplicado.

## Monitor e validação

Acesse `/monitor` no endereço do chatbot. A equipe entra com uma senha de
20 caracteres. A permissão é exclusiva do monitor e independente dos perfis da
Core. A tela e o JSON das métricas exigem a mesma sessão.

Para configurar, execute `python -m app.monitor_access` e informe a senha no
terminal. Guarde a linha `MONITOR_PASSWORD_HASH` retornada no `.env` local ou
injete o valor como segredo no ambiente AWS. Configure o mesmo valor em todas
as réplicas e reinicie o serviço. Use uma senha própria em produção.
Sem o hash configurado, o monitor recusa novas sessões.

O servidor compara um hash PBKDF2 com salt e limita tentativas no MongoDB
em seis por endereço e 30 no total por minuto. O cookie de acesso expira
em 30 minutos, exige HTTPS e é HttpOnly. O botão Sair revoga a sessão no
MongoDB. As sessões e as cotas usam a coleção existente `limites_api` e
seu índice TTL. Alterar o hash invalida as sessões anteriores.

No ambiente público, acesse por HTTPS e configure o proxy da aplicação para
informar o esquema HTTPS por cabeçalhos encaminhados de proxies confiáveis.
Se o gateway registrar o corpo de requisições, exclua `/api/v1/monitor/entrar`
desse registro. Para desenvolvimento local, abra `http://127.0.0.1:8000/monitor`
em um navegador que aceite cookies Secure em loopback.

Testes não acessam Core, bancos ou provedores reais. Executar `python -m pytest`.
A validação real do endpoint da Core, permissões MongoDB e migração dos dados
continua necessária no ambiente de implantação. Nenhum commit, push ou deploy
foi realizado por estas correções.
