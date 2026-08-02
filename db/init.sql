CREATE DATABASE IF NOT EXISTS quran_school;
USE quran_school;

CREATE TABLE IF NOT EXISTS student_progress (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_name VARCHAR(120) NOT NULL,
  juz_number INT NOT NULL,
  ayah_reference VARCHAR(120) NOT NULL,
  recorded_at DATETIME NOT NULL,
  is_present BOOLEAN NOT NULL DEFAULT TRUE,
  is_approved BOOLEAN NOT NULL DEFAULT FALSE,
  approved_at DATETIME NULL,
  feedback TEXT NULL
);
