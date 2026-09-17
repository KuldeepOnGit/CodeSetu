
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal, Optional
import mysql.connector
import os
import hashlib
import secrets


# ==========================================
# APP
# ==========================================

app = FastAPI(
    title="Farmer Procurement API"
)


# ==========================================
# DATABASE CONFIG
# ==========================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "farmer_procurement")


if not DB_PASSWORD:
    raise RuntimeError(
        "DB_PASSWORD environment variable is missing."
    )


def get_db():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


# ==========================================
# STARTUP DATABASE INITIALIZATION
# ==========================================

def initialize_tables():

    connection = get_db()
    cursor = connection.cursor()

    try:

        # ======================================
        # FARMERS
        # ======================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS farmers (
                id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) UNIQUE NOT NULL,
                village VARCHAR(100)
            )
        """)


        # ======================================
        # USERS
        # ======================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                farmer_id INT,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                password_salt VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (farmer_id)
                    REFERENCES farmers(id)
                    ON DELETE SET NULL
            )
        """)


        # ======================================
        # PROCUREMENT
        # ======================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS procurements (
                id INT AUTO_INCREMENT PRIMARY KEY,
                farmer_id INT NOT NULL,
                crop VARCHAR(50) NOT NULL,
                quantity DECIMAL(10,2) NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # ======================================
        # TOKENS
        # ======================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token INT AUTO_INCREMENT PRIMARY KEY,
                farmer_id INT NOT NULL,
                center_id INT NOT NULL,
                crop VARCHAR(50),
                quantity DECIMAL(10,2),
                preferred_date DATE,
                queue_position INT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # ======================================
        # NOTIFICATIONS
        # ======================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                farmer_id INT NOT NULL,
                message TEXT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Sent',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # ======================================
        # DEFAULT FARMERS
        # ======================================

        cursor.execute("""
            INSERT INTO farmers
                (id, name, phone, village)
            VALUES
                (101, 'Farmer One', '9876543210', 'Village A')
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                phone = VALUES(phone),
                village = VALUES(village)
        """)


        cursor.execute("""
            INSERT INTO farmers
                (id, name, phone, village)
            VALUES
                (102, 'Farmer Two', '9876543211', 'Village B')
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                phone = VALUES(phone),
                village = VALUES(village)
        """)


        connection.commit()

    finally:

        cursor.close()
        connection.close()


initialize_tables()

print("MySQL Database Connected Successfully!")


# ==========================================
# CORS
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# PASSWORD HELPERS
# ==========================================

def hash_password(password, salt=None):

    if salt is None:
        salt = secrets.token_hex(16)

    hashed = hashlib.sha256(
        (salt + password).encode("utf-8")
    ).hexdigest()

    return hashed, salt


def verify_password(password, stored_hash, stored_salt):

    hashed, _ = hash_password(
        password,
        stored_salt
    )

    return hashed == stored_hash


# ==========================================
# HOME
# ==========================================

@app.get("/")
def home():

    return {
        "message": "Farmer Procurement Backend is working"
    }


# ==========================================
# AUTHENTICATION
# ==========================================

class User(BaseModel):
    name: str
    phone: str
    password: str


@app.post("/auth/register")
def register(user: User):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        # ==================================
        # CHECK EXISTING USER
        # ==================================

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE phone = %s
            """,
            (user.phone,)
        )

        existing_user = cursor.fetchone()


        if existing_user:

            return {
                "message": "User already registered",
                "phone": user.phone
            }


        # ==================================
        # FIND EXISTING FARMER
        # ==================================

        cursor.execute(
            """
            SELECT id
            FROM farmers
            WHERE phone = %s
            """,
            (user.phone,)
        )

        farmer = cursor.fetchone()


        farmer_id = None


        if farmer:

            farmer_id = farmer["id"]

        else:

            # ==================================
            # CREATE NEW FARMER ID
            # ==================================

            cursor.execute(
                """
                SELECT COALESCE(MAX(id), 100) + 1 AS next_id
                FROM farmers
                """
            )

            next_id_row = cursor.fetchone()
            farmer_id = next_id_row["next_id"]


            cursor.execute(
                """
                INSERT INTO farmers
                    (id, name, phone, village)
                VALUES
                    (%s, %s, %s, %s)
                """,
                (
                    farmer_id,
                    user.name,
                    user.phone,
                    "Village A"
                )
            )


        # ==================================
        # HASH PASSWORD
        # ==================================

        password_hash, password_salt = hash_password(
            user.password
        )


        # ==================================
        # SAVE USER
        # ==================================

        cursor.execute(
            """
            INSERT INTO users
                (
                    farmer_id,
                    name,
                    phone,
                    password_hash,
                    password_salt
                )
            VALUES
                (%s, %s, %s, %s, %s)
            """,
            (
                farmer_id,
                user.name,
                user.phone,
                password_hash,
                password_salt
            )
        )


        connection.commit()


        return {
            "message": "Registration successful",
            "name": user.name,
            "phone": user.phone,
            "farmer_id": farmer_id
        }

    finally:

        cursor.close()
        connection.close()


# ==========================================
# LOGIN
# ==========================================

class Login(BaseModel):
    phone: str
    password: str


@app.post("/auth/login")
def login(data: Login):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                farmer_id,
                name,
                phone,
                password_hash,
                password_salt
            FROM users
            WHERE phone = %s
            """,
            (data.phone,)
        )

        user = cursor.fetchone()


        if user:

            valid = verify_password(
                data.password,
                user["password_hash"],
                user["password_salt"]
            )

            if valid:

                return {
                    "message": "Login successful",
                    "name": user["name"],
                    "phone": user["phone"],
                    "farmer_id": user["farmer_id"]
                }


        return {
            "message": "Invalid phone number or password"
        }

    finally:

        cursor.close()
        connection.close()


# ==========================================
# FARMER API
# ==========================================

@app.get("/farmers")
def get_farmers():

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                name,
                phone,
                village
            FROM farmers
            ORDER BY id
            """
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


@app.get("/farmers/{farmer_id}")
def get_farmer(farmer_id: int):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                name,
                phone,
                village
            FROM farmers
            WHERE id = %s
            """,
            (farmer_id,)
        )

        farmer = cursor.fetchone()


        if farmer:
            return farmer


        return {
            "message": "Farmer not found"
        }

    finally:

        cursor.close()
        connection.close()


# ==========================================
# MANDI / CENTERS
# ==========================================

mandis = [

    {
        "id": 1,
        "name": "Center A",
        "location": "Village A",
        "crop": "Wheat"
    },

    {
        "id": 2,
        "name": "Center B",
        "location": "Village B",
        "crop": "Rice"
    },

    {
        "id": 3,
        "name": "Center C",
        "location": "Village C",
        "crop": "Wheat"
    }

]


@app.get("/mandis")
def get_mandis():

    return mandis


@app.get("/mandis/{mandi_id}")
def get_mandi(mandi_id: int):

    for mandi in mandis:

        if mandi["id"] == mandi_id:
            return mandi


    return {
        "message": "Mandi not found"
    }


@app.get("/centers")
def get_centers():

    return mandis


# ==========================================
# SCHEDULE API
# ==========================================

schedules = [

    {
        "center_id": 1,
        "center_name": "Center A",
        "crop": "Wheat",
        "date": "2026-09-05",
        "time": "10:00 AM"
    },

    {
        "center_id": 2,
        "center_name": "Center B",
        "crop": "Rice",
        "date": "2026-09-06",
        "time": "11:00 AM"
    },

    {
        "center_id": 3,
        "center_name": "Center C",
        "crop": "Wheat",
        "date": "2026-09-07",
        "time": "09:00 AM"
    }

]


@app.get("/schedules")
def get_schedules():

    return schedules


@app.get("/schedules/{center_id}")
def get_schedule(center_id: int):

    for schedule in schedules:

        if schedule["center_id"] == center_id:
            return schedule


    return {
        "message": "Schedule not found"
    }


# ==========================================
# PROCUREMENT API
# ==========================================

class Procurement(BaseModel):

    farmer_id: int
    crop: str
    quantity: float


@app.post("/procurements")
def create_procurement(data: Procurement):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            INSERT INTO procurements
                (
                    farmer_id,
                    crop,
                    quantity,
                    status
                )
            VALUES
                (%s, %s, %s, 'Pending')
            """,
            (
                data.farmer_id,
                data.crop,
                data.quantity
            )
        )


        connection.commit()

        request_id = cursor.lastrowid


        cursor.execute(
            """
            SELECT
                id,
                farmer_id,
                crop,
                quantity,
                status,
                created_at
            FROM procurements
            WHERE id = %s
            """,
            (request_id,)
        )


        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()


@app.get("/procurements")
def get_procurements():

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                farmer_id,
                crop,
                quantity,
                status,
                created_at
            FROM procurements
            ORDER BY id DESC
            """
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


@app.get("/procurements/{request_id}")
def get_procurement(request_id: int):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                farmer_id,
                crop,
                quantity,
                status,
                created_at
            FROM procurements
            WHERE id = %s
            """,
            (request_id,)
        )

        request = cursor.fetchone()


        if request:
            return request


        return {
            "message": "Procurement request not found"
        }

    finally:

        cursor.close()
        connection.close()


@app.get("/farmers/{farmer_id}/procurements")
def get_farmer_procurements(farmer_id: int):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                farmer_id,
                crop,
                quantity,
                status,
                created_at
            FROM procurements
            WHERE farmer_id = %s
            ORDER BY id DESC
            """,
            (farmer_id,)
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


class StatusUpdate(BaseModel):

    status: Literal[
        "Pending",
        "Scheduled",
        "Completed"
    ]


@app.put("/procurements/{request_id}")
def update_procurement_status(
    request_id: int,
    data: StatusUpdate
):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            UPDATE procurements
            SET status = %s
            WHERE id = %s
            """,
            (
                data.status,
                request_id
            )
        )


        connection.commit()


        if cursor.rowcount == 0:

            return {
                "message":
                    "Procurement request not found"
            }


        cursor.execute(
            """
            SELECT
                id,
                farmer_id,
                crop,
                quantity,
                status,
                created_at
            FROM procurements
            WHERE id = %s
            """,
            (request_id,)
        )


        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()


# ==========================================
# TOKEN / QUEUE API
# ==========================================

class TokenRequest(BaseModel):

    farmer_id: int
    center_id: int
    crop: Optional[str] = None
    quantity: Optional[float] = None
    preferred_date: Optional[str] = None


@app.post("/tokens")
def create_token(data: TokenRequest):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        # ==================================
        # CENTER QUEUE COUNT
        # ==================================

        cursor.execute(
            """
            SELECT COUNT(*) AS queue_count
            FROM tokens
            WHERE
                center_id = %s
                AND status IN ('Waiting', 'Scheduled')
            """,
            (data.center_id,)
        )


        result = cursor.fetchone()


        queue_position = (
            int(result["queue_count"]) + 1
        )


        # ==================================
        # CREATE TOKEN
        # ==================================

        cursor.execute(
            """
            INSERT INTO tokens
                (
                    farmer_id,
                    center_id,
                    crop,
                    quantity,
                    preferred_date,
                    queue_position,
                    status
                )
            VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'Waiting'
                )
            """,
            (
                data.farmer_id,
                data.center_id,
                data.crop,
                data.quantity,
                data.preferred_date,
                queue_position
            )
        )


        connection.commit()

        token_number = cursor.lastrowid


        cursor.execute(
            """
            SELECT
                token,
                farmer_id,
                center_id,
                crop,
                quantity,
                preferred_date,
                queue_position,
                status,
                created_at
            FROM tokens
            WHERE token = %s
            """,
            (token_number,)
        )


        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()


@app.get("/tokens")
def get_tokens():

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                token,
                farmer_id,
                center_id,
                crop,
                quantity,
                preferred_date,
                queue_position,
                status,
                created_at
            FROM tokens
            ORDER BY token
            """
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


@app.get("/tokens/{token_number}")
def get_token(token_number: int):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                token,
                farmer_id,
                center_id,
                crop,
                quantity,
                preferred_date,
                queue_position,
                status,
                created_at
            FROM tokens
            WHERE token = %s
            """,
            (token_number,)
        )

        token = cursor.fetchone()


        if token:
            return token


        return {
            "message": "Token not found"
        }

    finally:

        cursor.close()
        connection.close()


@app.get("/queue/{center_id}")
def get_queue(center_id: int):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                token,
                farmer_id,
                center_id,
                crop,
                quantity,
                preferred_date,
                queue_position,
                status,
                created_at
            FROM tokens
            WHERE
                center_id = %s
                AND status IN ('Waiting', 'Scheduled')
            ORDER BY queue_position
            """,
            (center_id,)
        )


        center_queue = cursor.fetchall()


        return {
            "center_id": center_id,
            "queue": center_queue
        }

    finally:

        cursor.close()
        connection.close()


# ==========================================
# AI PREDICTION API
# ==========================================

class PredictionRequest(BaseModel):

    center_id: int
    queue_size: int


@app.post("/ai/predict-waiting-time")
def predict_waiting_time(
    data: PredictionRequest
):

    # Prototype/demo prediction.
    # This can later be replaced by a
    # trained ML model.

    estimated_minutes = (
        data.queue_size * 10
    )


    return {
        "center_id":
            data.center_id,

        "queue_size":
            data.queue_size,

        "estimated_waiting_time_minutes":
            estimated_minutes,

        "message":
            "Demo prediction - ML model can be connected later"
    }


# ==========================================
# NOTIFICATION API
# ==========================================

class Notification(BaseModel):

    farmer_id: int
    message: str


@app.post("/notifications")
def create_notification(
    data: Notification
):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            INSERT INTO notifications
                (
                    farmer_id,
                    message,
                    status
                )
            VALUES
                (
                    %s,
                    %s,
                    'Sent'
                )
            """,
            (
                data.farmer_id,
                data.message
            )
        )


        connection.commit()

        notification_id = cursor.lastrowid


        cursor.execute(
            """
            SELECT
                id,
                farmer_id,
                message,
                status,
                created_at
            FROM notifications
            WHERE id = %s
            """,
            (notification_id,)
        )


        return cursor.fetchone()

    finally:

        cursor.close()
        connection.close()


@app.get("/notifications/{farmer_id}")
def get_notifications(farmer_id: int):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                farmer_id,
                message,
                status,
                created_at
            FROM notifications
            WHERE farmer_id = %s
            ORDER BY id DESC
            """,
            (farmer_id,)
        )


        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


# ==========================================
# WAREHOUSE API
# ==========================================

@app.get("/warehouses")
def get_warehouses():

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                warehouse_id,
                warehouse_name,
                location,
                capacity,
                available_space,
                status
            FROM warehouses
            """
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        connection.close()


@app.get("/warehouses/{warehouse_id}")
def get_warehouse(warehouse_id: str):

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                warehouse_id,
                warehouse_name,
                location,
                capacity,
                available_space,
                status
            FROM warehouses
            WHERE warehouse_id = %s
            """,
            (warehouse_id,)
        )

        warehouse = cursor.fetchone()


        if warehouse:
            return warehouse


        return {
            "message": "Warehouse not found"
        }

    finally:

        cursor.close()
        connection.close()


# ==========================================
# MAPS API
# ==========================================

@app.get("/maps/{center_id}")
def get_map(center_id: int):

    for mandi in mandis:

        if mandi["id"] == center_id:

            return {
                "center_id":
                    center_id,

                "center_name":
                    mandi["name"],

                "location":
                    mandi["location"],

                "latitude":
                    28.6139,

                "longitude":
                    77.2090,

                "message":
                    "Map location available"
            }


    return {
        "message": "Center not found"
    }

