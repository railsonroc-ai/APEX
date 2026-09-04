# Backend APEX

O diretório `backend` contém a aplicação Flask e os serviços centrais do APEX.

## Componentes

- `app.py` — rotas HTTP, SSE e orquestração.
- `config.py` — variáveis de ambiente, caminhos e limites.
- `database.py` — conexões e inicialização do SQLite.
- `migrations.py` — evolução versionada e atômica do schema SQLite.
- `security.py` — autenticação por `X-Apex-Key`.
- `services/llm_gateway.py` — adapter único para Groq, limites por finalidade e telemetria segura.
- `prompts/tutor.py` — prompt pedagógico do tutor.
- `services/tutor_core.py` — preparação e proteção do contexto.
- `identity.py` — IDs estáveis do aluno e das sessões padrão do APEX individual.
- `concepts.py` — definições seed, aliases e IDs estáveis do catálogo de competências.
- `services/concept_catalog.py` — resolução autoritativa de `concept_id` e nomes canônicos.
- `services/student_context.py` — resolução server-side da identidade pedagógica.
- `services/process_learning_turn.py` — preview e commit do turno pedagógico.
- `services/concept_tracker.py` — seleção de competência somente entre IDs permitidos pelo catálogo.
- `services/evidence_evaluator.py` — avaliação semântica com critérios estruturados e outcome derivado pelo servidor.
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

A interface consulta o lifecycle no servidor ao abrir a página e depois de cada turno confirmado. Em `paused`, o campo de mensagem fica desabilitado e aparecem apenas as opções de retomada; em `reviewing`, o painel informa que a revisão está ativa. O navegador renderiza o estado recebido do backend, mas não decide a transição pedagógica.

## TutorCore

O TutorCore aplica o prompt pedagógico, adiciona o estado atual e limita o
contexto. O histórico usado pelo tutor vem de turnos confirmados no SQLite;
o navegador não é fonte de verdade para a conversa pedagógica.

## Testes

Os testes ficam em `tests/`.

Execute:

    pytest -q

Gate automatizado:

    python3 tools/apex_validate.py

## Produção

O servidor de produção utiliza Gunicorn através de `start_apex.sh`.

Valide a configuração com:

    gunicorn backend.app:app --check-config
