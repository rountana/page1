Mongo db

start mogodb
   /Users/shaamsarath/Devstudio/projects/page1/start-mogodb.sh

open a shell connection
   mongosh

switch to the cache db
      use amadeus_cache

List collections
   show collections

Inspect cached entried=s
   db.api_responses.find().pretty()

Filter by endpoint
   db.api_responses.find({ endpoint: "/v3/shopping/hotel-offers" }).pretty()

lookup a specific cache key
   db.api_responses.findOne({ cache_key: "<hash from logs>" })

check TTL index and expiration info
   db.api_responses.getIndexes()

stop mongodb
   /Users/shaamsarath/Devstudio/projects/page1/services/stop-mongodb.sh

count items
    db.api_responses.countDocuments()
    db.api_responses.countDocuments({ endpoint: "/v3/shopping/hotel-offers" })

    count for each endpoint
        db.api_responses.aggregate([
            { $group: { _id: "$endpoint", count: { $sum: 1 } } },
            { $sort: { count: -1 } }
        ])
    non-expired
        db.api_responses.countDocuments({ 
        endpoint: "/v3/shopping/hotel-offers",
        expires_at: { $gt: new Date() }
        })
    expired items
        db.api_responses.countDocuments({ 
        expires_at: { $lt: new Date() }
        })

summary with counts
    db.api_responses.aggregate([
    {
        $group: {
        _id: "$endpoint",
        total: { $sum: 1 },
        expired: {
            $sum: {
            $cond: [{ $lt: ["$expires_at", new Date()] }, 1, 0]
            }
        },
        active: {
            $sum: {
            $cond: [{ $gt: ["$expires_at", new Date()] }, 1, 0]
            }
        }
        }
    },
    { $sort: { total: -1 } }
    ])