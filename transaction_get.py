import pymongo

if __name__ == '__main__':
    client = pymongo.MongoClient('localhost', 27017)

    db = client.htn_stats

    data = {}
    cats = set()

    for transaction in db.transactions.find():
        customerID = transaction['customerId']
        customer = db.accountProfiles.find_one({'id': customerID, 'totalIncome': {'$exists': True}})
        if customer:
            if customer['totalIncome'] < 30000:
                if '30000' not in data.keys():
                    data['30000'] = {}
                if transaction['categoryTags'][0] not in data['30000'].keys():
                    data['30000'][transaction['categoryTags'][0]] = []
                data['30000'][transaction['categoryTags'][0]].append(transaction)
            elif customer['totalIncome'] < 70000:
                if '70000' not in data.keys():
                    data['70000'] = {}
                if transaction['categoryTags'][0] not in data['70000'].keys():
                    data['70000'][transaction['categoryTags'][0]] = []
                data['70000'][transaction['categoryTags'][0]].append(transaction)
            elif customer['totalIncome'] < 100000:
                if '100000' not in data.keys():
                    data['100000'] = {}
                if transaction['categoryTags'][0] not in data['100000'].keys():
                    data['100000'][transaction['categoryTags'][0]] = []
                data['100000'][transaction['categoryTags'][0]].append(transaction)
            else:
                if '100001' not in data.keys():
                    data['100001'] = {}
                if transaction['categoryTags'][0] not in data['100001'].keys():
                    data['100001'][transaction['categoryTags'][0]] = []
                data['100001'][transaction['categoryTags'][0]].append(transaction)
            cats.add(transaction['categoryTags'][0])
            print(cats)

    monthly = {'30000': {}, '70000': {}, '100000': {}, '100001': {}}
    for key in monthly.keys():
        for tag in data[key]:
            tag_sort = sorted(data[key][tag], key=lambda obj: obj['originationDateTime'])
            for i in tag_sort:
                date, _ = i['originationDateTime'].split('T')
                year, month, day = date.split('-')
                if year == '2019' and month == '08':
                    if i['categoryTags'][0] not in monthly[key].keys():
                        monthly[key][i['categoryTags'][0]] = []
                    monthly[key][i['categoryTags'][0]].append(i['currencyAmount'])
    monthly['date'] = '2019-08'
    # db.stats.insert_one(monthly)




