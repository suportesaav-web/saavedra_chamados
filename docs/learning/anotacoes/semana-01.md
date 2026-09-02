# 📝 Anotações de Estudo: Semana 01

**Tema da Semana:** Fundamentos de Python e Versionamento  
**Período:** __/__/____ a __/__/____  
**Status:** 🟡 Em Andamento / 🟢 Concluído  

---

## 🎯 Objetivos da Semana

- [ ] Configurar ambiente de desenvolvimento no VS Code.
- [ ] Entender a sintaxe básica de Python (variáveis, listas, dicionários, laços e funções).
- [ ] Aprender os comandos fundamentais do Git e fluxo no GitHub.
- [ ] Publicar o primeiro repositório no GitHub com os exercícios práticos.

---

## 📖 Resumo dos Conceitos Aprendidos

### 1. Python - Sintaxe e Estruturas Basicas
- **Variáveis e Tipos:** `str`, `int`, `float`, `bool`.
- **Coleções:**
  - `list`: Coleção ordenada e mutável (`[1, 2, 3]`).
  - `dict`: Estrutura de chave-valor (`{"nome": "Dev", "funcao": "DevOps"}`).
- **Controle de Fluxo:** `if/elif/else`, laços `for` e `while`.
- **Funções:** `def nome_funcao(parametro): return valor`.

### 2. Git & GitHub - Versionamento
- `git init`: Inicializa o repositório local.
- `git status`: Exibe o estado dos arquivos na árvore de trabalho.
- `git add .`: Adiciona alterações para a Staging Area.
- `git commit -m "mensagem"`: Registra a alteração no histórico local.
- `git push origin main`: Envia os commits para o repositório remoto.

---

## 💻 Laboratórios & Exercícios Realizados

### Lab 1: Script de Boas-Vindas e Coleta de Dados
```python
def registrar_usuario(nome, cargo):
    usuario = {"nome": nome, "cargo": cargo, "status": "Ativo"}
    print(f"[OK] Usuário {usuario['nome']} cadastrado como {usuario['cargo']}.")
    return usuario

if __name__ == "__main__":
    registrar_usuario("Alex", "Engenheiro DevOps")
```

### Lab 2: Primeiro Repositório Git
1. `git init`
2. `echo "# Estudos Automação" > README.md`
3. `git add README.md`
4. `git commit -m "feat: commit inicial"`
5. `git remote add origin <URL_DO_REPOSITORIO>`
6. `git push -u origin main`

---

## ❓ Principais Dúvidas & Soluções (IA Support)

- **Dúvida 1:** Qual a diferença entre `git add .` e `git add -A`?
  - *Solução:* `git add .` adiciona novos arquivos e modificados no diretório atual. `git add -A` adiciona todas as mudanças no repositório inteiro.
- **Dúvida 2:** Como tratar exceções de conversão de tipos em Python?
  - *Solução:* Utilizar blocos `try / except ValueError`.

---

## 📌 Anotações Gerais & Insights

> *Escreva aqui observações pessoais, dicas de atalhos do VS Code, comandos úteis do terminal, etc.*

---

## ✅ Checklist de Entrega da Semana

- [ ] Todos os exercícios foram testados localmente.
- [ ] O código foi refatorado e limpo.
- [ ] Alterações foram enviadas para o GitHub via `git push`.
