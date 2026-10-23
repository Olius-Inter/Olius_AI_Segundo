# Testes do ChatBot

Na raiz do repositório:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
```

O pytest descobre testes em `tests/` e em subpastas de `app/`.
Use arquivos `test_*.py` ou `*_test.py`. Uma execução sem testes falha.

A suíte inicial valida configuração completa, ausência de cada chave,
ausência do PDF e combinação dos problemas. Usa valores fictícios,
bloqueia o carregamento do `.env` e não chama serviços de IA.
O arquivo PDF temporário apenas verifica existência; não testa leitura de PDF.

O comando gera `reports/coverage.xml` para o Sonar e `reports/pytest.xml`
para diagnóstico. Fontes usam caminhos relativos ao repositório.
Os testes ficam separados do código principal no Sonar e na cobertura.

A cobertura considera todo o código em `app/`. A suíte inicial ainda não
testa agentes, guardrails nem rotas; o relatório reflete essa limitação.
Não há percentual mínimo local configurado; o CI aguarda o Quality Gate
definido no Sonar. Amplie a suíte ao implementar cada funcionalidade,
substituindo chamadas externas por mocks nos testes unitários.
