# Arquitetura do APEX

Este documento descreve a arquitetura técnica atualmente implementada.

## Fluxo principal

```text
Navegador -> JS -> Flask/SSE -> serviços pedagógicos -> Groq
                         \-> SQLite
```

## Backend

- `app.py`: `create_app()`, rotas HTTP, coordenação do caso de uso e SSE; não acessa o SDK do provider diretamente e não inicializa o SQLite durante import.
- `config.py`: ambiente, caminhos, limites e timeout.
- `security.py`: autenticação por `X-Apex-Key`, request identity e rate-limit enforcement.
- `services/access_control.py`: credenciais por hash, provisionamento/revogação e quota SQLite multi-worker.
- `database.py`: SQLite e configuração das conexões.
- `migrations.py`: migrations ordenadas, atômicas e registradas no banco.
- `identity.py`: identificadores estáveis do aluno e das sessões padrão.
- `concepts.py`: catálogo seed versionado, aliases e IDs estáveis de competência.
- `services/concept_catalog.py`: resolução autoritativa de `concept_id` e nomes canônicos.
- `services/student_context.py`: resolve a identidade no servidor; o navegador não escolhe `student_id`.

## Tutor

- `services/llm_gateway.py`: única fronteira com o SDK do provider; aplica timeout, retries deliberados, limites de geração por finalidade e logs de metadados sem conteúdo.
- `services/observability.py`: contexto operacional por request/turno, pseudonimização de identidade e emissão de eventos JSON privacy-first.
- `services/tutor_core.py`: prepara o contexto e incorpora o contrato executável do turno.
- `services/learning_intent.py`: resolve pedidos explícitos de início/troca/reinício.
- `services/curriculum.py`: mapeia conceitos visíveis, pré-requisitos e a próxima microcompetência executável.
- `services/turn_teaching_contract.py`: define novidade permitida, proibições, representação, tarefa, tamanho e teto de ajuda.
- `services/tutor_response_validator.py`: valida a resposta completa antes da tela e observa a assistência real.
- `services/task_spec.py`: extrai a tarefa única da resposta confirmada.
- `prompts/tutor.py`: contém as regras pedagógicas atuais.
- `docs/PEDAGOGICAL_CONTRACT.md`: rastreia cada diretriz até enforcement e teste;
  regra presente apenas no prompt permanece explicitamente parcial.

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
- `AssistancePolicy`: converte ações pedagógicas server-side em tetos de ajuda e valida a assistência observada.
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

A migration 9 cria `assistance_events`, também imutável. A ação escolhida pelo kernel define o teto (`independent`, `light`, `guided` ou `direct`), enquanto o nível persistido vem da resposta final observada pelo validador e nunca pode exceder esse teto. Ao avaliar a resposta seguinte, o backend usa o `source_turn_id` exato e o mesmo aluno, sessão, área e `concept_id` para copiar a assistência ao `EvidenceEvent`.

A migration 10 separa formalmente a ação do aluno do julgamento semântico. `learning_attempts` registra a tentativa confirmada, o estágio, o tipo pedagógico, a assistência observada, o artefato opcional e o turno-fonte do tutor. `rubric_assessments` registra os três critérios da rubrica — resposta à tarefa, correção conceitual e compreensão/aplicação —, sua completude, confiança e origem do outcome. Ambos os ledgers são protegidos contra `UPDATE` e `DELETE`. Na rubrica `semantic_evidence` v2, a LLM deixa de escolher diretamente o outcome global: ela classifica os critérios e `RubricPolicy` deriva `demonstrated`, `partial`, `misconception` ou `insufficient` no servidor. Respostas históricas/internas sem critérios continuam auditáveis como `legacy_outcome`, sem fingir que possuem uma rubrica completa.

A migration 11 cria `learning_tasks` e adiciona `task_id` opcional a `learning_attempts`. O `TaskPolicy` define quando há tarefa avaliável. No fluxo HTTP atual, `TaskSpec` extrai somente a tarefa da resposta já validada; `LearningTask` não armazena mais toda a explicação como se fosse o enunciado. No turno seguinte, a associação usa aluno, sessão, conceito e `source_turn_id`.

`ObjectiveTaskEvaluator` corrige localmente tarefas fechadas que reconhece pelo
`concept_id` e pelo enunciado imutável do `LearningTask`. O primeiro exercício
de ordenação aceita linguagem natural e a notação `2, 3, 1`, produz a mesma
rubrica estruturada do avaliador semântico e registra a origem
`deterministic_task`. Tarefas não reconhecidas continuam na LLM. Se essa
avaliação não produzir rubrica válida, a rota não chama o tutor nem confirma o
turno: falha fechada em vez de interpretar indisponibilidade como ausência de
aprendizagem e repetir a explicação anterior.

Uma evidência confirmada também gera um contrato explícito de feedback. A
resposta seguinte deve começar com `Correto.`, `Parcialmente correto.`, `Ainda
não está correto.` ou a indicação de evidência insuficiente antes de avançar
para outra tarefa. Esse prefixo é decidido e validado no servidor; não depende
de o texto livre da LLM lembrar de informar o resultado ao aluno.
Se a única violação for a ausência do prefixo, o servidor preserva a resposta
válida e acrescenta o veredito. Violações reais continuam usando fallback seguro.

Mensagens de controle puras, como “não entendi”, não são evidência. Quando a
mensagem também contém uma resposta à tarefa, a produção é avaliada e o sinal de
dificuldade é aplicado separadamente. Na primeira dificuldade da fatia inicial,
o contrato reduz o recorte com ajuda guiada; correção direta fica para recorrência.

A migration 15 sincroniza o catálogo v2 e inclui `ads.algorithms.ordered_steps`
como unidade interna não selecionável. `ads.algorithms` permanece o tópico que o
aluno escolhe, mas `Curriculum` ativa o primeiro microconceito. Essa é a primeira
fatia vertical com controle completo; os demais tópicos ainda usam contratos
genéricos e devem ganhar percursos próprios incrementalmente.

A migration 16 sincroniza o catálogo v3 e inclui
`ads.algorithms.goal_result` como segundo nó interno. O `Curriculum` declara a
aresta e o pré-requisito; a rota só fornece esse candidato ao `ConceptTracker`
quando o primeiro nó está `concluido` e o aluno envia `continuar`. A conclusão e
a ativação ficam em turnos diferentes, evitando empilhar a novidade seguinte no
feedback final. `ConceptActivation` então carrega ou cria o progresso isolado do
novo `concept_id`. As tarefas dos dois nós são avaliadas localmente.

## Fronteira de entrega pedagógica

O provider não transmite mais diretamente ao navegador. A rota acumula a
resposta, aplica `TutorResponseValidator`, confirma o turno e só então divide o
texto validado em eventos SSE. Se o modelo antecipar uma novidade ou exceder o
teto de ajuda no percurso executável, um fallback determinístico e testado é
usado antes da persistência e da tela.

A migration 12 cria `learning_session_states` e `learning_session_events`. O lifecycle é controlado no servidor: `pause` captura o conceito e a etapa atuais; `resume` em modo `direct` volta a `studying` sem alterar o estado pedagógico, enquanto `review` coloca a sessão em `reviewing` e move temporariamente o `LearnerState` para `reencontrar`. Uma evidência aplicada com outcome `demonstrated` conclui essa revisão e restaura a etapa capturada. Enquanto `paused`, novos turnos são recusados; pause/resume usam o mesmo `LearningTurnLease` de aluno+área e o chat revalida o estado depois de adquirir a lease para fechar a janela de corrida. Eventos anteriores à migration 12 não são inventados: sessões existentes recebem apenas estado inicial `studying`.

A interface não cria uma segunda máquina de estados. `apex-api.js` apenas consulta e solicita transições; `chat-engine.js` mantém uma cópia transitória para renderização e sempre a substitui pela resposta server-side. Ao carregar, o envio fica temporariamente indisponível até a primeira consulta de sessão. Em `paused`, textarea e envio são bloqueados; em `reviewing`, a revisão é iniciada por um turno explícito e, depois de cada resposta confirmada, o frontend consulta novamente o lifecycle para refletir automaticamente a conclusão da revisão.

`/api/session` também projeta, de forma read-only, o conceito, a etapa, a ação
pedagógica e o próximo passo. A interface usa essa projeção para externalizar o
foco sem decidir ou persistir transições no navegador.

A tela inicial é uma camada de navegação sobre essa mesma autoridade. O arquivo
`apex-shell.js` não mantém domínio ou agenda próprios: consulta `/api/dashboard`
e usa os endpoints server-side de sessão, estudo e revisão. A arte aprovada fica
em `backend/static/img/apex-home.jpg`; em telas largas, os alvos HTML coincidem
com as quatro teclas da composição, e em telas estreitas os mesmos controles são
reorganizados para toque sem duplicar estado. `chat-engine.js` continua dono da
conversa e expõe somente operações transitórias de interface por `ApexChat`.

`POST /api/study/start` aceita apenas conceitos selecionáveis do catálogo.
`POST /api/review/start` aceita revisão programada ou conceito já estudado.
Ambos rejeitam sessão pausada/revisando, adquirem `LearningTurnLease`, releem o
lifecycle depois da aquisição e só então alteram o `LearnerState`. A mudança de
interface não adiciona migration nem altera o formato dos ledgers existentes.

O schema não é mais alterado por comandos avulsos no `init_database`. Cada
mudança possui versão e nome, é aplicada junto do seu registro em uma transação
e pode ser executada novamente com segurança durante a inicialização.

A migration 13 mantém `access_credentials` e `api_rate_limits` por compatibilidade de schema e histórico arquitetural. No APEX 1.0 individual, porém, a fronteira HTTP opera aberta para o aluno padrão: não há senha, API key ou prompt de autenticação no fluxo do usuário. O `StudentContext` continua resolvendo a identidade no servidor, preservando o isolamento do kernel pedagógico de detalhes de transporte.

A app factory aplica headers HTTP defensivos a todas as respostas: CSP compatível com as dependências frontend atuais, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` e `Permissions-Policy` bloqueando câmera, microfone e geolocalização. A CSP ainda precisa permitir scripts/estilos inline e CDNs enquanto o frontend não for totalmente empacotado; remover esses allowances fica para um hardening posterior.

## Runtime LLM

O `LLMGateway` é a única camada autorizada a importar o SDK Groq. O adapter expõe apenas texto completo ou tokens de streaming ao restante do APEX. As chamadas são classificadas como `concept_identification`, `evidence_evaluation` ou `tutor_response`, cada uma com limite próprio de geração. O cliente do provider recebe timeout e número de retries configurados explicitamente; os logs registram `call_id`, finalidade, modelo, latência, uso de tokens quando disponível e classe de erro, sem registrar prompts ou respostas.

## Observabilidade operacional

A app factory cria um `request_id` server-side para cada request e o devolve em `X-Apex-Request-ID`. No chat SSE, o mesmo ID é reatado ao contexto do generator para preservar correlação durante todo o streaming. `turn_id`, área e referências SHA-256 truncadas de aluno/sessão compõem o contexto operacional. Os eventos são serializados como JSON com prefixo `apex_event` e incluem somente metadados escalares permitidos. O contrato rejeita explicitamente campos como `user_message`, `assistant_message`, `student_answer`, `prompt`, `response`, `content`, notas e segredos.

Eventos centrais: `http_response_ready`, `llm_call`, `learning_turn_completed`, `learning_turn_failed`, `learning_turn_replay`, `learning_turn_blocked`, `session_transition`, `auth_rejected` e `auth_rate_limited`. Assim, é possível correlacionar latência, tokens, erros, etapa antes/depois e decisão pedagógica sem transformar logs em uma cópia das conversas educacionais.

## Produção e testes

Produção: Gunicorn via `start_apex.sh`. O bootstrap executa `init_database()` antes de iniciar os workers; importar `backend.app:app` não abre nem migra o SQLite.

Testes: `pytest -q`. `tests/conftest.py` força um `APEX_DATA_DIR` temporário e inicializa somente esse banco, tornando a suíte hermética em relação a `data/apex.db`.

Gate automatizado: `python3 tools/apex_validate.py`.

Gate de Release Candidate: `python3 tools/apex_release_gate.py`. Ele nunca usa `data/apex.db`: executa a suíte, uma seleção explícita de jornadas/falhas críticas e uma reconstrução de SQLite temporário usando exatamente `MIGRATIONS`. Por padrão também exige working tree limpo.

Aplicação segura de pacotes futuros: `python3 tools/apex_apply_update.py <pacote> <sha256> <head>`; a migração do banco real permanece em uma segunda ação explícita com `python3 tools/apex_migrate_real.py`. Nenhum desses scripts faz commit ou push.

## Limite atual

O APEX 1.0 continua operando como produto individual, mas a fundação de identidade
já existe: `student_id` participa das chaves pedagógicas e o aluno atual é resolvido
no servidor. Ainda não existem cadastro, login, autorização individual, revogação,
seleção de perfil ou gestão multiusuário completa. O ledger de evidências, o catálogo de conceitos, o ledger de assistência e a `MasteryPolicy` tornam a conclusão explicável e resistente a uma única classificação. O nível de ajuda já é mensurado no contrato server-side do turno e as tentativas/rubricas básicas já são auditáveis. Ainda faltam requisitos/artefatos estruturados por tipo de tarefa, rubricas profissionais específicas e uma política de retenção mais rica; o ChallengeEngine completo continua fora deste estágio.


## Privacidade e ciclo de vida de dados

O limite de privacidade fica no adapter HTTP + `DataLifecycle`; o navegador nunca envia um `student_id` para exportar ou excluir. A identidade vem exclusivamente da credencial já autenticada.

A exportação é uma projeção read-only das tabelas pertencentes ao aluno e omite `key_hash`, rate-limit interno e catálogo global. A exclusão é uma operação destrutiva explícita e transacional. Como os ledgers pedagógicos são imutáveis por design, a migration 14 não remove essa proteção: ela cria uma autorização temporária por `student_id` que os triggers consultam apenas durante o fluxo de privacidade. Sem esse marcador, `UPDATE`/`DELETE` dos ledgers continuam proibidos.

Retenção não roda como side effect do startup. O CLI de retenção calcula candidatos de forma conservadora — conta não padrão, sem credencial ativa e inativa além da janela — e permanece em dry-run até receber `--apply`. Isso separa política de retenção de disponibilidade do serviço e evita exclusão silenciosa durante deploy/restart.


## Contrato E2E e confiabilidade

O hardening v19 trata as jornadas como contratos entre camadas, não como testes unitários justapostos. A jornada pedagógica real usa as implementações de `ProcessLearningTurn`, `LearningTask`, `LearningAttempt`, `RubricAssessment`, `EvidenceEvent`, `MasteryAssessment`, `ConceptProgress` e SQLite; apenas o provider externo é substituído por fake determinística nos cenários HTTP.

O contrato operacional de pacote também faz parte da confiabilidade. `APEX_UPDATE_MANIFEST.txt` é o único manifesto aceito; a seção `Arquivos:` precisa representar exatamente os arquivos do tarball. Um arquivo `_MANIFEST.txt` adicional ou conteúdo não declarado faz a aplicação falhar antes do staging. O manifesto também informa se há migration nova, removendo a antiga orientação genérica de sempre executar `apex_migrate_real.py`.
