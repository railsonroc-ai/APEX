# Backend APEX

## Objetivo

O diretório `backend` concentra a lógica de aplicação do APEX 3.0.

## Responsabilidades

O backend será responsável por:

- expor APIs do sistema
- processar solicitações do frontend
- integrar tutor, conteúdo e progresso
- controlar execução segura no Code Lab
- centralizar regras de negócio

## Áreas principais

### 1. Tutor API
Responsável por:
- receber perguntas do usuário
- encaminhar contexto ao tutor
- devolver respostas estruturadas

### 2. Code Execution
Responsável por:
- executar código com segurança
- retornar saídas e erros
- limitar ambiente de execução

### 3. Progress Service
Responsável por:
- registrar evolução do aluno
- salvar lições concluídas
- acompanhar dificuldades recorrentes

### 4. Content Delivery
Responsável por:
- entregar módulos e lições
- estruturar trilhas
- integrar conteúdo ao tutor

## Direção inicial

Durante a reorganização do APEX 3.0, o backend será preparado para receber a lógica que hoje ainda está espalhada em arquivos soltos na raiz do projeto.