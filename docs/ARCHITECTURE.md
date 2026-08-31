# APEX 3.0 - Arquitetura Inicial

## Visão Geral

O APEX 3.0 é uma plataforma educacional adaptativa focada em estudos de Tecnologia da Informação.

A arquitetura do sistema foi reorganizada para priorizar ensino, prática, acompanhamento de progresso e expansão modular, deixando a antiga automação operacional como infraestrutura secundária.

## Objetivos da Arquitetura

- Tornar o projeto mais limpo e modular
- Facilitar manutenção e evolução do produto
- Separar claramente produto, infraestrutura e legado
- Preparar a base para tutor inteligente, Code Lab e progresso adaptativo

## Módulos Principais

### 1. Tutor Inteligente
Responsável por:
- explicar conteúdos
- responder dúvidas
- orientar trilhas de estudo
- adaptar o fluxo de aprendizagem

### 2. Code Lab
Responsável por:
- editar código
- executar Python e JavaScript com segurança
- fornecer feedback sobre erros e resultados
- integrar prática com explicação

### 3. Progresso
Responsável por:
- armazenar evolução do aluno
- registrar lições concluídas
- mapear erros recorrentes
- sugerir próximos passos

### 4. Core APEX
Responsável por:
- memória
- configuração
- integração entre módulos
- orquestração interna
- agentes e serviços centrais

### 5. Voz
Responsável por:
- entrada por voz
- saída por voz
- experiências imersivas
- acessibilidade e interação natural

## Estrutura-alvo

```text
APEX/
├── frontend/
├── backend/
├── core/
├── content/
├── data/
├── infra/
├── tests/
└── docs/