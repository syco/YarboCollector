#!/usr/bin/env python3

from yarbo import discover_yarbo, YarboLocalClient
import argparse
import asyncio
import json
import pymysql
import sys
import traceback

def flatten(obj, parent_key="", sep="_"):
  result = {}
  for key, value in obj.items():
    new_key = (f"{parent_key}{sep}{key}" if parent_key else key).replace('.', '_')

    if isinstance(value, dict):
      result.update(flatten(value, new_key, sep))

    elif isinstance(value, list):
      result[new_key] = json.dumps(value, ensure_ascii=False)

    else:
      result[new_key] = value

  return result


async def main():
  parser = argparse.ArgumentParser(description="YarboLink Telemetry Collector")
  parser.add_argument('--debug', action='store_true', help='Enable debug output')
  args = parser.parse_args()

  CONFIG_FILE = "config.json"
  with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

  robot_ip = config.get("ip")
  robot_sn = config.get("sn")

  if not robot_ip or not robot_sn:
    print("Scanning for Yarbo robots...", flush=True)
    robots = await discover_yarbo()

    if not robots:
      print("No robots found", flush=True)
      return

    print(f"Found: {robots}", flush=True)
    robot_ip = robots[0].broker_host
    robot_sn = robots[0].sn

  with open(config.get("fallback_log_file", "telemetry.json"), "ab") as fallback_log_file:
    with pymysql.connect(**config["db_config"]) as conn:
      with conn.cursor() as cursor:
        table = config.get("table", "telemetry")

        async with (YarboLocalClient(broker=robot_ip, sn=robot_sn)) as client:
          print(f"Client open", flush=True)
          await client.start_polling(interval_seconds=10.0)
          last_flat = None
          async for telemetry in client.watch_telemetry():
            obj = telemetry.__dict__
            flat = flatten(obj)

            try:
              if not flat:
                continue

              if args.debug:
                if last_flat is not None:
                  diff = {k: v for k, v in flat.items() if v != last_flat.get(k)}
                  if diff:
                    print(f"Diff: {diff}", flush=True)
                last_flat = flat

              columns = sorted(flat.keys())

              sql = f"""
                INSERT INTO {table}
                ({",".join(columns)})
                VALUES
                ({",".join(["%s"] * len(columns))})
                ON DUPLICATE KEY UPDATE name=VALUES(name)
              """

              values = []
              values.append([flat.get(col) for col in columns])
              cursor.executemany(sql, values)

            except Exception as err:
              print(f"Unexpected {err=}, {type(err)=}", flush=True)
              print(traceback.format_exc(), flush=True)

              json_line = json.dumps(flat) + '\n'
              fallback_log_file.write(json_line.encode('utf-8'))
              fallback_log_file.flush()

if __name__ == "__main__":
  asyncio.run(main())
