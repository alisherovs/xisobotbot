# database.py
import aiosqlite
import time

DB_NAME = "autoservice.db"

async def init_db():
    """Baza va jadvallarni yaratish"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Foydalanuvchilar (Xodimlar va Adminlar)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                full_name TEXT,
                status TEXT DEFAULT 'pending', -- pending, approved, admin, fired
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Xizmatlar (Buyurtmalar)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_model TEXT,
                modifications TEXT,
                price INTEGER,
                vin_code TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Kross-jadval (Qaysi xizmatda qaysi xodimlar ishlagan)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS service_workers (
                service_id INTEGER,
                user_id INTEGER,
                FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        await db.commit()

# --- USERS CRUD ---
async def add_user(telegram_id: int, full_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute("INSERT INTO users (telegram_id, full_name) VALUES (?, ?)", (telegram_id, full_name))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            return await cursor.fetchone()

async def update_user_status(telegram_id: int, status: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET status = ? WHERE telegram_id = ?", (status, telegram_id))
        await db.commit()

async def get_active_workers(limit=10, offset=0):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE status = 'approved' LIMIT ? OFFSET ?", (limit, offset)) as cursor:
            return await cursor.fetchall()

async def get_all_active_workers():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE status = 'approved'") as cursor:
            return await cursor.fetchall()

async def count_active_workers():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE status = 'approved'") as cursor:
            return (await cursor.fetchone())[0]

# --- SERVICES CRUD ---
async def add_service(car_model: str, modifications: str, price: int, vin_code: str, worker_ids: list):
    async with aiosqlite.connect(DB_NAME) as db:
        # Tranzaksiya boshlash
        cursor = await db.execute(
            "INSERT INTO services (car_model, modifications, price, vin_code) VALUES (?, ?, ?, ?)",
            (car_model, modifications, price, vin_code)
        )
        service_id = cursor.lastrowid
        
        # Xodimlarni bog'lash
        for w_id in worker_ids:
            await db.execute("INSERT INTO service_workers (service_id, user_id) VALUES (?, ?)", (service_id, w_id))
            
        await db.commit()
        return service_id

# --- STATISTIKA ---
async def get_general_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(id), SUM(price) FROM services") as cursor:
            row = await cursor.fetchone()
            return row[0] or 0, row[1] or 0

async def get_top_workers():
    async with aiosqlite.connect(DB_NAME) as db:
        query = '''
            SELECT u.full_name, COUNT(sw.service_id) as jobs_done
            FROM users u
            JOIN service_workers sw ON u.id = sw.user_id
            WHERE u.status = 'approved'
            GROUP BY u.id
            ORDER BY jobs_done DESC
            LIMIT 5
        '''
        async with db.execute(query) as cursor:
            return await cursor.fetchall()

# --- BACKGROUND CLEANUP ---
async def cleanup_old_records():
    """365 kundan oshgan ma'lumotlarni tozalash"""
    async with aiosqlite.connect(DB_NAME) as db:
        one_year_ago = time.time() - (365 * 24 * 60 * 60)
        # SQLite datetime formatiga moslash yoki timestamp bilan ishlash
        await db.execute("DELETE FROM services WHERE strftime('%s', date) < ?", (str(one_year_ago),))
        await db.commit()
