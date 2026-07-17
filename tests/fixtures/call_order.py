from app import client

client.request(timeout=1, method="GET", url="/")
