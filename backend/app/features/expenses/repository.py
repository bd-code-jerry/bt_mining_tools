from __future__ import annotations

import sqlite3

from ...core.database import utc_now_iso


def sync_participants(conn) -> None:
    conn.execute(
        """INSERT INTO expense_participants(user_id,username,role,created_at)
           SELECT u.id,u.username,u.role,? FROM users u
           WHERE NOT EXISTS (SELECT 1 FROM expense_participants p WHERE p.user_id=u.id)
           ORDER BY u.id""", (utc_now_iso(),))


def list_participants(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT p.id,p.user_id,COALESCE(u.username,p.username) AS username,
                  COALESCE(u.role,p.role) AS role,COALESCE(u.status,'deleted') AS status
           FROM expense_participants p LEFT JOIN users u ON u.id=p.user_id ORDER BY p.id""")
    return [{**dict(row),'eligible':row['status']=='active' and row['user_id'] is not None} for row in rows]


def list_categories(conn) -> list[dict]:
    return [dict(row) for row in conn.execute('SELECT id,name,parent_id,archived FROM expense_categories ORDER BY id')]


def historical_category_paths(conn) -> dict[int,list[str]]:
    result = {}
    for row in conn.execute('SELECT DISTINCT category_id,category_path FROM expense_costs ORDER BY category_path'):
        result.setdefault(row['category_id'],[]).append(row['category_path'])
    return result


def exact_sum(conn,query: str,params=()) -> int:
    """Preserve integer cents even if many valid records exceed SQLite's aggregate range."""
    try:
        return int(conn.execute(f'SELECT COALESCE(SUM(cents),0) FROM ({query})',params).fetchone()[0])
    except sqlite3.OperationalError as exc:
        if 'integer overflow' not in str(exc):
            raise
        return sum(row[0] for row in conn.execute(query,params))


def get_record(conn,kind: str,record_id: int) -> dict | None:
    row = conn.execute(f'SELECT * FROM expense_{kind} WHERE id=?',(record_id,)).fetchone()
    return dict(row) if row else None


def retry_record(conn,kind: str,actor_id: int,request_id: str) -> dict | None:
    row = conn.execute(f'SELECT * FROM expense_{kind} WHERE request_actor_id=? AND request_id=?',
                       (actor_id,request_id)).fetchone()
    return dict(row) if row else None


def insert_record(conn,kind: str,values: dict) -> int:
    columns = ','.join(values)
    placeholders = ','.join('?' for _ in values)
    cursor = conn.execute(f'INSERT INTO expense_{kind} ({columns}) VALUES ({placeholders})',tuple(values.values()))
    return int(cursor.lastrowid)


def update_record(conn,kind: str,record_id: int,values: dict) -> None:
    columns = ','.join(f'{column}=?' for column in values)
    conn.execute(f'UPDATE expense_{kind} SET {columns} WHERE id=?',(*values.values(),record_id))


def allocations(conn,cost_id: int) -> list[dict]:
    return [dict(row) for row in conn.execute(
        """SELECT a.participant_id,COALESCE(u.username,p.username) AS username,a.share_cents
           FROM expense_allocations a JOIN expense_participants p ON p.id=a.participant_id
           LEFT JOIN users u ON u.id=p.user_id WHERE a.expense_id=? ORDER BY a.participant_id""", (cost_id,))]


def replace_allocations(conn,cost_id: int,shares: list[tuple[int,int]]) -> None:
    conn.execute('DELETE FROM expense_allocations WHERE expense_id=?',(cost_id,))
    conn.executemany('INSERT INTO expense_allocations(expense_id,participant_id,share_cents) VALUES (?,?,?)',
                     [(cost_id,p,share) for p,share in shares])


def summary(conn) -> dict:
    origin = exact_sum(conn,"SELECT amount_cents AS cents FROM expense_transfers WHERE kind='origin'")
    received = exact_sum(conn,"SELECT amount_cents AS cents FROM expense_transfers WHERE kind='received'")
    spent = exact_sum(conn,'SELECT amount_cents AS cents FROM expense_costs')
    return {'origin_cents':origin,'received_cents':received,'spent_cents':spent,'remaining_cents':received-spent}


def cost_rows(conn,where: str,params: list,*,matching_ids: list[int] | None,page: dict) -> list[dict]:
    if matching_ids is None:
        allocated = 'c.amount_cents'
        leading = []
    else:
        placeholders = ','.join('?' for _ in matching_ids) or 'NULL'
        allocated = f'(SELECT SUM(a.share_cents) FROM expense_allocations a WHERE a.expense_id=c.id AND a.participant_id IN ({placeholders}))'
        leading = matching_ids
    rows = conn.execute(
        f'''SELECT c.*, {allocated} AS allocated_cents FROM expense_costs c {where}
            ORDER BY c.expense_date DESC,c.id DESC LIMIT ? OFFSET ?''',
        [*leading,*params,page['page_size'],(page['page']-1)*page['page_size']])
    return [dict(row) for row in rows]


def cost_count_total(conn,where: str,params: list,matching_ids: list[int] | None) -> tuple[int,int]:
    count = conn.execute(f'SELECT COUNT(*) FROM expense_costs c {where}',params).fetchone()[0]
    if matching_ids is None:
        total = exact_sum(conn,f'SELECT c.amount_cents AS cents FROM expense_costs c {where}',params)
    else:
        placeholders = ','.join('?' for _ in matching_ids) or 'NULL'
        total = exact_sum(conn,f'''SELECT a.share_cents AS cents FROM expense_allocations a
            WHERE a.participant_id IN ({placeholders}) AND a.expense_id IN (SELECT c.id FROM expense_costs c {where})''',
            [*matching_ids,*params])
    return int(count),int(total)


def participant_totals(conn,where: str,params: list) -> dict[int,int]:
    condition = f'WHERE a.expense_id IN (SELECT c.id FROM expense_costs c {where})'
    try:
        return {row['participant_id']:row['total'] for row in conn.execute(
            f'SELECT a.participant_id,SUM(a.share_cents) AS total FROM expense_allocations a {condition} GROUP BY a.participant_id',params)}
    except sqlite3.OperationalError as exc:
        if 'integer overflow' not in str(exc):
            raise
        totals = {}
        for row in conn.execute(f'SELECT a.participant_id,a.share_cents FROM expense_allocations a {condition}',params):
            totals[row['participant_id']] = totals.get(row['participant_id'],0)+row['share_cents']
        return totals


def historical_participant_ids(conn) -> set[int]:
    return {row[0] for row in conn.execute('SELECT DISTINCT participant_id FROM expense_allocations')}


def transfer_page(conn,kind: str | None,page: int,page_size: int,make_pagination) -> tuple[list[dict],dict]:
    where = 'WHERE kind=?' if kind else ''
    params = [kind] if kind else []
    total = conn.execute(f'SELECT COUNT(*) FROM expense_transfers {where}',params).fetchone()[0]
    info = make_pagination(total,page,page_size)
    rows = conn.execute(f'''SELECT * FROM expense_transfers {where}
        ORDER BY transfer_date DESC,id DESC LIMIT ? OFFSET ?''',
        [*params,info['page_size'],(info['page']-1)*info['page_size']])
    return [dict(row) for row in rows],info
