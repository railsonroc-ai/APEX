# Plano de Migração - APEX 3.0

## Objetivo

Este documento descreve como o repositório atual do APEX será reorganizado para a arquitetura do APEX 3.0.

## Situação atual

O repositório ainda possui arquivos e pastas misturando:

- produto educacional
- automação antiga
- scripts operacionais
- interface
- backend
- agentes locais
- documentação legada

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