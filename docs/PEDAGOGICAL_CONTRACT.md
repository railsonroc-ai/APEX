# Contrato pedagógico do APEX

Este documento é a fonte de verdade das decisões pedagógicas do produto. Uma
regra escrita apenas no prompt não conta como implementada. Cada requisito deve
apontar para uma barreira executável e para pelo menos um teste de comportamento.

Status usados:

- **ENFORCED**: existe regra server-side e teste de comportamento;
- **PARCIAL**: existe apenas em uma fatia da trilha ou depende de heurística/LLM;
- **PLANEJADO**: requisito preservado, mas deliberadamente fora da fatia atual.

## Contratos do kernel atual

| ID | Requisito | Status | Enforcement principal | Evidência automatizada |
|---|---|---|---|---|
| PED-001 | Uma novidade cognitiva principal por turno | PARCIAL | `TurnTeachingContract` bloqueia termos no primeiro microconceito | `test_pedagogical_guard_e2e.py`, `test_tutor_response_validator.py` |
| PED-002 | “Entendi”, “ok” ou concordância não avançam | ENFORCED na tarefa objetiva inicial | `ObjectiveTaskEvaluator` produz `insufficient` | `test_objective_task_evaluator.py`, `test_pedagogical_guard_e2e.py` |
| PED-003 | Avanço exige tarefa vinculada e evidência aplicada | ENFORCED | `LearningTask`, `EvidenceEvaluator`, `ProcessLearningTurn` | `test_e2e_learning_pipeline.py`, `test_learning_task.py` |
| PED-004 | Toda evidência recebe veredito antes da próxima tarefa | ENFORCED | prefixo decidido e validado pelo servidor | `test_tutor_response_validator.py`, `test_pedagogical_guard_e2e.py` |
| PED-005 | Falta isolada do veredito não apaga conteúdo válido | ENFORCED | reparo específico de `feedback_missing` | `test_tutor_response_validator.py` |
| PED-006 | Resposta inválida não chega à tela | ENFORCED | validação completa antes de commit e projeção SSE | `test_stream_commit_confirmation_order.py`, `test_pedagogical_guard_e2e.py` |
| PED-007 | Mensagem mista preserva a resposta e trata dificuldade separadamente | ENFORCED | `LearnerSignals.is_control_only` | `test_evidence_evaluator.py`, `test_pedagogical_guard_e2e.py` |
| PED-008 | Primeira dificuldade reduz o recorte sem entregar gabarito | ENFORCED no primeiro microconceito | teto `guided` por estado e fallback menor | `test_tutor_response_validator.py`, `test_pedagogical_guard_e2e.py` |
| PED-009 | Ajuda direta só após dificuldade recorrente | ENFORCED no primeiro microconceito | `difficulty_count >= 2` libera fallback direto | `test_teaching_policy.py`, `test_tutor_response_validator.py` |
| PED-010 | Revisão começa por recuperação e não introduz novidade | ENFORCED no contrato de turno | estágio/ação ativam `review_mode`; validator bloqueia ensino prévio | `test_tutor_response_validator.py`, `test_teaching_policy.py` |
| PED-011 | Conclusão não depende de uma única resposta | ENFORCED | `MasteryPolicy` exige portfólio, diversidade e baixa ajuda | `test_mastery_policy.py`, `test_e2e_learning_pipeline.py` |
| PED-012 | Pausa e revisão de retomada restauram o ponto exato | ENFORCED | `LearningSessionLifecycle` server-side | `test_e2e_session_resume_review.py` |
| PED-013 | O aluno vê o foco e a próxima ação | ENFORCED | projeção read-only de `LearnerState` em `/api/session` | `test_session_api.py`, `test_session_ui.py` |
| PED-014 | Histórico pedagógico é confirmado pelo servidor | ENFORCED | `LearningHistory` ignora histórico do navegador | `test_server_authoritative_history.py` |
| PED-015 | Falha do avaliador não altera progresso | ENFORCED | fluxo fail-closed | `test_pedagogical_guard_e2e.py`, `test_chat_stream.py` |

## Diretrizes preservadas que ainda não estão completas

| ID | Requisito | Status | Lacuna atual |
|---|---|---|---|
| ROAD-001 | Concreto → lógica → representação → código | PARCIAL | somente `ads.algorithms.ordered_steps` possui contrato curricular específico |
| ROAD-002 | LER → COMPREENDER → EXPLICAR → TESTAR → CORRIGIR → FIXAR → CONCLUIR → REENCONTRAR | PARCIAL | os nomes ainda não correspondem a uma FSM integralmente observável |
| ROAD-003 | Revisões vencidas reaparecem sem depender da memória do aluno | PARCIAL | scheduler e fila existem; falta dispatcher automático com política de interrupção |
| ROAD-004 | Ajuda diminui progressivamente com medida robusta | PARCIAL | assistência observada ainda usa heurísticas textuais |
| ROAD-005 | Conceitos antigos reaparecem intercalados com novos | PLANEJADO | requer instância de revisão e trilha com mais microcompetências |
| ROAD-006 | Trilha completa de fundamentos em microcompetências | PLANEJADO | a fatia executável atual contém uma microcompetência |
| ROAD-007 | Competência profissional por artefatos executáveis | PLANEJADO | requer ChallengeEngine, rubricas de artefato e workspace isolado |
| ROAD-008 | Tickets, código legado, testes, Git, PR, incidentes e deploy | PLANEJADO | não pertence ao kernel vertical atual |
| ROAD-009 | Inglês técnico progressivo dentro do trabalho | PLANEJADO | deve acompanhar artefatos profissionais, não virar curso genérico de inglês |

## Regras de release

1. Uma correção pedagógica precisa incluir teste de regressão no mesmo pacote.
2. Nenhum requisito pode ser marcado **ENFORCED** se depender somente do prompt.
3. Fallbacks devem ser validados para todas as ações antes da release.
4. A suíte completa e o gate crítico devem usar SQLite temporário.
5. Novas trilhas entram por fatias verticais: microcompetência, contrato, tarefa,
   avaliação, feedback, mastery e revisão; adicionar apenas conteúdo ao prompt não
   constitui uma trilha.

## Forma de ensino preservada

- uma novidade cognitiva principal por vez;
- realidade concreta → lógica → representação → código;
- leitura curta → compreensão → produção própria → feedback → nova tentativa;
- “entendi” nunca é prova suficiente;
- dificuldade reduz complexidade e muda a representação;
- revisão usa recuperação ativa e não ensina novidade antes da tentativa;
- pistas diminuem conforme a autonomia cresce;
- o sistema externaliza o foco, o checkpoint e a próxima ação;
- domínio futuro precisa ser demonstrado em tarefas e artefatos profissionais;
- inglês aparece progressivamente dentro do trabalho técnico.
