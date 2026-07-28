"""Measure recovery after an operator or managed database initiates failover."""
from __future__ import annotations
import argparse
import json
import time
import httpx

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--ready-url",required=True);parser.add_argument("--max-rto-seconds",type=int,default=300);parser.add_argument("--expected-version",default="");args=parser.parse_args()
    started=time.monotonic();attempts=0;last="unreachable"
    with httpx.Client(timeout=5) as client:
        while time.monotonic()-started<=args.max_rto_seconds:
            attempts+=1
            try:
                response=client.get(args.ready_url);last=f"HTTP {response.status_code}"
                if response.status_code==200:
                    payload=response.json()
                    if args.expected_version and payload.get("version") not in (None,args.expected_version):raise SystemExit("recovered endpoint reports unexpected version")
                    result={"recovered":True,"rto_seconds":round(time.monotonic()-started,2),"attempts":attempts,"checks":payload.get("checks",{})};print(json.dumps(result));return
            except (httpx.HTTPError,ValueError):pass
            time.sleep(2)
    print(json.dumps({"recovered":False,"rto_seconds":args.max_rto_seconds,"attempts":attempts,"last":last}));raise SystemExit(1)

if __name__=="__main__":main()
