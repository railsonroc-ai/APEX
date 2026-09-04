# APEX 1.0 — Estado técnico

## Objetivo

O APEX 1.0 é uma plataforma individual de aprendizagem adaptativa baseada em Flask, SQLite e LLM, com foco em progressão pedagógica controlada por evidências.

## Kernel pedagógico

Fluxo principal:

LER → COMPREENDER → EXPLICAR → TESTAR → CORRIGIR → FIXAR → CONCLUIR → REENCONTRAR

A progressão não depende apenas do texto gerado pela LLM. Regras de estado, domínio, evidência e revisão são aplicadas pelo backend.

## Componentes principais

- `LearnerState`: estado pedagógico atual.
- `LearnerStateTransition`: transições por sinais e evidências.
- `EvidenceEvaluator`: avaliação semântica da resposta do aluno.
- `ConceptTracker`: identificação do conceito.
- `ConceptActivation`: início e retomada de conceitos sem contaminação de estado.
- `ConceptProgress`: progresso persistente por conceito.
- `ReviewScheduler`: cálculo de revisão espaçada.
- `ReviewQueue`: seleção de revisões vencidas.
- `ReviewLifecycle`: ativação, conclusão e reagendamento de revisões.
- `ProcessLearningTurn`: orquestração determinística do turno pedagógico.
- `LearningHistory`: histórico confirmado, limitado e isolado por aluno, área e conceito.
- `StudentContext`: identidade pedagógica resolvida no servidor para o aluno padrão atual.

## Confiabilidade

- persistência SQLite;
- migrations de schema versionadas, atômicas e idempotentes;
- identidade estável de aluno e sessão, com migração dos registros legados para o aluno padrão;
- transações atômicas no turno pedagógico;
- rollback quando uma gravação falha;
- rollback quando o streaming da resposta falha;
- proteção contra envio concorrente no frontend;
- idempotência por `turn_id` e replay da resposta confirmada;
- serialização server-side de turnos por aluno + área entre threads/workers;
- histórico pedagógico autoritativo no servidor;
- descarte de histórico forjado enviado pelo navegador;
- limite explícito de mensagens e notas;
- configuração de produção exige `SECRET_KEY` e `APEX_ACCESS_KEY`.

## Validação da release

A versão candidata foi validada com:

- suíte automatizada completa;
- validação sintática Python;
- validação sintática do JavaScript;
- `/health` via Flask;
- smoke test real com Gunicorn.

## Escopo adiado

Não fazem parte desta release:

- autenticação e gestão multiusuário completas;
- SkillGraph avançado;
- ChallengeEngine;
- Workspace/IDE;
- Git integrado;
- sandbox de execução;
- simulação empresarial completa.

Esses itens devem ser evoluídos após a auditoria técnica final da 1.0.
