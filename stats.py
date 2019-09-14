import requests
import json
import pymongo
import os

client = pymongo.MongoClient('localhost', 27017)

db = client.htn_stats

r = requests.post("https://api.td-davinci.com/api/raw-customer-data",
                  headers= {
                      'Authorization': os.getenv('TD_API_KEY')
                  })
data = json.loads(r.content.decode('utf-8'))
all_users = [data['result']['customers']]
print(data.keys())
while data:
    if 'errorMsg' in data.keys():
        print(data['errorMsg'])
    try:
        r = requests.post("https://api.td-davinci.com/api/raw-customer-data",
                          json={
                            'continuationToken': data['result']['continuationToken']
                          },
                          headers={
                              'Authorization': os.getenv('TD_API_KEY'),
                              'content-type': 'application/json'
                          })
        data = json.loads(r.content.decode('utf-8'))
        all_users += data['result']['customers']
        for user in data['result']['customers']:
            db.accountProfiles.insert_one(user)
    except:
        pass
db.accountProfiles.create_index('id')
# with open('data.json', 'w+') as file:
#     file.write(json.dumps(all_users))

