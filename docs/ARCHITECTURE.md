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
- `services/student_context.py`: resolve a identidade no servidor; o navegador não escolhe `student_id`.

## Tutor

- `services/tutor_core.py`: prepara e protege o contexto enviado ao modelo.
- `prompts/tutor.py`: contém as regras pedagógicas atuais.

## Kernel pedagógico

- `LearnerState`: estado pedagógico atual por aluno + área.
- `LearnerStateTransition`: mudanças por sinais e evidências.
- `TeachingPolicy`: escolha determinística da próxima ação.
- `ConceptTracker` e `ConceptActivation`: identificação e ativação de conceitos.
- `EvidenceEvaluator`: contrato da avaliação semântica.
- `ConceptProgress`: progresso persistente por aluno + área + conceito.
- `ReviewScheduler`, `ReviewQueue` e `ReviewLifecycle`: revisão espaçada.
- `ProcessLearningTurn`: preview e commit atômico do turno.
- `LearningHistory`: histórico confirmado e autoritativo, isolado por aluno.
- `LearningTurnLease`: reserva temporária cross-process por aluno + área.

## Frontend

- `chat-engine.js`: conversa e interface.
- `apex-api.js`: HTTP, autenticação, notas e SSE.
- `apex-tts.js`: síntese de voz.
- `index.html`: página principal.

## Persistência

O SQLite atual usa `data/apex.db`.

Tabelas principais:

- `schema_migrations`: versões de schema já aplicadas;
- `students`: identidade estável do aluno;
- `learning_sessions`: episódios de estudo associados ao aluno e à área;
- `notes`: notas pertencentes ao aluno;
- `learner_state`: estado atual por aluno + área;
- `concept_progress`: progresso e revisão por aluno + área + conceito;
- `learning_turns`: turnos idempotentes por aluno, associados a uma sessão;
- `learning_turn_leases`: reserva temporária por aluno + área.

O navegador não fornece o histórico usado pelo tutor e não escolhe livremente
o `student_id`. O backend resolve a identidade do aluno padrão atual, lê apenas
turnos confirmados e isola contexto, estado, revisão e idempotência por aluno.

A reserva de turno usa a chave `student_id + area`: duas sessões do mesmo aluno
na mesma área permanecem serializadas, enquanto alunos diferentes podem estudar
a mesma área em paralelo. A lease fica no SQLite, funciona entre threads/workers
e expira para permitir recuperação caso um worker seja interrompido.

O schema não é mais alterado por comandos avulsos no `init_database`. Cada
mudança possui versão e nome, é aplicada junto do seu registro em uma transação
e pode ser executada novamente com segurança durante a inicialização.

## Produção e testes

Produção: Gunicorn via `start_apex.sh`.

Testes: `pytest -q`.

## Limite atual

O APEX 1.0 continua operando como produto individual, mas a fundação de identidade
já existe: `student_id` participa das chaves pedagógicas e o aluno atual é resolvido
no servidor. Ainda não existem cadastro, login, autorização individual, revogação,
seleção de perfil ou gestão multiusuário completa.
