# Backend APEX

O diretório `backend` contém a aplicação Flask e os serviços centrais do APEX.

## Componentes

- `app.py` — rotas HTTP, SSE e orquestração.
- `config.py` — variáveis de ambiente, caminhos e limites.
- `database.py` — conexões e inicialização do SQLite.
- `migrations.py` — evolução versionada e atômica do schema SQLite.
- `security.py` — autenticação por `X-Apex-Key`.
- `prompts/tutor.py` — prompt pedagógico do tutor.
- `services/tutor_core.py` — preparação e proteção do contexto.
- `identity.py` — IDs estáveis do aluno e das sessões padrão do APEX individual.
- `services/student_context.py` — resolução server-side da identidade pedagógica.
- `services/process_learning_turn.py` — preview e commit do turno pedagógico.
- `services/evidence_evaluator.py` — avaliação semântica com rubrica versionada.
- `services/evidence_policy.py` — IDs/versões de rubrica, política e assistência.
- `services/evidence_event.py` — ledger imutável das avaliações confirmadas.
- `services/learning_history.py` — histórico confirmado no servidor.
- `services/learning_turn_lease.py` — serialização de turnos por aluno + área entre workers.
- `templates/index.html` — interface principal.
- `static/js/chat-engine.js` — estado da conversa e interface.
- `static/js/apex-api.js` — HTTP, autenticação, notas e SSE.
- `static/js/apex-tts.js` — síntese de voz no navegador.

## Rotas atuais

- `/` — interface principal.
- `/health` — verifica Flask e SQLite.
- `/chat/stream` — conversa com o tutor via SSE.
- `/api/notes` — salva notas no SQLite.

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
