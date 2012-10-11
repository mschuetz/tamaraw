#!/bin/bash

DB=pictures_$(pwgen 4 -1)
echo "create database $DB" | mysql -u root
MYSQL="mysql -u root $DB" 
$MYSQL < pictures.sql
LOC=$(mktemp -d /tmp/abcdeXXXX)
echo "insert into locations (path) values ('$LOC')" | $MYSQL

echo database: localhost/$DB
echo location: $LOC