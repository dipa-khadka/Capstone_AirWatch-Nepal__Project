-- AirWatch Nepal: physical design (Week 5, Section 3.4)
CREATE DATABASE IF NOT EXISTS airwatch CHARACTER SET utf8mb4;
USE airwatch;

CREATE TABLE IF NOT EXISTS location (
  location_id INT AUTO_INCREMENT PRIMARY KEY,
  city_name   VARCHAR(50) NOT NULL UNIQUE,
  district    VARCHAR(50) NOT NULL,
  latitude    DECIMAL(9,6),
  longitude   DECIMAL(9,6)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS data_source (
  source_id   INT AUTO_INCREMENT PRIMARY KEY,
  source_name VARCHAR(50)  NOT NULL UNIQUE,
  source_url  VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS health_category (
  category_id INT AUTO_INCREMENT PRIMARY KEY,
  aqi_min     INT NOT NULL,
  aqi_max     INT NOT NULL,
  label       VARCHAR(40)  NOT NULL,
  message     VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS aq_reading (
  reading_id  INT AUTO_INCREMENT PRIMARY KEY,
  location_id INT NOT NULL,
  source_id   INT NOT NULL,
  `timestamp` DATETIME NOT NULL,
  pm25 DECIMAL(6,2), pm10 DECIMAL(6,2), o3 DECIMAL(6,2),
  no2  DECIMAL(6,2), so2  DECIMAL(6,2), co DECIMAL(6,2),
  aqi_value   INT NOT NULL,
  CONSTRAINT fk_reading_location FOREIGN KEY (location_id) REFERENCES location(location_id),
  CONSTRAINT fk_reading_source   FOREIGN KEY (source_id)   REFERENCES data_source(source_id),
  CONSTRAINT uq_reading UNIQUE (location_id, source_id, `timestamp`),
  INDEX idx_location_time (location_id, `timestamp`)
) ENGINE=InnoDB;
