# Varredura de segurança da API

Data: 1 de novembro de 2026.
Branch: security/86e3xw668-verificacao_seguranca_chatbot.
Base: c57f9d0, diretório inicialmente limpo.

## Escopo

Revisão das rotas, grafo, ferramentas SQL e MongoDB, memória, integrações HTTP,
guardrails, observabilidade, frontend do monitor e CI. Excluídos dos achados novos:
identidade escolhida pelo cliente, autorização de sessões e consumo sem limites.
Nenhum código de produção foi alterado. Não foram acessados bancos ou provedores reais.

## 1. Alta — monitor expõe IDs reais de conversas

Referências: app/routes/monitor.py:162-171; app/observability.py:348;
app/main.py:29-31.

GET /api/v1/monitor publica os últimos 50 turnos do processo, incluindo session_id,
sem autenticação ou autorização administrativa. O router é incluído diretamente
na aplicação, sem proteção global de identidade.

Isso permite descobrir IDs efetivamente usados por outras pessoas. Com a falha de
autorização de sessões já conhecida, o atacante recebe os identificadores necessários
para tentar acessar contexto ou encerrar uma conversa e receber seu resumo.
A exposição dos identificadores é o achado adicional; a falha de sessões não foi
contada novamente. A severidade alta considera essa combinação.

Validação: registrado um turno sintético e confirmado seu session_id no retorno da
função do endpoint. A rota foi inspecionada: não possui dependências de autenticação
ou parâmetros de cabeçalho. Não houve requisição HTTP completa ou acesso a conversa real.

Correção: exigir autorização administrativa e remover IDs de conversa da resposta
pública. Quando necessário, usar um identificador exclusivo de observabilidade.
Uma proteção efetiva no gateway pode mitigar a exposição; o deploy não foi inspecionado.

## 2. Alta — mensagens bloqueadas voltam ao contexto sem anonimização

Referências: app/graph.py:31-63; app/graph.py:71; app/graph.py:184-185.

No caminho aprovado, o guardrail usa RemoveMessage para substituir a mensagem original
pelo texto anonimizado. No caminho bloqueado, apenas adiciona a resposta de bloqueio.
A mensagem original permanece no checkpoint, inclusive com dados pessoais originais.

No turno seguinte, o guardrail verifica somente a mensagem mais recente, mas o
roteador recebe todo o histórico. Enviar uma instrução rejeitada e depois uma pergunta
permitida reintroduz o conteúdo rejeitado no contexto dos modelos, sem nova avaliação
ou anonimização. Especialistas encaminhados pelo roteador recebem esse histórico.

Validação: executado o grafo compilado real em modo síncrono com checkpointer real e
dois turnos na mesma sessão. Agentes, filtros e persistência externa foram simulados
para isolar o fluxo. A primeira mensagem retornou bloqueio sem chamar o roteador;
a segunda fez o roteador receber a primeira integralmente, incluindo um CPF sintético
que a simulação do anonimizador havia substituído.

Isso comprova o desvio do filtro e da anonimização. Não comprova que um LLM real
obedeceria à instrução, executaria ferramentas indevidas ou vazaria dados de terceiros.
A classificação alta considera a quebra das barreiras de filtragem e privacidade.

Correção: remover a mensagem original também no caminho bloqueado, impedir que
conteúdo rejeitado participe do contexto e tratar checkpoints existentes. Incluir
regressão com dois turnos e mensagem bloqueada contendo dados pessoais.

## Reprodução e limites

Prova local: reports/security_probe.py (ignorado pelo Git).
Executar na raiz do chatbot: python -u -m reports.security_probe.
As duas verificações finais concluíram com código de saída zero.

TestClient e execução assíncrona não concluíram neste ambiente e foram interrompidos.
A validação final utilizou o grafo síncrono e inspeção e chamada direta do endpoint.
Não houve validação HTTP completa, teste de deploy, nova auditoria online de dependências
ou análise completa do histórico Git.

Não foram confirmados novos caminhos de SQL injection, execução de comandos ou SSRF
nos módulos examinados. Os valores externos das consultas SQL inspecionadas são
parametrizados e os destinos HTTP do Maps e do juiz são fixos.
Nenhuma outra vulnerabilidade crítica independente das exclusões foi confirmada.


## Correções posteriores

Em 2 de novembro de 2026, os cinco problemas desta revisão e da lista original
receberam correções no código. Este documento preserva o diagnóstico anterior.
Consulte `seguranca_configuracao.md` para o novo contrato de autenticação,
limites, tratamento de conversas antigas e condições de implantação.
A prova em `reports/security_probe.py` descreve a versão vulnerável e não deve
ser usada como teste da versão corrigida; as regressões atuais estão em `tests/`.
