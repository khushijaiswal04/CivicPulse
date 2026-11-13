from database import get_db_connection

try:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT DATABASE(), VERSION()")

    result = cur.fetchone()

    print("Aiven Connection Successful!")
    print("Database:", result[0])
    print("MySQL Version:", result[1])

    cur.close()
    conn.close()

except Exception as e:
    print("Connection Failed:", e)