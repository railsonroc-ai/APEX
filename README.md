# APEX

APEX é uma plataforma educacional adaptativa em desenvolvimento para ensino de programação e Tecnologia da Informação.

O objetivo é evoluir além de um chatbot: ensinar, verificar compreensão, adaptar o nível de ajuda e conduzir o estudante progressivamente até práticas próximas do desenvolvimento profissional.

## Estado atual

A fundação técnica e o hardening inicial estão concluídos.

O APEX possui Flask, Groq, streaming SSE, TutorCore, histórico controlado, autenticação vinculada ao aluno, rate limit server-side, headers HTTP de segurança, SQLite, identidade pedagógica explícita, notas, health check, síntese de voz, frontend JavaScript modular, timeout da IA, Gunicorn, um ledger imutável de evidências pedagógicas, catálogo mínimo de competências com `concept_id` estável e uma política de domínio baseada em portfólio de evidências. O backend agora expõe `create_app()` sem inicializar o SQLite durante o import; produção e testes fazem o bootstrap do banco explicitamente. A observabilidade operacional usa `request_id`/`turn_id` correlacionados e eventos estruturados sem conteúdo sensível. A camada de privacidade permite exportar os dados do aluno, excluir transacionalmente seus registros e executar retenção administrativa em dry-run por padrão.

A fundação do Evidence Engine torna avaliações confirmadas auditáveis por aluno/turno, com rubrica e policy versionadas. A identidade das competências também é estável: aliases convergem para `concept_id` versionado e texto livre do LLM não funciona como chave de negócio. A `MasteryPolicy` adiciona um segundo gate: score sozinho não conclui uma competência; são exigidas evidências aplicadas suficientes, demonstrações, diversidade mínima de etapas e uma evidência atual válida. A assistência é rastreada pelo servidor: cada resposta do tutor recebe um `AssistanceEvent` derivado da ação pedagógica e a evidência seguinte herda esse nível de suporte. A tentativa do aluno existe como entidade própria (`LearningAttempt`), separada do julgamento, e uma `RubricAssessment` imutável registra os critérios usados na avaliação. A partir da migration 11, o fluxo real também registra uma `LearningTask` imutável para o turno do tutor; novas avaliações sem tarefa server-side confirmada não são produzidas pelo app, e a tentativa passa a carregar o `task_id` correspondente. A migration 12 adiciona um lifecycle persistente de sessão: o aluno pode pausar, retomar direto ou iniciar uma revisão de retomada, com transições auditáveis e bloqueio de novos turnos enquanto a sessão está pausada. A interface principal já consome esse lifecycle: exibe o estado server-side, bloqueia o campo de mensagem durante a pausa e oferece as ações **Pausar**, **Retomar direto** e **Revisar antes** sem manter uma segunda fonte de verdade no navegador.

## Executar

Instale as dependências:

    python3 -m pip install -r requirements-dev.txt

Execute localmente:

    python3 -m backend.app

Execute os testes (pytest cria um SQLite temporário isolado e não usa `data/apex.db`):

    pytest -q

Ou rode o gate automatizado sem tocar no banco real:

    python3 tools/apex_validate.py

Use `.env.example` como referência de configuração e nunca versione `.env`.

## Próxima fase

O kernel adaptativo principal já está implementado. A reta final do APEX 1.0 concentra-se em privacidade operacional, testes E2E de jornadas completas e hardening final.

Depois da auditoria final da 1.0 serão adicionadas experiências de formação profissional, incluindo projetos, debugging, manutenção de código, Git, testes, APIs, bancos de dados, refatoração, code review, logs, deploy e problemas realistas.

A meta continua sendo desenvolver autonomia técnica, não dependência do tutor.

## Documentação

Arquitetura técnica: `docs/ARCHITECTURE.md`

Direção visual: `docs/DESIGN_SYSTEM.md`

Materiais históricos: `docs/legacy/`

## Status

**Fundação técnica:** concluída.

**Próxima etapa:** fechar privacidade/E2E e executar a auditoria técnica final do APEX 1.0, ainda sem ChallengeEngine completo ou execução de código.

## Segurança de acesso

Em produção, `APEX_ACCESS_KEY` é provisionada como credencial do aluno padrão durante o bootstrap. O SQLite armazena apenas o hash da chave. Credenciais adicionais podem ser vinculadas a alunos distintos pelo serviço de acesso, com sessões próprias e revogação; o frontend continua usando o header `X-Apex-Key`, sem mudança de fluxo visual.

## Runtime de IA

As chamadas ao provider passam por `LLMGateway`, que centraliza timeout, retries, limites de geração e telemetria de latência/tokens sem registrar conteúdo do aluno.

## Observabilidade

Cada resposta HTTP recebe `X-Apex-Request-ID`. Eventos operacionais são emitidos em JSON com o prefixo `apex_event`, correlacionando request, turno, área e referências pseudonimizadas de aluno/sessão. O APEX registra latência HTTP, chamadas LLM, transições de sessão, conclusão/falha de turnos e bloqueios operacionais, sem persistir mensagem do aluno, prompt, resposta do tutor, notas ou segredos nos logs.


## Privacidade e ciclo de vida dos dados

`GET /api/privacy/export` gera um JSON dos dados pertencentes ao aluno autenticado, sem exportar hashes de credenciais. `DELETE /api/privacy/data` exige a confirmação literal `EXCLUIR MEUS DADOS` e remove, em uma única transação, identidade, sessões, histórico, notas, tarefas, tentativas, rubricas, evidências, mastery, assistência e credenciais daquele aluno. Ledgers continuam imutáveis fora desse fluxo.

A retenção administrativa é deliberadamente manual: `python3 tools/apex_retention.py` apenas lista candidatos por padrão. Somente contas não padrão, sem credencial ativa e além da janela configurada podem entrar na lista. A flag `--apply` é necessária para executar exclusões.
