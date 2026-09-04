# APEX

APEX é uma plataforma educacional adaptativa em desenvolvimento para ensino de programação e Tecnologia da Informação.

O objetivo é evoluir além de um chatbot: ensinar, verificar compreensão, adaptar o nível de ajuda e conduzir o estudante progressivamente até práticas próximas do desenvolvimento profissional.

## Estado atual

A fundação técnica e o hardening inicial estão concluídos.

O APEX possui Flask, Groq, streaming SSE, TutorCore, histórico controlado, autenticação, SQLite, identidade pedagógica explícita, notas, health check, síntese de voz, frontend JavaScript modular, timeout da IA, Gunicorn, um ledger imutável de evidências pedagógicas, catálogo mínimo de competências com `concept_id` estável e uma política de domínio baseada em portfólio de evidências.

A fundação do Evidence Engine torna avaliações confirmadas auditáveis por aluno/turno, com rubrica e policy versionadas. A identidade das competências também é estável: aliases convergem para `concept_id` versionado e texto livre do LLM não funciona como chave de negócio. A `MasteryPolicy` adiciona um segundo gate: score sozinho não conclui uma competência; são exigidas evidências aplicadas suficientes, demonstrações, diversidade mínima de etapas e uma evidência atual válida. Quando assistência explícita for rastreada, a política também exige demonstração com baixa ajuda.

## Executar

Instale as dependências:

    python3 -m pip install -r requirements-dev.txt

Execute localmente:

    python3 -m backend.app

Execute os testes:

    pytest -q

Ou rode o gate automatizado sem tocar no banco real:

    python3 tools/apex_validate.py

Use `.env.example` como referência de configuração e nunca versione `.env`.

## Próxima fase

O cérebro pedagógico do APEX será desenvolvido com controle de novidade, estado do aluno, verificação de compreensão, recuperação de conhecimentos, revisão espaçada e redução progressiva de ajuda.

Depois serão adicionadas experiências de formação profissional, incluindo projetos, debugging, manutenção de código, Git, testes, APIs, bancos de dados, refatoração, code review, logs, deploy e problemas realistas.

A meta é desenvolver autonomia técnica, não dependência do tutor.

## Documentação

Arquitetura técnica: `docs/ARCHITECTURE.md`

Direção visual: `docs/DESIGN_SYSTEM.md`

Materiais históricos: `docs/legacy/`

## Status

**Fundação técnica:** concluída.

**Próxima etapa:** tornar scaffolding/nível de ajuda explícito e evoluir a estimativa de competência com retenção e contextos profissionais, mantendo decisões auditáveis.
