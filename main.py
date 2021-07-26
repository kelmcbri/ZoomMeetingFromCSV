import jwt
from jwt import encode
import requests
import json
from time import time
import csv
from datetime import datetime


"""
Load the keys from config.json file
The config.json file looks like this:
{
  "API_KEY": "yourkeyhere",
  "API_SEC": "yoursecrethere",
  "inputFile: "CSV path/filename with class info",
  "outputFile": "JSON path/filename with combined saba zoom info"
}
"""
with open('./config.json', 'r') as reader:
    try:
        config = json.load(reader)
        API_KEY = config["API_KEY"]
        API_SEC = config["API_SEC"]
        inputFile = config["inputFile"]
        outputFile = config["outputFile"]
    except:
        print("An exception occured reading in the config.json file.")

# Generate a token using the pyjwt library
def generateToken():
    token = jwt.encode(
        # Create a payload of the token containing API Key & expiration time
        {'iss': API_KEY, 'exp': time() + 5000},
        # Secret used to generate token signature
        API_SEC,
        # Specify the hashing alg
        algorithm='HS256'
        # Convert token to utf-8
    )
    return token
    # send a request with headers including a token

""" Read in list of meetings from saba file
    Create Array of meetings to be created on zoom

Input file is determined by "inputFile" field in ./config.json file.
The input file must be in CSV format.

"""
def getCSV():
    meetingDetails = []

    with open(inputFile) as csvfile:
        csvReader = csv.DictReader(csvfile)
        for rows in csvReader:
            startDate = rows["startDate"]
            classStartTime = rows["startTime"]
            startTimeSplit = classStartTime.split()
            meetingStartDateTime = (startDate + ' ' + startTimeSplit[0] + ' ' + startTimeSplit[1])
            meetingStart = datetime.strptime(meetingStartDateTime, "%d-%b-%Y %I:%M:%S %p")
            startTime = meetingStart.strftime("%Y-%m-%dT%H:%M:%S")
            classLocation = rows["location"]
            locationSplit = classLocation.split()
            timezone = ""
            if locationSplit[1] == "Eastern":
                    timezone = "America/New_York"
            if locationSplit[1] == "Central":
                    timezone = "America/Chicago"
            if locationSplit[1] == "Mountain":
                    timezone = "America/Denver"
            if locationSplit[1] =="Pacific":
                    timezone = "America/Los_Angeles"

            meetingDetails.append(
                {
                "tracking_fields": [
                                    {"field": "CLASS_ID",
                                    "value": rows["CLASS_ID"]
                                    }],
                "Saba_ID": rows["CLASS_ID"],
                "topic": rows["topic"],
                "type": 2,
                "host": rows["host"],
                "start_time": (startTime),
                "agenda": "",
                "schedule_for": "",
                "recurrence": {"type": 1,
                             "repeat_interval": 1
                             },
                "timezone":(timezone),
                "duration":rows["duration"],
                "settings": {"host_video": "true",
                             "participant_video": "true",
                             "join_before_host": "False",
                             "jbh_time": 5,
                             "mute_upon_entry": "False",
                             "watermark": "true",
                             "audio": "both",
                             "auto_recording": "none",
                             "waiting_room": "False",
                             "alternative_hosts": "",
                             "alternative_hosts_email_notification": "False"
                             }
                })

        #print(meetingDetails)
        return(meetingDetails)

# Check to be sure all the hosts are zoom registered with paid license
def checkLicense(meetingsList):
    headers = {'authorization': 'Bearer %s' % generateToken()}
    print("\nChecking each instructor to see if they are a Zoom Host: \n")

    for eachMeeting in meetingsList:
        zoomUser = eachMeeting['host']
        url = "https://api.zoom.us/v2/users/" + str(zoomUser)
        payload = {}
        hostStatus = "True"
        try :
            response = requests.request("GET", url, headers=headers, data=payload)
            data=json.loads(response.text)
            if data["type"] != 2 :
                print("\n*** " + (zoomUser) + " is a free license Zoom user in this account. \n")
                hostStatus = "False"
            else :
                print(".")
        except  :
            print("\n*** " + (zoomUser) + " is not in this account's Zoom user list. \n" )
            hostStatus = "False"
    return(hostStatus)

# Function to create meeting
def createMeetings(meetingsList):
    headers = {'authorization': 'Bearer %s' % generateToken(),
               'content-type': 'application/json'}
    meetingsReport = []
    for eachMeeting in meetingsList:
        user = eachMeeting['host']
        response = requests.post(
            f'https://api.zoom.us/v2/users/{user}/meetings',
                headers=headers,
                data=json.dumps(eachMeeting))

        response_json_object = json.loads(response.text)
        response_json_object["Saba_ID"] = eachMeeting["Saba_ID"]
        meetingsReport.append(
            {
            "Saba_ID":response_json_object["Saba_ID"],
            "Zoom_UUID":response_json_object["uuid"],
            "Zoom_ID":response_json_object["id"],
            "start_url":response_json_object["start_url"],
            "join_url":response_json_object["join_url"]
            })

        print("Created Zoom Meeting ID" + str(response_json_object["id"]) +
              " with Saba_ID " + response_json_object["Saba_ID"])
    return(meetingsReport)

#import meeting info from csv file
meetingsList = getCSV()

# Creat a new Zoom meeting for each meeting read in from csv file
# Generate meetine report that links zoom info with Saba Class ID
# If hosts all have Zoom paid licenses, generate Zoom Meetings
if checkLicense(meetingsList) == "True" :
    meetingsReport = createMeetings(meetingsList)
    # Save Meetings Report to JSON file
    try :
        with open((outputFile), 'w', encoding='utf-8') as f:
            json.dump(meetingsReport, f, ensure_ascii=False, indent=2)
        print("Output File " + str(outputFile) + " with Saba-Zoom info created. \n")
    except :
        print("*** Failed to write output File. \n")
else:
    print("*** No Zoom meetings were created. Correct Hosts in input file and run again. \n")
