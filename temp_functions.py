from datetime import datetime
from sqlalchemy import text

def get_user_balance(db, user_id):
    result = db.execute(
        text("SELECT balance, last_allocation_date FROM user_profiles WHERE id = :user_id"),
        {"user_id": user_id}
    ).fetchone()
    
    if not result:
        return 0.0, None
        
    return float(result[0]), result[1]

def check_and_allocate_daily_amount(db, user_id):
    balance, last_allocation = get_user_balance(db, user_id)
    today = datetime.now().date()
    
    # Se nunca alocou ou última alocação não foi hoje
    if not last_allocation or last_allocation < today:
        # Obter todos os gigantes ativos ordenados por eficiência de pagamento
        giants = db.execute(
            text("""
                SELECT id, weekly_goal, payoff_efficiency 
                FROM giants 
                WHERE user_id = :user_id 
                AND status = 'Ativo'
                ORDER BY payoff_efficiency DESC
            """),
            {"user_id": user_id}
        ).fetchall()
        
        # Calcular alocação diária para cada gigante
        for giant in giants:
            daily_goal = float(giant.weekly_goal) / 7  # Converter meta semanal para diária
            
            # Se tiver saldo suficiente, aloca o valor
            if balance >= daily_goal:
                db.execute(
                    text("""
                        INSERT INTO transactions (giant_id, amount, type, date)
                        VALUES (:giant_id, :amount, 'Alocação Automática', :date)
                    """),
                    {
                        "giant_id": giant.id,
                        "amount": daily_goal,
                        "date": today
                    }
                )
                balance -= daily_goal
        
        # Atualizar saldo e data da última alocação
        db.execute(
            text("""
                UPDATE user_profiles 
                SET balance = :balance, last_allocation_date = :date
                WHERE id = :user_id
            """),
            {
                "balance": balance,
                "date": today,
                "user_id": user_id
            }
        )
        db.commit()
