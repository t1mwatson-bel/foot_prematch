def get_pending_signals():
    """Возвращает сигналы, которые еще не проверены."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM signals WHERE status = 'PENDING'")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_result(match_slug, goals_total):
    """Обновляет результат матча. Если голов > 2.5, то WIN."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    status = 'WIN' if goals_total > 2.5 else 'LOSE'
    
    # Берем коэффициент для расчета профита
    c.execute("SELECT odds FROM signals WHERE match_slug = ? AND status = 'PENDING'", (match_slug,))
    row = c.fetchone()
    
    if row:
        odds = row[0]
        profit = (odds - 1.0) if status == 'WIN' else -1.0 # Ставка 1 у.е.
        
        c.execute('''
            UPDATE signals 
            SET status = ?, profit = ?
            WHERE match_slug = ? AND status = 'PENDING'
        ''', (status, profit, match_slug))
        conn.commit()
        print(f"✅ БД обновлена: {match_slug} -> {status} (Профит: {profit})", flush=True)
        
    conn.close()
