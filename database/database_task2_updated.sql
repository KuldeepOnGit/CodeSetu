CREATE DATABASE IF NOT EXISTS farmer_procurement
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE farmer_procurement;

CREATE TABLE IF NOT EXISTS farmers (
    farmer_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    mobile_number VARCHAR(15) NOT NULL,
    password_hash VARCHAR(128) NULL,
    password_salt VARCHAR(64) NULL,
    village VARCHAR(100) NULL,
    district VARCHAR(100) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_farmers_mobile_number (mobile_number),
    KEY idx_farmers_district (district)
) ENGINE=InnoDB;

-- Safe compatibility migration for farmers tables created before authentication.
SET @add_password_hash = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE farmers ADD COLUMN password_hash VARCHAR(128) NULL AFTER mobile_number',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'farmers'
      AND column_name = 'password_hash'
);
PREPARE add_password_hash_statement FROM @add_password_hash;
EXECUTE add_password_hash_statement;
DEALLOCATE PREPARE add_password_hash_statement;

SET @add_password_salt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE farmers ADD COLUMN password_salt VARCHAR(64) NULL AFTER password_hash',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'farmers'
      AND column_name = 'password_salt'
);
PREPARE add_password_salt_statement FROM @add_password_salt;
EXECUTE add_password_salt_statement;
DEALLOCATE PREPARE add_password_salt_statement;

CREATE TABLE IF NOT EXISTS procurement_centers (
    center_id VARCHAR(10) PRIMARY KEY,
    center_name VARCHAR(150) NOT NULL,
    agency_name VARCHAR(150) NULL,
    center_code VARCHAR(30) NULL,
    address VARCHAR(255) NULL,
    village_city VARCHAR(100) NULL,
    district VARCHAR(100) NULL,
    state VARCHAR(100) NULL,
    latitude DECIMAL(10,7) NULL,
    longitude DECIMAL(10,7) NULL,
    processing_speed DECIMAL(8,2) NULL,
    location VARCHAR(150) NULL,
    daily_capacity INT UNSIGNED NOT NULL DEFAULT 100,
    current_queue INT UNSIGNED NOT NULL DEFAULT 0,
    status ENUM('Available', 'Full', 'Closed') NOT NULL DEFAULT 'Available',
    UNIQUE KEY uq_procurement_centers_center_code (center_code),
    KEY idx_procurement_centers_status (status),
    KEY idx_procurement_centers_district (district)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS crops (
    crop_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    crop_name VARCHAR(50) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    farmer_id VARCHAR(10) NULL,
    KEY idx_crops_farmer_id (farmer_id),
    KEY idx_crops_crop_name (crop_name),
    CONSTRAINT fk_crops_farmer
        FOREIGN KEY (farmer_id)
        REFERENCES farmers (farmer_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tokens (
    token_id VARCHAR(15) PRIMARY KEY,
    farmer_id VARCHAR(10) NOT NULL,
    center_id VARCHAR(10) NOT NULL,
    crop_name VARCHAR(50) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    booking_date DATE NOT NULL,
    reporting_time TIME NOT NULL,
    queue_position INT UNSIGNED NOT NULL,
    predicted_waiting_time INT UNSIGNED NOT NULL DEFAULT 0,
    status ENUM(
        'Registered',
        'Scheduled',
        'Arrived',
        'Quality Check',
        'Procured',
        'Payment'
    ) NOT NULL DEFAULT 'Registered',
    KEY idx_tokens_farmer_booking (farmer_id, booking_date),
    KEY idx_tokens_center_booking_queue (
        center_id,
        booking_date,
        queue_position
    ),
    KEY idx_tokens_center_status (center_id, status),
    KEY idx_tokens_booking_status (booking_date, status),
    CONSTRAINT fk_tokens_farmer
        FOREIGN KEY (farmer_id)
        REFERENCES farmers (farmer_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_tokens_center
        FOREIGN KEY (center_id)
        REFERENCES procurement_centers (center_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
    payment_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    token_id VARCHAR(15) NOT NULL,
    farmer_id VARCHAR(10) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    payment_status ENUM(
        'Pending',
        'Processing',
        'Completed',
        'Failed'
    ) NOT NULL DEFAULT 'Pending',
    payment_date DATE NULL,
    KEY idx_payments_token_id (token_id),
    KEY idx_payments_farmer_status (farmer_id, payment_status),
    KEY idx_payments_payment_date (payment_date),
    CONSTRAINT fk_payments_token
        FOREIGN KEY (token_id)
        REFERENCES tokens (token_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_payments_farmer
        FOREIGN KEY (farmer_id)
        REFERENCES farmers (farmer_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS center_history (
    history_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    center_id VARCHAR(10) NOT NULL,
    record_date DATE NOT NULL,
    total_farmers INT UNSIGNED NULL,
    processed_farmers INT UNSIGNED NULL,
    avg_processing_time DECIMAL(6,2) NULL,
    queue_length INT UNSIGNED NULL,
    actual_waiting_time DECIMAL(6,2) NULL,
    KEY idx_center_history_center_date (center_id, record_date),
    CONSTRAINT fk_center_history_center
        FOREIGN KEY (center_id)
        REFERENCES procurement_centers (center_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id VARCHAR(10) PRIMARY KEY,
    warehouse_name VARCHAR(150) NOT NULL,
    location VARCHAR(150) NULL,
    capacity DECIMAL(12,2) NOT NULL DEFAULT 0,
    available_space DECIMAL(12,2) NOT NULL DEFAULT 0,
    status ENUM('Available', 'Full', 'Closed') NOT NULL DEFAULT 'Available',
    KEY idx_warehouses_status (status),
    KEY idx_warehouses_location (location)
) ENGINE=InnoDB;

-- Preserve the existing sample records without introducing fake centers.
INSERT INTO farmers (
    farmer_id,
    name,
    mobile_number,
    village,
    district
) VALUES (
    'F001',
    'Rajesh Kumar',
    '9812345678',
    'Rampur',
    'Bareilly'
)
ON DUPLICATE KEY UPDATE farmer_id = farmer_id;

INSERT INTO procurement_centers (
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
) VALUES (
    'C001',
    'Bareilly Procurement Center',
    NULL,
    'C001',
    NULL,
    'Bareilly',
    'Bareilly',
    'Uttar Pradesh',
    NULL,
    NULL,
    NULL,
    'Bareilly',
    100,
    12,
    'Available'
)
ON DUPLICATE KEY UPDATE center_id = center_id;

INSERT INTO crops (
    crop_name,
    quantity,
    farmer_id
)
SELECT
    'Wheat',
    25,
    'F001'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1
    FROM crops
    WHERE farmer_id = 'F001'
      AND crop_name = 'Wheat'
);

INSERT INTO tokens (
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
) VALUES (
    'KSN-1025',
    'F001',
    'C001',
    'Wheat',
    25,
    '2026-09-05',
    '10:30:00',
    12,
    35,
    'Scheduled'
)
ON DUPLICATE KEY UPDATE token_id = token_id;

INSERT INTO payments (
    token_id,
    farmer_id,
    amount,
    payment_status,
    payment_date
)
SELECT
    'KSN-1025',
    'F001',
    48500,
    'Processing',
    '2026-09-05'
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1
    FROM payments
    WHERE token_id = 'KSN-1025'
      AND farmer_id = 'F001'
      AND payment_date = '2026-09-05'
);