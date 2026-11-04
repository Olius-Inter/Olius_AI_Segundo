# Revisão antes do envio

Revisão local de 1 de novembro de 2026. Nenhum commit ou push foi realizado
pela revisão. As demais alterações existentes no diretório foram preservadas.

## Resultado dos testes

- Suíte completa: 169 testes aprovados.
- Cobertura de linhas em `app/`: 97,32% (1163 de 1195 instruções).
- Guardrail, configuração, modelos, sessões, FAQ e rotas: 100% de cobertura de linhas.
- Instrumentação dos agentes: 100%; coletor de observabilidade: 97%.
- Instalação limpa com as dependências corrigidas: suíte aprovada e `pip check`
  sem conflitos. A inicialização real retornou HTTP 200 em `/health`, `/monitor`
  e `/api/v1/monitor`, sem executar inferências pagas.
- O comando `python -m pytest` agora exige pelo menos 80% de cobertura total.
- Não foram removidos módulos de produção da cobertura para atingir esse valor.
- A cobertura local é de linhas Python. O Sonar calcula o código novo conforme
  a branch de destino e as regras do projeto; HTML e JavaScript não estão
  incluídos na configuração atual `sonar.sources=app`.

## Correções realizadas

- Teste da tela atualizado após a renomeação de `monitor2.html` para `monitor.html`.
- CORS substituído por uma lista explícita de origens configuráveis; curinga
  recusado na validação. Para outro domínio, configure `CORS_ORIGINS` no deploy.
- Guardrail de entrada rejeita classificação ausente ou desconhecida.
- Saída revisada pelo modelo passa por uma nova remoção de PII antes da entrega.
- Ausência da chave OpenAI não provoca mais acesso a `None.with_fallbacks`
  durante a importação; a validação da configuração continua exigindo a chave.
- Testes adicionados aos fluxos de guardrail, sessões, configuração de modelos,
  consulta ao FAQ e metadados da coleta, com chamadas externas substituídas por mocks.
- Dependências com alertas conhecidos atualizadas em `requirements.txt`;
  `security-constraints.txt` aplica os mínimos corrigidos também às transitivas.
  A compatibilidade foi testada em um ambiente separado do Python do usuário.

## Segurança e limites da análise

A busca por padrões comuns de chaves de API e chaves privadas não encontrou
indícios nos arquivos atuais elegíveis para Git. O `.env` permanece ignorado.
Essa verificação não certifica todo o histórico Git nem todos os formatos de segredo.

O Bandit foi executado em todos os módulos de `app/`, sem supressões e sem
falhas de leitura. Não apontou achados de alta severidade. Apontou sete alertas
B608, todos de severidade média e confiança baixa, em consultas SQL montadas
com fragmentos em `discard_tools.py` e `routes_maps_tools.py`.
Na inspeção desses pontos, os fragmentos vêm de constantes ou alternativas
fixas; valores externos são enviados separadamente por parâmetros `%s`.
Há também teste de entrada semelhante a SQL injection em consulta de locais.
Os alertas foram mantidos no relatório, não silenciados para melhorar a nota.

Os relatórios locais estão em `reports/`, ignorado pelo Git:
`coverage.xml`, `pytest.xml`, `bandit.json`, `secret-review.json`,
`dependency-audit.json` e `dependency-audit-fixed.json`.

A auditoria final das 99 dependências efetivas de produção da instalação limpa
não encontrou vulnerabilidades conhecidas na base consultada. Isso não garante
ausência de vulnerabilidades ainda não publicadas. A árvore foi obtida da
instalação real, incluindo dependências transitivas; o resultado não se limita
aos pacotes diretos de `requirements.txt`.

Antes de executar o projeto no ambiente local, atualize os pacotes:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
```

Inclua `security-constraints.txt` e os novos testes no próximo commit junto com
as alterações de requisitos. Apenas commitar arquivos já rastreados deixaria
de fora o arquivo de constraints, necessário para instalar as dependências.

## Pendências que a cobertura não resolve

As rotas do chat e de sessões recebem a identidade do usuário na requisição,
sem comprovação de autenticação implementada neste serviço. O endpoint de
métricas também não tem autorização administrativa própria. Antes de expor
a API publicamente, a identidade e o acesso ao monitor precisam ser validados
por autenticação no serviço ou por um gateway confiável. CORS não substitui isso.

O ambiente original emitia avisos de compatibilidade de Pydantic V1 com Python
3.14 e de futura mudança no serializador do LangGraph. A instalação limpa
corrigida executou os 169 testes sem esses avisos. Isso não comprova todas as
integrações com provedores em produção; os testes não realizam inferências pagas.

O CI executa em push para `main` e em pull requests destinados à `main`.
Um push apenas para uma branch de funcionalidade não aciona esse workflow.
O resultado A e o Quality Gate só poderão ser confirmados na análise Sonar;
hotspots podem exigir revisão manual e a cobertura de código novo pode diferir
da cobertura total medida localmente.
