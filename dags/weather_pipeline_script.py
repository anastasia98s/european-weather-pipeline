
import urllib.request
import json
import csv
import os
import logging
import psycopg

# Logging konfigurieren
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

cities = [
    {"city": "Berlin", "latitude": 52.52, "longitude": 13.405},
    {"city": "Paris", "latitude": 48.8566, "longitude": 2.3522},
    {"city": "Rome", "latitude": 41.9028, "longitude": 12.4964},
]

def main():
    logging.info("Pipeline started")

    # 1. Extract
    weather_records = []

    for city in cities:
        logging.info("Fetching weather for %s", city["city"])

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={city['latitude']}"
            f"&longitude={city['longitude']}"
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
        )

        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        current = data["current"]

        record = {
            "city": city["city"],
            "timestamp": current["time"],
            "temperature_c": current["temperature_2m"],
            "humidity_percent": current["relative_humidity_2m"],
            "wind_speed_kmh": current["wind_speed_10m"],
        }

        # 2. Data quality checks
        assert record["city"]
        assert record["temperature_c"] is not None
        assert record["humidity_percent"] is not None
        assert 0 <= record["humidity_percent"] <= 100
        assert record["wind_speed_kmh"] is not None

        weather_records.append(record)

    logging.info("Data quality checks passed: %s records", len(weather_records))

    # 3. Save CSV
    os.makedirs("data", exist_ok=True)

    with open("data/weather.csv", "w", newline="", encoding="utf-8") as file:
        fieldnames = [
            "city",
            "timestamp",
            "temperature_c",
            "humidity_percent",
            "wind_speed_kmh",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(weather_records)

    logging.info("CSV saved to data/weather.csv")

    # 4. Load PostgreSQL
    password = os.environ["WEATHER_DB_PASSWORD"]

    with psycopg.connect(
        host="host.docker.internal",
        port=5432,
        dbname="weather_pipeline",
        user="postgres",
        password=password,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO weather_raw (
                    city, temperature_c, humidity_percent,
                    observed_at, wind_speed_kmh
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (city, observed_at) DO NOTHING
                """,
                [
                    (
                        r["city"],
                        r["temperature_c"],
                        r["humidity_percent"],
                        r["timestamp"],
                        r["wind_speed_kmh"],
                    )
                    for r in weather_records
                ],
            )

            logging.info("Raw data loaded")

            cursor.execute(
                """
                INSERT INTO weather_staging (
                    city, temperature_c, humidity_percent,
                    observed_at, wind_speed_kmh
                )
                SELECT
                    city, temperature_c, humidity_percent,
                    observed_at, wind_speed_kmh
                FROM weather_raw
                ON CONFLICT (city, observed_at) DO NOTHING
                """
            )

            logging.info("Staging data updated")

    logging.info("Pipeline completed successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Pipeline failed")
        raise
