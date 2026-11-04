# Testes do ChatBot

Na raiz do repositório:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
```

O pytest descobre testes em `tests/` e em subpastas de `app/`.
Use arquivos `test_*.py` ou `*_test.py`. Uma execução sem testes falha.

A suíte valida configuração, agentes, grafo, guardrails, memória, ferramentas,
rotas, métricas e embeddings. Os testes usam dados fictícios e substituem
provedores e bancos por mocks, sem chamadas pagas a serviços de IA.
O arquivo PDF temporário apenas verifica existência; não testa leitura de PDF.

O comando gera `reports/coverage.xml` para o Sonar e `reports/pytest.xml`
para diagnóstico. Fontes usam caminhos relativos ao repositório.
Os testes ficam separados do código principal no Sonar e na cobertura.

A cobertura considera todo o código em `app/`, sem excluir módulos de produção.
O pytest falha se a cobertura total ficar abaixo de 80%. Esse limite local
não substitui as condições sobre código novo, segurança e duplicação do Sonar.
O frontend não faz parte da cobertura Python nem de `sonar.sources=app`.

A API permite CORS apenas para as origens explícitas em `CORS_ORIGINS`,
separadas por vírgulas. Os padrões são localhost e 127.0.0.1 nas portas
8000, 3000 e 5173. Configure os domínios reais do frontend no ambiente de deploy.
Isso não implementa autenticação ou autorização dos usuários.
