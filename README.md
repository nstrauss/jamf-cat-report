# jamf_cat_report.py  
Python tool to output Jamf Pro mobile device app catalog info. Written mostly to get installed app count - the number of iOS devices on which an app is installed. Default behavior (or `-all`) is to loop through all available mobile device apps in a Jamf Pro server and write data to CSV. 

```
 /\_/\
( o.o )
 > ^ <
```

Reported fields:
- id - Jamf Pro mobile device app ID. 
- name - App name. 
- main_category - Main app category.
- self_service_cat1-5 - Five Self Service categories. Ends up being first five API returns.
- featured - If the app is included under the featured category in Self Service.
- installed_count - Number of iOS devices on which an app is installed.
- used_licenses - Used license count. 
- remaining_licenses - Remaining license count. 
- total_licenses - Total available licenses. 
- price - Current price from App Store. Default is to return USD from US App Store.
- latest_release - Date of latest version release. 
- average_rating - Total average rating. Not rating of current version.
- bundle_id - App bundle ID.
- jamf_url - Jamf Pro mobile device app link based on provided URL in `config.json`.
- itunes_url - App Store URL pulled from Jamf Pro.  

Note: Only apps where device based VPP is enabled are included. Want more fields? Submit a PR! :)  

Required Jamf Pro privileges:
- Create, read, update, and delete for Advanced Mobile Device Searches
- Read for Mobile Device Apps

Requires requests for API calls. Use `pip install --user requests` to install if you need it.  

Change values in `config.json` as needed before running. iTunes API country code can be changed following ISO 3166-1 format (https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)  

To get app counts an advanced search is created per app, devices counted, and then search object deleted. This can increase advanced search count by a lot, but shouldn't impact the database since the advanced search object is temporary. Tested with python3 on macOS 10.13 and 10.14.  

```
--all                   Default behavior. Loop through all Jamf Pro mobile
                        device apps and output data to CSV in working
                        directory.

--app-id jamf_pro_app_id [jamf_pro_app_id ...]
                        Pass in a mobile device app ID. Multiple IDs can be
                        included separated by space. e.g. --app-id 101 110 605

--file-path path_to_file
                        Path to file with list of new line separated app IDs.

--disable-count         Disable count of number of iOS devices on which an app
                        is installed. Speeds up reporting by a lot.
                        installed_count will be None.

--retry                 Number of retry attempts to get advanced search data
                        after object is created. Usually used when Jamf Cloud
                        is slow to create search objects.

--version               Print version and exit.
```

Future plans:
- Add multithreading to return large catalogs more quickly.
- Include scope data.
- Allow app lookup by name.
- Output app data to session instead of CSV.
