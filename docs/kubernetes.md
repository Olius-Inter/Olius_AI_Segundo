# Kubernetes da OlivIA

Os manifests em k8s/ incluem somente Deployment ia, Service ia (ClusterIP,
80 para 8000) e ConfigMap ia-config no namespace existente olius.
Não criam namespace, bancos, Ingress, LoadBalancer ou recursos da Core.
O Secret ia-secrets deve ser criado separadamente, fora do repositório.

## Antes de aplicar (CloudShell, Bash)

Confirme a conta, a região, o contexto e a saúde do EKS:

```bash
aws sts get-caller-identity --query Account --output text
kubectl config current-context
kubectl get nodes -L eks.amazonaws.com/nodegroup
kubectl get pods -n olius -o wide
kubectl describe nodes
```

Prossiga somente com os nós Ready, Core saudável e capacidade disponível.
Requests de 250m/512Mi e limites de 1 CPU/1536Mi são estimativas iniciais,
não medições de carga. RollingUpdate permite um pod adicional temporário.
Confirme também acesso dos nós ao ECR e saída de rede para os serviços externos.
Use kubectl compatível com a versão do cluster; o cliente local 1.28 não foi
validado contra o EKS descrito no contexto.

## Imagem e configuração

Publique a imagem linux/amd64 no ECR antes desta etapa.
Substitua SUBSTITUIR_SHA em k8s/deployment.yaml pela tag publicada e confirme
conta/região do registro. Não aplique com o marcador ainda presente.

Revise CORE_AUTH_URL em k8s/configmap.yaml: o código exige HTTPS e atualmente
consulta o Gateway público para autenticação. http://core não é aceito.
O Service interno http://ia não cria integração nem autorização entre Core e IA.
ClusterIP não impede chamadas de outros pods. A API continua exigindo Bearer
validado pela Core; esta configuração não implementa um proxy de chat na Core.
CORS_ORIGINS contém apenas origens locais para acesso por port-forward.
Revise origens se houver um cliente web autorizado.

Prepare um arquivo exclusivo de Secrets, ../olivia-secrets.env, protegido e fora do repositório, com os pares NOME=valor:

- CHATGPT_API_KEY, GROQ_API_KEY, MONGODB_URI e DATABASE_URL.
- QDRANT_URL e QDRANT_API_KEY conforme o serviço.
- GOOGLE_MAPS_API_KEY e TYPESAFE_API_KEY conforme as funcionalidades utilizadas.

Não reutilize diretamente ../olivia-runtime.env do teste Docker: ele pode conter
configuração que pertence ao ConfigMap. Remova CORE_AUTH_URL do arquivo usado
para criar ia-secrets; mantenha também CORS_ORIGINS e GOOGLE_MAPS_API_URL somente
em ia-config. O arquivo de Secrets deve conter apenas as chaves listadas acima.
O Deployment carrega ia-secrets depois de ia-config: em caso de nomes repetidos,
o Secret tem precedência e pode sobrescrever a URL revisada no ConfigMap.

Use formato psycopg para DATABASE_URL e SSL adequado ao serviço; não copie
uma URL JDBC. Não use dados reais em comandos publicados ou no chat.
No CloudShell, evite histórico de shell para valores: use um editor e
permissão 600 no arquivo. Não envie o arquivo junto ao código.

Para a primeira criação, após confirmar que ia-secrets ainda não existe:

```bash
kubectl get secrets -n olius
chmod 600 ../olivia-secrets.env &&
kubectl create secret generic ia-secrets -n olius --from-env-file=../olivia-secrets.env &&
rm -- ../olivia-secrets.env
```

O arquivo local só é removido se a criação do Secret tiver sucesso. Se falhar,
corrija a causa e tente novamente com o arquivo preservado.

Se ia-secrets já existir, revise suas chaves e planeje a atualização específica;
não apague ou substitua Secrets da Core. Confira nomes de chaves sem imprimir valores:

```bash
kubectl describe secret ia-secrets -n olius
```

## Revisar, validar e aplicar somente a IA

Execute na raiz do repositório. O render não contém Secret:

```bash
kubectl kustomize k8s
kubectl apply --dry-run=server -k k8s
```

Após conferir o resultado, aplique manualmente:

```bash
kubectl apply -k k8s
kubectl rollout status deployment/ia -n olius --timeout=300s
kubectl get pods -n olius -l app.kubernetes.io/component=ia -o wide
kubectl get svc ia -n olius
kubectl logs deployment/ia -n olius --tail=50
kubectl get events -n olius --sort-by=.metadata.creationTimestamp
```

Não aplique diretórios antigos da Core. Não compartilhe logs sem revisar dados
sensíveis. Timeout de rollout status não cancela a atualização.
Após mudar ConfigMap ou Secret, reinicie somente ia e acompanhe o rollout.

## Probes e teste

Startup e liveness consultam /health por HTTP; readiness exige status igual
a ok no JSON, pois a rota atual pode retornar HTTP 200 com problemas.
As probes não chamam LLM e não comprovam acesso aos bancos, Core ou provedores.
O filesystem é somente leitura, com /tmp e cache em volumes efêmeros.
Não há persistência local, nem necessidade de EBS CSI.

```bash
kubectl port-forward -n olius service/ia 8000:80 --address=127.0.0.1
```

Em outro terminal, consulte http://localhost:8000/health.
Não envie Bearer ou credenciais por um endpoint HTTP público.
Testes de chat precisam de autenticação, serviços configurados e consomem
cota de LLM; executar separadamente após validar a infraestrutura.

## Limpeza específica

Se precisar remover somente estes recursos, após revisar o alvo:

```bash
kubectl delete -k k8s
```

O comando não remove ia-secrets. Não apague o namespace olius.
Nenhum desses comandos foi executado contra a AWS nesta preparação.
