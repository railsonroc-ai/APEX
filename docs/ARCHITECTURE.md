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
- `EvidenceEvaluator`: contrato da avaliação semântica e rubrica versionada.
- `EvidenceEvent`: ledger imutável de avaliações confirmadas.
- `EvidencePolicy`: IDs/versões de rubrica e política, além do nível de assistência registrado.
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
- `concept_definitions`: definições versionadas de competências por `concept_id`;
- `concept_aliases`: aliases normalizados que convergem para um `concept_id`;
- `concept_progress`: progresso e revisão por aluno + área + `concept_id`;
- `learning_turns`: turnos idempotentes por aluno, associados a uma sessão;
- `learning_turn_leases`: reserva temporária por aluno + área;
- `evidence_events`: avaliações imutáveis ligadas ao aluno, sessão, turno e `concept_id` confirmado.

O navegador não fornece o histórico usado pelo tutor e não escolhe livremente
o `student_id`. O backend resolve a identidade do aluno padrão atual, lê apenas
turnos confirmados e isola contexto, estado, revisão e idempotência por aluno.

A reserva de turno usa a chave `student_id + area`: duas sessões do mesmo aluno
na mesma área permanecem serializadas, enquanto alunos diferentes podem estudar
a mesma área em paralelo. A lease fica no SQLite, funciona entre threads/workers
e expira para permitir recuperação caso um worker seja interrompido.

A migration 6 cria o ledger `evidence_events`, protegido por triggers contra `UPDATE` e `DELETE`. O evento registra outcome, confiança, contexto avaliado, rubrica/policy versionadas, assistência, artefato opcional, flag de aplicação e mastery antes/depois. O nível de ajuda permanece `untracked` enquanto o APEX ainda não mede scaffolding explicitamente; nenhum valor de autonomia é inventado.

A migration 7 introduz `concept_definitions` e `concept_aliases` e reconstrói as tabelas pedagógicas para que `concept_id` seja a chave de negócio e foreign key real. Aliases conhecidos como `Variáveis`, `variaveis` e `variables` convergem para `ads.variables`. Valores legados fora do catálogo são preservados sob IDs determinísticos `legacy.*`, marcados como não selecionáveis e apresentados com nome sintético seguro; o texto legado não é promovido ao prompt de sistema.

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
seleção de perfil ou gestão multiusuário completa. O ledger de evidências torna as decisões atuais auditáveis e o catálogo estabiliza a identidade das competências, mas a política de mastery ainda deve evoluir para múltiplas evidências, variedade, independência, retenção e assistência medida explicitamente.
