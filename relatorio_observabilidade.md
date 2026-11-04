# Relatório de observabilidade do assistente Olius

## 1. Objetivo e critérios

Este relatório apresenta os resultados de duas amostras de testes, considerando os requisitos de custo estimado para 100 e 1.000 usuários semanais, tempo total de resposta, latência interagentes, índice de erros, custo por resolução e retorno sobre investimento (ROI).

Foram avaliadas as personas **Ricardo (B2B)** e **Fernanda (B2C)**. Os cenários consideram **15 a 20 turnos por usuário B2B por semana** e **10 a 15 turnos por usuário B2C por semana**. Em cada amostra, o cenário menor corresponde aos primeiros turnos do cenário maior. Esses recortes não são amostras independentes e não devem ser somados.

Os valores estão em **dólares americanos (US$)** e representam custos estimados de uso dos modelos registrados nos testes. As projeções assumem o mesmo padrão de uso para todos os usuários e não incluem infraestrutura, manutenção ou outros custos operacionais. Não representam uma fatura do provedor. Para a estimativa mensal, foram considerados **4 a 5 semanas**.

- **Taxa de erro:** turnos com status erro ÷ total de turnos × 100. Bloqueios são registrados separadamente, pois não representam necessariamente uma falha do sistema.
- **Latência média:** soma dos tempos de resposta ÷ quantidade de turnos, incluindo erros e bloqueios.
- **p95:** tempos em ordem crescente, usando a posição `arredondar_para_cima(0,95 × n)`.
- **Custo semanal projetado:** custo da sequência de uma persona × quantidade de usuários.
- **Custo por resolução:** custo total dos atendimentos avaliados ÷ quantidade de atendimentos efetivamente resolvidos. Os custos das tentativas sem resolução também entram no numerador.

## 2. Primeira amostra: custos e desempenho

A primeira amostra foi utilizada para obter os primeiros valores de consumo, custo, erros e tempo de resposta. Esses dados servem de base para as projeções de custo semanal e mensal das duas personas. Nesta etapa não foi registrada a avaliação de resolução de cada atendimento, portanto o custo por resolução foi calculado na segunda amostra.

### 2.1. Tempo total de resposta e erros

| Persona | Turnos | Erros | Taxa de erro | Bloqueados | Latência média (s) | p95 (s) |
| --- | --- | --- | --- | --- | --- | --- |
| B2B — Ricardo | 15 | 4 | 26,67% | 1 | 6,55 | 14,6 |
| B2B — Ricardo | 20 | 4 | 20,00% | 1 | 5,95 | 13,1 |
| B2C — Fernanda | 10 | 1 | 10,00% | 1 | 8,26 | 36,9 |
| B2C — Fernanda | 15 | 1 | 6,67% | 1 | 13,09 | 46,9 |

### 2.2. Consumo e custo registrado

Os totais de tokens de entrada e saída e de custo foram coletados diretamente do monitor e utilizados como referência neste relatório.

| Persona | Turnos | Tokens de entrada | Tokens de saída | Tokens totais | Custo da sequência (US$) |
| --- | --- | --- | --- | --- | --- |
| B2B — Ricardo | 15 | 56.262 | 3.132 | 59.394 | 0,007192 |
| B2B — Ricardo | 20 | 75.763 | 3.651 | 79.414 | 0,009402 |
| B2C — Fernanda | 10 | 50.531 | 4.887 | 55.418 | 0,010657 |
| B2C — Fernanda | 15 | 91.645 | 8.863 | 100.508 | 0,019065 |

### 2.3. Projeções para 100 e 1.000 usuários

Cada linha pressupõe que todos os usuários sigam o perfil da persona indicada. Não foi estimada uma composição mista de usuários B2B e B2C.

| Persona | Turnos/usuário/semana | 100 usuários: semanal (US$) | 100 usuários: mensal (US$) | 1.000 usuários: semanal (US$) | 1.000 usuários: mensal (US$) |
| --- | --- | --- | --- | --- | --- |
| B2B — Ricardo | 15 | 0,719200 | 2,876800 a 3,596000 | 7,192000 | 28,768000 a 35,960000 |
| B2B — Ricardo | 20 | 0,940200 | 3,760800 a 4,701000 | 9,402000 | 37,608000 a 47,010000 |
| B2C — Fernanda | 10 | 1,065700 | 4,262800 a 5,328500 | 10,657000 | 42,628000 a 53,285000 |
| B2C — Fernanda | 15 | 1,906500 | 7,626000 a 9,532500 | 19,065000 | 76,260000 a 95,325000 |

## 3. Segunda amostra: complementação dos testes

A segunda amostra dá continuidade aos testes de custos e complementa os dados da primeira. Além dos mesmos indicadores de consumo, custo, erros e tempo de resposta, foram registrados os tempos de execução dos agentes, os intervalos entre as etapas e a avaliação de resolução dos atendimentos. Assim, foi possível calcular a **latência interagentes** e o **custo por resolução**.

Nesta amostra, cada turno foi tratado como um atendimento avaliado. A marcação **1** indica atendimento considerado resolvido, e **0**, atendimento sem resolução. O status técnico `ok` ou `Concluído` não garante que a solicitação foi resolvida: a avaliação do resultado foi registrada separadamente.

### 3.1. Tempo total de resposta e erros

| Persona | Turnos | Erros | Taxa de erro | Bloqueados | Latência média (s) | p95 (s) |
| --- | --- | --- | --- | --- | --- | --- |
| B2B — Ricardo | 15 | 2 | 13,33% | 0 | 5,89 | 11,6 |
| B2B — Ricardo | 20 | 2 | 10,00% | 0 | 5,57 | 10,5 |
| B2C — Fernanda | 10 | 0 | 0,00% | 0 | 7,64 | 11,1 |
| B2C — Fernanda | 15 | 0 | 0,00% | 0 | 8,58 | 19,1 |

### 3.2. Consumo e custo registrado

Os totais de tokens de entrada e saída e de custo foram coletados diretamente do monitor e utilizados como referência neste relatório.

| Persona | Turnos | Tokens de entrada | Tokens de saída | Tokens totais | Custo da sequência (US$) |
| --- | --- | --- | --- | --- | --- |
| B2B — Ricardo | 15 | 64.300 | 3.221 | 67.521 | 0,008041 |
| B2B — Ricardo | 20 | 84.233 | 3.853 | 88.086 | 0,010350 |
| B2C — Fernanda | 10 | 59.059 | 2.727 | 61.786 | 0,007269 |
| B2C — Fernanda | 15 | 105.218 | 3.939 | 109.157 | 0,012491 |

### 3.3. Projeções para 100 e 1.000 usuários

Cada linha pressupõe que todos os usuários sigam o perfil da persona indicada. Não foi estimada uma composição mista de usuários B2B e B2C.

| Persona | Turnos/usuário/semana | 100 usuários: semanal (US$) | 100 usuários: mensal (US$) | 1.000 usuários: semanal (US$) | 1.000 usuários: mensal (US$) |
| --- | --- | --- | --- | --- | --- |
| B2B — Ricardo | 15 | 0,804100 | 3,216400 a 4,020500 | 8,041000 | 32,164000 a 40,205000 |
| B2B — Ricardo | 20 | 1,035000 | 4,140000 a 5,175000 | 10,350000 | 41,400000 a 51,750000 |
| B2C — Fernanda | 10 | 0,726900 | 2,907600 a 3,634500 | 7,269000 | 29,076000 a 36,345000 |
| B2C — Fernanda | 15 | 1,249100 | 4,996400 a 6,245500 | 12,491000 | 49,964000 a 62,455000 |

### 3.4. Custo por resolução

O custo total inclui as tentativas com erro e as respostas que não resolveram a solicitação. Apenas os atendimentos marcados como resolvidos entram no denominador.

| Persona | Atendimentos avaliados | Resolvidos | Sem resolução | Taxa de resolução | Custo total (US$) | Custo por resolução (US$) |
| --- | --- | --- | --- | --- | --- | --- |
| B2B — Ricardo | 15 | 11 | 4 | 73,33% | 0,008041 | 0,000731000 |
| B2B — Ricardo | 20 | 12 | 8 | 60,00% | 0,010350 | 0,000862500 |
| B2C — Fernanda | 10 | 6 | 4 | 60,00% | 0,007269 | 0,001211500 |
| B2C — Fernanda | 15 | 6 | 9 | 40,00% | 0,012491 | 0,002081833 |

Por exemplo, para Ricardo no recorte de 20 atendimentos: **US$ 0,010350 ÷ 12 = US$ 0,000862500 por resolução**. Para Fernanda no recorte de 15 atendimentos: **US$ 0,012491 ÷ 6 ≈ US$ 0,002081833 por resolução**.

### 3.5. Duração dos agentes e latência interagentes

As tabelas de **duração por agente** mostram o tempo gasto no processamento de cada etapa. As tabelas de **intervalos entre etapas** representam a latência interagentes: o tempo entre o término de uma etapa e o início da próxima. São medidas distintas; o intervalo não inclui a duração completa do agente seguinte.

Todos os valores abaixo estão em **milissegundos (ms)**. Foram mantidos os agregados fornecidos, pois os registros individuais de todas as execuções não acompanham o material. Cada média corresponde às execuções ou ocorrências daquela linha; não foi calculada uma média simples entre médias nem um p95 global a partir dos p95 por agente. Com uma única ocorrência, média e p95 são iguais e não permitem avaliar a variação de desempenho.

#### B2B — 15 turnos

**Duração por agente**

| Agente | Execuções | Erros de execução | Média (ms) | p95 (ms) |
| --- | --- | --- | --- | --- |
| guardrail_entrada | 15 | Não informado | 1.625,043 | 2.295,495 |
| router | 15 | Não informado | 1.742,469 | 2.577,552 |
| faq | 2 | Não informado | 975,743 | 1.910,416 |
| oil_advisor | 1 | Não informado | 2.547,163 | 2.547,163 |
| business_analyst | 1 | Não informado | 3.162,504 | 3.162,504 |
| ranking_sustainable | 2 | Não informado | 4.842,846 | 5.626,525 |
| orchestrator | 5 | Não informado | 1.627,647 | 1.771,158 |
| guardrail_saida | 5 | Não informado | 1.557,979 | 1.797,214 |
| routes_maps | 1 | Não informado | 4.077,555 | 4.077,555 |

**Intervalos entre etapas — latência interagentes**

| De | Para | Ocorrências | Média (ms) | p95 (ms) |
| --- | --- | --- | --- | --- |
| guardrail_entrada | router | 15 | 4,929 | 7,126 |
| router | faq | 2 | 5,083 | 5,570 |
| router | oil_advisor | 1 | 4,314 | 4,314 |
| oil_advisor | orchestrator | 1 | 3,221 | 3,221 |
| orchestrator | guardrail_saida | 5 | 3,926 | 4,316 |
| router | business_analyst | 1 | 5,992 | 5,992 |
| business_analyst | orchestrator | 1 | 3,536 | 3,536 |
| router | ranking_sustainable | 2 | 6,763 | 9,701 |
| ranking_sustainable | orchestrator | 2 | 4,409 | 4,586 |
| router | routes_maps | 1 | 4,946 | 4,946 |
| routes_maps | orchestrator | 1 | 4,504 | 4,504 |

#### B2B — 20 turnos

**Duração por agente**

| Agente | Execuções | Erros de execução | Média (ms) | p95 (ms) |
| --- | --- | --- | --- | --- |
| ranking_sustainable | 2 | 0 | 4.842,845 | 5.626,525 |
| routes_maps | 1 | 0 | 4.077,555 | 4.077,555 |
| business_analyst | 1 | 0 | 3.162,504 | 3.162,504 |
| oil_advisor | 1 | 0 | 2.547,163 | 2.547,163 |
| router | 20 | 0 | 1.961,783 | 2.807,892 |
| guardrail_entrada | 20 | 0 | 1.707,077 | 2.295,495 |
| orchestrator | 5 | 0 | 1.627,647 | 1.771,158 |
| guardrail_saida | 5 | 0 | 1.557,979 | 1.797,214 |
| faq | 2 | 2 | 975,743 | 1.910,416 |

**Intervalos entre etapas — latência interagentes**

| De | Para | Ocorrências | Média (ms) | p95 (ms) |
| --- | --- | --- | --- | --- |
| business_analyst | orchestrator | 1 | 3,536 | 3,536 |
| guardrail_entrada | router | 20 | 5,034 | 7,126 |
| oil_advisor | orchestrator | 1 | 3,221 | 3,221 |
| orchestrator | guardrail_saida | 5 | 3,926 | 4,316 |
| ranking_sustainable | orchestrator | 2 | 4,409 | 4,586 |
| router | business_analyst | 1 | 5,992 | 5,992 |
| router | faq | 2 | 5,082 | 5,57 |
| router | oil_advisor | 1 | 4,314 | 4,314 |
| router | ranking_sustainable | 2 | 6,763 | 9,701 |
| router | routes_maps | 1 | 4,946 | 4,946 |
| routes_maps | orchestrator | 1 | 4,504 | 4,504 |

#### B2C — 10 turnos

**Duração por agente**

| Agente | Execuções | Erros de execução | Média (ms) | p95 (ms) |
| --- | --- | --- | --- | --- |
| routes_maps | 4 | 0 | 3.463,588 | 4.450,448 |
| oil_advisor | 3 | 0 | 2.168,22 | 2.271,238 |
| router | 10 | 0 | 1.727,713 | 2.693,998 |
| orchestrator | 7 | 0 | 1.635,843 | 2.036,013 |
| guardrail_saida | 7 | 0 | 1.630,333 | 1.794,247 |
| guardrail_entrada | 10 | 0 | 1.545,773 | 2.227,493 |

**Intervalos entre etapas — latência interagentes**

| De | Para | Ocorrências | Média (ms) | p95 (ms) |
| --- | --- | --- | --- | --- |
| guardrail_entrada | router | 10 | 4,35 | 6,72 |
| oil_advisor | orchestrator | 3 | 2,608 | 2,854 |
| orchestrator | guardrail_saida | 7 | 2,415 | 3,693 |
| router | oil_advisor | 3 | 2,218 | 3,815 |
| router | routes_maps | 4 | 3,074 | 3,911 |
| routes_maps | orchestrator | 4 | 3,111 | 3,938 |

#### B2C — 15 turnos

**Duração por agente**

| Agente | Execuções | Erros de execução | Média (ms) | p95 (ms) |
| --- | --- | --- | --- | --- |
| ranking_sustainable | 1 | 0 | 5.026,75 | 5.026,75 |
| business_analyst | 2 | 0 | 4.089,593 | 4.267,27 |
| routes_maps | 4 | 0 | 3.463,588 | 4.450,448 |
| oil_advisor | 3 | 0 | 2.168,22 | 2.271,238 |
| guardrail_entrada | 15 | 0 | 2.088,496 | 9.650,399 |
| router | 15 | 0 | 1.850,667 | 2.996,276 |
| orchestrator | 10 | 0 | 1.843,505 | 3.243,654 |
| guardrail_saida | 10 | 0 | 1.692,454 | 2.063,731 |

**Intervalos entre etapas — latência interagentes**

| De | Para | Ocorrências | Média (ms) | p95 (ms) |
| --- | --- | --- | --- | --- |
| business_analyst | orchestrator | 2 | 5,082 | 5,576 |
| guardrail_entrada | router | 15 | 4,795 | 6,72 |
| oil_advisor | orchestrator | 3 | 2,608 | 2,854 |
| orchestrator | guardrail_saida | 10 | 3,238 | 6,149 |
| ranking_sustainable | orchestrator | 1 | 5,621 | 5,621 |
| router | business_analyst | 2 | 5,514 | 5,587 |
| router | oil_advisor | 3 | 2,218 | 3,815 |
| router | ranking_sustainable | 1 | 2,465 | 2,465 |
| router | routes_maps | 4 | 3,074 | 3,911 |
| routes_maps | orchestrator | 4 | 3,111 | 3,938 |

Na segunda amostra B2B de 20 turnos, as duas execuções do agente `faq` foram registradas com erro. Na segunda amostra B2C, não houve erro técnico registrado, mas parte dos atendimentos foi marcada como não resolvida. Isso reforça a necessidade de distinguir a execução técnica da resolução da solicitação.

## 4. ROI — retorno sobre investimento

**O ROI não foi calculado.** Não foi possível obter essa medida devido ao tempo restante para a entrega do projeto, que não permitiu reunir os integrantes e realizar a medição dos valores necessários ao cálculo, incluindo o tempo e o custo do atendimento manual para comparação com o uso do chatbot. Portanto, não é apresentado um valor estimado de ROI sem essas medições.

## 5. Considerações sobre os resultados

As médias de tempo total de resposta deste relatório foram recalculadas a partir das latências por turno fornecidas, com arredondamento para duas casas decimais. Os p95 seguem o método descrito na seção 1. Na segunda amostra B2C de 10 turnos, o p95 anotado era **11,6 s**, mas o maior tempo entre os dez turnos listados é **11,1 s**. Pelo método adotado, a posição é 10; por isso foi utilizado **11,1 s**.

Os totais de custos e tokens foram coletados diretamente do monitor e adotados como fonte para as tabelas de consumo, as projeções de custo e o cálculo do custo por resolução. A comparação com os valores individuais transcritos apresenta diferenças, registradas abaixo para transparência. Essas diferenças não demonstram, por si só, um erro de cálculo de quem coletou os dados.

No caso dos custos, o arredondamento dos valores exibidos por turno pode contribuir para diferenças na soma, mas essa hipótese não foi confirmada. Nos tokens, que são contagens inteiras, o arredondamento não explica a diferença; sua origem permanece sem confirmação.

| Amostra | Persona | Turnos | Total registrado no monitor (US$) | Soma dos custos listados (US$) |
| --- | --- | --- | --- | --- |
| 1 | B2B | 15 | 0,007192 | 0,007202 |
| 1 | B2B | 20 | 0,009402 | 0,009412 |
| 1 | B2C | 15 | 0,019065 | 0,019064 |
| 2 | B2B | 15 | 0,008041 | 0,008042 |
| 2 | B2B | 20 | 0,010350 | 0,010352 |
| 2 | B2C | 10 | 0,007269 | 0,007270 |
| 2 | B2C | 15 | 0,012491 | 0,012493 |

Também há uma diferença nos tokens da segunda amostra B2B: os valores por turno somam **67.679 tokens nos primeiros 15 turnos** e **88.244 nos 20 turnos**, enquanto os totais coletados diretamente do monitor são **67.521** e **88.086**, respectivamente. As tabelas de consumo preservam os totais consolidados, sem redistribuir essa diferença entre entrada e saída.

As projeções e os custos por resolução usam os **totais consolidados exibidos pelo monitor**, de forma consistente. A adoção dessa fonte identifica a origem dos valores e não representa uma validação independente do cálculo interno do monitor. Na segunda amostra B2B de 15 turnos, a projeção mensal para 1.000 usuários foi corrigida para **US$ 32,164000 a US$ 40,205000**, correspondente a 4 e 5 vezes o custo semanal de US$ 8,041000.

As amostras são pequenas e descrevem os testes realizados; não constituem um teste de carga com 100 ou 1.000 usuários simultâneos. As diferenças de desempenho entre as amostras não demonstram, por si só, uma melhora do sistema, pois o conteúdo e as condições dos testes podem variar. O custo por resolução está disponível apenas para a segunda amostra, em que houve avaliação do resultado.

## 6. Atendimento aos requisitos

| Requisito | Situação | Evidência |
| --- | --- | --- |
| Custo estimado para 100 e 1.000 usuários semanais | Calculado por projeção | Seções 2.3 e 3.3, com cenários B2B e B2C. |
| Latência interagentes e tempo total de resposta | Registrado | Tempo total nas seções 2.1 e 3.1; duração dos agentes e intervalos entre etapas na seção 3.5. |
| Índice de erros | Calculado | Taxas de erro por persona e recorte nas seções 2.1 e 3.1; bloqueios separados. |
| Custo / retorno (ROI) | Não calculado | Custos apresentados; ausência do ROI justificada na seção 4. |
| Custo por resolução | Calculado na segunda amostra | Seção 3.4, com tentativas sem resolução incluídas no custo total. |

**Fonte dos dados:** registros da primeira amostra enviados na conversa e arquivo “Texto colado.txt” contendo os registros da segunda amostra. Conforme informado pelo responsável pela coleta, os totais consolidados de custos e tokens foram obtidos diretamente do monitor. Nenhum resultado de ROI ou de teste de carga foi presumido.
