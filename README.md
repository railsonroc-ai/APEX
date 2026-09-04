# APEX

APEX é uma plataforma educacional adaptativa em desenvolvimento para ensino de programação e Tecnologia da Informação.

O objetivo é evoluir além de um chatbot: ensinar, verificar compreensão, adaptar o nível de ajuda e conduzir o estudante progressivamente até práticas próximas do desenvolvimento profissional.

## Estado atual

A fundação técnica e o hardening inicial estão concluídos.

O APEX possui Flask, Groq, streaming SSE, TutorCore, histórico controlado, autenticação, SQLite, identidade pedagógica explícita, notas, health check, síntese de voz, frontend JavaScript modular, timeout da IA, Gunicorn e um ledger imutável de evidências pedagógicas e uma suíte automatizada com mais de 150 casos.

A fundação do Evidence Engine está em construção: avaliações confirmadas passam a ser auditáveis por aluno/turno, com rubrica e policy versionadas. A próxima evolução é derivar domínio de evidências variadas e independentes, em vez de depender apenas do acumulador atual.

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

**Próxima etapa:** Evidence Engine auditável, `concept_id` estável e política de domínio baseada em evidências múltiplas.
