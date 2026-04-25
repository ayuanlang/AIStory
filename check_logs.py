import os
import sys

def main():
    print("Run this on the remote server via SSH shell:")
    print("journalctl -u aistory-backend -n 50 --no-pager | grep -i DB")

if __name__ == "__main__":
    main()