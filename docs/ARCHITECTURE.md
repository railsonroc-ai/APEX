# Arquitetura do APEX

Este documento descreve a arquitetura técnica atualmente implementada.

## Fluxo principal

```text
Navegador -> JS -> Flask/SSE -> serviços pedagógicos -> Groq
                         \-> SQLite
```

## Backend

- `app.py`: rotas HTTP, coordenação das chamadas LLM e SSE.
- `config.py`: ambiente, caminhos, limites e timeout.
- `security.py`: autenticação por `X-Apex-Key`.
- `database.py`: SQLite e configuração das conexões.
- `migrations.py`: migrations ordenadas, atômicas e registradas no banco.
- `identity.py`: identificadores estáveis do aluno e das sessões padrão.
- `concepts.py`: catálogo seed versionado, aliases e IDs estáveis de competência.
- `services/concept_catalog.py`: resolução autoritativa de `concept_id` e nomes canônicos.
- `services/student_context.py`: resolve a identidade no servidor; o navegador não escolhe `student_id`.

## Tutor

- `services/tutor_core.py`: prepara e protege o contexto enviado ao modelo.
- `prompts/tutor.py`: contém as regras pedagógicas atuais.

## Kernel pedagógico

- `LearnerState`: estado pedagógico atual por aluno + área.
- `LearnerStateTransition`: mudanças por sinais e evidências.
- `TeachingPolicy`: escolha determinística da próxima ação.
- `ConceptCatalog`, `ConceptTracker` e `ConceptActivation`: catálogo, seleção por ID estável e ativação segura de conceitos.
- `EvidenceEvaluator`: coleta classificações estruturadas por critério.
- `AttemptPolicy` e `LearningAttempt`: classificam e preservam a tentativa do aluno antes da avaliação.
- `TaskPolicy` e `LearningTask`: definem e preservam a tarefa avaliável criada por um turno confirmado do tutor.
- `RubricPolicy`: deriva deterministicamente o outcome a partir dos critérios da rubrica v2.
- `RubricAssessment`: snapshot imutável dos critérios e da origem do outcome.
- `EvidenceEvent`: ledger imutável de avaliações confirmadas.
- `EvidencePolicy`: IDs/versões de rubrica e política, além dos níveis válidos de assistência.
- `AssistancePolicy`: converte somente ações pedagógicas server-side em níveis de ajuda e contratos de geração.
- `AssistanceEvent`: ledger imutável da assistência fornecida por turno confirmado.
- `MasteryPolicy`: decisão determinística de conclusão sobre o portfólio de evidências e assistência.
- `MasteryAssessment`: snapshot imutável da decisão de domínio ligada ao `EvidenceEvent`.
- `ConceptProgress`: progresso persistente por aluno + área + conceito.
- `ReviewScheduler`, `ReviewQueue` e `ReviewLifecycle`: revisão espaçada.
- `ProcessLearningTurn`: preview e commit atômico do turno.
- `LearningHistory`: histórico confirmado e autoritativo, isolado por aluno.
- `LearningTurnLease`: reserva temporária cross-process por aluno + área.
- `LearningSessionLifecycle`: lifecycle persistente da sessão, incluindo pausa, retomada direta e revisão antes de retomar.

## Frontend

- `chat-engine.js`: conversa, streaming e projeção visual do lifecycle da sessão.
- `apex-api.js`: HTTP, autenticação, notas, lifecycle da sessão e SSE.
- `apex-tts.js`: síntese de voz.
- `index.html`: página principal.

## Persistência

O SQLite atual usa `data/apex.db`.

Tabelas principais:

- `schema_migrations`: versões de schema já aplicadas;
- `students`: identidade estável do aluno;
- `learning_sessions`: episódios de estudo associados ao aluno e à área;
- `learning_session_states`: estado operacional persistente (`studying`, `paused`, `reviewing`) e snapshot da etapa/conceito para retomada;
- `learning_session_events`: ledger imutável de pausas, retomadas e conclusão da revisão de retomada;
- `notes`: notas pertencentes ao aluno;
- `learner_state`: estado atual por aluno + área;
- `concept_definitions`: definições versionadas de competências por `concept_id`;
- `concept_aliases`: aliases normalizados que convergem para um `concept_id`;
- `concept_progress`: progresso e revisão por aluno + área + `concept_id`;
- `learning_turns`: turnos idempotentes por aluno, associados a uma sessão;
- `learning_turn_leases`: reserva temporária por aluno + área;
- `evidence_events`: avaliações imutáveis ligadas ao aluno, sessão, turno e `concept_id` confirmado;
- `mastery_assessments`: decisões imutáveis da política de domínio ligadas ao evento de evidência e ao turno;
- `assistance_events`: assistência imutável de cada resposta do tutor, derivada da ação pedagógica controlada pelo servidor;
- `learning_tasks`: tarefa imutável apresentada pelo tutor, ligada ao turno-fonte, conceito, etapa, ação pedagógica, assistência e rubrica;
- `learning_attempts`: tentativa imutável do aluno, ligada ao turno confirmado e opcionalmente ao turno-fonte do tutor;
- `rubric_assessments`: critérios imutáveis que sustentam a avaliação da tentativa e apontam para a evidência correspondente.

O navegador não fornece o histórico usado pelo tutor e não escolhe livremente
o `student_id`. O backend resolve a identidade do aluno padrão atual, lê apenas
turnos confirmados e isola contexto, estado, revisão e idempotência por aluno.

A reserva de turno usa a chave `student_id + area`: duas sessões do mesmo aluno
na mesma área permanecem serializadas, enquanto alunos diferentes podem estudar
a mesma área em paralelo. A lease fica no SQLite, funciona entre threads/workers
e expira para permitir recuperação caso um worker seja interrompido.

A migration 6 cria o ledger `evidence_events`, protegido por triggers contra `UPDATE` e `DELETE`. O evento registra outcome, confiança, contexto avaliado, rubrica/policy versionadas, assistência, artefato opcional, flag de aplicação e mastery antes/depois. Eventos históricos anteriores ao rastreamento server-side de ajuda continuam `untracked`; o APEX não retropreenche autonomia que não observou.

A migration 7 introduz `concept_definitions` e `concept_aliases` e reconstrói as tabelas pedagógicas para que `concept_id` seja a chave de negócio e foreign key real. Aliases conhecidos como `Variáveis`, `variaveis` e `variables` convergem para `ads.variables`. Valores legados fora do catálogo são preservados sob IDs determinísticos `legacy.*`, marcados como não selecionáveis e apresentados com nome sintético seguro; o texto legado não é promovido ao prompt de sistema.

A migration 8 cria `mastery_assessments`, também protegido contra `UPDATE` e `DELETE`. A `MasteryPolicy` não substitui o score numérico por uma fórmula opaca: ela usa o score existente como um sinal, mas exige um portfólio mínimo antes da conclusão. O gate atual exige evidência aplicada suficiente, múltiplas demonstrações, diversidade entre etapas pedagógicas, etapa atual `fixar`, outcome atual `demonstrated` e score mínimo. Quando a assistência deixa de ser `untracked`, ao menos uma demonstração deve ocorrer com assistência `independent` ou `light`. Se um conceito legado chega a `fixar` sem diversidade de etapas, a decisão recomenda `testar` para produzir evidência em outro contexto e evitar retenção infinita em `fixar`. Demonstrações em `reencontrar` são contabilizadas explicitamente como sinal de retenção para a evolução posterior da política.

A migration 9 cria `assistance_events`, também imutável. A classificação não vem do navegador nem de uma autoavaliação da LLM: `AssistancePolicy` deriva o nível do `teaching_action` escolhido pelo kernel. `testar` e `revisar` são contratos `independent`; `verificar` e `consolidar`, `light`; `explicar`, `guided`; `corrigir`, `direct`; `avancar` permanece `untracked`. O `TutorCore` recebe um contrato de geração correspondente para limitar o suporte permitido. Ao avaliar a resposta seguinte, o backend localiza o turno anterior exato do tutor pelo mesmo aluno, sessão, área, `concept_id` e mensagem confirmada, então copia o nível desse `AssistanceEvent` para o `EvidenceEvent`. A `MasteryPolicy` v2 exige pelo menos uma demonstração de baixa assistência e impede conclusão quando a evidência final foi produzida sob ajuda `guided`, `direct` ou não rastreada; nesses casos, em `fixar`, recomenda um novo `testar` para obter uma demonstração mais autônoma.

A migration 10 separa formalmente a ação do aluno do julgamento semântico. `learning_attempts` registra a tentativa confirmada, o estágio, o tipo pedagógico, a assistência observada, o artefato opcional e o turno-fonte do tutor. `rubric_assessments` registra os três critérios da rubrica — resposta à tarefa, correção conceitual e compreensão/aplicação —, sua completude, confiança e origem do outcome. Ambos os ledgers são protegidos contra `UPDATE` e `DELETE`. Na rubrica `semantic_evidence` v2, a LLM deixa de escolher diretamente o outcome global: ela classifica os critérios e `RubricPolicy` deriva `demonstrated`, `partial`, `misconception` ou `insufficient` no servidor. Respostas históricas/internas sem critérios continuam auditáveis como `legacy_outcome`, sem fingir que possuem uma rubrica completa.

A migration 11 cria `learning_tasks` e adiciona `task_id` opcional a `learning_attempts`. O `TaskPolicy` transforma a ação pedagógica controlada pelo servidor em um tipo de tarefa e um contrato de geração; `TutorCore` recebe esse contrato para terminar o turno com uma única microtarefa quando a ação é avaliável. Depois que a resposta do tutor é confirmada, o backend persiste a `LearningTask` usando o texto real do turno, sem pedir à LLM que invente identidade, rubrica ou nível de assistência. No turno seguinte, o app só monta uma nova avaliação semântica se localizar essa tarefa pelo mesmo aluno, sessão, conceito e `source_turn_id`; o `LearningAttempt` resultante recebe o `task_id`. Tentativas anteriores à migration 11 permanecem com `task_id = NULL`, sem retropreenchimento fictício. `AttemptPolicy` v2 e `EvidencePolicy` v5 marcam essa mudança de contrato.

A migration 12 cria `learning_session_states` e `learning_session_events`. O lifecycle é controlado no servidor: `pause` captura o conceito e a etapa atuais; `resume` em modo `direct` volta a `studying` sem alterar o estado pedagógico, enquanto `review` coloca a sessão em `reviewing` e move temporariamente o `LearnerState` para `reencontrar`. Uma evidência aplicada com outcome `demonstrated` conclui essa revisão e restaura a etapa capturada. Enquanto `paused`, novos turnos são recusados; pause/resume usam o mesmo `LearningTurnLease` de aluno+área e o chat revalida o estado depois de adquirir a lease para fechar a janela de corrida. Eventos anteriores à migration 12 não são inventados: sessões existentes recebem apenas estado inicial `studying`.

A interface não cria uma segunda máquina de estados. `apex-api.js` apenas consulta e solicita transições; `chat-engine.js` mantém uma cópia transitória para renderização e sempre a substitui pela resposta server-side. Ao carregar, o envio fica temporariamente indisponível até a primeira consulta de sessão. Em `paused`, textarea e envio são bloqueados; em `reviewing`, a revisão é iniciada por um turno explícito e, depois de cada resposta confirmada, o frontend consulta novamente o lifecycle para refletir automaticamente a conclusão da revisão.

O schema não é mais alterado por comandos avulsos no `init_database`. Cada
mudança possui versão e nome, é aplicada junto do seu registro em uma transação
e pode ser executada novamente com segurança durante a inicialização.

## Produção e testes

Produção: Gunicorn via `start_apex.sh`.

Testes: `pytest -q`.

Gate automatizado: `python3 tools/apex_validate.py`.

Aplicação segura de pacotes futuros: `python3 tools/apex_apply_update.py <pacote> <sha256> <head>`; a migração do banco real permanece em uma segunda ação explícita com `python3 tools/apex_migrate_real.py`. Nenhum desses scripts faz commit ou push.

## Limite atual

O APEX 1.0 continua operando como produto individual, mas a fundação de identidade
já existe: `student_id` participa das chaves pedagógicas e o aluno atual é resolvido
no servidor. Ainda não existem cadastro, login, autorização individual, revogação,
seleção de perfil ou gestão multiusuário completa. O ledger de evidências, o catálogo de conceitos, o ledger de assistência e a `MasteryPolicy` tornam a conclusão explicável e resistente a uma única classificação. O nível de ajuda já é mensurado no contrato server-side do turno e as tentativas/rubricas básicas já são auditáveis. Ainda faltam requisitos/artefatos estruturados por tipo de tarefa, rubricas profissionais específicas e uma política de retenção mais rica; o ChallengeEngine completo continua fora deste estágio.
