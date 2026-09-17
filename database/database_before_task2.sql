USE farmer_procurement;

CREATE TABLE farmers (

    farmer_id VARCHAR(10) PRIMARY KEY,

    name VARCHAR(100) NOT NULL,

    mobile_number VARCHAR(15) NOT NULL UNIQUE,

    village VARCHAR(100),

    district VARCHAR(100),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);

CREATE TABLE procurement_centers (

    center_id VARCHAR(10) PRIMARY KEY,

    center_name VARCHAR(150) NOT NULL,

    location VARCHAR(150),

    daily_capacity INT NOT NULL,

    current_queue INT DEFAULT 0,

    status ENUM('Available', 'Full', 'Closed') DEFAULT 'Available'

);

CREATE TABLE crops (

    crop_id INT AUTO_INCREMENT PRIMARY KEY,

    crop_name VARCHAR(50) NOT NULL,

    quantity DECIMAL(10,2) NOT NULL,

    farmer_id VARCHAR(10),

    FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id)

);

CREATE TABLE tokens (

    token_id VARCHAR(15) PRIMARY KEY,

    farmer_id VARCHAR(10),

    center_id VARCHAR(10),

    crop_name VARCHAR(50),

    quantity DECIMAL(10,2),

    booking_date DATE,

    reporting_time TIME,

    queue_position INT,

    predicted_waiting_time INT,

    status ENUM('Registered','Scheduled','Arrived','Quality Check','Procured','Payment')

           DEFAULT 'Registered',

    FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id),

    FOREIGN KEY (center_id) REFERENCES procurement_centers(center_id)

);

CREATE TABLE payments (

    payment_id INT AUTO_INCREMENT PRIMARY KEY,

    token_id VARCHAR(15),

    farmer_id VARCHAR(10),

    amount DECIMAL(12,2),

    payment_status ENUM('Pending','Processing','Completed','Failed') DEFAULT 'Pending',

    payment_date DATE,

    FOREIGN KEY (token_id) REFERENCES tokens(token_id),

    FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id)

);

CREATE TABLE center_history (

    history_id INT AUTO_INCREMENT PRIMARY KEY,

    center_id VARCHAR(10),

    record_date DATE,

    total_farmers INT,

    processed_farmers INT,

    avg_processing_time DECIMAL(6,2),

    queue_length INT,

    actual_waiting_time DECIMAL(6,2),

    FOREIGN KEY (center_id) REFERENCES procurement_centers(center_id)

);

INSERT INTO farmers VALUES ('F001','Rajesh Kumar','9812345678','Rampur','Bareilly',NOW());

INSERT INTO procurement_centers VALUES

('C001','Bareilly Procurement Center','Bareilly',100,12,'Available');

INSERT INTO crops (crop_name, quantity, farmer_id) VALUES ('Wheat', 25, 'F001');

INSERT INTO tokens VALUES

('KSN-1025','F001','C001','Wheat',25,'2026-09-05','10:30:00',12,35,'Scheduled');

INSERT INTO payments (token_id, farmer_id, amount, payment_status, payment_date)

VALUES ('KSN-1025','F001',48500,'Processing','2026-09-05'); 