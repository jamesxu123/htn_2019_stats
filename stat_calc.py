import pymongo
import multiprocessing

client = pymongo.MongoClient('localhost', 27017)

db = client.htn_stats

totalIncome = 0
users = 0

for acc in db.accountProfiles.find():
    if 'totalIncome' in acc.keys():
        totalIncome += acc['totalIncome']
        users += 1
print(totalIncome / users, users)