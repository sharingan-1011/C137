import pathlib
import requests

p = pathlib.Path(".")
print("iterdir exists:", hasattr(p, "iterdir"))
print("rglob exists:", hasattr(p, "rglob"))

print("requests.HTTPError:", hasattr(requests, "HTTPError"))
print("requests.exceptions.HTTPError:", hasattr(requests.exceptions, "HTTPError"))
print("requests.exceptions.RequestException:", hasattr(requests.exceptions, "RequestException"))