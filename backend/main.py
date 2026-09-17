from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date, time, datetime, timedelta, timezone
import hashlib
import hmac
import mysql.connector
import os
import re
import secrets
import jwt
from jwt import InvalidTokenError


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="CodeSetu - Smart Procurement Management System",
    description="Backend API for Farmers, Procurement Centers, Tokens, Payments and Warehouses",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE
# =========================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "farmer_procurement")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

PASSWORD_HASH_ITERATIONS = 600_000
SUPPORTED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}

def get_db():
    try:
        if not DB_PASSWORD:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Database configuration missing. "
                    "Set DB_PASSWORD in the environment."
                )
            )

        return mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )


# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
def startup():
    try:
        db = get_db()
        db.close()
        print("MySQL Database Connected Successfully!")
        print("CodeSetu Backend Started Successfully!")
    except Exception as e:
        print("Database connection error:", e)


# =========================================================
# MODELS
# =========================================================

class FarmerLogin(BaseModel):
    mobile_number: str
    password: str = Field(..., min_length=1)


class FarmerRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    mobile_number: str
    password: str = Field(..., min_length=8)
    village: Optional[str] = None
    district: Optional[str] = None


class FarmerCreate(BaseModel):
    farmer_id: str = Field(..., max_length=10)
    name: str
    mobile_number: str
    village: Optional[str] = None
    district: Optional[str] = None


class TokenCreate(BaseModel):
    farmer_id: str
    center_id: str
    crop_name: str
    quantity: float = Field(gt=0)
    booking_date: date
    reporting_time: str


class TokenStatusUpdate(BaseModel):
    status: Literal[
        "Registered",
        "Scheduled",
        "Arrived",
        "Quality Check",
        "Procured",
        "Payment"
    ]


class PaymentCreate(BaseModel):
    token_id: str
    farmer_id: str
    amount: float = Field(gt=0)
    payment_status: Literal[
        "Pending",
        "Processing",
        "Completed",
        "Failed"
    ] = "Pending"
    payment_date: Optional[date] = None


class PaymentStatusUpdate(BaseModel):
    payment_status: Literal[
        "Pending",
        "Processing",
        "Completed",
        "Failed"
    ]


class AIWaitRequest(BaseModel):
    center_id: str
    queue_size: Optional[int] = None


# =========================================================
# AUTHENTICATION
# =========================================================

@app.post("/auth/register", status_code=201)
def register_farmer(data: FarmerRegister):
    name = data.name.strip()
    mobile_number = normalize_mobile_number(data.mobile_number)
    validate_password_strength(data.password)

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Name is required."
        )

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT farmer_id, password_hash
            FROM farmers
            WHERE mobile_number = %s
        """, (mobile_number,))

        existing_farmer = cursor.fetchone()

        if existing_farmer:
            if existing_farmer[1]:
                raise HTTPException(
                    status_code=409,
                    detail="A farmer account with this mobile number already exists."
                )

            raise HTTPException(
                status_code=409,
                detail=(
                    "A farmer record with this mobile number already exists "
                    "without an activated password. No password was assigned."
                )
            )

        farmer_id = generate_farmer_id(db)
        password_hash, password_salt = hash_password(data.password)

        cursor.execute("""
            INSERT INTO farmers (
                farmer_id,
                name,
                mobile_number,
                village,
                district,
                password_hash,
                password_salt
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            farmer_id,
            name,
            mobile_number,
            data.village.strip() if data.village else None,
            data.district.strip() if data.district else None,
            password_hash,
            password_salt
        ))

        db.commit()

        cursor.execute("""
            SELECT
                farmer_id,
                name,
                mobile_number,
                village,
                district
            FROM farmers
            WHERE farmer_id = %s
        """, (farmer_id,))

        farmer = cursor.fetchone()

        return {
            "success": True,
            "message": "Farmer account created successfully.",
            "farmer": farmer_payload(farmer)
        }

    except mysql.connector.IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A farmer with this mobile number or ID already exists."
        )
    finally:
        cursor.close()
        db.close()


@app.post("/auth/login")
def login_farmer(data: FarmerLogin):
    mobile_number = normalize_mobile_number(data.mobile_number)
    ensure_jwt_configuration()

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT
                farmer_id,
                name,
                mobile_number,
                village,
                district,
                password_hash,
                password_salt
            FROM farmers
            WHERE mobile_number = %s
        """, (mobile_number,))

        row = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if (
        not row
        or not row[5]
        or not row[6]
        or not verify_password(data.password, row[5], row[6])
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid mobile number or password."
        )

    farmer = farmer_payload(row)

    return {
        "success": True,
        "message": "Login successful.",
        "farmer": farmer,
        "access_token": create_access_token(row[0]),
        "token_type": "bearer"
    }


@app.get("/auth/me")
def get_authenticated_farmer_profile(
    authorization: Optional[str] = Header(default=None)
):
    return {
        "success": True,
        "farmer": get_authenticated_farmer(authorization)
    }


# =========================================================
# HELPERS
# =========================================================

def rows_to_dict(cursor):
    columns = cursor.column_names
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def normalize_mobile_number(value: str):
    mobile_number = value.strip()

    if not re.fullmatch(r"\d{10}", mobile_number):
        raise HTTPException(
            status_code=400,
            detail="Mobile number must contain exactly 10 digits."
        )

    return mobile_number


def validate_password_strength(password: str):
    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long."
        )

    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one letter and one number."
        )


def hash_password(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS
    ).hex()

    return password_hash, salt


def verify_password(password: str, stored_hash: str, stored_salt: str):
    calculated_hash, _ = hash_password(password, stored_salt)
    return hmac.compare_digest(calculated_hash, stored_hash)


def ensure_jwt_configuration():
    if not JWT_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="JWT configuration missing. Set JWT_SECRET_KEY in the environment."
        )

    if JWT_ALGORITHM not in SUPPORTED_JWT_ALGORITHMS:
        raise HTTPException(
            status_code=500,
            detail="Unsupported JWT algorithm configuration."
        )

    if JWT_EXPIRE_MINUTES <= 0:
        raise HTTPException(
            status_code=500,
            detail="JWT_EXPIRE_MINUTES must be greater than zero."
        )


def create_access_token(farmer_id: str):
    ensure_jwt_configuration()

    now = datetime.now(timezone.utc)
    payload = {
        "sub": farmer_id,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES)
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )


def generate_farmer_id(db):
    cursor = db.cursor()

    cursor.execute("""
        SELECT farmer_id
        FROM farmers
        WHERE farmer_id LIKE 'F%'
        ORDER BY CAST(SUBSTRING(farmer_id, 2) AS UNSIGNED) DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    cursor.close()

    if not row:
        return "F001"

    match = re.fullmatch(r"F(\d+)", row[0])
    next_number = int(match.group(1)) + 1 if match else 1
    return f"F{next_number:03d}"


def farmer_payload(row):
    return {
        "farmer_id": row[0],
        "name": row[1],
        "mobile_number": row[2],
        "village": row[3],
        "district": row[4]
    }


def get_authenticated_farmer(authorization: Optional[str]):
    ensure_jwt_configuration()

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization token is required."
        )

    access_token = authorization[7:].strip()

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Authorization token is required."
        )

    try:
        payload = jwt.decode(
            access_token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authorization token."
        )

    farmer_id = payload.get("sub")

    if not farmer_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization token."
        )

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT
                farmer_id,
                name,
                mobile_number,
                village,
                district
            FROM farmers
            WHERE farmer_id = %s
        """, (farmer_id,))

        row = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    if not row:
        raise HTTPException(
            status_code=401,
            detail="Authenticated farmer was not found."
        )

    return farmer_payload(row)


def parse_reporting_time(value: str):
    """
    Supports:
    10:30
    10:30:00
    10:30 AM
    10:30 PM
    """

    value = value.strip()

    formats = [
        "%H:%M",
        "%H:%M:%S",
        "%I:%M %p",
        "%I:%M:%S %p"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            pass

    raise HTTPException(
        status_code=400,
        detail="Invalid reporting_time. Use 10:30, 10:30:00 or 10:30 AM."
    )


def generate_token_id(db):
    cursor = db.cursor()

    cursor.execute("""
        SELECT token_id
        FROM tokens
        WHERE token_id LIKE 'KSN-%'
        ORDER BY CAST(SUBSTRING(token_id, 5) AS UNSIGNED) DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    cursor.close()

    if not row:
        return "KSN-1001"

    current = row[0]

    match = re.search(r"KSN-(\d+)", current)

    if match:
        number = int(match.group(1)) + 1
    else:
        number = 1001

    return f"KSN-{number}"


def get_center_history_average(db, center_id):
    cursor = db.cursor()

    cursor.execute("""
        SELECT AVG(avg_processing_time)
        FROM center_history
        WHERE center_id = %s
          AND avg_processing_time IS NOT NULL
    """, (center_id,))

    row = cursor.fetchone()
    cursor.close()

    if row and row[0] is not None:
        return float(row[0])

    # Prototype fallback
    return 10.0


def active_statuses():
    return (
        "Registered",
        "Scheduled",
        "Arrived",
        "Quality Check"
    )


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "message": "Farmer Procurement Backend is working",
        "project": "CodeSetu",
        "version": "2.0.0",
        "database": DB_NAME
    }


@app.get("/health")
def health():
    db = get_db()
    db.close()

    return {
        "status": "healthy",
        "database": "connected"
    }


# =========================================================
# FARMERS
# =========================================================

@app.get("/farmers")
def get_farmers():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            farmer_id,
            name,
            mobile_number,
            village,
            district,
            created_at
        FROM farmers
        ORDER BY created_at DESC
    """)

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return data


@app.get("/farmers/{farmer_id}")
def get_farmer(farmer_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            farmer_id,
            name,
            mobile_number,
            village,
            district,
            created_at
        FROM farmers
        WHERE farmer_id = %s
    """, (farmer_id,))

    row = cursor.fetchone()

    cursor.close()
    db.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Farmer not found"
        )

    columns = [
        "farmer_id",
        "name",
        "mobile_number",
        "village",
        "district",
        "created_at"
    ]

    return dict(zip(columns, row))


@app.post("/farmers")
def create_farmer(data: FarmerCreate):
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT farmer_id FROM farmers WHERE farmer_id = %s",
        (data.farmer_id,)
    )

    if cursor.fetchone():
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=400,
            detail="Farmer ID already exists"
        )

    cursor.execute(
        "SELECT farmer_id FROM farmers WHERE mobile_number = %s",
        (data.mobile_number,)
    )

    if cursor.fetchone():
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=400,
            detail="Mobile number already registered"
        )

    cursor.execute("""
        INSERT INTO farmers
        (farmer_id, name, mobile_number, village, district)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        data.farmer_id,
        data.name,
        data.mobile_number,
        data.village,
        data.district
    ))

    db.commit()

    cursor.close()
    db.close()

    return {
        "message": "Farmer created successfully",
        "farmer_id": data.farmer_id
    }



# =========================================================
# PROCUREMENT CENTERS
# =========================================================

class CenterCreate(BaseModel):
    center_id: str = Field(..., max_length=10)
    center_name: str = Field(..., max_length=150)

    agency_name: Optional[str] = None
    center_code: Optional[str] = None
    address: Optional[str] = None
    village_city: Optional[str] = None
    district: Optional[str] = None

    state: str = "Uttar Pradesh"

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    daily_capacity: int = Field(default=100, gt=0)
    processing_speed: Optional[float] = Field(default=None, gt=0)

    status: Literal[
        "Available",
        "Full",
        "Closed"
    ] = "Available"


class CenterUpdate(BaseModel):
    center_name: Optional[str] = None
    agency_name: Optional[str] = None
    center_code: Optional[str] = None
    address: Optional[str] = None
    village_city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    processing_speed: Optional[float] = Field(
        default=None,
        gt=0
    )

    daily_capacity: Optional[int] = Field(
        default=None,
        gt=0
    )

    status: Optional[
        Literal[
            "Available",
            "Full",
            "Closed"
        ]
    ] = None


# =========================================================
# CREATE PROCUREMENT CENTER
# =========================================================

@app.post("/centers")
def create_center(data: CenterCreate):

    db = get_db()
    cursor = db.cursor()

    try:

        # -------------------------------------------------
        # Check duplicate internal center ID
        # -------------------------------------------------

        cursor.execute("""
            SELECT center_id
            FROM procurement_centers
            WHERE center_id = %s
        """, (data.center_id,))

        if cursor.fetchone():

            raise HTTPException(
                status_code=400,
                detail="Center ID already exists"
            )


        # -------------------------------------------------
        # Check duplicate official center code
        # -------------------------------------------------

        if data.center_code:

            cursor.execute("""
                SELECT center_id
                FROM procurement_centers
                WHERE center_code = %s
            """, (data.center_code,))

            if cursor.fetchone():

                raise HTTPException(
                    status_code=400,
                    detail="Official Center Code already exists"
                )


        # -------------------------------------------------
        # Insert center
        # -------------------------------------------------

        cursor.execute("""
            INSERT INTO procurement_centers
            (
                center_id,
                center_name,
                agency_name,
                center_code,
                address,
                village_city,
                district,
                state,
                latitude,
                longitude,
                processing_speed,
                location,
                daily_capacity,
                current_queue,
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
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                0,
                %s
            )
        """, (
            data.center_id,
            data.center_name,
            data.agency_name,
            data.center_code,
            data.address,
            data.village_city,
            data.district,
            data.state,
            data.latitude,
            data.longitude,
            data.processing_speed,

            # location
            data.village_city or data.district,

            data.daily_capacity,
            data.status
        ))

        db.commit()

        return {
            "message": "Procurement center created successfully",
            "center_id": data.center_id,
            "center_code": data.center_code,
            "center_name": data.center_name,
            "status": data.status
        }

    except mysql.connector.Error as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    finally:

        cursor.close()
        db.close()


# =========================================================
# GET ALL PROCUREMENT CENTERS
# =========================================================

@app.get("/centers")
def get_centers():

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            SELECT
                center_id,
                center_name,
                agency_name,
                center_code,
                address,
                village_city,
                district,
                state,
                latitude,
                longitude,
                processing_speed,
                location,
                daily_capacity,
                current_queue,
                status
            FROM procurement_centers
            ORDER BY center_name
        """)

        return rows_to_dict(cursor)

    finally:

        cursor.close()
        db.close()


# =========================================================
# GET SINGLE PROCUREMENT CENTER
# =========================================================

@app.get("/centers/{center_id}")
def get_center(center_id: str):

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute("""
            SELECT
                center_id,
                center_name,
                agency_name,
                center_code,
                address,
                village_city,
                district,
                state,
                latitude,
                longitude,
                processing_speed,
                location,
                daily_capacity,
                current_queue,
                status
            FROM procurement_centers
            WHERE center_id = %s
        """, (center_id,))

        row = cursor.fetchone()

        if not row:

            raise HTTPException(
                status_code=404,
                detail="Procurement center not found"
            )

        columns = [
            "center_id",
            "center_name",
            "agency_name",
            "center_code",
            "address",
            "village_city",
            "district",
            "state",
            "latitude",
            "longitude",
            "processing_speed",
            "location",
            "daily_capacity",
            "current_queue",
            "status"
        ]

        return dict(zip(columns, row))

    finally:

        cursor.close()
        db.close()


# =========================================================
# UPDATE PROCUREMENT CENTER
# =========================================================

@app.put("/centers/{center_id}")
def update_center(
    center_id: str,
    data: CenterUpdate
):

    db = get_db()
    cursor = db.cursor()

    try:

        # -------------------------------------------------
        # Check center exists
        # -------------------------------------------------

        cursor.execute("""
            SELECT center_id
            FROM procurement_centers
            WHERE center_id = %s
        """, (center_id,))

        if not cursor.fetchone():

            raise HTTPException(
                status_code=404,
                detail="Procurement center not found"
            )


        # -------------------------------------------------
        # Check center code duplicate
        # -------------------------------------------------

        if data.center_code is not None:

            cursor.execute("""
                SELECT center_id
                FROM procurement_centers
                WHERE center_code = %s
                  AND center_id != %s
            """, (
                data.center_code,
                center_id
            ))

            if cursor.fetchone():

                raise HTTPException(
                    status_code=400,
                    detail="Official Center Code already exists"
                )


        # -------------------------------------------------
        # Prepare update fields
        # -------------------------------------------------

        update_fields = []
        values = []

        fields = {
            "center_name": data.center_name,
            "agency_name": data.agency_name,
            "center_code": data.center_code,
            "address": data.address,
            "village_city": data.village_city,
            "district": data.district,
            "state": data.state,
            "latitude": data.latitude,
            "longitude": data.longitude,
            "processing_speed": data.processing_speed,
            "daily_capacity": data.daily_capacity,
            "status": data.status
        }


        for column, value in fields.items():

            if value is not None:

                update_fields.append(
                    f"{column} = %s"
                )

                values.append(value)


        # -------------------------------------------------
        # Keep location synchronized
        # -------------------------------------------------

        if data.village_city is not None:

            update_fields.append(
                "location = %s"
            )

            values.append(
                data.village_city
            )


        # -------------------------------------------------
        # No update fields
        # -------------------------------------------------

        if not update_fields:

            raise HTTPException(
                status_code=400,
                detail="No fields provided for update"
            )


        # -------------------------------------------------
        # Update database
        # -------------------------------------------------

        values.append(center_id)

        query = f"""
            UPDATE procurement_centers
            SET {", ".join(update_fields)}
            WHERE center_id = %s
        """

        cursor.execute(
            query,
            tuple(values)
        )

        db.commit()

        return {
            "message": "Procurement center updated successfully",
            "center_id": center_id
        }

    except mysql.connector.Error as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    finally:

        cursor.close()
        db.close()


# =========================================================
# DELETE PROCUREMENT CENTER
# =========================================================

@app.delete("/centers/{center_id}")
def delete_center(center_id: str):

    db = get_db()
    cursor = db.cursor()

    try:

        # -------------------------------------------------
        # Check center
        # -------------------------------------------------

        cursor.execute("""
            SELECT center_id
            FROM procurement_centers
            WHERE center_id = %s
        """, (center_id,))

        if not cursor.fetchone():

            raise HTTPException(
                status_code=404,
                detail="Procurement center not found"
            )


        # -------------------------------------------------
        # Check procurement records
        # -------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM tokens
            WHERE center_id = %s
        """, (center_id,))

        token_count = cursor.fetchone()[0]


        if token_count > 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Center cannot be deleted because "
                    "procurement records exist. "
                    "Mark it Closed instead."
                )
            )


        # -------------------------------------------------
        # Delete center
        # -------------------------------------------------

        cursor.execute("""
            DELETE FROM procurement_centers
            WHERE center_id = %s
        """, (center_id,))

        db.commit()

        return {
            "message": "Procurement center deleted successfully",
            "center_id": center_id
        }

    except mysql.connector.Error as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    finally:

        cursor.close()
        db.close()

# =========================================================
# CROPS
# =========================================================

@app.get("/crops")
def get_crops():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            crop_id,
            crop_name,
            quantity,
            farmer_id
        FROM crops
        ORDER BY crop_id DESC
    """)

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return data


@app.get("/farmers/{farmer_id}/crops")
def get_farmer_crops(farmer_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            crop_id,
            crop_name,
            quantity,
            farmer_id
        FROM crops
        WHERE farmer_id = %s
        ORDER BY crop_id DESC
    """, (farmer_id,))

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return data


# =========================================================
# TOKENS
# =========================================================

@app.post("/tokens")
def create_token(data: TokenCreate):

    db = get_db()
    cursor = db.cursor()

    # Check farmer
    cursor.execute("""
        SELECT farmer_id
        FROM farmers
        WHERE farmer_id = %s
    """, (data.farmer_id,))

    if not cursor.fetchone():
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=404,
            detail="Farmer not found"
        )

    # Check center
    cursor.execute("""
        SELECT
            center_id,
            daily_capacity,
            status
        FROM procurement_centers
        WHERE center_id = %s
    """, (data.center_id,))

    center = cursor.fetchone()

    if not center:
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=404,
            detail="Procurement center not found"
        )

    center_id = center[0]
    capacity = center[1]
    center_status = center[2]

    if center_status == "Closed":
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=400,
            detail="Procurement center is currently closed"
        )

    # Current queue for selected date
    cursor.execute("""
        SELECT COALESCE(MAX(queue_position), 0)
        FROM tokens
        WHERE center_id = %s
          AND booking_date = %s
          AND status IN (
              'Registered',
              'Scheduled',
              'Arrived',
              'Quality Check'
          )
    """, (data.center_id, data.booking_date))

    max_position = cursor.fetchone()[0] or 0

    queue_position = max_position + 1

    if queue_position > capacity:
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=400,
            detail="Daily capacity of this center is full"
        )

    # AI / smart waiting time
    avg_processing_time = get_center_history_average(
        db,
        data.center_id
    )

    predicted_waiting_time = int(
        (queue_position - 1) * avg_processing_time
    )

    reporting_time = parse_reporting_time(
        data.reporting_time
    )

    token_id = generate_token_id(db)

    cursor.execute("""
        INSERT INTO tokens
        (
            token_id,
            farmer_id,
            center_id,
            crop_name,
            quantity,
            booking_date,
            reporting_time,
            queue_position,
            predicted_waiting_time,
            status
        )
        VALUES
        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        token_id,
        data.farmer_id,
        data.center_id,
        data.crop_name,
        data.quantity,
        data.booking_date,
        reporting_time,
        queue_position,
        predicted_waiting_time,
        "Scheduled"
    ))

    db.commit()

    cursor.close()
    db.close()

    return {
        "message": "Token booked successfully",
        "token_id": token_id,
        "farmer_id": data.farmer_id,
        "center_id": data.center_id,
        "crop_name": data.crop_name,
        "quantity": data.quantity,
        "booking_date": data.booking_date,
        "reporting_time": reporting_time,
        "queue_position": queue_position,
        "predicted_waiting_time": predicted_waiting_time,
        "status": "Scheduled"
    }


@app.get("/tokens")
def get_tokens():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            token_id,
            farmer_id,
            center_id,
            crop_name,
            quantity,
            booking_date,
            reporting_time,
            queue_position,
            predicted_waiting_time,
            status
        FROM tokens
        ORDER BY booking_date DESC, queue_position ASC
    """)

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return data


@app.get("/tokens/{token_id}")
def get_token(token_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            token_id,
            farmer_id,
            center_id,
            crop_name,
            quantity,
            booking_date,
            reporting_time,
            queue_position,
            predicted_waiting_time,
            status
        FROM tokens
        WHERE token_id = %s
    """, (token_id,))

    row = cursor.fetchone()

    cursor.close()
    db.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Token not found"
        )

    columns = [
        "token_id",
        "farmer_id",
        "center_id",
        "crop_name",
        "quantity",
        "booking_date",
        "reporting_time",
        "queue_position",
        "predicted_waiting_time",
        "status"
    ]

    return dict(zip(columns, row))


@app.get("/farmers/{farmer_id}/tokens")
def get_farmer_tokens(farmer_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            token_id,
            farmer_id,
            center_id,
            crop_name,
            quantity,
            booking_date,
            reporting_time,
            queue_position,
            predicted_waiting_time,
            status
        FROM tokens
        WHERE farmer_id = %s
        ORDER BY booking_date DESC, queue_position ASC
    """, (farmer_id,))

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return data


# =========================================================
# TOKEN STATUS
# =========================================================

@app.put("/tokens/{token_id}/status")
def update_token_status(
    token_id: str,
    data: TokenStatusUpdate
):
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT token_id FROM tokens WHERE token_id = %s",
        (token_id,)
    )

    if not cursor.fetchone():
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=404,
            detail="Token not found"
        )

    cursor.execute("""
        UPDATE tokens
        SET status = %s
        WHERE token_id = %s
    """, (
        data.status,
        token_id
    ))

    db.commit()

    cursor.close()
    db.close()

    return {
        "message": "Token status updated",
        "token_id": token_id,
        "status": data.status
    }


# =========================================================
# QUEUE
# =========================================================

@app.get("/queue/{center_id}")
def get_queue(center_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            token_id,
            farmer_id,
            crop_name,
            quantity,
            booking_date,
            reporting_time,
            queue_position,
            predicted_waiting_time,
            status
        FROM tokens
        WHERE center_id = %s
          AND status IN (
              'Registered',
              'Scheduled',
              'Arrived',
              'Quality Check'
          )
        ORDER BY booking_date ASC, queue_position ASC
    """, (center_id,))

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return {
        "center_id": center_id,
        "queue_count": len(data),
        "queue": data
    }


# =========================================================
# AI WAITING TIME PREDICTION
# =========================================================

@app.post("/ai/predict-waiting-time")
def predict_waiting_time(data: AIWaitRequest):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT center_id
        FROM procurement_centers
        WHERE center_id = %s
    """, (data.center_id,))

    if not cursor.fetchone():
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=404,
            detail="Center not found"
        )

    # If queue size isn't provided, calculate it
    if data.queue_size is None:

        cursor.execute("""
            SELECT COUNT(*)
            FROM tokens
            WHERE center_id = %s
              AND status IN (
                  'Registered',
                  'Scheduled',
                  'Arrived',
                  'Quality Check'
              )
        """, (data.center_id,))

        queue_size = cursor.fetchone()[0]

    else:
        queue_size = max(0, data.queue_size)

    cursor.close()

    avg_processing_time = get_center_history_average(
        db,
        data.center_id
    )

    db.close()

    predicted_time = int(
        queue_size * avg_processing_time
    )

    return {
        "center_id": data.center_id,
        "queue_size": queue_size,
        "average_processing_time": avg_processing_time,
        "predicted_waiting_time_minutes": predicted_time,
        "model": "Smart Queue Prediction"
    }


# =========================================================
# PAYMENTS
# =========================================================

@app.get("/payments")
def get_payments():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            payment_id,
            token_id,
            farmer_id,
            amount,
            payment_status,
            payment_date
        FROM payments
        ORDER BY payment_id DESC
    """)

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return data


@app.get("/payments/{payment_id}")
def get_payment(payment_id: int):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            payment_id,
            token_id,
            farmer_id,
            amount,
            payment_status,
            payment_date
        FROM payments
        WHERE payment_id = %s
    """, (payment_id,))

    row = cursor.fetchone()

    cursor.close()
    db.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Payment not found"
        )

    columns = [
        "payment_id",
        "token_id",
        "farmer_id",
        "amount",
        "payment_status",
        "payment_date"
    ]

    return dict(zip(columns, row))


@app.get("/farmers/{farmer_id}/payments")
def get_farmer_payments(farmer_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            payment_id,
            token_id,
            farmer_id,
            amount,
            payment_status,
            payment_date
        FROM payments
        WHERE farmer_id = %s
        ORDER BY payment_id DESC
    """, (farmer_id,))

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return data


@app.post("/payments")
def create_payment(data: PaymentCreate):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT token_id, farmer_id
        FROM tokens
        WHERE token_id = %s
    """, (data.token_id,))

    token = cursor.fetchone()

    if not token:
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=404,
            detail="Token not found"
        )

    if token[1] != data.farmer_id:
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=400,
            detail="Token does not belong to this farmer"
        )

    cursor.execute("""
        INSERT INTO payments
        (
            token_id,
            farmer_id,
            amount,
            payment_status,
            payment_date
        )
        VALUES
        (%s, %s, %s, %s, %s)
    """, (
        data.token_id,
        data.farmer_id,
        data.amount,
        data.payment_status,
        data.payment_date
    ))

    db.commit()

    payment_id = cursor.lastrowid

    cursor.close()
    db.close()

    return {
        "message": "Payment record created",
        "payment_id": payment_id
    }


@app.put("/payments/{payment_id}/status")
def update_payment_status(
    payment_id: int,
    data: PaymentStatusUpdate
):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT payment_id
        FROM payments
        WHERE payment_id = %s
    """, (payment_id,))

    if not cursor.fetchone():
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=404,
            detail="Payment not found"
        )

    cursor.execute("""
        UPDATE payments
        SET payment_status = %s
        WHERE payment_id = %s
    """, (
        data.payment_status,
        payment_id
    ))

    db.commit()

    cursor.close()
    db.close()

    return {
        "message": "Payment status updated",
        "payment_id": payment_id,
        "payment_status": data.payment_status
    }


# =========================================================
# WAREHOUSES
# =========================================================

@app.get("/warehouses")
def get_warehouses():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            warehouse_id,
            warehouse_name,
            location,
            capacity,
            available_space,
            status
        FROM warehouses
        ORDER BY warehouse_name
    """)

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return data


@app.get("/warehouses/{warehouse_id}")
def get_warehouse(warehouse_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            warehouse_id,
            warehouse_name,
            location,
            capacity,
            available_space,
            status
        FROM warehouses
        WHERE warehouse_id = %s
    """, (warehouse_id,))

    row = cursor.fetchone()

    cursor.close()
    db.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Warehouse not found"
        )

    columns = [
        "warehouse_id",
        "warehouse_name",
        "location",
        "capacity",
        "available_space",
        "status"
    ]

    return dict(zip(columns, row))


# =========================================================
# CENTER ADMIN DASHBOARD
# =========================================================

@app.get("/dashboard/center/{center_id}")
def center_dashboard(center_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            center_id,
            center_name,
            location,
            daily_capacity,
            current_queue,
            status
        FROM procurement_centers
        WHERE center_id = %s
    """, (center_id,))

    center = cursor.fetchone()

    if not center:
        cursor.close()
        db.close()

        raise HTTPException(
            status_code=404,
            detail="Center not found"
        )

    cursor.execute("""
        SELECT COUNT(*)
        FROM tokens
        WHERE center_id = %s
          AND status IN (
              'Registered',
              'Scheduled',
              'Arrived',
              'Quality Check'
          )
    """, (center_id,))

    active_queue = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM tokens
        WHERE center_id = %s
          AND status = 'Procured'
    """, (center_id,))

    procured = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM tokens
        WHERE center_id = %s
          AND status = 'Quality Check'
    """, (center_id,))

    quality_check = cursor.fetchone()[0]

    cursor.close()
    db.close()

    return {
        "center": {
            "center_id": center[0],
            "center_name": center[1],
            "location": center[2],
            "daily_capacity": center[3],
            "current_queue": center[4],
            "status": center[5]
        },
        "live_queue": active_queue,
        "procured": procured,
        "quality_check": quality_check
    }


# =========================================================
# GOVERNMENT DASHBOARD
# =========================================================

@app.get("/dashboard/government")
def government_dashboard():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM farmers
    """)
    total_farmers = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM procurement_centers
    """)
    total_centers = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM warehouses
    """)
    total_warehouses = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM tokens
    """)
    total_tokens = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM tokens
        WHERE status IN (
            'Registered',
            'Scheduled',
            'Arrived',
            'Quality Check'
        )
    """)
    active_tokens = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM tokens
        WHERE status = 'Procured'
    """)
    procured_tokens = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE payment_status IN ('Pending', 'Processing')
    """)
    pending_payments = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM payments
        WHERE payment_status = 'Completed'
    """)
    completed_payment_amount = cursor.fetchone()[0]

    cursor.close()
    db.close()

    return {
        "total_farmers": total_farmers,
        "total_centers": total_centers,
        "total_warehouses": total_warehouses,
        "total_tokens": total_tokens,
        "active_tokens": active_tokens,
        "procured_tokens": procured_tokens,
        "pending_payments": pending_payments,
        "completed_payment_amount": float(
            completed_payment_amount or 0
        )
    }


# =========================================================
# CENTER HISTORY / ANALYTICS
# =========================================================

@app.get("/analytics/center/{center_id}")
def center_analytics(center_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            history_id,
            center_id,
            record_date,
            total_farmers,
            processed_farmers,
            avg_processing_time,
            queue_length,
            actual_waiting_time
        FROM center_history
        WHERE center_id = %s
        ORDER BY record_date DESC
    """, (center_id,))

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return {
        "center_id": center_id,
        "history": data
    }


# =========================================================
# MAP / SMART CENTER DATA
# =========================================================

@app.get("/maps/{center_id}")
def center_map_data(center_id: str):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            center_id,
            center_name,
            location,
            daily_capacity,
            current_queue,
            status
        FROM procurement_centers
        WHERE center_id = %s
    """, (center_id,))

    row = cursor.fetchone()

    cursor.close()
    db.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Center not found"
        )

    return {
        "center_id": row[0],
        "center_name": row[1],
        "location": row[2],
        "daily_capacity": row[3],
        "current_queue": row[4],
        "status": row[5]
    }


# =========================================================
# SCHEDULE COMPATIBILITY
# =========================================================

@app.get("/schedules")
def get_schedules():
    """
    Current database does not contain a separate schedules table.
    Therefore schedules are derived from booked token dates.
    """

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            center_id,
            booking_date,
            COUNT(*) AS booked_tokens
        FROM tokens
        GROUP BY center_id, booking_date
        ORDER BY booking_date DESC
    """)

    data = rows_to_dict(cursor)

    cursor.close()
    db.close()

    return data