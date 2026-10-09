-- MySQL schema for the LPP price monitoring project
-- MAP and LPP are in INR. The `violation` table is created automatically by price_monitoring.py.

create database map_projectDB;
use map_projectdb;

create table SKU(
Product_number varchar(20),
SKU varchar(20) primary key);

create table Product_Line(
Product_Line varchar(50),
SKU varchar(20),
Sub_category varchar(20),
Primary key(Product_Line,SKU),
FOREIGN KEY (SKU) REFERENCES SKU(SKU));


create table Price_List(
Product_Line varchar(50),
SKU varchar(20),
MAP decimal(10,2),
LPP decimal(10,2),
foreign key (Product_Line) references Product_Line(Product_Line),
foreign key (SKU) references SKU(SKU));

create table Seller_Mapping(
Seller_Name varchar(100) primary key,
Homologated_Name varchar(100));

create table Promotion(
Product_Line varchar(50),
SKU Varchar(20),
Season varchar(10),
Promotion Varchar(50));



create table Seller(
Seller_Name varchar(50),
SKU varchar(20),
Region varchar(20),
Advertised_Price decimal(10,2),   -- local currency, as collected
Marketplace varchar(100),
Screenshot varchar(500),
Live_Link varchar(500),
Last_Time_Collected timestamp,
foreign key (SKU) references SKU(SKU),
foreign key (Seller_Name) references Seller_Mapping(Seller_Name));

create table Price_Monitoring(
SKU varchar(20),
Violation_date date,
Product_Line varchar(50),
Category varchar(50),
Sub_Category varchar(50),
Region varchar(50),
Marketplace varchar(100),
Seller_Name varchar(50),
Homologated_Name varchar(50),
Map_Price decimal(10,2),
LPP decimal(10,2),
Advertised_Price decimal(10,2),   -- converted to INR
season varchar(20),
Promotional_Price decimal(10,2),
foreign key (SKU) references SKU(SKU));
