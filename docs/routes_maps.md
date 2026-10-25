# Rotas e Mapas

As duas tools estão em `app/tools/routes_maps_tools.py`. O agente deve ser
executado com `ainvoke`/`astream`, pois as chamadas MCP são assíncronas.

## Contexto enviado pelo backend

Após autenticar a sessão na Core, o web/mobile fornece sua localização autorizada:

```python
config = {"configurable": {
    "user_id": str(usuario_autenticado.id),
    "localizacao": {"latitude": -23.5, "longitude": -46.7},
}}
```

O backend deve validar a identidade da sessão antes de preencher o contexto.
As duas tools consultam exclusivamente PEVs aprovados de responsáveis ativos.
Usuários ativos B2B e B2C têm o mesmo acesso a esses PEVs, sem permissão adicional.
Não há consulta de B2Bs comuns, exceção para ADMIN nem flag de acesso especial.

## Buscar locais próximos

`buscar_locais_proximos` usa coordenadas enviadas pelo dispositivo, sem origem
fictícia. Seleciona somente PEVs aprovados, tanto para B2B quanto para B2C, no primeiro raio não vazio:
100 m, 150 m, 200 m etc. O teto padrão é 5.000 m e pode ser alterado pelo argumento
`raio_maximo_metros` até 50.000 m. Não há corte de três destinos.

Uma consulta SQL calcula a distância geográfica dos candidatos. O raio efetivo
é calculado matematicamente, sem repetir o SELECT para cada incremento. Depois
chama `calcular_tempos_deslocamento.ainvoke` com os IDs dos endereços selecionados.
A segunda consulta revalida aprovação do PEV e atividade do usuário/responsável antes das chamadas remotas.

Endereços sem coordenadas não entram na classificação por proximidade. O retorno
informa `cadastros_sem_coordenadas` e `busca_completa=false`; isso não comprova
que não existam outros locais próximos. Coordenadas devem ser completadas no
cadastro por um processo próprio, sem inventar valores.

## Calcular tempos diretamente

`calcular_tempos_deslocamento` recebe `cidade`, `estado` ou `ids_enderecos`.
Por exemplo: todos os PEVs aprovados da cidade `Osasco`, estado `SP`.
Sem limite de raio, quantidade ou paginação: todos os PEVs aprovados do
filtro são enviados ao cálculo. A origem pode ser a localização do contexto ou
`origem_endereco` explicitamente informado pelo usuário.

Há duas chamadas `compute_routes` por destino, DRIVE e WALK. Cada viagem parte
da mesma origem, sem otimização de roteiro entre vários estabelecimentos.
Grandes consultas de cidade podem demorar e consumir quota proporcional ao
número de destinos; não há corte silencioso. Em escala, considerar tarefa de
exportação/processamento em segundo plano, em vez de uma resposta de chat única.

O banco é a fonte dos locais: `search_places` não descobre destinos nesta etapa.
Destinos com coordenadas usam latitude/longitude; na consulta direta, endereços
sem coordenadas são enviados como endereço completo ao Google. Distância em
linha reta e distância/tempo do trajeto são campos separados. Erros individuais
ou ausência de rota não viram valores zero, e os demais modos continuam.

PEV de cidadão não possui nome público próprio no modelo: usa um rótulo de
endereço, sem expor o nome do responsável. Um estabelecimento B2B só aparece
como destino quando vinculado a um PEV aprovado, usando o endereço desse PEV.

Preservar atribuição e links retornados pelo Google e exibir o aviso de WALK.
Não armazenar resultados Google no banco nem prometer trânsito ao vivo.

## Testes

Os scripts manuais com shopping/farmácia/colégio foram removidos. Os testes
automatizados de conexão MCP foram preservados; as regras definitivas estão em
`tests/test_routes_maps_tools.py`, com banco e Google simulados.

Executar `python -m pytest`. Nenhum teste usa a chave real para calcular trajetos.
