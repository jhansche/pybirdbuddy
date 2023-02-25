import asyncio
import json

from birdbuddy.client import BirdBuddy

bb = BirdBuddy()
# Redirect output to schema.txt file
with open('schema.json', 'w') as f:
    json.dump(asyncio.run(bb.dump_schema()), f, indent=2)
