USE airwatch;

INSERT IGNORE INTO location (city_name, district, latitude, longitude) VALUES
 ('Kathmandu','Kathmandu',27.717200,85.324000),
 ('Pokhara','Kaski',28.209600,83.985600),
 ('Bhaktapur','Bhaktapur',27.671000,85.429800),
 ('Lalitpur','Lalitpur',27.658800,85.324700),
 ('Bharatpur','Chitwan',27.683300,84.433300);

INSERT IGNORE INTO data_source (source_name, source_url) VALUES
 ('aqicn.org','https://api.waqi.info');

DELETE FROM health_category;
INSERT INTO health_category (aqi_min, aqi_max, label, message) VALUES
 (0,   50,  'Good', 'Air quality is good. You can go outside as usual.'),
 (51,  100, 'Moderate', 'Air quality is acceptable. People who are very sensitive to pollution should take it easy outdoors.'),
 (101, 150, 'Unhealthy for Sensitive Groups', 'Children, older people, and people with breathing problems should limit time outside.'),
 (151, 200, 'Unhealthy', 'Everyone should reduce outdoor activity. Wear a mask if you need to go out.'),
 (201, 300, 'Very Unhealthy', 'Avoid outdoor activity. Stay indoors if you can, and wear a mask outside.'),
 (301, 500, 'Hazardous', 'Health emergency. Stay indoors and avoid all outdoor activity.');
