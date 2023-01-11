import asyncio
import pprint

from birdbuddy.client import BirdBuddy

bb = BirdBuddy(email=None, password=None)
# Redirect output to schema.txt file
pprint.pprint({"data": asyncio.run(bb.dump_schema())})
