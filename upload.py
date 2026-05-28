#!/usr/bin/env python3

import argparse
import json
import pymysql
import os
import sys

def main():
  parser = argparse.ArgumentParser(description="Upload fallback telemetry JSON to database")
  parser.add_argument('file', help='Path to the telemetry.json fallback file')
  args = parser.parse_args()

  CONFIG_FILE = "config.json"
  if not os.path.exists(CONFIG_FILE):
    print(f"Error: {CONFIG_FILE} not found.")
    sys.exit(1)

  try:
    with open(CONFIG_FILE, "r") as f:
      config = json.load(f)
  except Exception as e:
    print(f"Error reading config: {e}")
    sys.exit(1)

  db_config = config.get("db_config")
  table = config.get("table", "telemetry")

  if not os.path.exists(args.file):
    print(f"Error: File {args.file} not found.")
    sys.exit(1)

  try:
    with pymysql.connect(**db_config) as conn:
      with conn.cursor() as cursor:
        count = 0
        with open(args.file, "r") as f:
          for line in f:
            line = line.strip()
            if not line:
              continue

            try:
              flat = json.loads(line)
            except json.JSONDecodeError:
              print("Warning: Skipping invalid JSON line.")
              continue

            if not flat:
              continue

            columns = sorted(flat.keys())
            sql = f"""
              INSERT INTO {table}
              ({",".join(columns)})
              VALUES
              ({",".join(["%s"] * len(columns))})
              ON DUPLICATE KEY UPDATE name=VALUES(name)
            """

            values = [flat.get(col) for col in columns]
            cursor.execute(sql, values)
            count += 1

        conn.commit()
        print(f"Successfully uploaded {count} records from {args.file}.")
  except Exception as e:
    print(f"An error occurred during upload: {e}")
    sys.exit(1)

if __name__ == "__main__":
  main()
