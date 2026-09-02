# Arquitetura do APEX

Este documento descreve a arquitetura técnica atualmente implementada.

## Fluxo principal

```text
Navegador -> JS -> Flask -> TutorCore -> Groq
                  \-> SQLite
```

## Backend

- `app.py`: rotas HTTP, SSE e orquestração.
- `config.py`: ambiente, caminhos, limites e timeout.
- `security.py`: autenticação por `X-Apex-Key`.
- `database.py`: SQLite e configuração das conexões.

## Tutor

- `services/tutor_core.py`: prepara e protege o contexto enviado ao modelo.
- `prompts/tutor.py`: contém as regras pedagógicas atuais.

## Frontend

- `chat-engine.js`: conversa e interface.
- `apex-api.js`: HTTP, autenticação, notas e SSE.
- `apex-tts.js`: síntese de voz.
- `index.html`: página principal.

## Persistência

O SQLite atual usa `data/apex.db`.
Hoje ele armazena notas; estado pedagógico e progresso serão adicionados depois.

## Produção e testes

Produção: Gunicorn via `start_apex.sh`.

Testes: `pytest -q`.

A fundação técnica foi validada com 19 testes.

## Próxima fase

A próxima evolução será o sistema pedagógico adaptativo: estado do aluno, controle de novidade, política de ensino, recuperação, revisão e progresso.
