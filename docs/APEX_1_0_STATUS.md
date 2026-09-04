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
- `EvidenceEvaluator`: coleta classificações por critério; o outcome final é derivado pelo backend.
- `AttemptPolicy`: classifica a tentativa pelo estágio pedagógico confirmado.
- `TaskPolicy`: define quais ações do tutor geram uma tarefa avaliável e qual tipo de tarefa deve ser produzido.
- `LearningTask`: preserva a tarefa concreta, o turno-fonte, conceito, etapa, assistência e rubrica esperada.
- `LearningAttempt`: ledger imutável da ação do aluno, separado do julgamento semântico.
- `RubricPolicy`: rubrica v2 com critérios estáveis e derivação determinística do outcome.
- `RubricAssessment`: ledger imutável dos critérios, completude e origem do outcome.
- `EvidenceEvent`: ledger imutável das avaliações confirmadas, com contexto, confiança, assistência, versão da rubrica/política e mastery antes/depois.
- `MasteryPolicy`: política versionada que impede conclusão apenas por score e exige portfólio mínimo de evidências.
- `MasteryAssessment`: ledger imutável da decisão de domínio, contagens, diversidade, retenção observada e bloqueadores.
- `AssistancePolicy`: política server-side que converte a ação pedagógica em nível estável de ajuda.
- `AssistanceEvent`: ledger imutável da assistência vinculada à resposta do tutor; a evidência seguinte usa esse evento anterior.
- `ConceptCatalog`: catálogo mínimo versionado com `concept_id` estável, aliases e nomes canônicos.
- `ConceptTracker`: seleção do conceito somente entre IDs permitidos pelo catálogo.
- `ConceptActivation`: início e retomada de conceitos sem contaminação de estado.
- `ConceptProgress`: progresso persistente por `concept_id` estável.
- `ReviewScheduler`: cálculo de revisão espaçada.
- `ReviewQueue`: seleção de revisões vencidas.
- `ReviewLifecycle`: ativação, conclusão e reagendamento de revisões.
- `ProcessLearningTurn`: orquestração determinística do turno pedagógico.
- `LearningHistory`: histórico confirmado, limitado e isolado por aluno, área e conceito.
- `StudentContext`: identidade pedagógica resolvida no servidor a partir da credencial autenticada, com fallback para o aluno padrão em desenvolvimento sem chave.
- `AccessControl`: credenciais por hash vinculadas a `student_id`, com provisionamento, rotação e revogação.
- `AccessRateLimiter`: quota fixed-window persistida em SQLite e compartilhada entre workers.
- `LearningSessionLifecycle`: máquina de estados persistente `studying → paused → studying/reviewing`, com revisão antes de retomar e ledger imutável de transições.
- `Session UI`: controles da página principal que refletem o estado server-side e expõem Pausar / Retomar direto / Revisar antes.
- `LLMGateway`: fronteira única com o provider de IA, com timeout/retries deliberados, limites de geração por finalidade e telemetria sem conteúdo.
- `create_app()`: factory Flask sem efeitos de persistência no import; bootstrap de produção e pytest inicializam o SQLite explicitamente em ambientes separados.
- `Observability`: correlação por `request_id`/`turn_id`, eventos JSON e referências pseudonimizadas de identidade, sem conteúdo pedagógico sensível nos logs.
- `DataLifecycle`: exportação do aluno, exclusão transacional completa e retenção administrativa explícita/dry-run.

## Confiabilidade

- persistência SQLite;
- migrations de schema versionadas, atômicas e idempotentes;
- ledger de evidências imutável, isolado por aluno e ligado ao turno confirmado;
- tentativa e julgamento são entidades distintas: `learning_attempts` preserva a ação do aluno e `rubric_assessments` preserva os critérios usados para julgá-la;
- tarefa e tentativa também são distintas: `learning_tasks` preserva o que o tutor realmente apresentou e novas tentativas do fluxo real carregam o `task_id` correspondente;
- a rubrica semântica v2 não aceita `demonstrated` como decisão global autoatribuída pela LLM: o backend deriva o outcome a partir de três critérios estruturados;
- identidade estável de aluno e sessão, com migração dos registros legados para o aluno padrão;
- pausa e retomada são estado server-side persistente; novos turnos são bloqueados durante `paused`, a interface também bloqueia o envio nesse estado, e a opção `review` restaura a etapa anterior somente depois de uma evidência demonstrada;
- transições de pausa/retomada geram `learning_session_events` imutáveis e são serializadas pelo mesmo lease aluno+área usado pelos turnos;
- transações atômicas no turno pedagógico;
- rollback quando uma gravação falha;
- rollback quando o streaming da resposta falha;
- proteção contra envio concorrente no frontend;
- controles de sessão ficam indisponíveis durante turno/ação de lifecycle e o frontend ressincroniza o estado pelo servidor depois de cada turno confirmado;
- idempotência por `turn_id` e replay da resposta confirmada;
- serialização server-side de turnos por aluno + área entre threads/workers;
- histórico pedagógico autoritativo no servidor;
- identidade de competência baseada em `concept_id` com foreign keys reais;
- aliases de conceito convergem para uma única competência e texto livre não entra como chave de negócio;
- descarte de histórico forjado enviado pelo navegador;
- limite explícito de mensagens e notas;
- avaliações abaixo do limiar podem ser auditadas sem alterar o estado pedagógico;
- conclusão de competência exige decisão explícita da `MasteryPolicy`; chamar a transição isoladamente não contorna o gate;
- cada evidência confirmada recebe uma avaliação de domínio versionada e explicável por bloqueadores;
- o nível de assistência não é fornecido pelo navegador nem declarado pela LLM: nasce da `TeachingPolicy`/`AssistancePolicy` e é persistido no turno confirmado;
- a assistência atribuída à resposta do aluno vem da mensagem anterior do tutor, associada por aluno, sessão, área, conceito e turno;
- conclusão de domínio exige pelo menos uma demonstração com assistência `independent` ou `light`, e a evidência final não pode ser `untracked`, `guided` ou `direct`;
- conceitos legados desconhecidos são preservados como não selecionáveis e recebem nome seguro;
- configuração de produção exige `SECRET_KEY`; o APEX 1.0 individual não exige senha ou chave de acesso do usuário.
- rotas protegidas aplicam rate limit compartilhado e retornam HTTP 429 com `Retry-After` ao exceder a quota.
- a app factory aplica CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e `Permissions-Policy`.
- o SDK Groq não é mais chamado diretamente pelas rotas; todas as chamadas passam pelo `LLMGateway`.
- cada finalidade LLM possui limite de geração configurável e o provider recebe política explícita de retries.
- logs LLM registram latência e tokens quando disponíveis, sem persistir prompt/resposta.
- importar `backend.app` não executa migrations nem cria `apex.db`; a suíte pytest força um diretório SQLite temporário próprio.
- cada resposta HTTP recebe `X-Apex-Request-ID`; logs operacionais estruturados correlacionam requests, turnos, chamadas LLM, transições de sessão e falhas sem registrar mensagens, prompts, respostas, notas ou chaves.
- exportação de privacidade nunca inclui `key_hash`; exclusão de aluno exige confirmação explícita e usa uma autorização transacional temporária que não enfraquece a imutabilidade normal dos ledgers.
- retenção administrativa não roda automaticamente; o CLI é dry-run por padrão e só considera contas não padrão sem credencial ativa.

- jornada E2E real de conclusão: tarefa confirmada → tentativa → rubrica → evidência → mastery → conclusão → revisão agendada;
- replay E2E de `turn_id` confirmado não duplica tentativa, evidência ou avaliação de mastery;
- pausa → revisar antes → tarefa de retenção → evidência demonstrada → restauração exata da etapa anterior é coberta como jornada única;
- exportação seguida de exclusão de um aluno populado confirma isolamento, remoção de credencial/rate-limit e ausência de foreign keys órfãs;
- `apex_apply_update.py` valida manifesto canônico e correspondência exata entre manifesto e conteúdo do pacote, rejeitando manifestos técnicos extras;

## Validação da release

O checkpoint corrente deve ser validado em duas camadas:

1. `python3 tools/apex_validate.py`: sintaxe Python/JavaScript, suíte automatizada completa e `git diff --check`, sempre com SQLite temporário.
2. `python3 tools/apex_release_gate.py`: exige working tree limpo, repete a suíte completa, executa a seleção de jornadas/falhas críticas e recria um banco novo validando todas as migrations, foreign keys e integridade.

Antes de declarar a 1.0, ainda deve existir smoke test real com Gunicorn e `/health` no ambiente de release.

A rotina operacional também possui `tools/apex_validate.py`, `tools/apex_apply_update.py` e `tools/apex_migrate_real.py` para reduzir passos manuais sem remover os gates de segurança. O Release Candidate acrescenta `tools/apex_release_gate.py`, que exige working tree limpo, repete a suíte, executa jornadas/falhas críticas e recria um banco temporário pela cadeia completa de migrations.

## Escopo adiado

Não fazem parte desta release:

- cadastro/self-service, recuperação de conta e gestão administrativa multiusuário completas;
- SkillGraph avançado;
- ChallengeEngine;
- Workspace/IDE;
- Git integrado;
- sandbox de execução;
- simulação empresarial completa.

Esses itens devem ser evoluídos após a auditoria técnica final da 1.0.
