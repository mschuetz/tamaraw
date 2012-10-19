/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

DROP TABLE IF EXISTS enum_values;
CREATE TABLE enum_values (
  id int(11) NOT NULL AUTO_INCREMENT,
  type_id int(11) NOT NULL,
  name varchar(255) NOT NULL,
  PRIMARY KEY (id),
  KEY type_id (type_id),
  CONSTRAINT enum_values_ibfk_1 FOREIGN KEY (id) REFERENCES property_types (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS images;
CREATE TABLE images (
  id int(11) NOT NULL AUTO_INCREMENT,
  created_at timestamp DEFAULT now(),
  upload_group varchar(255) NOT NULL,
  s3_key varchar(255) NOT NULL,
  PRIMARY KEY (id),
  KEY s3_key (s3_key),
  KEY upload_group (upload_group),
  KEY created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS images_enums;
CREATE TABLE images_enums (
  image_id int(11) NOT NULL,
  enum_value_id int(11) NOT NULL,
  PRIMARY KEY (image_id,enum_value_id),
  KEY images_properties_ibfk_2 (enum_value_id),
  CONSTRAINT images_enums_ibfk_1 FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE,
  CONSTRAINT images_enums_ibfk_2 FOREIGN KEY (enum_value_id) REFERENCES enum_values (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS images_text;
CREATE TABLE images_text (
  image_id int(11) NOT NULL,
  property_type_id int(11) NOT NULL,
  value TEXT NOT NULL, 
  PRIMARY KEY (image_id,property_type_id),
  CONSTRAINT images_text_ibfk_1 FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE,
  CONSTRAINT images_text_ibfk_2 FOREIGN KEY (property_type_id) REFERENCES property_types (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS property_types;
CREATE TABLE property_types (
  id int(11) NOT NULL AUTO_INCREMENT,
  name varchar(255) NOT NULL,
  property_type enum('text','enum') NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- some defaults
insert into property_types (name, property_type) values ('description', 'text'), ('photographer', 'text'), ('artifact_type', 'enum');
insert into enum_values (type_id, name) values (3, 'coin'), (3, 'jewellery');
insert into images (s3_key) values('001.jpg');
insert into images_text (image_id, property_type_id, value) values (1, 1, 'Before the old man could answer, the boy recollected and triumphantly shoved his hand into a pouch under his bear-skin and pulled forth a battered and tarnished silver dollar.');
insert into images_enums (image_id, enum_value_id) values (1, 1);

