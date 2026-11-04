# Docker da OlivIA

Execute os comandos na raiz deste repositório. A imagem usa Python 3.14,
como o CI, e um usuário sem privilégios (UID/GID 10001). O processo Uvicorn
escuta em 0.0.0.0:8000, com um worker. Não utiliza reload.

## Construir

O Docker Desktop deve estar iniciado, usando containers Linux.

```bash
docker build --platform linux/amd64 -t olius-ia:local .
```

A instalação inclui security-constraints.txt e executa pip check.
O build precisa de internet para obter a imagem base, pacotes Debian e Python.
A compatibilidade das dependências será confirmada pelo build; a presença do
Dockerfile não comprova uma imagem construída.

Somente app/, frontend/ e os arquivos de dependências são copiados.
O PDF do FAQ acompanha app/data/faq.pdf. A lista de inclusão do .dockerignore
exclui Git, testes, relatórios e arquivos locais; arquivos .env e chaves também
são excluídos dentro das pastas incluídas. Não coloque credenciais no código,
em argumentos de build ou no Dockerfile.

## Configurar o ambiente

Crie um arquivo de ambiente fora do repositório, por exemplo
../olivia-runtime.env. Use valores reais somente nesse arquivo local,
sem compartilhar seu conteúdo ou incluí-lo no ZIP enviado à AWS.

Variáveis obrigatórias na validação atual:

- CHATGPT_API_KEY
- GROQ_API_KEY
- MONGODB_URI
- DATABASE_URL (formato aceito pelo psycopg, não JDBC)

Configure também QDRANT_URL e QDRANT_API_KEY conforme seu serviço.
Para mapas, configure GOOGLE_MAPS_API_KEY e
GOOGLE_MAPS_API_URL=https://mapstools.googleapis.com/mcp.
TYPESAFE_API_KEY habilita a configuração do juiz conforme a implementação atual.

CORE_AUTH_URL deve apontar para a rota de sessão da Core e exige HTTPS no
código atual. Sem essa variável, utiliza o Gateway AWS definido em
app/security.py. O endereço http://core não é aceito atualmente.
CORS_ORIGINS recebe origens explícitas separadas por vírgula, quando necessário.

Não há banco ou serviço externo embutido na imagem. Confirme conectividade,
permissões e configuração TLS dos bancos antes de testar operações.

## Executar e verificar

```bash
docker run --detach --name olivia-local --env-file ../olivia-runtime.env --publish 127.0.0.1:8000:8000 olius-ia:local
docker inspect --format '{{.State.Health.Status}}' olivia-local
docker logs --tail 50 olivia-local
```

Acesse http://localhost:8000/health e http://localhost:8000/monitor.
A API do monitor exige usuário administrador; o chat exige Bearer validado
pela Core. Iniciar o container e consultar health não executa uma conversa.

O HEALTHCHECK exige status igual a ok no JSON de /health, além de uma
resposta HTTP válida. Isso verifica a configuração avaliada pela aplicação,
mas não comprova acesso a MongoDB, Qdrant, PostgreSQL, Core ou provedores LLM.
No Kubernetes, configure probes explicitamente: o HEALTHCHECK da imagem
não substitui readinessProbe e livenessProbe.

Para encerrar e remover somente o container local criado acima:

```bash
docker stop olivia-local
docker rm olivia-local
```

## Publicação posterior

A arquitetura linux/amd64 corresponde aos nós x86_64 descritos para o EKS.
Use uma tag nova, preferencialmente o SHA do commit, ao publicar no ECR.
No EKS, injete configuração e Secrets em runtime e use Service ClusterIP.
Esta etapa não cria recursos AWS, não publica a imagem e não altera a Core.
