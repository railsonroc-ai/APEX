# Backend APEX

O diretório `backend` contém a aplicação Flask e os serviços centrais do APEX.

## Componentes

- `app.py` — rotas HTTP, SSE e orquestração.
- `config.py` — variáveis de ambiente, caminhos e limites.
- `database.py` — conexões e inicialização do SQLite.
- `security.py` — autenticação por `X-Apex-Key`.
- `prompts/tutor.py` — prompt pedagógico do tutor.
- `services/tutor_core.py` — preparação e proteção do contexto.
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

Atualmente o TutorCore aplica o prompt do tutor, adiciona contexto da área, filtra o histórico, bloqueia injeção de mensagens `system`, limita o contexto e garante que a pergunta atual seja adicionada uma única vez.

A próxima grande fase será evoluir essa camada para o sistema pedagógico adaptativo do APEX.

## Testes

Os testes ficam em `tests/`.

Execute:

    pytest -q

## Produção

O servidor de produção utiliza Gunicorn através de `start_apex.sh`.

Valide a configuração com:

    gunicorn backend.app:app --check-config
