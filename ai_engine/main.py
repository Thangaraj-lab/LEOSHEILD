import argparse
import os

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Start the local LEO Shield inspection API")
    parser.add_argument("--host", default=os.getenv("LEO_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("LEO_PORT", "8001")))
    parser.add_argument("--tls-cert", help="Certificate trusted by the phone for timed camera capture")
    parser.add_argument("--tls-key", help="Private key for --tls-cert")
    args = parser.parse_args()
    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error("--tls-cert and --tls-key must be supplied together")
    if args.host not in ("127.0.0.1", "::1", "localhost") and not os.getenv("LEO_API_TOKEN"):
        parser.error("LAN binding requires LEO_API_TOKEN")
    uvicorn.run("ai_engine.api.app:app", host=args.host, port=args.port, limit_concurrency=16,
                workers=1, access_log=False, ssl_certfile=args.tls_cert, ssl_keyfile=args.tls_key)


if __name__ == "__main__":
    main()
