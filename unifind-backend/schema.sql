-- Optional: manual MySQL setup. The app also creates the tables automatically.
CREATE DATABASE IF NOT EXISTS unifind CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'unifind_user'@'localhost' IDENTIFIED BY 'StrongPassword123';
GRANT ALL PRIVILEGES ON unifind.* TO 'unifind_user'@'localhost';
FLUSH PRIVILEGES;
