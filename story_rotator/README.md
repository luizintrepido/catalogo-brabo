# Rotação Automática de Criativos — Stories

Roda **a cada 3 dias** (GitHub Actions). Para cada anúncio do conjunto **Stories**
que está performando mal, troca a foto por uma **ainda não usada** da pasta do
Drive "story ads".

## Como funciona

```
A cada 3 dias (cron)
        ↓
Lê performance dos anúncios do conjunto Stories (últimos 7 dias)
        ↓
Marca os que performam mal (ver critérios abaixo)
        ↓
Busca fotos novas na pasta do Drive (não usadas ainda)
        ↓
Sobe a foto nova na Meta e troca o criativo do anúncio ruim
        ↓
Registra a foto como usada (usadas.json) e dá commit
```

## Critério de "mau desempenho" (ajustável no topo do `rotacionar.py`)

Um anúncio é trocado se, na janela de 7 dias:
- Gastou **≥ R$2** e teve **0 conversas**, OU
- Teve **≥ 150 impressões** e **CTR < 1,5%**, OU
- Tem conversas mas **CPL > R$12**

Limita a **2 trocas por execução** (evita churn).

## Configuração (parâmetros no `rotacionar.py`)

| Variável | Padrão | O que é |
|----------|--------|---------|
| `DIAS` | 7 | Janela de avaliação |
| `MAX_TROCAS` | 2 | Máx. de trocas por rodada |
| `GASTO_MIN` | 2.0 | Gasto mínimo pra avaliar |
| `CTR_MIN` | 1.5 | CTR mínimo aceitável (%) |
| `CPL_MAX` | 12.0 | CPL máximo aceitável (R$) |

## Pré-requisito (1 secret a adicionar)

O repo já tem as credenciais do Drive. Falta só o token da Meta:

```bash
gh secret set META_ACCESS_TOKEN --repo luizintrepido/catalogo-brabo
# cole o token quando pedir (mesmo do brabo-comments/.env)
```

## Como as fotos são controladas

- `usadas.json` guarda os IDs das fotos do Drive já usadas
- A automação só pega fotos que **não estão** nessa lista
- **Pra dar mais opções:** basta adicionar fotos novas na pasta do Drive
  (formato Story 9:16). A próxima rodada já considera elas.

## Rodar manualmente

GitHub → repo `catalogo-brabo` → aba **Actions** → "Rotacionar Criativos Stories"
→ **Run workflow**.
