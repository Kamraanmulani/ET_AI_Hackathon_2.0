from pymongo import MongoClient
db = MongoClient('mongodb://localhost:27017/').pragyan_ppi
db.documents.update_many({'ingestion.state': 'extracted'}, {'$set': {'ingestion.state': 'indexed'}})
print("Done")
