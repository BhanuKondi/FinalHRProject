CREATE TABLE `roles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `display_name` varchar(255) DEFAULT NULL,
  `role_id` int NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `must_change_password` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  KEY `role_id` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- sample roles
INSERT INTO roles (name) VALUES ('Admin'), ('HR'), ('Employee');

-- sample admin user (password: admin123)
INSERT INTO users (email, password_hash, display_name, role_id, is_active, must_change_password) VALUES ('admin@example.com', 'scrypt:32768:8:1$BehCWquJBlRfak87$5ef9e5167d77306881c021d30d005b46f52c5c0fd8f09704b22084db0b627ac43057f0beb0e02be3838a9cebac5b4e69f7c7e07e8d5e8be1797cffad189962e3', 'Administrator', 1, 1, 0);
