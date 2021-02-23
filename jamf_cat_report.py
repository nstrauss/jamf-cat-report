#!/usr/bin/python3

"""Python tool to output Jamf Pro mobile device app catalog info."""

import argparse
import csv
import datetime
import itertools
import json
import os
import re
import sys
import time
import uuid
from xml.etree import ElementTree as ET

import requests

__version__ = "0.4"


def import_conf():
    """Get Jamf Pro URL, API user, and pass from config file."""
    global WORKING_DIR
    WORKING_DIR = os.path.dirname(os.path.abspath(__file__))
    config_json = WORKING_DIR + "/" + "config.json"
    with open(config_json) as json_data:
        config = json.load(json_data)

    global JAMF_URL
    global JAMF_API_URL
    global JAMF_API_USER
    global JAMF_API_PASS
    global ITUNES_CC
    global ITUNES_API_URL
    JAMF_URL = config["jamf"]["url"]
    JAMF_API_URL = JAMF_URL + "/JSSResource/"
    JAMF_API_USER = config["jamf"]["user"]
    JAMF_API_PASS = config["jamf"]["pass"]
    ITUNES_CC = config["itunes"]["country_code"]
    ITUNES_API_URL = "https://itunes.apple.com/" + ITUNES_CC + "/lookup?id="


def jamf_api_get(resource):
    """Basic function for Jamf API get."""
    api_resource = JAMF_API_URL + resource
    headers = {"Accept": "application/json"}
    r = requests.get(api_resource, auth=(JAMF_API_USER, JAMF_API_PASS), headers=headers)

    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("Error: " + str(e))
        sys.exit(1)

    raw_json = r.json()
    return raw_json


def jamf_api_search_get(resource, retry_count=5):
    """Function for Jamf API advanced search get. Max retries can be incremented
    as needed based on speed of API advanced search object creation."""
    headers = {"Accept": "application/json"}

    # Jamf Pro API can be slow to create advanced search objects
    # Wait 10 seconds before next attempt. Default is 5 attempts
    # Use --retry flag to increase attempts
    time.sleep(5)
    for _ in range(retry_count + 1):
        r = requests.get(resource, auth=(JAMF_API_USER, JAMF_API_PASS), headers=headers)
        if r.status_code != 200:
            print(f"Get Error: {r.status_code} {resource}")
            time.sleep(10)
        else:
            break

    try:
        raw_json = r.json()
    except json.decoder.JSONDecodeError:
        raw_json = None

    return raw_json


def jamf_api_search_delete(resource, retry_count=5):
    """Function for Jamf API advanced search deletion. Max retries can be incremented
    as needed based on speed of API advanced search object creation."""
    headers = {"Accept": "application/json"}

    # Jamf Pro API can be slow to create advanced search objects
    # Wait 10 seconds before next attempt. Default is 5 attempts
    # Use --retry flag to increase attempts
    time.sleep(5)
    for _ in range(retry_count + 1):
        r = requests.delete(
            resource, auth=(JAMF_API_USER, JAMF_API_PASS), headers=headers
        )
        if r.status_code != 200:
            print(f"Delete Error: {r.status_code} {resource}")
            time.sleep(10)
        else:
            break


def jamf_api_advancedsearch(app_id, bundle_id, retry_count=3):
    """Create advanced search object, get device count data, and delete."""
    api_resource = JAMF_API_URL + "advancedmobiledevicesearches/id/0"
    random_gen = uuid.uuid4()

    # Construct XML
    search = ET.Element("advanced_mobile_device_search")
    ET.SubElement(search, "name").text = str(f"api_tmp_id_{app_id}_{random_gen}")
    criteria = ET.SubElement(search, "criteria")
    ET.SubElement(criteria, "size").text = str("1")
    criterion = ET.SubElement(criteria, "criterion")
    ET.SubElement(criterion, "name").text = str("App Identifier")
    ET.SubElement(criterion, "priority").text = str("0")
    ET.SubElement(criterion, "and_or").text = str("and")
    ET.SubElement(criterion, "search_type").text = str("is")
    ET.SubElement(criterion, "value").text = str(f"{bundle_id}")
    xml_raw = ET.ElementTree(search)
    xml_root = xml_raw.getroot()
    xml_data = ET.tostring(xml_root)
    # Create advanced search
    post_search = requests.post(
        api_resource, auth=(JAMF_API_USER, JAMF_API_PASS), data=xml_data
    )

    try:
        post_search.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("Create Error: " + str(e))
        sys.exit(1)

    # Get generated advanced search ID from response
    raw_xml = ET.fromstring(post_search.content)
    tmp_search_id = raw_xml.find("id").text

    # Get results of newly created advanced search
    tmp_resource = JAMF_API_URL + "advancedmobiledevicesearches/id/" + tmp_search_id
    search_data = jamf_api_search_get(tmp_resource, retry_count)

    # Count number of devices in returned JSON
    count = str("0")
    if search_data is not None:
        count = len(search_data["advanced_mobile_device_search"]["mobile_devices"])

    # Delete advanced search object
    jamf_api_search_delete(tmp_resource, retry_count)

    return str(count)


def get_adam_id(itunes_url):
    """Regex to get app adam ID from iTunes URL."""
    try:
        pattern = re.compile(r"id(\d+)(?=\?)")
        adam_id = str(pattern.findall(itunes_url)[0])
    except IndexError:
        pass

    try:
        pattern = re.compile(r"id(\d+)")
        adam_id = str(pattern.findall(itunes_url)[0])
    except (IndexError, TypeError):
        pass

    if adam_id.isdigit() is False:
        adam_id = None
    return adam_id


def itunes_api_get(adam_id):
    """Basic function for iTunes API get."""
    api_resource = ITUNES_API_URL + adam_id
    r = requests.get(api_resource)

    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("Error: " + str(e))
        sys.exit(1)

    raw_json = r.json()
    return raw_json


def list_apps():
    """Get a list of sorted Jamf Pro mobile device app IDs."""
    app_list = jamf_api_get("mobiledeviceapplications")
    app_id_list = []
    for app in app_list["mobile_device_applications"]:
        app_id_list.append(str(app["id"]))

    app_id_list.sort()
    return app_id_list


def get_solo_app(jamf_id):
    """Look up an invididual mobile device app based on ID."""
    app_info = jamf_api_get("mobiledeviceapplications/id/" + jamf_id)
    return app_info


def get_ss_cats(cat_data):
    """Get up to five Self Service categories."""
    cats_keys = ["cat1", "cat2", "cat3", "cat4", "cat5"]
    cats_values = []
    for cat in cat_data:
        cats_values.append(str(cat["name"]))
    cat_dict = dict(itertools.zip_longest(cats_keys, cats_values))
    return cat_dict


def main():
    """Do the main thing here."""
    # Import config.json
    import_conf()

    # Available arguments. Only one can be used at a time.
    parser = argparse.ArgumentParser(
        description="Tool to output Jamf Pro mobile device app catalog info."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all",
        default="--all",
        action="store_true",
        help="Default behavior. Loop through all Jamf Pro mobile device apps and "
        "output data to CSV in working directory.",
    )
    group.add_argument(
        "--app-id",
        metavar="jamf_pro_app_id",
        nargs="+",
        help="Pass in a mobile device app ID. "
        "Multiple IDs can be included separated by space. e.g. --app-id 101 110 605",
    )
    group.add_argument(
        "--file-path",
        metavar="path_to_file",
        help="Path to file with list of new line separated app IDs.",
    )
    parser.add_argument(
        "--enable-count",
        action="store_true",
        help="Enable count of number of iOS devices on which an app is installed. "
        "Slows down reporting significantly.",
    )
    parser.add_argument(
        "--retry",
        action="store",
        type=int,
        default=3,
        nargs="?",
        help="Number of retry attempts to get advanced search data after object is created. "
        "Usually used when Jamf Cloud is slow to create search objects.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="Print version and exit.",
    )
    arg = parser.parse_args()

    # Get mobile device app ID list. Default is all from Jamf Pro
    if arg.app_id is not None:
        app_ids = []
        for app_id in arg.app_id:
            app_ids.append(str(app_id))
    elif arg.file_path is not None:
        app_ids = []
        with open(arg.file_path):
            lines = [line.rstrip("\n") for line in open(arg.file_path)]
        for app_id in lines:
            app_ids.append(str(app_id))
    else:
        app_ids = list_apps()

    # CSV header fields
    fields = [
        "id",
        "name",
        "main_category",
        "self_service_cat1",
        "self_service_cat2",
        "self_service_cat3",
        "self_service_cat4",
        "self_service_cat5",
        "featured",
        "installed_count",
        "used_licenses",
        "remaining_licenses",
        "total_licenses",
        "free",
        "price",
        "latest_release",
        "average_rating",
        "bundle_id",
        "jamf_url",
        "jamf_itunes_url",
        "apple_app_url",
    ]

    # Write CSV file and headers
    now = datetime.datetime.now()
    csv_file = (
        WORKING_DIR + "/" + now.strftime("%Y-%m-%d-%S") + "-jamf_cat_report" + ".csv"
    )
    with open(csv_file, "w") as f:
        w = csv.writer(f, delimiter=",")
        w.writerow(fields)

    # Loop through mobile device app IDs, append data to CSV
    for app_id in app_ids:
        app = get_solo_app(app_id)
        app_data = app["mobile_device_application"]
        device_vpp = app_data["vpp"]["assign_vpp_device_based_licenses"]

        # Device VPP enabled must be true
        if device_vpp is True:
            # Parse data from JSON
            general_data = app_data["general"]
            name = str(general_data["name"])
            main_category = str(general_data["category"]["name"])
            bundle_id = str(general_data["bundle_id"])
            jamf_itunes_url = str(general_data["itunes_store_url"])
            jps_url = JAMF_URL + "/mobileDeviceApps.html?id=" + app_id

            # Get Self Service categories - max five
            ss_data = app_data["self_service"]
            ss_featured = str(ss_data["feature_on_main_page"])
            ss_cats_data = ss_data["self_service_categories"]
            cat_dict = get_ss_cats(ss_cats_data)
            ss_cat1 = str(cat_dict["cat1"])
            ss_cat2 = str(cat_dict["cat2"])
            ss_cat3 = str(cat_dict["cat3"])
            ss_cat4 = str(cat_dict["cat4"])
            ss_cat5 = str(cat_dict["cat5"])

            # Get VPP data
            vpp_data = app_data["vpp"]
            used_licenses = str(vpp_data["used_vpp_licenses"])
            remaining_licenses = str(vpp_data["remaining_vpp_licenses"])
            total_licenses = str(vpp_data["total_vpp_licenses"])

            # Get device count
            if arg.enable_count is True:
                installed_count = jamf_api_advancedsearch(app_id, bundle_id, arg.retry)
            else:
                installed_count = str("0")

            # Get iTunes API data
            adam_id = get_adam_id(jamf_itunes_url)
            itunes_raw = itunes_api_get(adam_id)
            try:
                itunes_data = itunes_raw["results"][0]
                itunes_price = float(itunes_data["price"])
                if itunes_price > 0:
                    free = "False"
                else:
                    free = "True"
                itunes_release_date = str(itunes_data["currentVersionReleaseDate"])
                apple_itunes_url = str(itunes_data["trackViewUrl"])
            except Exception:
                itunes_price = "None"
                itunes_release_date = "None"

            try:
                itunes_avg_rating = str(itunes_data["averageUserRating"])
            except Exception:
                itunes_avg_rating = "None"

            # Write data to CSV
            cat_data = [
                app_id,
                name,
                main_category,
                ss_cat1,
                ss_cat2,
                ss_cat3,
                ss_cat4,
                ss_cat5,
                ss_featured,
                installed_count,
                used_licenses,
                remaining_licenses,
                total_licenses,
                free,
                itunes_price,
                itunes_release_date,
                itunes_avg_rating,
                bundle_id,
                jps_url,
                jamf_itunes_url,
                apple_itunes_url,
            ]

            with open(csv_file, "a") as f:
                w = csv.writer(f, delimiter=",")
                w.writerow(cat_data)


if __name__ == "__main__":
    main()
