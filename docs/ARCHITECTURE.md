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

## Tutor

- `services/tutor_core.py`: prepara e protege o contexto enviado ao modelo.
- `prompts/tutor.py`: contém as regras pedagógicas atuais.

## Kernel pedagógico

- `LearnerState`: estado pedagógico atual por área.
- `LearnerStateTransition`: mudanças por sinais e evidências.
- `TeachingPolicy`: escolha determinística da próxima ação.
- `ConceptTracker` e `ConceptActivation`: identificação e ativação de conceitos.
- `EvidenceEvaluator`: contrato da avaliação semântica.
- `ConceptProgress`: progresso persistente por conceito.
- `ReviewScheduler`, `ReviewQueue` e `ReviewLifecycle`: revisão espaçada.
- `ProcessLearningTurn`: preview e commit atômico do turno.
- `LearningHistory`: histórico confirmado e autoritativo do servidor.
- `LearningTurnLease`: reserva temporária cross-process por área.

## Frontend

- `chat-engine.js`: conversa e interface.
- `apex-api.js`: HTTP, autenticação, notas e SSE.
- `apex-tts.js`: síntese de voz.
- `index.html`: página principal.

## Persistência

O SQLite atual usa `data/apex.db`.

Tabelas principais:

- `schema_migrations`: versões de schema já aplicadas;
- `notes`: notas do aluno;
- `learner_state`: estado atual por área;
- `concept_progress`: progresso e revisão por conceito;
- `learning_turns`: mensagem do aluno, resposta confirmada do tutor e conceito.
- `learning_turn_leases`: reserva temporária do turno em processamento.

O navegador não fornece o histórico usado pelo tutor. O backend lê apenas
turnos confirmados, limita o contexto e o isola por área e conceito.

Como a versão 1.0 ainda é individual, somente um turno por área pode estar
em processamento. A reserva fica no SQLite, funciona entre threads/workers e
expira para permitir recuperação caso um worker seja interrompido.

O schema não é mais alterado por comandos avulsos no `init_database`. Cada
mudança possui versão e nome, é aplicada junto do seu registro em uma transação
e pode ser executada novamente com segurança durante a inicialização.

## Produção e testes

Produção: Gunicorn via `start_apex.sh`.

Testes: `pytest -q`.

## Limite atual

O APEX 1.0 ainda é individual. `area` e `concept` isolam o contexto
pedagógico, mas ainda não existe identidade multiusuário completa.
