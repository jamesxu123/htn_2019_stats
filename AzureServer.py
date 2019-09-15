# Server Setup with flask
# Importing module
import datetime
import requests
import json
import time
import flask
from flask_cors import CORS
import base64
import re
import math

# Function to return spendings from receipt using a combination of azure vision apis
app = flask.Flask(__name__)
CORS(app)


@app.route('/getCategories')
def getCategories():
    return json.dumps([
        "food",
        "snacks",
        "beverages",
        "pants",
        "shirts",
        "shoes",
        "skirts",
        "dresses",
        "coats",
        "electronics",
        "tools",
        "furniture",
        "cleaning supplies",
        "medicine",
        "sosmetics",
        "office supplies",
        "toys",
        "Unknown"
    ])


def bingSearch(
        search):  # Gets top result image, and checks our ML for category, then returns category prediction or None
    endPoint = "https://api.cognitive.microsoft.com/bing/v7.0/images/search"
    key = ""
    headers = {"Ocp-Apim-Subscription-Key": key}
    data = {"safeSearch": "Strict", "q": search, "size": "Medium"}
    req = requests.get(endPoint, params=data, headers=headers)
    if not req.json().get("value"):
        return None

    items = req.json()["value"]
    checking = 0
    while checking < 4:
        image = items[checking]["contentUrl"]
        if requests.get(image).status_code == 200:  # this one works
            # Match that image to our DB
            predictionUrl = "https://northcentralus.api.cognitive.microsoft.com/customvision/v3.0/Prediction/54549c5a-b8e6-4371-bfa3-b55b4ca4d352/classify/iterations/Iteration2/url"
            headers = {"Prediction-Key": "", "Content-Type": "application/json"}
            res = requests.post(predictionUrl, data=json.dumps({"Url": image}), headers=headers)

            # Get prediction
            product = res.json()
            if product.get("predictions") and product["predictions"][0]["probability"] > 0.7:
                print(search, product["predictions"][0]["probability"])
                return product["predictions"][0]
        checking += 1

    if len(items) > checking:
        return items[checking]["contentUrl"]

    return None


@app.route('/receiptRead', methods=['POST'])
def receiptRead():
    # image = open("rec.jpg", "rb").read() #
    image = flask.request.files["receipt"]

    if not image:
        print("Wrong format")
        return "wrong format"

    # Normal variables
    endPoint = "https://receiptread.cognitiveservices.azure.com/"
    link = endPoint + "/vision/v2.0/recognizeText?mode=Printed"  # "/vision/v1.0/ocr" #"/vision/v1.0/analyze"#[?visualFeatures][&details][&language]"
    key = ""

    # Request
    heads = {"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/octet-stream"}
    startProccess = requests.post(link, data=image, headers=heads)

    # Handle response
    items = []
    if startProccess.status_code == 202:
        linkID = startProccess.headers["Operation-Location"]
        print("Recieved ID", linkID)

        finalResult = None
        while not finalResult:
            tempReq = requests.get(linkID, headers={"Ocp-Apim-Subscription-Key": key})
            if tempReq.status_code == 200 and tempReq.json()["status"] == "Succeeded":
                finalResult = tempReq

        results = finalResult.json()["recognitionResult"]["lines"]
        lineNumber = 0
        lastTaken = 0
        items = []
        for result in results:
            text = result["text"]
            print(text)
            if text.lower().find("total") > -1:
                break

            se = re.search("[0-9]+\.[0-9]{2}", text.lower())
            if se:
                cost = float(se.group())
                print("Found cost at", cost)

                # Backtrack until we find correct item
                curNumber = lineNumber - 1
                while curNumber >= 0 and curNumber > lastTaken:
                    oldLine = results[curNumber]["text"]
                    for num in range(10):
                        oldLine = oldLine.replace(str(num), "")
                    if len(oldLine) > 3:
                        items.append([oldLine, cost])
                        print("Answer", oldLine, cost)
                        break
                    curNumber -= 1
            lineNumber += 1

        for item in items:
            print(item)
    else:
        print("Request did not send right")
        return

    print("Done with getting items", items)
    newPurchases = []  # [item name, item category, money spent]
    for item in items:
        # Grab best image result for that word
        product = bingSearch(item[0])
        if product:  # preeetty sure
            newPurchases.append([item[0], product["tagName"], item[1]])
        else:
            newPurchases.append([item[0], "Unknown", item[1]])

    return json.dumps(newPurchases)


@app.route('/detectAnomalies')
def detectAnomalies():
    dataReq = requests.get("http://dallas.masseyhacks.ca:9000/getReceipt").json()
    data = []  # Loaded player receipts for up to a week ago like newPurchases
    dataOld = []  # Loaded player receipts for previous week
    for transaction in dataReq:  # Load data in
        if len(transaction["originationDateTime"]) == 20:
            transaction["originationDateTime"] += ".000"
        transaction["originationDateTime"] = transaction["originationDateTime"][:-8] + ":00Z"

        date = datetime.datetime.strptime(transaction["originationDateTime"], '%Y-%m-%dT%H:%M:%SZ')
        if (date.today() - date).days < 7:  # New data
            data += [[transaction["originationDateTime"], transaction["details"]]]
        elif (date.today() - date).days < 14:
            dataOld += [transaction["details"]]

    # Setting up an older grid with identical methods for comparison
    oldGrid = {}
    # for item in data:
    #    if not oldGrid.get(item[2]):
    #        oldGrid[item[2]] = 0
    #    oldGrid[item[2]] += item[1]

    # Calculating category costs for this week
    grid = {}
    anomalyGrid = {"maxAnomalyRatio": 0.25, "sensitivity": 95, "granularity": "yearly", "series": []}
    anamolyRef = []
    messages = []
    ind = 0
    for transaction in data[::-1]:
        for item in transaction[1]:
            if not grid.get(item[2]):
                grid[item[2]] = 0
            grid[item[2]] += item[1]
            newTime = datetime.datetime(ind + 1972, 1, 1)
            newTime = newTime.strftime("%Y-%m-%dT%H:%M:%SZ")

            anomalyGrid["series"].append({"timestamp": newTime, "value": item[1]})
            anamolyRef.append(item[0])
            ind += 1

    # Checking for anamolies in our recent purchases
    if len(anamolyRef) >= 12:
        print("Checking anamolies")
        anamolyEndPoint = "https://suggestionresult.cognitiveservices.azure.com/anomalydetector/v1.0/timeseries/entire/detect"
        headers = {"Content-Type": "application/json", "Ocp-Apim-Subscription-Key": ""}
        req = requests.post(anamolyEndPoint, data=json.dumps(anomalyGrid), headers=headers).json()
        # Constructing anomaly messages
        for a in range(len(req["isPositiveAnomaly"])):
            if req["isAnomaly"][a]:
                anom = anamolyRef[a]
                print(anom, "is an anomally")
                messages.append("Your purchase of " + anom + " for $" + str(
                    anomalyGrid["series"][a]['value']) + " is an anomally, you might want to reconsider!")

    # Loop through this week's receipts and see if we need new messages
    for category in grid:
        if grid[category] >= (oldGrid.get(category) or 5):
            messages.append("You have spent more money on " + category + " than usual, you better slow down.")

    # order it for client
    o = list(grid.keys())

    def fakeSort(e):
        return anomalyGrid["series"][o.index(e)]["value"]

    ordered = o[:]
    ordered.sort(key=fakeSort)

    # Send data back
    return json.dumps({"Messages": messages, "Grid": grid, "Old Grid": oldGrid, "Order": json.dumps(ordered)})

# detectAnomalies()
# print(receiptRead())
