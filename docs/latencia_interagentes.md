# Coleta de latência dos agentes

A medição é automática nas novas mensagens enviadas a `POST /api/v1/chat`.
As telas não foram alteradas. Reinicie a API após instalar esta mudança.

## Como salvar a amostra

1. Execute os testes de uma persona, identificando a persona e as sessões nas suas anotações.
2. Espere os turnos terminarem. A tela principal fica em `http://127.0.0.1:8000/monitor`; abra `http://127.0.0.1:8000/api/v1/monitor` para obter o JSON.
3. Salve o JSON antes de reiniciar a API ou ultrapassar 50 turnos.
4. Repita a coleta para a outra persona e salve um arquivo separado.

O histórico continua em memória, limitado aos últimos 50 turnos concluídos.
Ele não é persistido por esta mudança. Os agregados misturam todos os turnos
retidos no processo; mantenha as amostras separadas ou agrupe as sessões no JSON.
Nenhuma pergunta ou resposta é registrada pela instrumentação.

## Campos por turno

Cada item de `turnos` mantém os campos anteriores e acrescenta:

- `turno_id`: identifica a requisição, mesmo quando a sessão tem várias mensagens.
- `etapas`: uma entrada para cada execução de nó, inclusive guardrails.
- `transicoes`: intervalos entre etapas consecutivas que não se sobrepõem.

Em `etapas`, `agente` identifica o nó e `ordem` diferencia execuções repetidas.
`inicio_em` e `fim_em` são horários completos com data e fuso de São Paulo.
`inicio_ms` e `fim_ms` são posições na linha do tempo a partir da abertura do turno.
`duracao_ms` mede o tempo decorrido no nó com relógio monotônico (`perf_counter`),
incluindo ferramentas, chamadas de modelo e tentativas de fallback dentro dele.
`status` indica `erro` se o nó lançou uma exceção e `ok` nos demais casos.
Um guardrail que bloqueia corretamente pode ter etapa `ok` e turno `bloqueado`;
esse status não indica resolução do atendimento.

Em `transicoes`, `de` e `para` identificam as etapas. `intervalo_ms` é o início
da próxima menos o fim da anterior. Esse intervalo inclui o trabalho do grafo,
como encaminhamento e checkpoint; não é uma medição isolada de rede.
Sobreposições não geram intervalos negativos nem são tratadas como espera.
Se o fluxo for paralelizado no futuro, a ordem de execução sozinha não comprova
dependência entre agentes: nesse caso, será necessário registrar as arestas causais.

## Agregados para o relatório

- `por_agente`: execuções, erros, duração média e p95 por agente.
- `por_transicao`: ocorrências, intervalo médio e p95 por par de etapas.

Os tempos são expressos em milissegundos. O p95 usa nearest-rank: ordene as
amostras e selecione a posição `ceil(0,95 × quantidade)`, contando a partir de 1.
O tempo total do turno continua incluindo trabalho fora dos nós, como a abertura
da sessão. Portanto, não precisa ser igual à soma das durações dos agentes.
Falhas preservam as etapas já executadas e a duração da etapa que lançou o erro.
Turnos anteriores à instrumentação não ganham tempos retroativos.
