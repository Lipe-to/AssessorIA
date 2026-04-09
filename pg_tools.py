import os
from dotenv import load_dotenv
import psycopg2
from typing import Optional
from langchain.tools import tool
from pydantic import BaseModel, Field

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL, options="-c client_encoding=UTF8")


# ─── Schemas ────────────────────────────────────────────────────────────────

class AddTransactionArgs(BaseModel):
    amount: float = Field(..., description="Valor da transacão (use positivo).")
    source_text: str = Field(..., description="Texto original do usuário.")
    occurred_at: Optional[str] = Field(
        default=None,
        description="Timestamp ISO 8601; se ausente, usa NOW() no banco."
    )
    type_id: Optional[int] = Field(default=None, description="ID em transaction_types (1=INCOME, 2=EXPENSES, 3=TRANSFER).")
    type_name: Optional[str] = Field(default=None, description="Nome do tipo: INCOME | EXPENSES | TRANSFER.")
    category_id: Optional[int] = Field(default=None, description="FK de categoria (int) 1-comida | 2-besteira | 3-estudo | 4-férias | 5-transporte | 6-moradia | 7-saúde | 8-lazer | 9-contas | 10-investimento | 11-presente | 12-outros")
    category_name: Optional[str] = Field(default=None, description="Nome da categoria: comida | besteira | estudo | férias | transporte | moradia | saúde | lazer | contas | investimento | presente | outros")
    description: Optional[str] = Field(default=None, description="Descricão (opcional).")
    payment_method: Optional[str] = Field(default=None, description="Forma de pagamento (opcional).")


class QueryTransactionsArgs(BaseModel):
    search_text: Optional[str] = Field(
        default=None,
        description="Texto para buscar em source_text ou description da transacão. Se omitido, retorna todas as transações (respeitando os demais filtros)."
    )
    type_name: Optional[str] = Field(default=None, description="Filtrar por tipo: INCOME | EXPENSES | TRANSFER.")
    category_name: Optional[str] = Field(default=None, description="Filtrar por categoria: comida | besteira | estudo | férias | transporte | moradia | saúde | lazer | contas | investimento | presente | outros.")
    date_from_local: Optional[str] = Field(default=None, description="Data início (YYYY-MM-DD) em America/Sao_Paulo.")
    date_to_local: Optional[str] = Field(default=None, description="Data fim (YYYY-MM-DD) em America/Sao_Paulo.")


class DailyBalanceArgs(BaseModel):
    date_local: str = Field(..., description="Data no formato YYYY-MM-DD em America/Sao_Paulo.")


class TopTransactionsArgs(BaseModel):
    type_name: Optional[str] = Field(default=None, description="Filtrar por tipo: INCOME | EXPENSES | TRANSFER.")
    category_name: Optional[str] = Field(default=None, description="Filtrar por categoria.")
    date_from_local: Optional[str] = Field(default=None, description="Data início (YYYY-MM-DD) em America/Sao_Paulo.")
    date_to_local: Optional[str] = Field(default=None, description="Data fim (YYYY-MM-DD) em America/Sao_Paulo.")
    limit: int = Field(default=1, description="Quantas transações retornar (padrão 1 = maior).")
    order: str = Field(default="DESC", description="DESC = maior primeiro, ASC = menor primeiro.")


class UpdateTransactionArgs(BaseModel):
    transaction_id: int = Field(..., description="ID da transação a ser atualizada.")
    amount: Optional[float] = Field(default=None, description="Novo valor da transação (positivo).")
    type_name: Optional[str] = Field(default=None, description="Novo tipo: INCOME | EXPENSES | TRANSFER.")
    category_name: Optional[str] = Field(default=None, description="Nova categoria: comida | besteira | estudo | férias | transporte | moradia | saúde | lazer | contas | investimento | presente | outros.")
    description: Optional[str] = Field(default=None, description="Nova descrição.")
    payment_method: Optional[str] = Field(default=None, description="Novo método de pagamento (ex: pix, cartão, dinheiro, débito, crédito).")
    occurred_at: Optional[str] = Field(default=None, description="Nova data/hora ISO 8601.")
    source_text: Optional[str] = Field(default=None, description="Novo texto original.")


# ─── Aliases e labels ───────────────────────────────────────────────────────

TYPE_ALIASES = {
    # INCOME
    "INCOME": "INCOME", "INCOMES": "INCOME", "GANHEI": "INCOME", "RECEBI": "INCOME",
    "SALÁRIO": "INCOME", "PAGAMENTO": "INCOME", "BONUS": "INCOME", "EXTRA": "INCOME",
    "ENTRADA": "INCOME", "DEPÓSITO": "INCOME", "PIX RECEBIDO": "INCOME",
    "TRANSFERÊNCIA RECEBIDA": "INCOME", "LUCRO": "INCOME", "RENDIMENTO": "INCOME",
    "GANHO": "INCOME", "HONORÁRIOS": "INCOME", "COMISSÃO": "INCOME",
    "PROVENTOS": "INCOME", "RECEITA": "INCOME", "CREDITO": "INCOME",
    # EXPENSES
    "EXPENSE": "EXPENSES", "EXPENSES": "EXPENSES", "GASTO": "EXPENSES", "COMPRA": "EXPENSES",
    "PAGUEI": "EXPENSES", "DESPESA": "EXPENSES", "SAÍDA": "EXPENSES", "PIX ENVIADO": "EXPENSES",
    "TRANSFERÊNCIA FEITA": "EXPENSES", "CUSTO": "EXPENSES", "INVESTIMENTO": "EXPENSES",
    "CONTA": "EXPENSES", "BOLETO": "EXPENSES", "ALUGUEL": "EXPENSES", "PARCELA": "EXPENSES",
    "MENSALIDADE": "EXPENSES", "TAXA": "EXPENSES", "SERVIcO": "EXPENSES",
    "DESCONTOS": "EXPENSES", "DÉBITO": "EXPENSES",
    # TRANSFER
    "TRANSFER": "TRANSFER", "TRANSFERS": "TRANSFER", "TRANSFERÊNCIA": "TRANSFER",
    "MANDEI": "TRANSFER", "ENVIEI": "TRANSFER", "DEI": "TRANSFER", "REMESSA": "TRANSFER",
    "DEPÓSITO PARA": "TRANSFER", "PIX": "TRANSFER", "TED": "TRANSFER", "DOC": "TRANSFER",
    "PASSEI": "TRANSFER", "MOVI": "TRANSFER", "ENVIO": "TRANSFER", "TRANSAcÃO": "TRANSFER",
    "SAQUE": "TRANSFER", "APORTE": "TRANSFER", "REALOCAR": "TRANSFER",
    "DISTRIBUI": "TRANSFER", "CREDITEI": "TRANSFER",
}

TYPE_LABELS = {
    "INCOME": "Receita",
    "EXPENSES": "Despesa",
    "TRANSFER": "Transferência",
}


# ─── Helpers ────────────────────────────────────────────────────────────────

def _resolve_type_id(cur, type_id: Optional[int], type_name: Optional[str]) -> Optional[int]:
    if type_name:
        t = type_name.strip().upper()
        t = TYPE_ALIASES.get(t, t)
        cur.execute("SELECT id FROM transaction_types WHERE UPPER(type)=%s LIMIT 1;", (t,))
        row = cur.fetchone()
        return row[0] if row else None
    if type_id:
        return int(type_id)
    return None


def _resolve_category_id(cur, category_id: Optional[int], category_name: Optional[str]) -> int:
    if category_name:
        cur.execute("SELECT id FROM categories WHERE LOWER(name)=LOWER(%s) LIMIT 1;", (category_name,))
        row = cur.fetchone()
        return row[0] if row else 12
    if category_id:
        return int(category_id)
    return 12


# ─── Tool: add_transaction ──────────────────────────────────────────────────

@tool("add_transaction", args_schema=AddTransactionArgs)
def add_transaction(
    amount: float,
    source_text: str,
    occurred_at: Optional[str] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> dict:
    """Insere uma transacão financeira no banco de dados Postgres."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        resolved_type_id = _resolve_type_id(cur, type_id, type_name)
        if not resolved_type_id:
            return {"status": "error", "message": "Tipo inválido (use type_id ou type_name: INCOME/EXPENSES/TRANSFER)."}

        resolved_category_id = _resolve_category_id(cur, category_id, category_name)

        payment_method = payment_method.strip().lower() if payment_method else None

        if occurred_at:
            cur.execute(
                """
                INSERT INTO transactions
                    (amount, type, category_id, description, payment_method, occurred_at, source_text)
                VALUES (%s, %s, %s, %s, %s, %s::timestamptz, %s)
                RETURNING id, occurred_at;
                """,
                (amount, resolved_type_id, resolved_category_id, description, payment_method, occurred_at, source_text),
            )
        else:
            cur.execute(
                """
                INSERT INTO transactions
                    (amount, type, category_id, description, payment_method, occurred_at, source_text)
                VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                RETURNING id, occurred_at;
                """,
                (amount, resolved_type_id, resolved_category_id, description, payment_method, source_text),
            )

        new_id, occurred = cur.fetchone()
        conn.commit()
        return {"status": "ok", "id": new_id, "occurred_at": str(occurred)}

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# ─── Tool: query_transactions ───────────────────────────────────────────────

@tool("query_transactions", args_schema=QueryTransactionsArgs)
def query_transactions(
    search_text: Optional[str] = None,
    type_name: Optional[str] = None,
    category_name: Optional[str] = None,
    date_from_local: Optional[str] = None,
    date_to_local: Optional[str] = None,
) -> dict:
    """
    Query transactions with optional filters:
    - search text (source_text/description)
    - type (income/expenses)
    - category
    - date range (America/Sao_Paulo timezone)

    If no filters → returns most recent transactions.
    If date range is given → results ordered ASC (chronological).
    If no date range → results ordered DESC (latest first).
    If more than 100 records → asks user to refine with date range.
    Always returns 'id' for later updates.
    """
    conn = get_conn()   # connect to database
    cur = conn.cursor() # create cursor to run SQL

    try:
        # Resolve type and category IDs if names are provided
        resolved_type_id = _resolve_type_id(cur, None, type_name) if type_name else None
        resolved_category_id = _resolve_category_id(cur, None, category_name) if category_name else None

        filters = ["1=1"]  # base condition (always true) avoid where (and) error
        params = []        # parameters for SQL query

        # Add filters depending on user input
        if search_text:
            filters.append("(t.source_text ILIKE %s OR t.description ILIKE %s)")
            params += [f"%{search_text}%", f"%{search_text}%"]

        if resolved_type_id:
            filters.append("t.type = %s")
            params.append(resolved_type_id)

        if resolved_category_id:
            filters.append("t.category_id = %s")
            params.append(resolved_category_id)

        if date_from_local:
            filters.append("(t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date >= %s::date")
            params.append(date_from_local)

        if date_to_local:
            filters.append("(t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date <= %s::date")
            params.append(date_to_local)

        # Build WHERE clause, for each filter add "and" between them
        where = " AND ".join(filters)
        # Decide order: ASC if date range, else DESC
        order = "ASC" if (date_from_local or date_to_local) else "DESC"

        # Count total records
        cur.execute(f"SELECT COUNT(*) FROM transactions t WHERE {where};", params)
        total = cur.fetchone()[0]

        # If too many results, ask user for date range
        if total > 100:
            return {
                "status": "too_many_results",
                "total": total,
                "message": (
                    f"Found {total} transactions. "
                    "Ask user for a date range (e.g., 2025-01-01 to 2025-01-31) to refine search."
                ),
            }

        # Fetch transaction details with joins to get type and category names just if not > 100
        cur.execute(
            f"""
            SELECT
                t.id,
                t.amount,
                tt.type AS type_key,
                c.name AS category_name,
                t.source_text,
                t.description,
                t.payment_method,
                (t.occurred_at AT TIME ZONE 'America/Sao_Paulo') AS occurred_local
            FROM transactions t
            LEFT JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE {where}
            ORDER BY t.occurred_at {order};
            """,
            params,
        )
        rows = cur.fetchall()

        transactions = []
        total_income = 0.0
        total_expenses = 0.0

        # Process each row
        for tid, amount, type_key, cat_name, src_text, desc, payment_method, occurred_local in rows:
            type_label = TYPE_LABELS.get(type_key, type_key)

            # Add to totals depending on type
            if type_key == "INCOME":
                total_income += float(amount)
            elif type_key == "EXPENSES":
                total_expenses += float(amount)

            # Build transaction dictionary
            transactions.append({
                "id": tid,
                "valor": float(amount),
                "tipo": type_label,
                "categoria": cat_name or "outros",
                "resumo": src_text or desc or "",
                "metodo_pagamento": payment_method or "não informado",
                "data": str(occurred_local)[:10] if occurred_local else None,
            })

        # Return final result
        return {
            "status": "ok",
            "total_registros": total,
            "transacoes": transactions,
            "total_receitas": round(total_income, 2),
            "total_despesas": round(total_expenses, 2),
            "saldo_periodo": round(total_income - total_expenses, 2),
        }

    except Exception as e:
        # Handle errors
        return {"status": "error", "message": str(e)}
    finally:
        # Always close cursor and connection
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# ─── Tool: total_balance ────────────────────────────────────────────────────

@tool("total_balance")
def total_balance() -> dict:
    """Retorna o saldo total (INCOME - EXPENSES) em todo o histórico (ignora TRANSFER)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN tt.type = 'INCOME'   THEN t.amount ELSE 0 END), 0) AS total_income,
                COALESCE(SUM(CASE WHEN tt.type = 'EXPENSES' THEN t.amount ELSE 0 END), 0) AS total_expenses
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            WHERE tt.type IN ('INCOME', 'EXPENSES');
            """
        )
        total_income, total_expenses = cur.fetchone()
        return {
            "status": "ok",
            "total_receitas": round(float(total_income), 2),
            "total_despesas": round(float(total_expenses), 2),
            "saldo_total": round(float(total_income) - float(total_expenses), 2),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# ─── Tool: daily_balance ────────────────────────────────────────────────────

@tool("daily_balance", args_schema=DailyBalanceArgs)
def daily_balance(date_local: str) -> dict:
    """Retorna o saldo (INCOME - EXPENSES) do dia local informado (YYYY-MM-DD) em America/Sao_Paulo. Ignora TRANSFER (type=3)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN tt.type = 'INCOME'   THEN t.amount ELSE 0 END), 0) AS total_income,
                COALESCE(SUM(CASE WHEN tt.type = 'EXPENSES' THEN t.amount ELSE 0 END), 0) AS total_expenses
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            WHERE tt.type IN ('INCOME', 'EXPENSES')
              AND (t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date = %s::date;
            """,
            (date_local,),
        )
        total_income, total_expenses = cur.fetchone()
        return {
            "status": "ok",
            "data": date_local,
            "total_receitas": round(float(total_income), 2),
            "total_despesas": round(float(total_expenses), 2),
            "saldo_dia": round(float(total_income) - float(total_expenses), 2),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# ─── Tool: top_transactions ─────────────────────────────────────────────────

@tool("top_transactions", args_schema=TopTransactionsArgs)
def top_transactions(
    type_name: Optional[str] = None,
    category_name: Optional[str] = None,
    date_from_local: Optional[str] = None,
    date_to_local: Optional[str] = None,
    limit: int = 1,
    order: str = "DESC",
) -> dict:
    """Retorna as N transações com maior (ou menor) valor. Ideal para perguntas como
    'qual foi minha maior compra?', 'qual o menor gasto?', 'top 5 despesas do mês?'.
    Retorna também id, categoria, método de pagamento e data.
    Use order=DESC para maior primeiro, order=ASC para menor primeiro.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        resolved_type_id = _resolve_type_id(cur, None, type_name) if type_name else None
        resolved_category_id = _resolve_category_id(cur, None, category_name) if category_name else None

        filters = ["1=1"]
        params = []

        if resolved_type_id:
            filters.append("t.type = %s")
            params.append(resolved_type_id)

        if resolved_category_id:
            filters.append("t.category_id = %s")
            params.append(resolved_category_id)

        if date_from_local:
            filters.append("(t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date >= %s::date")
            params.append(date_from_local)

        if date_to_local:
            filters.append("(t.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date <= %s::date")
            params.append(date_to_local)

        order_clause = "DESC" if order.upper() == "DESC" else "ASC"
        params.append(limit)

        where = " AND ".join(filters)
        cur.execute(
            f"""
            SELECT
                t.id,
                t.amount,
                tt.type AS type_key,
                c.name AS category_name,
                t.source_text,
                t.description,
                t.payment_method,
                (t.occurred_at AT TIME ZONE 'America/Sao_Paulo') AS occurred_local
            FROM transactions t
            LEFT JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE {where}
            ORDER BY t.amount {order_clause}
            LIMIT %s;
            """,
            params,
        )
        rows = cur.fetchall()

        result = []
        for tid, amount, type_key, cat_name, src_text, desc, payment_method, occurred_local in rows:
            result.append({
                "id": tid,
                "valor": float(amount),
                "tipo": TYPE_LABELS.get(type_key, type_key),
                "categoria": cat_name or "outros",
                "resumo": src_text or desc or "",
                "metodo_pagamento": payment_method or "não informado",
                "data": str(occurred_local)[:10] if occurred_local else None,
            })

        return {"status": "ok", "total_retornado": len(result), "transacoes": result}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# ─── Tool: update_transaction ───────────────────────────────────────────────

@tool("update_transaction", args_schema=UpdateTransactionArgs)
def update_transaction(
    transaction_id: int,
    amount: Optional[float] = None,
    type_name: Optional[str] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
    occurred_at: Optional[str] = None,
    source_text: Optional[str] = None,
) -> dict:
    """Atualiza campos de uma transação existente pelo seu ID.
    Só atualiza os campos informados — os demais permanecem inalterados.
    Ideal para corrigir método de pagamento, categoria, valor ou descrição
    de uma transação já registrada.
    Exemplo: usuário disse 'pix' após perguntar sobre uma transação →
    use o id retornado pela consulta anterior e passe payment_method='pix'.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM transactions WHERE id = %s;", (transaction_id,))
        if not cur.fetchone():
            return {"status": "error", "message": f"Transação com id={transaction_id} não encontrada."}

        fields = []
        params = []

        if amount is not None:
            fields.append("amount = %s")
            params.append(amount)

        if type_name is not None:
            resolved_type_id = _resolve_type_id(cur, None, type_name)
            if not resolved_type_id:
                return {"status": "error", "message": f"Tipo inválido: '{type_name}'. Use INCOME, EXPENSES ou TRANSFER."}
            fields.append("type = %s")
            params.append(resolved_type_id)

        if category_name is not None:
            resolved_category_id = _resolve_category_id(cur, None, category_name)
            fields.append("category_id = %s")
            params.append(resolved_category_id)

        if description is not None:
            fields.append("description = %s")
            params.append(description)

        if payment_method is not None:
            fields.append("payment_method = %s")
            params.append(payment_method.strip().lower())

        if occurred_at is not None:
            fields.append("occurred_at = %s::timestamptz")
            params.append(occurred_at)

        if source_text is not None:
            fields.append("source_text = %s")
            params.append(source_text)

        if not fields:
            return {"status": "error", "message": "Nenhum campo informado para atualizar."}

        params.append(transaction_id)
        cur.execute(
            f"""
            UPDATE transactions
            SET {', '.join(fields)}
            WHERE id = %s
            RETURNING id, amount, payment_method,
                      (occurred_at AT TIME ZONE 'America/Sao_Paulo') AS occurred_local;
            """,
            params,
        )
        row = cur.fetchone()
        conn.commit()

        return {
            "status": "ok",
            "message": "Transação atualizada com sucesso.",
            "id": row[0],
            "valor": float(row[1]),
            "metodo_pagamento": row[2] or "não informado",
            "data": str(row[3])[:10] if row[3] else None,
            "campos_atualizados": [f.split(" =")[0] for f in fields],
        }

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# Exporta a lista de tools
TOOLS = [add_transaction, query_transactions, total_balance, daily_balance, top_transactions, update_transaction]