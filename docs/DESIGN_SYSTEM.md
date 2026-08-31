# APEX Design System (Inicial)

Base visual inicial inspirada no logo futurista do APEX.

## 1) Paleta de cores

### Core (dark mode)
- Fundo base: `#0A1020`
- Fundo elevado: `#131D35`
- Fundo suave: `#1A2746`
- Texto principal: `#E8F3FF`
- Texto secundário: `#9FB9D7`
- Borda: `#2A3F6D`

### Identidade / Brand
- Primary Neon: `#5EF2FF`
- Secondary Blue: `#46A5FF`
- Accent Violet: `#836DFF`

### Feedback
- Sucesso: `#26D07C`
- Aviso: `#F0C24B`
- Erro: `#FF5B5B`

## 2) Tipografia
- Família: `Segoe UI, Inter, Roboto, Arial, sans-serif`
- Escala:
  - XS: `12px`
  - SM: `14px`
  - MD: `16px`
  - LG: `20px`
  - XL: `28px`
- Pesos: `400 / 500 / 600 / 700`

## 3) Espaçamento e forma
- Escala de espaçamento: `4, 8, 12, 16, 24, 32`
- Raios: `8, 12, 16`
- Sombras: suaves e frias para profundidade técnica

## 4) Componentes iniciais
- `ds-card`: contêiner elevado
- `ds-row`: linha de conteúdo
- `ds-btn` / `ds-btn--ghost`: botões padrão e secundário
- `ds-input`, `ds-select`, `ds-textarea`: campos de formulário
- `ds-link`: links
- `ok`, `warn`, `err`: estados de health/feedback
- `ds-logo-wrap`: container responsivo para logo

## 4.1) Variações visuais adicionadas

### Badge
- Base: `ds-badge`
- Variações: `ds-badge--primary`, `ds-badge--accent`, `ds-badge--success`, `ds-badge--warning`, `ds-badge--danger`
- Uso: status curtos, labels de ambiente e tags de telemetria.

### Table
- Wrapper responsivo: `ds-table-wrap`
- Estrutura: `ds-table`
- Recursos: header com gradiente, hover de linha, overflow horizontal no mobile.

### Modal
- Overlay: `ds-modal`
- Estado aberto: `is-open`
- Blocos: `ds-modal__dialog`, `ds-modal__header`, `ds-modal__title`, `ds-modal__body`, `ds-modal__actions`
- Recursos: fechamento por clique no backdrop e tecla `Esc`.

## 4.2) Catálogo completo de componentes (v1)

### Botões
- `ds-btn`
- `ds-btn--ghost`
- `ds-btn--success`
- `ds-btn--danger`
- `ds-btn--sm`
- `ds-btn--lg`

### Cards
- `ds-card`
- `ds-card--outlined`
- `ds-card--elevated`
- `ds-card--accent`

### Tabelas
- `ds-table-wrap`
- `ds-table`
- `ds-table--compact`
- `ds-table--striped`
- `ds-table--bordered`

### Agrupamentos e Containers
- `ds-container`, `ds-container--narrow`
- `ds-section`
- `ds-panel`
- `ds-stack`
- `ds-grid` + colunas (`ds-col-3/4/6/8/12`)
- `ds-group`
- `ds-btn-group`
- `ds-input-group`

## 5) Arquivo principal
- CSS de design system: `static/apex_design_system.css`

## 6) Páginas já conectadas
- `templates/index.html`
- `templates/atualizar.html`
- `templates/resultado_atualizacao.html`
- `templates/components_demo.html`

## 7) Próximo passo sugerido
- Extrair componentes HTML reutilizáveis (cards, badges, botões) para templates parciais.
