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

DROP TABLE IF EXISTS locations;
CREATE TABLE locations (
  id int(11) NOT NULL AUTO_INCREMENT,
  path varchar(255) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS pictures;
CREATE TABLE pictures (
  id int(11) NOT NULL AUTO_INCREMENT,
  name int(11) NOT NULL,
  location_id int(11) NOT NULL,
  PRIMARY KEY (id),
  KEY location_id (location_id),
  CONSTRAINT pictures_ibfk_1 FOREIGN KEY (location_id) REFERENCES locations (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS pictures_enums;
CREATE TABLE pictures_enums (
  picture_id int(11) NOT NULL,
  enum_value_id int(11) NOT NULL,
  PRIMARY KEY (picture_id,enum_value_id),
  KEY pictures_properties_ibfk_2 (enum_value_id),
  CONSTRAINT pictures_enums_ibfk_1 FOREIGN KEY (picture_id) REFERENCES pictures (id) ON DELETE CASCADE,
  CONSTRAINT pictures_enums_ibfk_2 FOREIGN KEY (enum_value_id) REFERENCES enum_values (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS pictures_text;
CREATE TABLE pictures_text (
  picture_id int(11) NOT NULL,
  property_type_id int(11) NOT NULL,
  value TEXT NOT NULL, 
  PRIMARY KEY (picture_id,property_type_id),
  CONSTRAINT pictures_text_ibfk_1 FOREIGN KEY (picture_id) REFERENCES pictures (id) ON DELETE CASCADE,
  CONSTRAINT pictures_text_ibfk_2 FOREIGN KEY (property_type_id) REFERENCES property_types (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS property_types;
CREATE TABLE property_types (
  id int(11) NOT NULL AUTO_INCREMENT,
  name varchar(255) NOT NULL,
  property_type enum('text','enum') NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
