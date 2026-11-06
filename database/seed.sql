-- Starting data: the cities, the data source and the six health levels.
-- Safe to run again: new cities are added and nothing is deleted from the readings.
USE airwatch;

INSERT IGNORE INTO location (city_name, district, latitude, longitude) VALUES
 ('Kathmandu','Kathmandu',27.717200,85.324000),
 ('Pokhara','Kaski',28.209600,83.985600),
 ('Bhaktapur','Bhaktapur',27.671000,85.429800),
 ('Lalitpur','Lalitpur',27.658800,85.324700),
 ('Bharatpur','Chitwan',27.683300,84.433300),
 ('Biratnagar','Morang',26.452500,87.271800),
 ('Janakpur','Dhanusha',26.728800,85.926600),
 ('Nepalgunj','Banke',28.050000,81.616700),
 ('Dhangadhi','Kailali',28.683300,80.600000),
 ('Lumbini','Rupandehi',27.489500,83.279100),
 ('Dhankuta','Dhankuta',26.983300,87.350000),
 ('Surkhet','Surkhet',28.600000,81.633300),
 ('Dhulikhel','Kavrepalanchok',27.619600,85.538900),
 ('Ghorahi','Dang',28.040000,82.483300),
 ('Itahari','Sunsari',26.666700,87.283300),
 ('Gaur','Rautahat',26.766700,85.283300),
 ('Siraha','Siraha',26.654400,86.207800);

-- The live data source used by the collector
INSERT IGNORE INTO data_source (source_name, source_url) VALUES
 ('aqicn.org','https://api.waqi.info');

-- The six levels and messages. They are the same ones shown in the Week 6 document.
DELETE FROM health_category WHERE category_id > 0;
INSERT INTO health_category (aqi_min, aqi_max, label, message) VALUES
 (0,   50,  'Good', 'Air quality is good. You can go outside as usual.'),
 (51,  100, 'Moderate', 'Air quality is acceptable. People who are very sensitive to pollution should take it easy outdoors.'),
 (101, 150, 'Unhealthy for Sensitive Groups', 'Children, older people, and people with breathing problems should limit time outside.'),
 (151, 200, 'Unhealthy', 'Everyone should reduce outdoor activity. Wear a mask if you need to go out.'),
 (201, 300, 'Very Unhealthy', 'Avoid outdoor activity. Stay indoors if you can, and wear a mask outside.'),
 (301, 500, 'Hazardous', 'Health emergency. Stay indoors and avoid all outdoor activity.');