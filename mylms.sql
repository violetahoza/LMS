-- MySQL Workbench Forward Engineering

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema mydb
-- -----------------------------------------------------
-- -----------------------------------------------------
-- Schema mylms
-- -----------------------------------------------------

-- -----------------------------------------------------
-- Schema mylms
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `mylms` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci ;
USE `mylms` ;

-- -----------------------------------------------------
-- Table `mylms`.`achievements`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`achievements` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL,
  `description` TEXT NULL DEFAULT NULL,
  `badge_icon` VARCHAR(255) NULL DEFAULT NULL,
  `points_value` INT NULL DEFAULT NULL,
  `criteria_type` ENUM('course_completion', 'quiz_score', 'streak', 'participation') NOT NULL,
  `criteria_value` INT NULL DEFAULT NULL,
  PRIMARY KEY (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 22
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`users`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(80) NOT NULL,
  `email` VARCHAR(120) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `full_name` VARCHAR(150) NOT NULL,
  `role` ENUM('ADMIN', 'TEACHER', 'STUDENT') NOT NULL,
  `phone` VARCHAR(20) NULL DEFAULT NULL,
  `age` INT NULL DEFAULT NULL,
  `created_at` DATETIME NULL DEFAULT NULL,
  `updated_at` DATETIME NULL DEFAULT NULL,
  `is_active` TINYINT(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `username` (`username` ASC) VISIBLE,
  UNIQUE INDEX `email` (`email` ASC) VISIBLE)
ENGINE = InnoDB
AUTO_INCREMENT = 48
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`courses`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`courses` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(200) NOT NULL,
  `description` TEXT NULL DEFAULT NULL,
  `category` VARCHAR(100) NULL DEFAULT NULL,
  `teacher_id` INT NOT NULL,
  `start_date` DATE NULL DEFAULT NULL,
  `end_date` DATE NULL DEFAULT NULL,
  `max_students` INT NULL DEFAULT NULL,
  `created_at` DATETIME NULL DEFAULT NULL,
  `updated_at` DATETIME NULL DEFAULT NULL,
  `is_published` TINYINT(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `teacher_id` (`teacher_id` ASC) VISIBLE,
  CONSTRAINT `courses_ibfk_1`
    FOREIGN KEY (`teacher_id`)
    REFERENCES `mylms`.`users` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 26
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`lessons`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`lessons` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `course_id` INT NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `content` TEXT NULL DEFAULT NULL,
  `order_number` INT NOT NULL,
  `lesson_type` ENUM('video', 'text', 'mixed') NULL DEFAULT NULL,
  `video_url` VARCHAR(500) NULL DEFAULT NULL,
  `duration_minutes` INT NULL DEFAULT NULL,
  `created_at` DATETIME NULL DEFAULT NULL,
  `updated_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `course_id` (`course_id` ASC) VISIBLE,
  CONSTRAINT `lessons_ibfk_1`
    FOREIGN KEY (`course_id`)
    REFERENCES `mylms`.`courses` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 69
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`quizzes`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`quizzes` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `course_id` INT NOT NULL,
  `lesson_id` INT NULL DEFAULT NULL,
  `title` VARCHAR(200) NOT NULL,
  `description` TEXT NULL DEFAULT NULL,
  `total_points` INT NULL DEFAULT NULL,
  `passing_score` INT NULL DEFAULT NULL,
  `time_limit_minutes` INT NULL DEFAULT NULL,
  `max_attempts` INT NULL DEFAULT NULL,
  `created_at` DATETIME NULL DEFAULT NULL,
  `updated_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `course_id` (`course_id` ASC) VISIBLE,
  INDEX `lesson_id` (`lesson_id` ASC) VISIBLE,
  CONSTRAINT `quizzes_ibfk_1`
    FOREIGN KEY (`course_id`)
    REFERENCES `mylms`.`courses` (`id`),
  CONSTRAINT `quizzes_ibfk_2`
    FOREIGN KEY (`lesson_id`)
    REFERENCES `mylms`.`lessons` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 24
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`questions`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`questions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `quiz_id` INT NOT NULL,
  `question_text` TEXT NOT NULL,
  `question_type` ENUM('multiple_choice', 'true_false', 'short_answer') NOT NULL,
  `points` INT NULL DEFAULT NULL,
  `order_number` INT NOT NULL,
  `created_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `quiz_id` (`quiz_id` ASC) VISIBLE,
  CONSTRAINT `questions_ibfk_1`
    FOREIGN KEY (`quiz_id`)
    REFERENCES `mylms`.`quizzes` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 58
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`answer_options`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`answer_options` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `question_id` INT NOT NULL,
  `option_text` VARCHAR(500) NOT NULL,
  `is_correct` TINYINT(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `question_id` (`question_id` ASC) VISIBLE,
  CONSTRAINT `answer_options_ibfk_1`
    FOREIGN KEY (`question_id`)
    REFERENCES `mylms`.`questions` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 271
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`assignments`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`assignments` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `course_id` INT NOT NULL,
  `lesson_id` INT NULL DEFAULT NULL,
  `title` VARCHAR(200) NOT NULL,
  `description` TEXT NULL DEFAULT NULL,
  `due_date` DATETIME NULL DEFAULT NULL,
  `total_points` INT NULL DEFAULT NULL,
  `created_at` DATETIME NULL DEFAULT NULL,
  `updated_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `course_id` (`course_id` ASC) VISIBLE,
  INDEX `lesson_id` (`lesson_id` ASC) VISIBLE,
  CONSTRAINT `assignments_ibfk_1`
    FOREIGN KEY (`course_id`)
    REFERENCES `mylms`.`courses` (`id`),
  CONSTRAINT `assignments_ibfk_2`
    FOREIGN KEY (`lesson_id`)
    REFERENCES `mylms`.`lessons` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 27
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`assignment_submissions`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`assignment_submissions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `assignment_id` INT NOT NULL,
  `student_id` INT NOT NULL,
  `submission_text` TEXT NULL DEFAULT NULL,
  `file_path` VARCHAR(500) NULL DEFAULT NULL,
  `submitted_at` DATETIME NULL DEFAULT NULL,
  `grade` FLOAT NULL DEFAULT NULL,
  `feedback` TEXT NULL DEFAULT NULL,
  `graded_at` DATETIME NULL DEFAULT NULL,
  `graded_by` INT NULL DEFAULT NULL,
  `status` ENUM('submitted', 'graded', 'returned') NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `assignment_id` (`assignment_id` ASC, `student_id` ASC) VISIBLE,
  INDEX `student_id` (`student_id` ASC) VISIBLE,
  INDEX `graded_by` (`graded_by` ASC) VISIBLE,
  CONSTRAINT `assignment_submissions_ibfk_1`
    FOREIGN KEY (`assignment_id`)
    REFERENCES `mylms`.`assignments` (`id`),
  CONSTRAINT `assignment_submissions_ibfk_2`
    FOREIGN KEY (`student_id`)
    REFERENCES `mylms`.`users` (`id`),
  CONSTRAINT `assignment_submissions_ibfk_3`
    FOREIGN KEY (`graded_by`)
    REFERENCES `mylms`.`users` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 10
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`certificate_requests`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`certificate_requests` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `student_id` INT NOT NULL,
  `course_id` INT NOT NULL,
  `requested_at` DATETIME NULL DEFAULT NULL,
  `status` ENUM('pending', 'approved', 'rejected') NULL DEFAULT NULL,
  `reviewed_by` INT NULL DEFAULT NULL,
  `reviewed_at` DATETIME NULL DEFAULT NULL,
  `rejection_reason` TEXT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `student_id` (`student_id` ASC, `course_id` ASC) VISIBLE,
  INDEX `course_id` (`course_id` ASC) VISIBLE,
  INDEX `reviewed_by` (`reviewed_by` ASC) VISIBLE,
  CONSTRAINT `certificate_requests_ibfk_1`
    FOREIGN KEY (`student_id`)
    REFERENCES `mylms`.`users` (`id`),
  CONSTRAINT `certificate_requests_ibfk_2`
    FOREIGN KEY (`course_id`)
    REFERENCES `mylms`.`courses` (`id`),
  CONSTRAINT `certificate_requests_ibfk_3`
    FOREIGN KEY (`reviewed_by`)
    REFERENCES `mylms`.`users` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 18
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`certificates`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`certificates` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `student_id` INT NOT NULL,
  `course_id` INT NOT NULL,
  `certificate_code` VARCHAR(100) NOT NULL,
  `issued_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `student_id` (`student_id` ASC, `course_id` ASC) VISIBLE,
  UNIQUE INDEX `certificate_code` (`certificate_code` ASC) VISIBLE,
  INDEX `course_id` (`course_id` ASC) VISIBLE,
  CONSTRAINT `certificates_ibfk_1`
    FOREIGN KEY (`student_id`)
    REFERENCES `mylms`.`users` (`id`),
  CONSTRAINT `certificates_ibfk_2`
    FOREIGN KEY (`course_id`)
    REFERENCES `mylms`.`courses` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 22
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`enrollments`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`enrollments` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `student_id` INT NOT NULL,
  `course_id` INT NOT NULL,
  `enrolled_at` DATETIME NULL DEFAULT NULL,
  `completed_at` DATETIME NULL DEFAULT NULL,
  `status` ENUM('active', 'completed', 'dropped') NULL DEFAULT NULL,
  `progress_percentage` FLOAT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `student_id` (`student_id` ASC, `course_id` ASC) VISIBLE,
  INDEX `course_id` (`course_id` ASC) VISIBLE,
  CONSTRAINT `enrollments_ibfk_1`
    FOREIGN KEY (`student_id`)
    REFERENCES `mylms`.`users` (`id`),
  CONSTRAINT `enrollments_ibfk_2`
    FOREIGN KEY (`course_id`)
    REFERENCES `mylms`.`courses` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 55
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`lesson_progress`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`lesson_progress` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `student_id` INT NOT NULL,
  `lesson_id` INT NOT NULL,
  `viewed_at` DATETIME NULL DEFAULT NULL,
  `completed_at` DATETIME NULL DEFAULT NULL,
  `time_spent_minutes` INT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `student_id` (`student_id` ASC, `lesson_id` ASC) VISIBLE,
  INDEX `lesson_id` (`lesson_id` ASC) VISIBLE,
  CONSTRAINT `lesson_progress_ibfk_1`
    FOREIGN KEY (`student_id`)
    REFERENCES `mylms`.`users` (`id`),
  CONSTRAINT `lesson_progress_ibfk_2`
    FOREIGN KEY (`lesson_id`)
    REFERENCES `mylms`.`lessons` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 22
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`messages`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`messages` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `sender_id` INT NOT NULL,
  `recipient_id` INT NOT NULL,
  `course_id` INT NULL DEFAULT NULL,
  `subject` VARCHAR(200) NOT NULL,
  `content` TEXT NOT NULL,
  `sent_at` DATETIME NOT NULL,
  `read_at` DATETIME NULL DEFAULT NULL,
  `is_announcement` TINYINT(1) NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `sender_id` (`sender_id` ASC) VISIBLE,
  INDEX `recipient_id` (`recipient_id` ASC) VISIBLE,
  INDEX `course_id` (`course_id` ASC) VISIBLE,
  CONSTRAINT `messages_ibfk_1`
    FOREIGN KEY (`sender_id`)
    REFERENCES `mylms`.`users` (`id`),
  CONSTRAINT `messages_ibfk_2`
    FOREIGN KEY (`recipient_id`)
    REFERENCES `mylms`.`users` (`id`),
  CONSTRAINT `messages_ibfk_3`
    FOREIGN KEY (`course_id`)
    REFERENCES `mylms`.`courses` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 18
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`notifications`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`notifications` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `recipient_id` INT NOT NULL,
  `sender_id` INT NULL DEFAULT NULL,
  `type` VARCHAR(40) NOT NULL,
  `priority` VARCHAR(30) NULL DEFAULT 'normal',
  `title` VARCHAR(200) NOT NULL,
  `message` TEXT NOT NULL,
  `action_url` VARCHAR(500) NULL DEFAULT NULL,
  `related_id` INT NULL DEFAULT NULL,
  `created_at` DATETIME NULL DEFAULT NULL,
  `read_at` DATETIME NULL DEFAULT NULL,
  `is_read` TINYINT(1) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `recipient_id` (`recipient_id` ASC) VISIBLE,
  INDEX `sender_id` (`sender_id` ASC) VISIBLE,
  CONSTRAINT `notifications_ibfk_1`
    FOREIGN KEY (`recipient_id`)
    REFERENCES `mylms`.`users` (`id`),
  CONSTRAINT `notifications_ibfk_2`
    FOREIGN KEY (`sender_id`)
    REFERENCES `mylms`.`users` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 62
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`quiz_attempts`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`quiz_attempts` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `quiz_id` INT NOT NULL,
  `student_id` INT NOT NULL,
  `attempt_number` INT NOT NULL,
  `score` FLOAT NULL DEFAULT NULL,
  `started_at` DATETIME NULL DEFAULT NULL,
  `submitted_at` DATETIME NULL DEFAULT NULL,
  `time_spent_minutes` INT NULL DEFAULT NULL,
  `status` ENUM('in_progress', 'completed', 'abandoned') NULL DEFAULT NULL,
  `graded_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `quiz_id` (`quiz_id` ASC) VISIBLE,
  INDEX `student_id` (`student_id` ASC) VISIBLE,
  CONSTRAINT `quiz_attempts_ibfk_1`
    FOREIGN KEY (`quiz_id`)
    REFERENCES `mylms`.`quizzes` (`id`),
  CONSTRAINT `quiz_attempts_ibfk_2`
    FOREIGN KEY (`student_id`)
    REFERENCES `mylms`.`users` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 15
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`student_achievements`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`student_achievements` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `student_id` INT NOT NULL,
  `achievement_id` INT NOT NULL,
  `earned_at` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `student_id` (`student_id` ASC, `achievement_id` ASC) VISIBLE,
  INDEX `achievement_id` (`achievement_id` ASC) VISIBLE,
  CONSTRAINT `student_achievements_ibfk_1`
    FOREIGN KEY (`student_id`)
    REFERENCES `mylms`.`users` (`id`),
  CONSTRAINT `student_achievements_ibfk_2`
    FOREIGN KEY (`achievement_id`)
    REFERENCES `mylms`.`achievements` (`id`))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table `mylms`.`student_answers`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `mylms`.`student_answers` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `attempt_id` INT NOT NULL,
  `question_id` INT NOT NULL,
  `answer_text` TEXT NULL DEFAULT NULL,
  `selected_option_id` INT NULL DEFAULT NULL,
  `is_correct` TINYINT(1) NULL DEFAULT NULL,
  `points_earned` FLOAT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `attempt_id` (`attempt_id` ASC) VISIBLE,
  INDEX `question_id` (`question_id` ASC) VISIBLE,
  INDEX `selected_option_id` (`selected_option_id` ASC) VISIBLE,
  CONSTRAINT `student_answers_ibfk_1`
    FOREIGN KEY (`attempt_id`)
    REFERENCES `mylms`.`quiz_attempts` (`id`),
  CONSTRAINT `student_answers_ibfk_2`
    FOREIGN KEY (`question_id`)
    REFERENCES `mylms`.`questions` (`id`),
  CONSTRAINT `student_answers_ibfk_3`
    FOREIGN KEY (`selected_option_id`)
    REFERENCES `mylms`.`answer_options` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 94
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
