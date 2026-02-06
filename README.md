# 🤖 APEX - Automação de Ferramentas Inteligente

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-Em%20Desenvolvimento-yellow.svg)]()

> **APEX** é um assistente inteligente de automação baseado em voz e NLP, similar ao Perplexity AI, com capacidades de busca web, processamento de linguagem natural e execução de comandos do sistema.

## ✨ Características

### 🎯 Funcionalidades Principais

- **🔍 Busca Web Inteligente** - Pesquisa na internet como Perplexity AI
- **🎙️ Interface de Voz** - Controle via comando de voz
- **🤖 NLP Avançado** - Processamento de linguagem natural em português
- **⚙️ Automação** - Execute comandos do sistema automaticamente
- **🔌 API REST** - Integre com outras aplicações
- **💾 Gerenciador de Dependências** - Instale pacotes e programas facilmente
- **🌐 Navegação Web** - Acesse e extraia informações de sites

## 🚀 Instalação

### Pré-requisitos

- Python 3.8+
- Windows (compatível com PowerShell)
- pip (gerenciador de pacotes Python)

### Passos de Instalação

1. **Clone o repositório**
```bash
git clone https://github.com/railsonroc-ai/APEX.git
cd APEX
```

2. **Instale as dependências**
```bash
pip install -r requirements.txt
```

3. **Configure o Whisper (para reconhecimento de voz)**
```bash
pip install openai-whisper
whisper --help
```

4. **Instale o modelo de linguagem (opcional)**
```bash
whisper --model tiny --language pt
```

## 📋 Arquivos do Projeto

| Arquivo | Descrição |
|---------|----------|
| `comandos.py` | Sistema de execução de comandos do sistema |
| `apex_nle.py` | Processador de linguagem natural (NLE) |
| `apex_web_search.py` | Sistema de busca web integrado |
| `jarvis_voz.py` | Interface de voz com Flask |
| `mensageiro_apex.py` | Gerenciador de mensagens e fila de comandos |
| `enviar_comando.py` | Cliente para enviar comandos ao APEX |
| `instalador.py` | Gerenciador de instalações de pacotes |

## 💻 Como Usar

### 1. **Modo Voz (Recomendado)**

```bash
python jarvis_voz.py
```

O APEX escutará por:
- "APEX, abrir YouTube"
- "APEX, qual é a capital da França?"
- "APEX, pesquisar receita de bolo de chocolate"

### 2. **Modo API REST**

```python
import requests
import json

comando = "abrir navegador chrome"
response = requests.post('http://localhost:5000/comando', json={"texto": comando})
print(response.json())
```

### 3. **Modo Cliente Direto**

```bash
python enviar_comando.py
# Digite: abrir youtube
# Digite: pesquisar dia da independência
```

### 4. **Busca Web Integrada**

```python
from apex_web_search import buscar_web

resultado = buscar_web("qual a melhor linguagem de programação em 2024?")
print(resultado)
```

## 🔧 Comandos Disponíveis

### Navegador
- "abrir youtube"
- "abrir chrome" / "abrir navegador"
- "abrir vs code"

### Sistema
- "abrir calculadora"
- "abrir bloco de notas"
- "abrir downloads"

### Informações
- "que horas são?"
- "pesquisar [termo]"

### Busca Web
- "pesquisar sobre [tema]"
- "qual é [pergunta]?"

## 📦 Dependências

```txt
requests>=2.28.0
beautifulsoup4>=4.11.0
sounddevice>=0.4.5
soundfile>=0.12.0
flask>=2.0.0
whisper-openai>=1.0.0
opencv-python>=4.5.0
numpy>=1.21.0
pyaudio>=0.2.11
```

## 🏗️ Arquitetura

```
APEX
├── Interface de Entrada
│   ├── Voz (jarvis_voz.py)
│   ├── API REST (Flask)
│   └── CLI (enviar_comando.py)
│
├── Processamento
│   ├── NLE (apex_nle.py) - Interpreta comandos
│   ├── Busca Web (apex_web_search.py)
│   └── Execução (comandos.py)
│
└── Saída
    ├── Síntese de Voz
    ├── Respostas em JSON
    └── Ações do Sistema
```

## 🧠 Fluxo de Funcionamento

1. **Entrada**: Usuário fala ou digita um comando
2. **Transcrição**: Whisper converte voz em texto
3. **NLE**: `apex_nle.py` interpreta a intenção
4. **Processamento**: Busca web ou executa comando
5. **Resposta**: Síntese de voz ou JSON retornado

## 🔍 Busca Web (Like Perplexity)

O APEX pode buscar e resumir informações da web:

```python
from apex_web_search import APEXWebSearch

search = APEXWebSearch()
resultado = search.pesquisar_e_resumir("tendências de IA em 2024")
```

## 🌍 Extensibilidade

Você pode adicionar novos comandos em `apex_nle.py`:

```python
# Em apex_nle.py
if "seu comando" in texto:
    return "seu_comando"
```

E implementar em `comandos.py`:

```python
if "seu_comando" in texto:
    # Sua lógica aqui
    return "Resultado do seu comando"
```

## ⚙️ Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
APEX_PORT=5000
APEX_MODEL=tiny
APEX_LANGUAGE=pt
```

## 📚 Exemplos de Uso

### Exemplo 1: Pesquisa Simples
```bash
$ python enviar_comando.py
Digite o comando para o APEX: qual é a capital do brasil
```

### Exemplo 2: Automação
```bash
$ python enviar_comando.py
Digite o comando para o APEX: abrir youtube
# YouTube abre automaticamente
```

### Exemplo 3: API
```bash
curl -X POST http://localhost:5000/comando \
  -H "Content-Type: application/json" \
  -d '{"texto": "abrir chrome"}'
```

## 🐛 Troubleshooting

### Problema: Microphone não funciona
**Solução**: Instale `pyaudio`
```bash
pip install pyaudio
```

### Problema: Whisper não encontrado
**Solução**: 
```bash
pip install openai-whisper
whisper --help
```

### Problema: Flask não inicia
**Solução**: Verifique se a porta 5000 está disponível
```bash
netstat -ano | findstr :5000
```

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Faça um Fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

## 📝 Roadmap

- [ ] Integração com OpenAI GPT
- [ ] Histórico de comandos e contexto
- [ ] Interface gráfica (GUI)
- [ ] Suporte para múltiplos idiomas
- [ ] Machine Learning para aprendizado de padrões
- [ ] Dashboard web
- [ ] Integração com smart home

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 👨‍💻 Autor

**Railson Rocha** - [GitHub](https://github.com/railsonroc-ai)

## 📞 Suporte

Tem dúvidas? Abra uma [Issue](https://github.com/railsonroc-ai/APEX/issues) no repositório.

## ⭐ Se gostou, deixe uma estrela!

---

**Feito com ❤️ por Railson Rocha**
