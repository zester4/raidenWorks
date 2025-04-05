# test_redis.py
from upstash_redis import Redis
import os
from dotenv import load_dotenv

load_dotenv() # Load .env file

upstash_dsn = os.getenv('REDIS_DSN')

if not upstash_dsn:
    print("ERROR: REDIS_DSN not found in .env file.")
else:
    print(f"Attempting to connect using DSN (password masked): {upstash_dsn.split('@')[0]}:******@{upstash_dsn.split('@')[1]}")
    try:
        # Use from_url which handles DSN parsing including SSL for 'rediss://'
        r = upstash-redis.Redis.from_url(upstash_dsn, decode_responses=True)

        print("Pinging Upstash Redis...")
        response = r.ping() # This will raise ConnectionError on failure
        print(f"Ping Successful! Response: {response}")

        print("Setting key 'raiden_test'...")
        r.set('raiden_test', 'connection_ok')
        print("Getting key 'raiden_test'...")
        value = r.get('raiden_test')
        print(f"Value retrieved: {value}")

        if value == 'connection_ok':
            print("\nSUCCESS: Redis connection test passed.")
        else:
            print("\nWARNING: Ping worked but set/get failed.")

    except upstash-redis.exceptions.AuthenticationError:
         print("\nERROR: Connection failed - AuthenticationError (Incorrect Password?).")
    except redis.exceptions.ConnectionError as e:
        print(f"\nERROR: Connection failed - ConnectionError: {e}")
    except Exception as e:
        print(f"\nERROR: An unexpected error occurred: {type(e).__name__} - {e}")