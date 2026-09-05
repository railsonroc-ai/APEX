# Backend APEX

O diretório `backend` contém a aplicação Flask e os serviços centrais do APEX.

## Componentes

- `app.py` — app factory, rotas HTTP, SSE e orquestração; importar o módulo não inicializa o SQLite.
- `config.py` — variáveis de ambiente, caminhos e limites.
- `database.py` — conexões e inicialização do SQLite.
- `migrations.py` — evolução versionada e atômica do schema SQLite.
- `security.py` — autenticação por `X-Apex-Key`, vínculo da credencial ao aluno e aplicação de rate limit.
- `services/access_control.py` — credenciais persistidas por hash, rotação/revogação e quota SQLite compartilhada entre workers.
- `services/llm_gateway.py` — adapter único para Groq, limites por finalidade e telemetria segura.
- `services/observability.py` — contexto de request/turno, pseudonimização de identidade e eventos JSON sem conteúdo pedagógico sensível.
- `services/data_lifecycle.py` — exportação, exclusão transacional do aluno e seleção/aplicação controlada de retenção.
- `prompts/tutor.py` — prompt pedagógico do tutor.
- `services/tutor_core.py` — preparação e proteção do contexto.
- `identity.py` — IDs estáveis do aluno e das sessões padrão do APEX individual.
- `concepts.py` — definições seed, aliases e IDs estáveis do catálogo de competências.
- `services/concept_catalog.py` — resolução autoritativa de `concept_id` e nomes canônicos.
- `services/student_context.py` — resolução server-side da identidade pedagógica.
- `services/process_learning_turn.py` — preview e commit do turno pedagógico.
- `services/concept_tracker.py` — seleção de competência somente entre IDs permitidos pelo catálogo.
- `services/learning_intent.py` — intenção determinística de iniciar, trocar ou recomeçar uma trilha.
- `services/curriculum.py` — entrada de conceitos amplos em microcompetências executáveis.
- `services/turn_teaching_contract.py` — contrato server-side da única novidade, representação, limites e tarefa do turno.
- `services/tutor_response_validator.py` — valida a resposta completa antes de qualquer conteúdo chegar à tela.
- `services/task_spec.py` — extrai a tarefa única realmente exibida para o ledger.
- `services/evidence_evaluator.py` — avaliação semântica com critérios estruturados e outcome derivado pelo servidor.
- `services/objective_task_evaluator.py` — correção determinística de tarefas fechadas reconhecidas pelo conceito e pelo enunciado confirmado.
- `services/rubric_policy.py` — contrato versionado dos critérios e derivação determinística do outcome.
- `services/attempt_policy.py` — classificação determinística do tipo pedagógico de tentativa.
- `services/learning_attempt.py` — ledger imutável da tentativa do aluno antes do julgamento.
- `services/task_policy.py` — contrato server-side que classifica tarefas avaliáveis por ação pedagógica.
- `services/learning_task.py` — ledger imutável da tarefa concreta apresentada pelo tutor e vinculada ao turno-fonte.
- `services/rubric_assessment.py` — ledger imutável dos critérios que sustentam a avaliação.
- `services/evidence_policy.py` — IDs/versões de rubrica, política e assistência.
- `services/evidence_event.py` — ledger imutável das avaliações confirmadas.
- `services/assistance_policy.py` — classificação server-side do nível de ajuda por ação pedagógica.
- `services/assistance_event.py` — ledger imutável da assistência fornecida em cada turno confirmado.
- `services/mastery_policy.py` — gate determinístico de conclusão baseado em portfólio de evidências e assistência.
- `services/mastery_assessment.py` — ledger imutável das decisões de domínio e seus bloqueadores.
- `services/learning_history.py` — histórico confirmado no servidor.
- `services/learning_turn_lease.py` — serialização de turnos por aluno + área entre workers.
- `services/learning_session_lifecycle.py` — estado persistente de sessão, pausa/retomada e revisão antes de retomar, com ledger imutável de transições.
- `templates/index.html` — interface principal.
- `static/js/chat-engine.js` — estado da conversa, streaming e controles visuais do lifecycle da sessão.
- `static/js/apex-api.js` — HTTP, autenticação, notas, lifecycle da sessão e SSE.
- `static/js/apex-tts.js` — síntese de voz no navegador.

## Rotas atuais

- `/` — interface principal.
- `/health` — verifica Flask e SQLite.
- `/chat/stream` — conversa com o tutor via SSE; bloqueia novos turnos enquanto a sessão está pausada.
- `/api/session` — consulta o lifecycle da sessão atual.
- `/api/session/pause` — pausa a sessão com serialização pelo mesmo lease dos turnos.
- `/api/session/resume` — retoma direto ou inicia revisão antes da retomada.
- `/api/notes` — salva notas no SQLite.
- `/api/privacy/export` — exporta somente os dados do aluno autenticado em JSON, sem hashes de credenciais.
- `/api/privacy/data` — exclui os dados do aluno autenticado após confirmação explícita.

A interface consulta o lifecycle no servidor ao abrir a página e depois de cada turno confirmado. Em `paused`, o campo de mensagem fica desabilitado e aparecem apenas as opções de retomada; em `reviewing`, o painel informa que a revisão está ativa. O navegador renderiza o estado recebido do backend, mas não decide a transição pedagógica.

O APEX 1.0 individual não exige autenticação do usuário: as rotas resolvem o aluno padrão no servidor e a interface não solicita senha ou chave. Cada resposta HTTP recebe `X-Apex-Request-ID`; eventos `apex_event` correlacionam requests, turnos, LLM e transições de sessão sem registrar mensagens, prompts, respostas, notas ou segredos.

## TutorCore

O TutorCore aplica o prompt pedagógico, adiciona o estado atual e limita o
contexto. O histórico usado pelo tutor vem de turnos confirmados no SQLite;
o navegador não é fonte de verdade para a conversa pedagógica.

No chat, tokens do provider são acumulados no servidor. O
`TutorResponseValidator` aceita ou substitui a resposta segundo o
`TurnTeachingContract`; `ProcessLearningTurn` confirma resposta, assistência
observada e tarefa extraída; somente depois o SSE entrega o texto validado.
Todas as respostas e tarefas controladas da primeira microcompetência são
produzidas pelo contrato e avaliadas localmente, inclusive a produção em três
passos. Isso impede variações sem rubrica e faz o percurso mínimo funcionar
mesmo com o provider indisponível.
Se uma tarefa futura realmente aberta exigir avaliação semântica e o provider
devolver JSON dentro de um único bloco Markdown, o parser aceita o envelope e
continua exigindo a rubrica completa. Se o provider não devolver uma rubrica
válida, o turno continua falhando fechado: não repete a explicação, não cria
falsa evidência e não altera o progresso.
Quando existe evidência válida, o `TurnTeachingContract` exige que a resposta
comece com feedback explícito sobre o resultado antes de apresentar a próxima
tarefa. Quando somente esse prefixo falta, o validador o acrescenta e preserva
o conteúdo válido; violações reais continuam usando fallback seguro.

As decisões, provas e lacunas pedagógicas são mantidas em
`docs/PEDAGOGICAL_CONTRACT.md`. Uma regra só é marcada como implementada quando
possui enforcement server-side e teste de comportamento.

## Testes

Os testes ficam em `tests/`. `tests/conftest.py` força `APP_ENV=test`, cria um diretório SQLite temporário por execução e inicializa esse banco explicitamente antes da coleta. Importar `backend.app` não cria nem migra o banco.

Execute:

    pytest -q

Gate automatizado:

    python3 tools/apex_validate.py

## Produção

O servidor de produção utiliza Gunicorn através de `start_apex.sh`. O script inicializa/migra o SQLite explicitamente antes de iniciar os workers; o import WSGI `backend.app:app` permanece sem efeito de persistência.

Valide a configuração com:

    gunicorn backend.app:app --check-config


## Privacidade e retenção

A migration 14 cria `privacy_deletion_authorizations` e altera apenas os triggers de `DELETE` dos ledgers imutáveis. Fora de uma autorização temporária para o `student_id` específico, `DELETE` continua abortando como antes. `DataLifecycle.delete_student()` cria a autorização e remove todos os registros dependentes dentro da mesma transação; qualquer falha faz rollback inclusive da autorização.

A migration 15 sincroniza o catálogo v2 e adiciona a microcompetência interna
`ads.algorithms.ordered_steps` como não selecionável. O conceito amplo
`ads.algorithms` continua sendo a intenção visível; `Curriculum` escolhe sua
primeira unidade executável.

A exportação inclui identidade, sessões, estado, progresso, turnos, tarefas, tentativas, rubricas, evidências, mastery, assistência, eventos de sessão, notas e metadados de credenciais. `key_hash` e valores secretos nunca entram no arquivo.

`tools/apex_retention.py` é dry-run por padrão. Candidatos precisam estar além de `PRIVACY_RETENTION_DAYS`, não podem ser `student_default` e não podem possuir credencial ativa. A remoção só ocorre com `--apply`; o APEX não executa retenção automaticamente no startup.
